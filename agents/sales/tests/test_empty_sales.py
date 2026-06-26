"""Unit tests for Sales Agent empty-sales handling (Step 7.2)."""

from __future__ import annotations

import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from agents.sales.analysis import run_sales_analysis
from agents.sales.empty_sales import (
    build_empty_sales_result,
    handle_empty_sales,
    is_empty_sales_context,
    is_empty_sales_period,
    normalize_sales_summary,
)
from agents.shared.schemas import SalesAnalysisResult, validate_agent_response


class _RecordingLLMProvider:
    def __init__(self) -> None:
        self.called = False

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.called = True
        return "{}"


EMPTY_CONTEXT_BUNDLE = {
    "report_run_id": "run-empty-1",
    "sales_summary": {
        "currency": "USD",
        "today": {
            "order_count": 0,
            "total_revenue": 0,
            "top_products": [],
        },
        "last_7_days": {
            "order_count": 0,
            "total_revenue": "0.00",
            "top_products": [],
        },
    },
}


class EmptySalesDetectionTests(unittest.TestCase):
    def test_zero_order_count_is_empty(self) -> None:
        period = {"order_count": 0, "total_revenue": 0, "top_products": []}
        self.assertTrue(is_empty_sales_period(period))

    def test_zero_total_revenue_is_empty(self) -> None:
        period = {"order_count": 0, "total_revenue": None, "top_products": []}
        self.assertTrue(is_empty_sales_period(period))

    def test_empty_top_products_is_empty_when_no_other_signals(self) -> None:
        period = {"order_count": 0, "total_revenue": 0, "top_products": []}
        self.assertTrue(is_empty_sales_period(period))

    def test_missing_sales_summary_is_empty(self) -> None:
        self.assertTrue(is_empty_sales_context(None))
        self.assertTrue(is_empty_sales_context({}))

    def test_null_sales_summary_section_is_empty(self) -> None:
        self.assertTrue(is_empty_sales_context({"sales_summary": None}))

    def test_partially_missing_optional_fields_is_empty(self) -> None:
        self.assertTrue(is_empty_sales_context({"sales_summary": {"today": {}}}))
        self.assertTrue(
            is_empty_sales_context(
                {
                    "sales_summary": {
                        "currency": "USD",
                        "today": {"order_count": 0},
                    }
                }
            )
        )

    def test_non_empty_when_last_7_days_has_orders(self) -> None:
        context = {
            "sales_summary": {
                "today": {"order_count": 0, "total_revenue": 0, "top_products": []},
                "last_7_days": {
                    "order_count": 3,
                    "total_revenue": "150.00",
                    "top_products": [{"sku": "SKU-1", "revenue": "150.00"}],
                },
            }
        }
        self.assertFalse(is_empty_sales_context(context))

    def test_api_shape_with_periods_key_is_supported(self) -> None:
        raw_summary = {
            "currency": "USD",
            "periods": {
                "today": {"order_count": 0, "total_revenue": 0, "top_products": []},
                "last_7_days": {
                    "order_count": 0,
                    "total_revenue": Decimal("0"),
                    "top_products": [],
                },
            },
        }
        normalized = normalize_sales_summary(raw_summary)
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertTrue(is_empty_sales_context(normalized))


class EmptySalesFallbackTests(unittest.TestCase):
    def test_build_empty_sales_result_has_valid_shape(self) -> None:
        result = build_empty_sales_result(report_run_id="run-123", output_language="en")

        self.assertIsInstance(result, SalesAnalysisResult)
        self.assertEqual(result.metadata.agent_name, "sales-agent")
        self.assertEqual(result.metadata.report_run_id, "run-123")
        self.assertEqual(result.recommendations, [])
        self.assertEqual(result.insights, [])
        self.assertEqual(result.warnings, [])

        validated = validate_agent_response(result.model_dump(), SalesAnalysisResult)
        self.assertEqual(validated.summary, result.summary)

    def test_recommendations_are_empty_for_no_sales(self) -> None:
        result = handle_empty_sales(
            sales_data=EMPTY_CONTEXT_BUNDLE,
            report_run_id="run-empty-1",
            output_language="en",
        )
        assert result is not None
        self.assertEqual(result.recommendations, [])

    def test_no_fabricated_revenue_or_sku_language(self) -> None:
        result = build_empty_sales_result(output_language="en")
        serialized = result.model_dump_json()

        for forbidden in (
            "revenue",
            "velocity",
            "demand",
            "restock",
            "discount",
            "follow_up",
            "SKU",
            "sku",
        ):
            self.assertNotIn(forbidden, serialized.lower())

    @patch.dict(os.environ, {"AI_OUTPUT_LANGUAGE": "fa"}, clear=False)
    def test_persian_empty_sales_message(self) -> None:
        result = build_empty_sales_result()
        self.assertEqual(result.summary, "در این بازه زمانی فروشی ثبت نشده است.")

    def test_english_empty_sales_message(self) -> None:
        result = build_empty_sales_result(output_language="en")
        self.assertEqual(result.summary, "No sales were recorded for this period.")

    def test_run_sales_analysis_returns_deterministic_fallback(self) -> None:
        result = run_sales_analysis(
            context=EMPTY_CONTEXT_BUNDLE,
            report_run_id="run-empty-1",
            output_language="en",
        )

        self.assertEqual(result.recommendations, [])
        self.assertEqual(result.summary, "No sales were recorded for this period.")

    def test_llm_provider_is_not_called_for_empty_sales(self) -> None:
        provider = _RecordingLLMProvider()

        run_sales_analysis(
            context=EMPTY_CONTEXT_BUNDLE,
            report_run_id="run-empty-1",
            output_language="en",
            llm_provider=provider,
        )

        self.assertFalse(provider.called)


if __name__ == "__main__":
    unittest.main()
