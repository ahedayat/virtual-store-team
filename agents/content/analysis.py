"""Content Agent result normalization with deterministic draft limiting."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agents.content.draft_limit import (
    limit_content_suggestions,
    resolve_max_drafts_per_run,
)


class ContentLLMOutputError(Exception):
    """Raised when Content Agent LLM output cannot be parsed as structured JSON."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def parse_llm_json_output(raw_output: str | Mapping[str, Any]) -> dict[str, Any]:
    """Parse LLM output from a JSON string or a mock-provider dict."""
    if isinstance(raw_output, Mapping):
        return dict(raw_output)

    if not isinstance(raw_output, str):
        raise ContentLLMOutputError("LLM output must be a JSON string or object.")

    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ContentLLMOutputError("LLM returned malformed JSON.") from None

    if not isinstance(parsed, dict):
        raise ContentLLMOutputError("LLM JSON output must be a JSON object.")

    return parsed


def apply_content_draft_limit(
    result: Mapping[str, Any],
    *,
    request_max_drafts: Any = None,
    store_settings: Mapping[str, Any] | None = None,
    env_max_drafts: str | None | object = None,
) -> dict[str, Any]:
    """Resolve the draft limit and trim suggestions before returning output."""
    kwargs: dict[str, Any] = {
        "request_max_drafts": request_max_drafts,
        "store_settings": store_settings,
    }
    if env_max_drafts is not None:
        kwargs["env_max_drafts"] = env_max_drafts

    max_drafts = resolve_max_drafts_per_run(**kwargs)
    return limit_content_suggestions(result, max_drafts)


def normalize_content_agent_output(
    raw_output: str | Mapping[str, Any],
    *,
    request_max_drafts: Any = None,
    store_settings: Mapping[str, Any] | None = None,
    env_max_drafts: str | None | object = None,
) -> dict[str, Any]:
    """Parse LLM/mock output and enforce the resolved draft limit in code."""
    parsed = parse_llm_json_output(raw_output)
    return apply_content_draft_limit(
        parsed,
        request_max_drafts=request_max_drafts,
        store_settings=store_settings,
        env_max_drafts=env_max_drafts,
    )
