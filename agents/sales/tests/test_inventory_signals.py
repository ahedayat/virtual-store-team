"""Unit tests for inventory-aware sales analysis signals (Step 7.6)."""

from __future__ import annotations

import unittest
from typing import Any

from agents.sales.analysis import run_sales_analysis
from agents.sales.inventory_signals import build_inventory_signals, build_sales_analysis_payload
from agents.shared.llm import MockProvider


def build_non_empty_sales_context(**overrides: object) -> dict[str, Any]:
    context: dict[str, Any] = {
        "sales_summary": {
            "currency": "USD",
            "today": {
                "order_count": 2,
                "total_revenue": "300.00",
                "top_products": [
                    {
                        "product_id": "00000000-0000-4000-8000-000000000001",
                        "sku": "BAG-FAST",
                        "quantity_sold": 2,
                        "revenue": "300.00",
                    }
                ],
            },
            "last_7_days": {
                "order_count": 10,
                "total_revenue": "1500.00",
                "top_products": [
                    {
                        "product_id": "00000000-0000-4000-8000-000000000001",
                        "sku": "BAG-FAST",
                        "quantity_sold": 8,
                        "revenue": "1200.00",
                    },
                    {
                        "product_id": "00000000-0000-4000-8000-000000000002",
                        "sku": "BAG-SLOW",
                        "quantity_sold": 1,
                        "revenue": "45.00",
                    },
                ],
            },
        },
        "inventory": {
            "low_stock_count": 1,
            "items": [
                {
                    "product_id": "00000000-0000-4000-8000-000000000001",
                    "sku": "BAG-FAST",
                    "available_quantity": 2,
                    "low_stock_threshold": 5,
                    "suggested_reorder_quantity": 24,
                }
            ],
        },
    }
    context.update(overrides)
    return context


class InventorySignalModelTests(unittest.TestCase):
    def test_build_inventory_signals_identifies_low_stock(self) -> None:
        context = build_non_empty_sales_context()
        signals = build_inventory_signals(
            inventory=context["inventory"],
            sales_summary=context["sales_summary"],
        )

        self.assertEqual(len(signals["low_stock_products"]), 1)
        self.assertEqual(signals["low_stock_products"][0]["sku"], "BAG-FAST")
        self.assertEqual(signals["low_stock_products"][0]["signal_type"], "low_stock")

    def test_build_inventory_signals_identifies_slow_moving_products(self) -> None:
        context = build_non_empty_sales_context()
        signals = build_inventory_signals(
            inventory=context["inventory"],
            sales_summary=context["sales_summary"],
        )

        slow_skus = {item["sku"] for item in signals["slow_moving_products"]}
        self.assertIn("BAG-SLOW", slow_skus)

    def test_build_sales_analysis_payload_includes_inventory_signals(self) -> None:
        context = build_non_empty_sales_context()
        payload = build_sales_analysis_payload(context)

        self.assertIn("inventory", payload)
        self.assertIn("inventory_signals", payload)
        self.assertIn("low_stock_products", payload["inventory_signals"])


class InventoryAwareAnalysisTests(unittest.TestCase):
    def test_low_stock_produces_restock_recommendation(self) -> None:
        result = run_sales_analysis(
            context=build_non_empty_sales_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        restock = [
            rec
            for rec in result.recommendations
            if rec.action_type == "sales.restock"
        ]
        self.assertGreaterEqual(len(restock), 1)
        self.assertEqual(restock[0].payload["sku"], "BAG-FAST")
        self.assertGreaterEqual(restock[0].priority, 1)
        self.assertLessEqual(restock[0].priority, 5)

    def test_slow_moving_product_produces_discount_recommendation(self) -> None:
        result = run_sales_analysis(
            context=build_non_empty_sales_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        discounts = [
            rec
            for rec in result.recommendations
            if rec.action_type == "sales.discount"
        ]
        self.assertGreaterEqual(len(discounts), 1)
        self.assertIn("sku", discounts[0].payload)

    def test_inventory_signals_influence_mock_llm_user_payload(self) -> None:
        captured_user_content: dict[str, Any] = {}

        class _CapturingMockProvider(MockProvider):
            def complete(self, messages: list[dict[str, str]], /) -> dict[str, Any]:
                for message in messages:
                    if message.get("role") == "user":
                        import json

                        captured_user_content.update(json.loads(message["content"]))
                return super().complete(messages)

        run_sales_analysis(
            context=build_non_empty_sales_context(),
            llm_provider=_CapturingMockProvider(),
        )

        self.assertIn("inventory_signals", captured_user_content)
        self.assertGreaterEqual(
            len(captured_user_content["inventory_signals"]["low_stock_products"]),
            1,
        )


if __name__ == "__main__":
    unittest.main()
