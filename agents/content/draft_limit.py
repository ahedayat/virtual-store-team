"""Deterministic draft count resolution and enforcement for the Content Agent."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

DEFAULT_MAX_DRAFTS_PER_RUN = 3
HARD_MAX_DRAFTS_PER_RUN = 5
CONTENT_AGENT_MAX_DRAFTS_ENV = "CONTENT_AGENT_MAX_DRAFTS_PER_RUN"

# Primary draft list key used by the Content Agent output envelope.
DRAFTS_FIELD = "drafts"


def _coerce_positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped, 10)
        except ValueError:
            return None
    return None


def _extract_store_max_drafts(store_settings: Mapping[str, Any] | None) -> Any:
    if not isinstance(store_settings, Mapping):
        return None

    content_agent = store_settings.get("content_agent")
    if not isinstance(content_agent, Mapping):
        return None

    return content_agent.get("max_drafts_per_run")


def _read_env_max_drafts() -> str | None:
    return os.environ.get(CONTENT_AGENT_MAX_DRAFTS_ENV)


def _normalize_resolved_limit(value: int) -> int:
    if value < 1:
        return 1
    if value > HARD_MAX_DRAFTS_PER_RUN:
        return HARD_MAX_DRAFTS_PER_RUN
    return value


def resolve_max_drafts_per_run(
    *,
    request_max_drafts: Any = None,
    store_settings: Mapping[str, Any] | None = None,
    env_max_drafts: str | None | object = _read_env_max_drafts,
) -> int:
    """Resolve the maximum number of draft suggestions allowed for one run.

    Resolution order:
    1. Explicit request-level value
    2. ``store.settings.content_agent.max_drafts_per_run``
    3. ``CONTENT_AGENT_MAX_DRAFTS_PER_RUN`` environment variable
    4. ``DEFAULT_MAX_DRAFTS_PER_RUN`` (3)

    Invalid or missing configured values fall back to the default. Valid integers
    below 1 clamp to 1; values above ``HARD_MAX_DRAFTS_PER_RUN`` clamp to 5.
    """
    candidates: list[Any] = [
        request_max_drafts,
        _extract_store_max_drafts(store_settings),
    ]

    if env_max_drafts is not _read_env_max_drafts:
        candidates.append(env_max_drafts)
    else:
        candidates.append(_read_env_max_drafts())

    for raw in candidates:
        if raw is None:
            continue
        coerced = _coerce_positive_int(raw)
        if coerced is None:
            continue
        return _normalize_resolved_limit(coerced)

    return DEFAULT_MAX_DRAFTS_PER_RUN


def limit_content_suggestions(
    result: Mapping[str, Any],
    max_drafts: int,
) -> dict[str, Any]:
    """Trim draft suggestions to ``max_drafts`` across the combined draft list.

    The MVP output envelope uses a single ``drafts`` array for all content
    suggestion types (Instagram captions and product descriptions). The limit
    applies globally to that list in first-seen order.
    """
    limited = dict(result)
    drafts = limited.get(DRAFTS_FIELD)

    if not isinstance(drafts, list):
        return limited

    limited[DRAFTS_FIELD] = list(drafts[:max_drafts])
    return limited
