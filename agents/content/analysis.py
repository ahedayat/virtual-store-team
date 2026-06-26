"""Content Agent result normalization with draft limiting and schema validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.content.draft_limit import (
    limit_content_suggestions,
    resolve_max_drafts_per_run,
)
from agents.content.validation import (
    ContentLLMOutputError,
    ensure_valid_content_suggestions,
    parse_llm_json_output,
)
from agents.shared.schemas.content import ContentSuggestions

__all__ = [
    "ContentLLMOutputError",
    "apply_content_draft_limit",
    "normalize_content_agent_output",
    "parse_llm_json_output",
]


def apply_content_draft_limit(
    result: Mapping[str, Any],
    *,
    request_max_drafts: Any = None,
    store_settings: Mapping[str, Any] | None = None,
    env_max_drafts: str | None | object = None,
) -> dict[str, Any]:
    """Resolve the draft limit and trim suggestions before schema validation."""
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
) -> ContentSuggestions:
    """Parse LLM/mock output, enforce the draft limit, and validate the schema."""
    parsed = parse_llm_json_output(raw_output)
    limited = apply_content_draft_limit(
        parsed,
        request_max_drafts=request_max_drafts,
        store_settings=store_settings,
        env_max_drafts=env_max_drafts,
    )
    return ensure_valid_content_suggestions(limited)
