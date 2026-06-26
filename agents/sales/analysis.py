"""Sales Agent analysis entry point with deterministic empty-sales fallback."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from agents.sales.empty_sales import handle_empty_sales
from agents.shared.schemas.sales import SalesAnalysisResult


class LLMProvider(Protocol):
    """Minimal protocol for future LLM integration in the Sales Agent."""

    def complete(self, messages: list[dict[str, str]], /) -> str:
        """Return structured model output as a JSON string."""


def run_sales_analysis(
    *,
    context: Mapping[str, Any] | None = None,
    sales_summary: Mapping[str, Any] | None = None,
    report_run_id: str | None = None,
    output_language: str | None = None,
    llm_provider: LLMProvider | None = None,
) -> SalesAnalysisResult:
    """Run sales analysis, bypassing the LLM when sales data is empty."""
    sales_data = sales_summary if sales_summary is not None else context

    empty_result = handle_empty_sales(
        sales_data=sales_data,
        report_run_id=report_run_id,
        output_language=output_language,
    )
    if empty_result is not None:
        return empty_result

    if llm_provider is not None:
        raise NotImplementedError(
            "Non-empty sales analysis via LLM is not implemented in Step 7.2."
        )

    raise NotImplementedError(
        "Non-empty sales analysis is not implemented yet. "
        "Provide sales data with completed orders or wait for a later Phase 7 step."
    )
