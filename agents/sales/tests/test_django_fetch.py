"""Unit tests for Sales Agent Django context fetching (Step 7.5)."""

from __future__ import annotations

import json
import unittest
from typing import Any

import httpx

from agents.sales.analysis import run_sales_analysis
from agents.sales.django_fetch import fetch_sales_context_from_django, fetch_sales_context_with_fallback
from agents.sales.sales_context import merge_sales_analysis_context
from agents.shared.django_client import DjangoClient
from agents.shared.llm import MockProvider


def build_django_sales_response() -> dict[str, Any]:
    return {
        "generated_at": "2026-06-26T12:00:00+00:00",
        "store_id": "00000000-0000-4000-8000-000000000010",
        "currency": "USD",
        "periods": {
            "today": {
                "order_count": 3,
                "total_revenue": "420.00",
                "top_products": [
                    {
                        "product_id": "00000000-0000-4000-8000-000000000001",
                        "sku": "BAG-001",
                        "quantity_sold": 2,
                        "revenue": "420.00",
                    }
                ],
            },
            "last_7_days": {
                "order_count": 8,
                "total_revenue": "1120.00",
                "top_products": [
                    {
                        "product_id": "00000000-0000-4000-8000-000000000001",
                        "sku": "BAG-001",
                        "quantity_sold": 6,
                        "revenue": "840.00",
                    }
                ],
            },
        },
    }


def build_django_inventory_response() -> dict[str, Any]:
    return {
        "generated_at": "2026-06-26T12:00:00+00:00",
        "store_id": "00000000-0000-4000-8000-000000000010",
        "low_stock_count": 1,
        "items": [
            {
                "product_id": "00000000-0000-4000-8000-000000000001",
                "sku": "BAG-001",
                "available_quantity": 2,
                "low_stock_threshold": 5,
                "suggested_reorder_quantity": 20,
            }
        ],
    }


class DjangoSalesFetchTests(unittest.TestCase):
    def _build_client(self, handler) -> DjangoClient:
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return DjangoClient(
            base_url="http://backend:8000",
            service_token="test-token",
            max_retries=0,
            http_client=http_client,
        )

    def test_successful_django_sales_inventory_fetch(self) -> None:
        store_id = "00000000-0000-4000-8000-000000000010"

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/sales/summary/"):
                return httpx.Response(200, json=build_django_sales_response())
            if request.url.path.endswith("/inventory/low-stock/"):
                return httpx.Response(200, json=build_django_inventory_response())
            return httpx.Response(404, json={"detail": "Not found."})

        client = self._build_client(handler)
        context = fetch_sales_context_from_django(client, store_id)

        self.assertTrue(context["django_fetched"])
        self.assertEqual(context["sales_summary"]["today"]["order_count"], 3)
        self.assertEqual(context["inventory"]["low_stock_count"], 1)
        self.assertEqual(context["inventory"]["items"][0]["sku"], "BAG-001")

    def test_django_client_failure_fallback(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "Service unavailable."})

        client = self._build_client(handler)
        django_context, warnings = fetch_sales_context_with_fallback(
            django_client=client,
            store_id="00000000-0000-4000-8000-000000000010",
            fetch_from_django=True,
        )

        self.assertIsNone(django_context)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].code, "django_fetch_failed")

    def test_caller_context_combined_with_django_fetched_context(self) -> None:
        django_context = {
            "sales_summary": {
                "currency": "USD",
                "today": {"order_count": 3, "total_revenue": "420.00", "top_products": []},
                "last_7_days": {"order_count": 8, "total_revenue": "1120.00", "top_products": []},
            },
            "inventory": {
                "low_stock_count": 1,
                "items": [{"sku": "BAG-001", "available_quantity": 2}],
            },
        }
        caller_context = {
            "inventory": {
                "low_stock_count": 1,
                "items": [{"sku": "BAG-002", "available_quantity": 1}],
            },
            "store": {"display_name": "Demo Store"},
        }

        merged = merge_sales_analysis_context(
            django_context=django_context,
            caller_context=caller_context,
        )

        skus = {item["sku"] for item in merged["inventory"]["items"]}
        self.assertEqual(skus, {"BAG-001", "BAG-002"})
        self.assertEqual(merged["store"]["display_name"], "Demo Store")

    def test_empty_sales_from_django_returns_deterministic_result_without_llm(self) -> None:
        empty_sales = {
            "currency": "USD",
            "periods": {
                "today": {"order_count": 0, "total_revenue": 0, "top_products": []},
                "last_7_days": {"order_count": 0, "total_revenue": 0, "top_products": []},
            },
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/sales/summary/"):
                return httpx.Response(200, json=empty_sales)
            return httpx.Response(200, json={"low_stock_count": 0, "items": []})

        client = self._build_client(handler)
        provider = MockProvider()
        provider.complete = lambda messages: (_ for _ in ()).throw(  # type: ignore[method-assign]
            AssertionError("LLM must not be called for empty sales")
        )

        result = run_sales_analysis(
            store_id="00000000-0000-4000-8000-000000000010",
            django_client=client,
            fetch_from_django=True,
            output_language="en",
            llm_provider=provider,
        )

        self.assertEqual(result.recommendations, [])
        self.assertIn("No sales were recorded", result.summary)


class DjangoClientSalesEndpointTests(unittest.TestCase):
    def test_get_sales_summary_and_low_stock_paths(self) -> None:
        captured_paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_paths.append(request.url.path)
            if request.url.path.endswith("/sales/summary/"):
                return httpx.Response(200, json=build_django_sales_response())
            return httpx.Response(200, json=build_django_inventory_response())

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )
        store_id = "00000000-0000-4000-8000-000000000010"

        client.get_sales_summary(store_id)
        client.get_low_stock_inventory(store_id)

        self.assertEqual(
            captured_paths,
            [
                f"/internal/ai/stores/{store_id}/sales/summary/",
                f"/internal/ai/stores/{store_id}/inventory/low-stock/",
            ],
        )


if __name__ == "__main__":
    unittest.main()
