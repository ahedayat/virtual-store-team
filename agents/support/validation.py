"""Schema validation gate for Support Agent scaffold outputs (Phase 6.6)."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.support import SupportRunResponse
from agents.shared.schemas.validation import validate_agent_response

logger = logging.getLogger(__name__)

SERVICE_NAME = "support-agent"


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


def ensure_valid_support_run_response(payload: Mapping[str, Any]) -> SupportRunResponse:
    """Validate a parsed payload against the Support Agent scaffold schema."""
    return validate_agent_response(dict(payload), SupportRunResponse)


def log_support_validation_failure(
    exc: AgentSchemaValidationError | SupportLLMOutputError,
    *,
    request_id: str | None = None,
) -> None:
    logger.warning(
        "Support Agent output validation failed",
        extra={
            "service": SERVICE_NAME,
            "request_id": request_id,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
    )
