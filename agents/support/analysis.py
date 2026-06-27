"""Support Agent scaffold analysis entry point (Phase 6.6)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from agents.shared.language import get_output_language, normalize_output_language
from agents.shared.llm import get_llm_provider
from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.support import SupportRunResponse
from agents.support.prompts import build_support_reply_messages
from agents.support.refusal import evaluate_support_scope
from agents.support.validation import (
    SupportLLMOutputError,
    ensure_valid_support_run_response,
    log_support_validation_failure,
    parse_llm_json_output,
)


class LLMProvider(Protocol):
    """Minimal protocol for Support Agent LLM integration."""

    def complete(self, messages: list[dict[str, str]], /) -> str | dict[str, Any]:
        """Return structured model output as a JSON string or parsed object."""


def _resolve_output_language(output_language: str | None) -> str:
    if output_language is None:
        return get_output_language()
    return normalize_output_language(output_language)


def run_support_analysis(
    *,
    customer_message: str,
    channel: str,
    tenant_id: str | None = None,
    store_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    report_run_id: str | None = None,
    output_language: str | None = None,
    request_id: str | None = None,
    llm_provider: LLMProvider | None = None,
) -> SupportRunResponse:
    """Run the Support Agent scaffold pipeline and validate output before return."""
    del report_run_id  # reserved for Phase 9 business workflows

    language = _resolve_output_language(output_language)
    scope = evaluate_support_scope(customer_message, output_language=language)
    if scope.is_refusal:
        return SupportRunResponse(
            agent="support-agent",
            status="refused",
            language=language,
            reply=scope.safe_message,
            intent=scope.refusal_code or "unknown_out_of_scope",
            confidence=1.0,
            requires_human_review=False,
            request_id=request_id,
        )

    provider = llm_provider if llm_provider is not None else get_llm_provider()
    messages = build_support_reply_messages(
        customer_message=customer_message,
        channel=channel,
        tenant_id=tenant_id,
        store_id=store_id,
        metadata=metadata,
        output_language=language,
        request_id=request_id,
    )

    try:
        raw_output = provider.complete(messages)
        parsed = parse_llm_json_output(raw_output)
        validated = ensure_valid_support_run_response(parsed)

        updates: dict[str, Any] = {}
        if validated.language != language:
            updates["language"] = language
        if request_id and validated.request_id is None:
            updates["request_id"] = request_id
        if updates:
            return validated.model_copy(update=updates)
        return validated
    except (AgentSchemaValidationError, SupportLLMOutputError) as exc:
        log_support_validation_failure(exc, request_id=request_id)
        raise
