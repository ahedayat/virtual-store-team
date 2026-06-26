"""Schema validation gate for Content Agent outputs (Step 8.3)."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from agents.shared.schemas.content import ContentSuggestions
from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.validation import validate_agent_response

logger = logging.getLogger(__name__)

SERVICE_NAME = "content-agent"


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


def validate_content_suggestions_output(
    payload: Mapping[str, Any],
) -> ContentSuggestions:
    """Validate a parsed payload against the official Content Agent schema."""
    return validate_agent_response(dict(payload), ContentSuggestions)


def ensure_valid_content_suggestions(
    result: ContentSuggestions | Mapping[str, Any],
) -> ContentSuggestions:
    """Shared validation gate for every Content Agent return path."""
    if isinstance(result, ContentSuggestions):
        payload = result.model_dump()
    elif isinstance(result, Mapping):
        payload = dict(result)
    else:
        raise AgentSchemaValidationError(
            (
                "Agent response failed validation against schema "
                "'ContentSuggestions': payload must be a JSON object."
            ),
            schema_name="ContentSuggestions",
            field_errors=[
                {
                    "field": "<root>",
                    "message": "payload must be a JSON object",
                    "type": "type_error",
                }
            ],
        )

    return validate_content_suggestions_output(payload)


def log_content_validation_failure(
    exc: AgentSchemaValidationError | ContentLLMOutputError,
    *,
    report_run_id: str | None = None,
    request_id: str | None = None,
) -> None:
    """Log a validation failure without raw LLM payloads or prompt context."""
    invalid_fields: list[str] = []
    schema_name: str | None = None

    if isinstance(exc, AgentSchemaValidationError):
        invalid_fields = [item["field"] for item in exc.field_errors]
        schema_name = exc.schema_name

    logger.warning(
        "Content agent output validation failed",
        extra={
            "service": SERVICE_NAME,
            "report_run_id": report_run_id,
            "request_id": request_id,
            "schema_name": schema_name,
            "error_summary": str(exc),
            "invalid_fields": invalid_fields,
        },
    )
