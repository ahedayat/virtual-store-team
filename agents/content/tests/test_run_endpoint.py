"""Endpoint tests for Content Agent POST /run (Step 8.5)."""

from __future__ import annotations

import json
import os
import unittest
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents.content.app.main import app
from agents.content.validation import ContentLLMOutputError
from agents.shared.schemas import AgentSchemaValidationError


def build_product_fixture(**overrides: object) -> dict[str, Any]:
    product: dict[str, Any] = {
        "product_id": "00000000-0000-4000-8000-000000000001",
        "title": "Everyday Leather Tote",
        "category": "Bags",
        "price": "89.00",
        "currency": "USD",
        "image_url": "https://cdn.example.test/products/tote.jpg",
    }
    product.update(overrides)
    return product


def build_store_context(**overrides: object) -> dict[str, Any]:
    store: dict[str, Any] = {
        "id": "store-1",
        "display_name": "Demo Store",
        "currency": "USD",
        "settings": {
            "brand_voice": {
                "tone": "luxury, warm, concise",
                "audience": "modern shoppers",
                "style_notes": "avoid exaggerated claims",
            },
            "content_agent": {
                "max_drafts_per_run": 3,
            },
        },
    }
    store.update(overrides)
    return store


def build_context_bundle(**overrides: object) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "store": build_store_context(),
        "products": [build_product_fixture()],
        "campaign_angle": "New arrivals",
    }
    bundle.update(overrides)
    return bundle


class ContentRunEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint_returns_success(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "content-agent"},
        )

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_returns_valid_content_suggestions(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "context": build_context_bundle(),
                "report_run_id": "run-valid-1",
                "output_language": "en",
            },
            headers={"X-Request-ID": "trace-123"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metadata"]["agent_name"], "content-agent")
        self.assertEqual(body["metadata"]["report_run_id"], "run-valid-1")
        self.assertGreaterEqual(len(body["drafts"]), 1)
        self.assertIn("summary", body)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_returns_instagram_draft_for_product_context(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "products": [build_product_fixture()],
                "store_context": build_store_context(),
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        instagram_drafts = [
            draft
            for draft in response.json()["drafts"]
            if draft["action_type"] == "content.instagram_draft"
        ]
        self.assertGreaterEqual(len(instagram_drafts), 1)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_respects_max_draft_limit(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "products": [build_product_fixture()],
                "store_context": build_store_context(),
                "output_language": "en",
                "max_drafts_per_run": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["drafts"]), 1)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_preserves_requires_approval(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "products": [build_product_fixture()],
                "store_context": build_store_context(),
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        for draft in response.json()["drafts"]:
            self.assertTrue(draft["requires_approval"])

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "AI_OUTPUT_LANGUAGE": "en"}, clear=False)
    def test_run_endpoint_english_mode_via_env(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "products": [build_product_fixture()],
                "store_context": build_store_context(),
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["output_language"], "en")
        self.assertIn("Reviewable content drafts", body["summary"])

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_run_endpoint_empty_product_context(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "context": {
                    "store": build_store_context(),
                    "products": [],
                },
                "report_run_id": "run-empty-1",
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["drafts"], [])
        self.assertEqual(
            body["summary"],
            "No products were available for content draft generation.",
        )
        self.assertEqual(body["metadata"]["report_run_id"], "run-empty-1")

    def test_run_endpoint_invalid_request_body_returns_validation_error(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "products": [build_product_fixture()],
                "max_drafts_per_run": "not-an-integer",
            },
        )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertIn("detail", body)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    @patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}, clear=False)
    def test_run_endpoint_no_real_llm_api_key_required(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "products": [build_product_fixture()],
                "store_context": build_store_context(),
                "output_language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()["drafts"]), 1)

    def test_run_endpoint_does_not_expose_stack_traces(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "products": [build_product_fixture()],
                "max_drafts_per_run": "bad",
            },
        )

        body_text = json.dumps(response.json())
        self.assertNotIn("Traceback", body_text)
        self.assertNotIn('File "', body_text)

    @patch("agents.content.app.main.run_content_analysis")
    def test_run_endpoint_maps_validation_errors_to_422(
        self,
        mock_run_content_analysis,
    ) -> None:
        mock_run_content_analysis.side_effect = AgentSchemaValidationError(
            "Agent response failed validation against schema 'ContentSuggestions': "
            "drafts[0].action_type: Input should be 'content.instagram_draft' or "
            "'content.product_description'",
            schema_name="ContentSuggestions",
            field_errors=[
                {
                    "field": "drafts[0].action_type",
                    "message": (
                        "Input should be 'content.instagram_draft' or "
                        "'content.product_description'"
                    ),
                    "type": "literal_error",
                }
            ],
        )

        response = self.client.post(
            "/run",
            json={
                "products": [build_product_fixture()],
                "store_context": build_store_context(),
                "report_run_id": "run-invalid-1",
            },
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "schema_validation_failed")
        self.assertEqual(detail["schema_name"], "ContentSuggestions")
        self.assertIn("field_errors", detail)
        self.assertNotIn("Traceback", json.dumps(detail))

    @patch("agents.content.app.main.run_content_analysis")
    def test_run_endpoint_maps_llm_output_errors_to_422(
        self,
        mock_run_content_analysis,
    ) -> None:
        mock_run_content_analysis.side_effect = ContentLLMOutputError(
            "LLM returned malformed JSON."
        )

        response = self.client.post(
            "/run",
            json={
                "products": [build_product_fixture()],
                "store_context": build_store_context(),
            },
        )

        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "llm_output_invalid")
        self.assertNotIn("Traceback", json.dumps(detail))


if __name__ == "__main__":
    unittest.main()
