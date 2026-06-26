"""Deterministic empty-sales detection and fallback for the Sales Agent."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from agents.shared.language import get_output_language, normalize_output_language
from agents.shared.schemas.sales import SalesAnalysisResult
from agents.shared.schemas.base import AgentResponseMetadata

SALES_AGENT_NAME = "sales-agent"

EMPTY_SALES_MESSAGES: dict[str, str] = {
    "fa": "در این بازه زمانی فروشی ثبت نشده است.",
    "en": "No sales were recorded for this period.",
}

_PERIOD_KEYS = ("today", "last_7_days")


def _is_positive_number(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float, Decimal)):
        return value > 0
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        try:
            return Decimal(stripped) > 0
        except Exception:
            return False
    return False


def normalize_sales_summary(sales_summary: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Normalize Django sales summary shapes into a flat period map."""
    if sales_summary is None:
        return None
    if not isinstance(sales_summary, Mapping):
        return None

    if "periods" in sales_summary:
        periods = sales_summary.get("periods") or {}
        if not isinstance(periods, Mapping):
            periods = {}
        return {
            "currency": sales_summary.get("currency"),
            "today": dict(periods.get("today") or {}),
            "last_7_days": dict(periods.get("last_7_days") or {}),
        }

    return {
        "currency": sales_summary.get("currency"),
        "today": dict(sales_summary.get("today") or {}),
        "last_7_days": dict(sales_summary.get("last_7_days") or {}),
    }


def extract_sales_summary(data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Extract a sales summary section from a context bundle or raw sales payload."""
    if data is None:
        return None
    if not isinstance(data, Mapping):
        return None

    if "sales_summary" in data:
        section = data.get("sales_summary")
        return dict(section) if isinstance(section, Mapping) else None

    if any(key in data for key in ("today", "last_7_days", "periods")):
        return dict(data)

    return None


def is_empty_sales_period(period: Mapping[str, Any] | None) -> bool:
    """Return True when a single sales period has no completed-order evidence."""
    if not period:
        return True

    order_count = period.get("order_count") or 0
    if isinstance(order_count, str) and order_count.strip().isdigit():
        order_count = int(order_count.strip())

    total_revenue = period.get("total_revenue")
    top_products = period.get("top_products") or []

    has_orders = isinstance(order_count, (int, float, Decimal)) and order_count > 0
    has_revenue = _is_positive_number(total_revenue)
    has_top_products = isinstance(top_products, list) and len(top_products) > 0

    return not (has_orders or has_revenue or has_top_products)


def is_empty_sales_context(sales_data: Mapping[str, Any] | None) -> bool:
    """Return True when sales input has no completed orders in any known period."""
    sales_summary = extract_sales_summary(sales_data)
    if sales_summary is None:
        return True

    normalized = normalize_sales_summary(sales_summary)
    if normalized is None:
        return True

    return all(
        is_empty_sales_period(normalized.get(period_key))
        for period_key in _PERIOD_KEYS
    )


def build_empty_sales_result(
    *,
    report_run_id: str | None = None,
    output_language: str | None = None,
) -> SalesAnalysisResult:
    """Build a deterministic, schema-valid response for empty or zero-sales input."""
    language = (
        get_output_language()
        if output_language is None
        else normalize_output_language(output_language)
    )
    summary = EMPTY_SALES_MESSAGES[language]

    return SalesAnalysisResult(
        metadata=AgentResponseMetadata(
            agent_name=SALES_AGENT_NAME,
            report_run_id=report_run_id,
        ),
        summary=summary,
        insights=[],
        recommendations=[],
        warnings=[],
    )


def handle_empty_sales(
    *,
    sales_data: Mapping[str, Any] | None,
    report_run_id: str | None = None,
    output_language: str | None = None,
) -> SalesAnalysisResult | None:
    """Return a deterministic empty-sales result when sales data is empty."""
    if not is_empty_sales_context(sales_data):
        return None
    return build_empty_sales_result(
        report_run_id=report_run_id,
        output_language=output_language,
    )
