"""Endpoint tests for Support Agent POST /run scaffold (Phase 6.6)."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents.support.app.main import app
from agents.support.validation import SupportLLMOutputError


class SupportRunEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint_returns_success(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "support-agent"},
        )

    def test_root_endpoint_returns_placeholder(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "support-agent")

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_run_endpoint_returns_structured_mock_output(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "customer_message": "Where is my order?",
                "channel": "instagram_dm",
                "tenant_id": "tenant-1",
                "store_id": "store-1",
                "request_id": "req-support-1",
                "output_language": "en",
            },
            headers={"X-Request-ID": "trace-support-1"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["agent"], "support-agent")
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["language"], "en")
        self.assertEqual(body["intent"], "order_status")
        self.assertEqual(body["request_id"], "trace-support-1")
        self.assertIn("reply", body)
        self.assertIsInstance(body["confidence"], float)
        self.assertIsInstance(body["requires_human_review"], bool)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_is_deterministic(self) -> None:
        payload = {
            "customer_message": "Hello, I have a question about sizing.",
            "channel": "instagram_dm",
            "output_language": "en",
        }

        first = self.client.post("/run", json=payload)
        second = self.client.post("/run", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_marks_refund_messages_for_review(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "customer_message": "I need a refund please",
                "channel": "instagram_dm",
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["intent"], "refund_request")
        self.assertTrue(body["requires_human_review"])

    def test_run_endpoint_rejects_missing_customer_message(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "channel": "instagram_dm",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_run_endpoint_rejects_empty_customer_message(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "customer_message": "",
                "channel": "instagram_dm",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_run_endpoint_rejects_missing_channel(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "customer_message": "Hello",
            },
        )

        self.assertEqual(response.status_code, 422)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_run_endpoint_no_real_llm_api_key_required(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "customer_message": "سلام",
                "channel": "instagram_dm",
                "output_language": "fa",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["language"], "fa")

    @patch("agents.support.app.main.run_support_analysis")
    def test_run_endpoint_maps_validation_errors_to_422(
        self,
        mock_run_support_analysis,
    ) -> None:
        mock_run_support_analysis.side_effect = SupportLLMOutputError("LLM returned malformed JSON.")

        response = self.client.post(
            "/run",
            json={
                "customer_message": "Hello",
                "channel": "instagram_dm",
            },
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "llm_output_invalid")
        self.assertNotIn("Traceback", json.dumps(detail))


if __name__ == "__main__":
    unittest.main()
