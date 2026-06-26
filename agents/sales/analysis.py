"""Sales Agent analysis entry point with schema validation before return."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

from agents.sales.django_fetch import fetch_sales_context_with_fallback
from agents.sales.empty_sales import extract_sales_summary, handle_empty_sales
from agents.sales.inventory_signals import build_sales_analysis_payload
from agents.sales.prompts import build_sales_analysis_messages
from agents.sales.sales_context import resolve_sales_run_context
from agents.sales.validation import (
    SalesLLMOutputError,
    ensure_valid_sales_analysis_result,
    log_sales_validation_failure,
    parse_llm_json_output,
)
from agents.shared.django_client import DjangoClient
from agents.shared.llm import get_llm_provider
from agents.shared.schemas.base import AgentWarning
from agents.shared.schemas.errors import AgentSchemaValidationError
from agents.shared.schemas.sales import SalesAnalysisResult


class LLMProvider(Protocol):
    """Minimal protocol for future LLM integration in the Sales Agent."""

    def complete(self, messages: list[dict[str, str]], /) -> str | dict[str, Any]:
        """Return structured model output as a JSON string or parsed object."""


def _serialize_analysis_context(analysis_payload: Mapping[str, Any]) -> str:
    return json.dumps(analysis_payload, default=str)


def _attach_warnings(
    result: SalesAnalysisResult,
    warnings: list[AgentWarning],
) -> SalesAnalysisResult:
    if not warnings:
        return result
    combined = list(result.warnings) + warnings
    return result.model_copy(update={"warnings": combined})


def _run_llm_sales_analysis(
    *,
    analysis_payload: Mapping[str, Any],
    report_run_id: str | None,
    output_language: str | None,
    llm_provider: LLMProvider,
    request_id: str | None = None,
) -> SalesAnalysisResult:
    messages = build_sales_analysis_messages(
        output_language=output_language,
        user_context=_serialize_analysis_context(analysis_payload),
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
    inventory: Mapping[str, Any] | None = None,
    store_id: str | None = None,
    report_run_id: str | None = None,
    output_language: str | None = None,
    llm_provider: LLMProvider | None = None,
    request_id: str | None = None,
    django_client: DjangoClient | None = None,
    fetch_from_django: bool = False,
) -> SalesAnalysisResult:
    """Run sales analysis and validate the final output before return."""
    django_context, fetch_warnings = fetch_sales_context_with_fallback(
        django_client=django_client,
        store_id=store_id,
        fetch_from_django=fetch_from_django,
    )

    merged_context, merge_warnings = resolve_sales_run_context(
        context=context,
        sales_summary=sales_summary,
        inventory=inventory,
        django_context=django_context,
    )
    pipeline_warnings = fetch_warnings + merge_warnings

    sales_data = extract_sales_summary(merged_context)

    empty_result = handle_empty_sales(
        sales_data=sales_data,
        report_run_id=report_run_id,
        output_language=output_language,
    )
    if empty_result is not None:
        validated = ensure_valid_sales_analysis_result(empty_result)
        return _attach_warnings(validated, pipeline_warnings)

    analysis_payload = build_sales_analysis_payload(merged_context)

    if llm_provider is None:
        llm_provider = get_llm_provider()

    result = _run_llm_sales_analysis(
        analysis_payload=analysis_payload,
        report_run_id=report_run_id,
        output_language=output_language,
        llm_provider=llm_provider,
        request_id=request_id,
    )

    updates: dict[str, Any] = {}
    if report_run_id and result.metadata.report_run_id is None:
        updates["metadata"] = result.metadata.model_copy(
            update={"report_run_id": report_run_id}
        )
    if updates:
        result = result.model_copy(update=updates)

    return _attach_warnings(result, pipeline_warnings)
