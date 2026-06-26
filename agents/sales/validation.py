"""Schema validation gate for Sales Agent outputs (Step 7.3)."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.sales import SalesAnalysisResult
from agents.shared.schemas.validation import validate_agent_response

logger = logging.getLogger(__name__)

SERVICE_NAME = "sales-agent"


class SalesLLMOutputError(Exception):
    """Raised when LLM output cannot be parsed as structured JSON."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def parse_llm_json_output(raw_output: str | Mapping[str, Any]) -> dict[str, Any]:
    """Parse LLM output from a JSON string or a mock-provider dict."""
    if isinstance(raw_output, Mapping):
        return dict(raw_output)

    if not isinstance(raw_output, str):
        raise SalesLLMOutputError("LLM output must be a JSON string or object.")

    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        raise SalesLLMOutputError("LLM returned malformed JSON.") from None

    if not isinstance(parsed, dict):
        raise SalesLLMOutputError("LLM JSON output must be a JSON object.")

    return parsed


def validate_sales_analysis_output(payload: Mapping[str, Any]) -> SalesAnalysisResult:
    """Validate a parsed payload against the official Sales Agent schema."""
    return validate_agent_response(dict(payload), SalesAnalysisResult)


def ensure_valid_sales_analysis_result(
    result: SalesAnalysisResult | Mapping[str, Any],
) -> SalesAnalysisResult:
    """Shared validation gate for every Sales Agent return path."""
    if isinstance(result, SalesAnalysisResult):
        payload = result.model_dump()
    elif isinstance(result, Mapping):
        payload = dict(result)
    else:
        raise AgentSchemaValidationError(
            (
                "Agent response failed validation against schema "
                "'SalesAnalysisResult': payload must be a JSON object."
            ),
            schema_name="SalesAnalysisResult",
            field_errors=[
                {
                    "field": "<root>",
                    "message": "payload must be a JSON object",
                    "type": "type_error",
                }
            ],
        )

    return validate_sales_analysis_output(payload)


def log_sales_validation_failure(
    exc: AgentSchemaValidationError | SalesLLMOutputError,
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
        "Sales analysis output validation failed",
        extra={
            "service": SERVICE_NAME,
            "report_run_id": report_run_id,
            "request_id": request_id,
            "schema_name": schema_name,
            "error_summary": str(exc),
            "invalid_fields": invalid_fields,
        },
    )
