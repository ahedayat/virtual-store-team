"""Phase 7 acceptance proof tests for the Sales Agent (Step 7.9)."""

from __future__ import annotations

import json
import os
import unittest
from typing import Any
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from agents.sales.action_mapping import (
    map_sales_analysis_to_actions,
    map_sales_recommendation_to_action_payload,
)
from agents.sales.analysis import run_sales_analysis
from agents.sales.app.main import app
from agents.sales.validation import ensure_valid_sales_analysis_result
from agents.shared.django_client import DjangoClient
from agents.shared.llm import MockProvider
from agents.shared.schemas import SalesAnalysisResult


def build_prestia_style_sales_context(**overrides: object) -> dict[str, Any]:
    """Prestia-style bag store sales/inventory fixture for acceptance tests only."""
    context: dict[str, Any] = {
        "store": {
            "display_name": "Prestia Main Store",
            "currency": "USD",
        },
        "sales_summary": {
            "currency": "USD",
            "today": {
                "order_count": 4,
                "total_revenue": "516.00",
                "top_products": [
                    {
                        "product_id": "00000000-0000-4000-8000-000000000101",
                        "sku": "PRESTIA-MILANO-TOTE",
                        "name": "Milano Leather Tote",
                        "quantity_sold": 3,
                        "revenue": "387.00",
                        "category": "Handbags",
                    }
                ],
            },
            "last_7_days": {
                "order_count": 18,
                "total_revenue": "2322.00",
                "top_products": [
                    {
                        "product_id": "00000000-0000-4000-8000-000000000101",
                        "sku": "PRESTIA-MILANO-TOTE",
                        "name": "Milano Leather Tote",
                        "quantity_sold": 12,
                        "revenue": "1548.00",
                        "category": "Handbags",
                    },
                    {
                        "product_id": "00000000-0000-4000-8000-000000000102",
                        "sku": "PRESTIA-CLASSIC-SATCHEL",
                        "name": "Classic Satchel",
                        "quantity_sold": 1,
                        "revenue": "79.00",
                        "category": "Shoulder Bags",
                    },
                ],
            },
        },
        "inventory": {
            "low_stock_count": 1,
            "items": [
                {
                    "product_id": "00000000-0000-4000-8000-000000000101",
                    "sku": "PRESTIA-MILANO-TOTE",
                    "product_name": "Milano Leather Tote",
                    "available_quantity": 2,
                    "low_stock_threshold": 6,
                    "suggested_reorder_quantity": 24,
                }
            ],
        },
    }
    context.update(overrides)
    return context


class Phase7AcceptancePipelineTests(unittest.TestCase):
    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    @patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}, clear=False)
    def test_prestia_style_data_returns_restock_or_discount_recommendation(self) -> None:
        result = run_sales_analysis(
            context=build_prestia_style_sales_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        actionable = [
            rec
            for rec in result.recommendations
            if rec.action_type in {"sales.restock", "sales.discount"}
        ]
        self.assertGreaterEqual(len(actionable), 1)

        recommendation = actionable[0]
        self.assertGreaterEqual(recommendation.priority, 1)
        self.assertLessEqual(recommendation.priority, 5)
        self.assertIn("sku", recommendation.payload)

    def test_recommendations_include_required_fields(self) -> None:
        result = run_sales_analysis(
            context=build_prestia_style_sales_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        self.assertGreaterEqual(len(result.recommendations), 1)
        for recommendation in result.recommendations:
            self.assertIsInstance(recommendation.priority, int)
            self.assertTrue(recommendation.title)
            self.assertTrue(recommendation.description)
            self.assertTrue(recommendation.rationale)
            self.assertIsInstance(recommendation.payload, dict)

    def test_generated_result_validates_against_sales_analysis_result(self) -> None:
        result = run_sales_analysis(
            context=build_prestia_style_sales_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        self.assertIsInstance(result, SalesAnalysisResult)
        revalidated = ensure_valid_sales_analysis_result(result.model_dump())
        self.assertIsInstance(revalidated, SalesAnalysisResult)

    def test_mapped_action_can_be_submitted_to_mock_django_workflow(self) -> None:
        result = run_sales_analysis(
            context=build_prestia_style_sales_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )
        action_bodies = map_sales_analysis_to_actions(result, report_run_id="run-prestia-1")
        self.assertGreaterEqual(len(action_bodies), 1)

        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content.decode("utf-8")))
            return httpx.Response(
                201,
                json={
                    "id": "action-prestia-1",
                    "status": "pending_approval",
                    "requires_approval": True,
                    "action_type": captured["action_type"],
                },
            )

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        response = client.create_action(action_bodies[0])
        self.assertEqual(response["status"], "pending_approval")
        self.assertTrue(captured["requires_approval"])
        self.assertIn(captured["action_type"], {"sales.restock", "sales.discount"})

    def test_only_allowed_sales_action_types_are_mapped(self) -> None:
        result = run_sales_analysis(
            context=build_prestia_style_sales_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        for recommendation in result.recommendations:
            action_body = map_sales_recommendation_to_action_payload(recommendation)
            self.assertIn(
                action_body["action_type"],
                {"sales.restock", "sales.discount", "sales.follow_up"},
            )


class Phase7AcceptanceRunEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_accepts_prestia_style_context(self) -> None:
        response = self.client.post(
            "/run",
            json={"context": build_prestia_style_sales_context(), "output_language": "en"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreaterEqual(len(body["recommendations"]), 1)
        action_types = {item["action_type"] for item in body["recommendations"]}
        self.assertTrue(action_types.intersection({"sales.restock", "sales.discount"}))


if __name__ == "__main__":
    unittest.main()
