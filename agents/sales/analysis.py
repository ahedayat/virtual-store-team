"""Sales Agent analysis entry point with schema validation before return."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

from agents.sales.empty_sales import extract_sales_summary, handle_empty_sales
from agents.sales.prompts import build_sales_analysis_messages
from agents.sales.validation import (
    SalesLLMOutputError,
    ensure_valid_sales_analysis_result,
    log_sales_validation_failure,
    parse_llm_json_output,
)
from agents.shared.llm import get_llm_provider
from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.sales import SalesAnalysisResult


class LLMProvider(Protocol):
    """Minimal protocol for future LLM integration in the Sales Agent."""

    def complete(self, messages: list[dict[str, str]], /) -> str | dict[str, Any]:
        """Return structured model output as a JSON string or parsed object."""


def _serialize_sales_context(sales_data: Mapping[str, Any]) -> str:
    return json.dumps(sales_data, default=str)


def _run_llm_sales_analysis(
    *,
    sales_data: Mapping[str, Any],
    report_run_id: str | None,
    output_language: str | None,
    llm_provider: LLMProvider,
    request_id: str | None = None,
) -> SalesAnalysisResult:
    messages = build_sales_analysis_messages(
        output_language=output_language,
        user_context=_serialize_sales_context(sales_data),
    )

    try:
        raw_output = llm_provider.complete(messages)
        parsed = parse_llm_json_output(raw_output)
        return ensure_valid_sales_analysis_result(parsed)
    except (AgentSchemaValidationError, SalesLLMOutputError) as exc:
        log_sales_validation_failure(
            exc,
            report_run_id=report_run_id,
            request_id=request_id,
        )
        raise


def run_sales_analysis(
    *,
    context: Mapping[str, Any] | None = None,
    sales_summary: Mapping[str, Any] | None = None,
    report_run_id: str | None = None,
    output_language: str | None = None,
    llm_provider: LLMProvider | None = None,
    request_id: str | None = None,
) -> SalesAnalysisResult:
    """Run sales analysis and validate the final output before return."""
    raw_sales_data = sales_summary if sales_summary is not None else context
    sales_data = (
        extract_sales_summary(raw_sales_data) if raw_sales_data is not None else None
    )

    empty_result = handle_empty_sales(
        sales_data=sales_data,
        report_run_id=report_run_id,
        output_language=output_language,
    )
    if empty_result is not None:
        return ensure_valid_sales_analysis_result(empty_result)

    if sales_data is None:
        raise NotImplementedError(
            "Non-empty sales analysis requires sales data. "
            "Provide sales data with completed orders or wait for a later Phase 7 step."
        )

    if llm_provider is None:
        llm_provider = get_llm_provider()

    return _run_llm_sales_analysis(
        sales_data=sales_data,
        report_run_id=report_run_id,
        output_language=output_language,
        llm_provider=llm_provider,
        request_id=request_id,
    )
