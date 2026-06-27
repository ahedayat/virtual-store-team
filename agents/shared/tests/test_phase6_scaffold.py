"""Cross-agent Phase 6 scaffold verification (Step 6.8)."""

from __future__ import annotations

import os
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents.content.app.main import app as content_app
from agents.coordinator.app.main import app as coordinator_app
from agents.coordinator.tests.test_daily_report_endpoint import build_valid_payload
from agents.sales.app.main import app as sales_app
from agents.sales.tests.test_schema_validation import EMPTY_CONTEXT_BUNDLE, NON_EMPTY_CONTEXT
from agents.support.app.main import app as support_app


class Phase6ScaffoldVerificationTests(unittest.TestCase):
    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_all_agents_expose_health_endpoints(self) -> None:
        agents = {
            "coordinator-agent": TestClient(coordinator_app),
            "sales-agent": TestClient(sales_app),
            "content-agent": TestClient(content_app),
            "support-agent": TestClient(support_app),
        }

        for service_name, client in agents.items():
            with self.subTest(service=service_name):
                response = client.get("/health")
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["status"], "ok")
                self.assertEqual(body["service"], service_name)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    @patch("agents.coordinator.app.main.execute_daily_report_workflow")
    def test_coordinator_daily_report_endpoint_returns_structured_output(
        self,
        mock_execute,
    ) -> None:
        from unittest.mock import MagicMock

        from agents.coordinator.app.workflow_endpoint import COMPLETED_MESSAGE

        mock_execute.return_value = MagicMock(
            status="completed",
            workflow="daily_report",
            report_run_id="11111111-1111-4111-8111-111111111111",
            message=COMPLETED_MESSAGE,
            warnings=[],
            partial=False,
        )
        client = TestClient(coordinator_app)
        response = client.post("/workflows/daily-report", json=build_valid_payload())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["workflow"], "daily_report")

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_sales_agent_run_returns_structured_mock_output(self) -> None:
        client = TestClient(sales_app)
        response = client.post(
            "/run",
            json={
                "context": NON_EMPTY_CONTEXT,
                "report_run_id": "phase6-sales-1",
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metadata"]["agent_name"], "sales-agent")
        self.assertGreaterEqual(len(body["recommendations"]), 1)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_content_agent_run_returns_structured_mock_output(self) -> None:
        client = TestClient(content_app)
        response = client.post(
            "/run",
            json={
                "products": [
                    {
                        "product_id": str(uuid.uuid4()),
                        "title": "Canvas Tote",
                        "category": "Bags",
                    }
                ],
                "store_context": {
                    "display_name": "Demo Store",
                    "settings": {"brand_voice": {"tone": "warm"}},
                },
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metadata"]["agent_name"], "content-agent")
        self.assertGreaterEqual(len(body["drafts"]), 1)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_support_agent_run_returns_structured_mock_output(self) -> None:
        client = TestClient(support_app)
        response = client.post(
            "/run",
            json={
                "customer_message": "Can you help with my order?",
                "channel": "instagram_dm",
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["agent"], "support-agent")
        self.assertEqual(body["status"], "ok")
        self.assertIn("reply", body)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_sales_empty_input_path_remains_deterministic(self) -> None:
        client = TestClient(sales_app)
        response = client.post(
            "/run",
            json={
                "context": EMPTY_CONTEXT_BUNDLE,
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["recommendations"], [])
        self.assertEqual(body["summary"], "No sales were recorded for this period.")


if __name__ == "__main__":
    unittest.main()
