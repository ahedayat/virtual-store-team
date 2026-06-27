"""Schema validation gate for Support Agent outputs (Phase 6.6 scaffold, Phase 9.4 insights)."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.support import SupportInsights, SupportRunResponse
from agents.shared.schemas.validation import validate_agent_response

logger = logging.getLogger(__name__)

SERVICE_NAME = "support-agent"
REFUSAL_WARNING_CODE = "support_out_of_scope_refusal"


class SupportLLMOutputError(Exception):
    """Raised when LLM output cannot be parsed as structured JSON."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def parse_llm_json_output(raw_output: str | Mapping[str, Any]) -> dict[str, Any]:
    """Parse LLM output from a JSON string or a mock-provider dict."""
    if isinstance(raw_output, Mapping):
        return dict(raw_output)

    if not isinstance(raw_output, str):
        raise SupportLLMOutputError("LLM output must be a JSON string or object.")

    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        raise SupportLLMOutputError("LLM returned malformed JSON.") from None

    if not isinstance(parsed, dict):
        raise SupportLLMOutputError("LLM JSON output must be a JSON object.")

    return parsed


def validate_support_insights(payload: Mapping[str, Any]) -> SupportInsights:
    """Validate a parsed payload against the final Support Agent schema."""
    return validate_agent_response(dict(payload), SupportInsights)


def ensure_valid_support_insights(
    result: SupportInsights | Mapping[str, Any],
) -> SupportInsights:
    """Shared validation gate for SupportInsights return paths."""
    if isinstance(result, SupportInsights):
        payload = result.model_dump()
    elif isinstance(result, Mapping):
        payload = dict(result)
    else:
        raise AgentSchemaValidationError(
            (
                "Agent response failed validation against schema "
                "'SupportInsights': payload must be a JSON object."
            ),
            schema_name="SupportInsights",
            field_errors=[
                {
                    "field": "<root>",
                    "message": "payload must be a JSON object",
                    "type": "type_error",
                }
            ],
        )

    return validate_support_insights(payload)


def ensure_valid_support_run_response(payload: Mapping[str, Any]) -> SupportRunResponse:
    """Validate a parsed payload against the Support Agent scaffold schema."""
    return validate_agent_response(dict(payload), SupportRunResponse)


def support_insights_to_run_response(
    insights: SupportInsights,
    *,
    output_language: str,
    request_id: str | None = None,
) -> SupportRunResponse:
    """Adapt schema-valid SupportInsights to the legacy /run response envelope."""
    refusal_warning = next(
        (warning for warning in insights.warnings if warning.code == REFUSAL_WARNING_CODE),
        None,
    )
    primary_draft = insights.reply_drafts[0]
    resolved_request_id = request_id
    if resolved_request_id is None and insights.metadata.report_run_id:
        resolved_request_id = insights.metadata.report_run_id

    if refusal_warning is not None:
        return SupportRunResponse(
            agent="support-agent",
            status="refused",
            language=insights.output_language or output_language,
            reply=primary_draft.reply_text,
            intent=primary_draft.matched_policy_code,
            confidence=1.0,
            requires_human_review=False,
            request_id=resolved_request_id,
            warnings=list(insights.warnings),
        )

    requires_human_review = any(draft.requires_approval for draft in insights.reply_drafts)
    confidence = 0.92 if not requires_human_review else 0.85
    return SupportRunResponse(
        agent="support-agent",
        status="ok",
        language=insights.output_language or output_language,
        reply=primary_draft.reply_text,
        intent=primary_draft.matched_policy_code,
        confidence=confidence,
        requires_human_review=requires_human_review,
        request_id=resolved_request_id,
        warnings=list(insights.warnings),
    )


def coerce_support_output_to_run_response(
    payload: Mapping[str, Any],
    *,
    output_language: str,
    request_id: str | None = None,
) -> SupportRunResponse:
    """Accept SupportInsights or legacy SupportRunResponse-shaped LLM output."""
    if "reply_drafts" in payload:
        insights = validate_support_insights(payload)
        primary_draft = insights.reply_drafts[0]
        requires_human_review = any(draft.requires_approval for draft in insights.reply_drafts)
        confidence = 0.92 if not requires_human_review else 0.85
        resolved_request_id = request_id
        if resolved_request_id is None and insights.metadata.report_run_id:
            resolved_request_id = insights.metadata.report_run_id

        return SupportRunResponse(
            agent="support-agent",
            status="ok",
            language=insights.output_language or output_language,
            reply=primary_draft.reply_text,
            intent=primary_draft.matched_policy_code,
            confidence=confidence,
            requires_human_review=requires_human_review,
            request_id=resolved_request_id,
        )

    return ensure_valid_support_run_response(payload)


def log_support_validation_failure(
    exc: AgentSchemaValidationError | SupportLLMOutputError,
    *,
    request_id: str | None = None,
) -> None:
    invalid_fields: list[str] = []
    schema_name: str | None = None

    if isinstance(exc, AgentSchemaValidationError):
        invalid_fields = [item["field"] for item in exc.field_errors]
        schema_name = exc.schema_name

    logger.warning(
        "Support Agent output validation failed",
        extra={
            "service": SERVICE_NAME,
            "request_id": request_id,
            "schema_name": schema_name,
            "error_summary": str(exc),
            "invalid_fields": invalid_fields,
        },
    )
