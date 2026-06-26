"""Content Agent runtime pipeline with draft limiting and schema validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from agents.content.draft_limit import (
    limit_content_suggestions,
    resolve_max_drafts_per_run,
)
from agents.content.empty_products import handle_empty_products
from agents.content.product_context import resolve_content_run_context
from agents.content.prompts import build_content_draft_messages
from agents.content.validation import (
    ContentLLMOutputError,
    ensure_valid_content_suggestions,
    log_content_validation_failure,
    parse_llm_json_output,
)
from agents.shared.language import get_output_language, normalize_output_language
from agents.shared.llm import get_llm_provider
from agents.shared.schemas.content import ContentSuggestions
from agents.shared.schemas.errors import AgentSchemaValidationError

__all__ = [
    "ContentLLMOutputError",
    "apply_content_draft_limit",
    "normalize_content_agent_output",
    "parse_llm_json_output",
    "run_content_analysis",
]


class LLMProvider(Protocol):
    """Minimal protocol for Content Agent LLM integration."""

    def complete(self, messages: list[dict[str, str]], /) -> str | dict[str, Any]:
        """Return structured model output as a JSON string or parsed object."""


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


def _resolve_output_language(output_language: str | None) -> str:
    if output_language is None:
        return get_output_language()
    return normalize_output_language(output_language)


def _resolve_store_settings(store_context: Mapping[str, Any]) -> Mapping[str, Any] | None:
    settings = store_context.get("settings")
    if settings is not None and isinstance(settings, Mapping):
        return settings
    return None


def _run_llm_content_analysis(
    *,
    products: list[dict[str, Any]],
    store_context: Mapping[str, Any],
    campaign_angle: str | None,
    report_run_id: str | None,
    output_language: str,
    max_drafts_per_run: int | None,
    llm_provider: LLMProvider,
    request_id: str | None = None,
) -> ContentSuggestions:
    store_settings = _resolve_store_settings(store_context)
    messages = build_content_draft_messages(
        store_context=store_context,
        products=products,
        campaign_angle=campaign_angle,
        output_language=output_language,
        max_drafts_per_run=max_drafts_per_run,
    )

    try:
        raw_output = llm_provider.complete(messages)
        parsed = parse_llm_json_output(raw_output)
        limited = apply_content_draft_limit(
            parsed,
            request_max_drafts=max_drafts_per_run,
            store_settings=store_settings,
        )
        validated = ensure_valid_content_suggestions(limited)

        updates: dict[str, Any] = {}
        if validated.output_language is None:
            updates["output_language"] = output_language
        if report_run_id and validated.metadata.report_run_id is None:
            updates["metadata"] = validated.metadata.model_copy(
                update={"report_run_id": report_run_id}
            )
        if updates:
            return validated.model_copy(update=updates)
        return validated
    except (AgentSchemaValidationError, ContentLLMOutputError) as exc:
        log_content_validation_failure(
            exc,
            report_run_id=report_run_id,
            request_id=request_id,
        )
        raise


def run_content_analysis(
    *,
    context: Mapping[str, Any] | None = None,
    products: list[Mapping[str, Any]] | None = None,
    store_context: Mapping[str, Any] | None = None,
    campaign_angle: str | None = None,
    report_run_id: str | None = None,
    output_language: str | None = None,
    max_drafts_per_run: int | None = None,
    llm_provider: LLMProvider | None = None,
    request_id: str | None = None,
) -> ContentSuggestions:
    """Run the Content Agent pipeline and validate output before return.

    Pipeline order:
    1. Resolve product/store context from explicit args or coordinator bundle.
    2. Return deterministic empty result when no products are available.
    3. Build prompts with brand voice and draft-limit instructions (Step 8.1).
    4. Call the configured LLM provider (MockProvider by default).
    5. Parse provider output.
    6. Apply draft limit (Step 8.2).
    7. Schema-validate (Step 8.3).
    """
    resolved_products, resolved_store, resolved_campaign_angle = resolve_content_run_context(
        context=context,
        products=products,
        store_context=store_context,
        campaign_angle=campaign_angle,
    )
    language = _resolve_output_language(output_language)

    empty_result = handle_empty_products(
        products=resolved_products,
        report_run_id=report_run_id,
        output_language=language,
    )
    if empty_result is not None:
        return ensure_valid_content_suggestions(empty_result)

    provider = llm_provider if llm_provider is not None else get_llm_provider()

    return _run_llm_content_analysis(
        products=resolved_products,
        store_context=resolved_store,
        campaign_angle=resolved_campaign_angle,
        report_run_id=report_run_id,
        output_language=language,
        max_drafts_per_run=max_drafts_per_run,
        llm_provider=provider,
        request_id=request_id,
    )
