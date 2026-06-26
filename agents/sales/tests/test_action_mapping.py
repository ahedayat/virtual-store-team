"""Unit tests for Sales Agent action mapping and persistence (Steps 7.7-7.8)."""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from agents.sales.action_mapping import (
    SalesActionMappingError,
    map_sales_analysis_to_actions,
    map_sales_recommendation_to_action_payload,
    persist_sales_actions,
)
from agents.sales.app.main import app
from agents.sales.tests.test_schema_validation import build_valid_sales_analysis_payload
from agents.sales.validation import ensure_valid_sales_analysis_result
from agents.shared.django_client import DjangoClient
from agents.shared.schemas.sales import SalesRecommendation


def build_restock_recommendation(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "priority": 2,
        "action_type": "sales.restock",
        "title": "Restock: BAG-001",
        "description": "Reorder before stockout.",
        "rationale": "Low stock with recent sales velocity.",
        "payload": {
            "product_id": "00000000-0000-4000-8000-000000000001",
            "sku": "BAG-001",
            "current_stock": 2,
            "suggested_order_qty": 20,
        },
    }
    payload.update(overrides)
    return payload


def build_discount_recommendation(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "priority": 3,
        "action_type": "sales.discount",
        "title": "Discount: BAG-SLOW",
        "description": "Review promotional pricing.",
        "rationale": "Slow-moving inventory with weak recent sales.",
        "payload": {
            "product_id": "00000000-0000-4000-8000-000000000002",
            "sku": "BAG-SLOW",
            "suggested_discount_pct": 10,
        },
    }
    payload.update(overrides)
    return payload


def build_follow_up_recommendation(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "priority": 4,
        "action_type": "sales.follow_up",
        "title": "Follow up on warm lead",
        "description": "Review follow-up opportunity.",
        "rationale": "Aggregate sales context suggests a follow-up review.",
        "payload": {
            "follow_up_reason": "High-value cart abandonment signal.",
            "order_ref": "ORD-1001",
        },
    }
    payload.update(overrides)
    return payload


class SalesActionMappingTests(unittest.TestCase):
    def test_valid_restock_mapping(self) -> None:
        recommendation = SalesRecommendation.model_validate(build_restock_recommendation())
        action_body = map_sales_recommendation_to_action_payload(recommendation)

        self.assertEqual(action_body["action_type"], "sales.restock")
        self.assertTrue(action_body["requires_approval"])
        self.assertEqual(action_body["payload"]["sku"], "BAG-001")

    def test_valid_discount_mapping(self) -> None:
        recommendation = SalesRecommendation.model_validate(build_discount_recommendation())
        action_body = map_sales_recommendation_to_action_payload(recommendation)

        self.assertEqual(action_body["action_type"], "sales.discount")
        self.assertEqual(action_body["payload"]["sku"], "BAG-SLOW")

    def test_valid_follow_up_mapping(self) -> None:
        recommendation = SalesRecommendation.model_validate(build_follow_up_recommendation())
        action_body = map_sales_recommendation_to_action_payload(recommendation)

        self.assertEqual(action_body["action_type"], "sales.follow_up")
        self.assertEqual(
            action_body["payload"]["follow_up_reason"],
            "High-value cart abandonment signal.",
        )

    def test_unsupported_action_type_is_rejected(self) -> None:
        recommendation = build_restock_recommendation(action_type="sales.promote")

        with self.assertRaises(SalesActionMappingError) as context:
            map_sales_recommendation_to_action_payload(recommendation)

        self.assertIn("Unsupported sales action_type", str(context.exception))

    def test_missing_required_payload_field_is_rejected(self) -> None:
        recommendation = build_restock_recommendation(
            payload={"product_id": "00000000-0000-4000-8000-000000000001"}
        )

        with self.assertRaises(SalesActionMappingError) as context:
            map_sales_recommendation_to_action_payload(recommendation)

        self.assertIn("sku is required", str(context.exception))

    def test_map_sales_analysis_to_actions_uses_metadata_report_run_id(self) -> None:
        result = ensure_valid_sales_analysis_result(
            build_valid_sales_analysis_payload(
                recommendations=[
                    build_restock_recommendation(),
                    build_discount_recommendation(),
                ]
            )
        )

        action_bodies = map_sales_analysis_to_actions(result)

        self.assertEqual(len(action_bodies), 2)
        for body in action_bodies:
            self.assertEqual(body["report_run_id"], "run-valid-1")
            self.assertTrue(body["requires_approval"])


class SalesActionPersistenceTests(unittest.TestCase):
    def test_successful_action_persistence(self) -> None:
        result = ensure_valid_sales_analysis_result(build_valid_sales_analysis_payload())
        captured_bodies: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_bodies.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(
                201,
                json={
                    "id": "action-1",
                    "status": "pending_approval",
                    "requires_approval": True,
                    "action_type": captured_bodies[-1]["action_type"],
                },
            )

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        responses = persist_sales_actions(
            result,
            django_client=client,
            report_run_id="run-persist-1",
        )

        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["status"], "pending_approval")
        self.assertEqual(captured_bodies[0]["action_type"], "sales.restock")
        self.assertEqual(captured_bodies[0]["report_run_id"], "run-persist-1")

    def test_dry_run_maps_without_posting(self) -> None:
        result = ensure_valid_sales_analysis_result(build_valid_sales_analysis_payload())

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("Django POST must not occur in dry_run mode")

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        mapped = persist_sales_actions(
            result,
            django_client=client,
            dry_run=True,
        )

        self.assertEqual(len(mapped), 1)
        self.assertEqual(mapped[0]["action_type"], "sales.restock")

    def test_django_failure_response_surfaces_as_warning_on_run_endpoint(self) -> None:
        client = TestClient(app)
        non_empty_context = {
            "sales_summary": {
                "today": {
                    "order_count": 2,
                    "total_revenue": "200.00",
                    "top_products": [{"sku": "BAG-001", "revenue": "200.00"}],
                },
                "last_7_days": {
                    "order_count": 0,
                    "total_revenue": 0,
                    "top_products": [],
                },
            },
            "inventory": {
                "low_stock_count": 1,
                "items": [{"sku": "BAG-001", "available_quantity": 1}],
            },
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"detail": "Invalid action payload."})

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        django_client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        with patch("agents.sales.app.main._build_django_client", return_value=django_client):
            with patch.dict("os.environ", {"LLM_PROVIDER": "mock"}, clear=False):
                response = client.post(
                    "/run",
                    json={
                        "context": non_empty_context,
                        "persist_actions": True,
                        "service_token": "test-token",
                    },
                )

        self.assertEqual(response.status_code, 200)
        warnings = response.json()["warnings"]
        self.assertTrue(any(item["code"] == "action_persistence_failed" for item in warnings))

    @patch.dict("os.environ", {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_dry_run_does_not_persist(self) -> None:
        client = TestClient(app)
        non_empty_context = {
            "sales_summary": {
                "today": {
                    "order_count": 2,
                    "total_revenue": "200.00",
                    "top_products": [{"sku": "BAG-001", "revenue": "200.00"}],
                },
                "last_7_days": {
                    "order_count": 0,
                    "total_revenue": 0,
                    "top_products": [],
                },
            },
            "inventory": {
                "low_stock_count": 1,
                "items": [{"sku": "BAG-001", "available_quantity": 1}],
            },
        }

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("Django POST must not occur when dry_run is true")

        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        django_client = DjangoClient(
            base_url="http://backend:8000",
            max_retries=0,
            http_client=http_client,
        )

        with patch("agents.sales.app.main._build_django_client", return_value=django_client):
            response = client.post(
                "/run",
                json={
                    "context": non_empty_context,
                    "persist_actions": True,
                    "dry_run": True,
                    "service_token": "test-token",
                },
            )

        self.assertEqual(response.status_code, 200)
        warnings = response.json()["warnings"]
        self.assertTrue(any(item["code"] == "dry_run" for item in warnings))


if __name__ == "__main__":
    unittest.main()
