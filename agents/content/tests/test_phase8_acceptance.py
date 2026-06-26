"""Phase 8 acceptance proof tests for the Content Agent (Step 8.7)."""

from __future__ import annotations

import inspect
import os
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents.content.action_mapping import (
    ContentActionMappingError,
    map_content_draft_to_action_payload,
    map_content_suggestions_to_actions,
)
from agents.content.analysis import run_content_analysis
from agents.content.app.main import app
from agents.content.prompts import build_content_draft_system_prompt
from agents.content.tests.test_runtime_pipeline import (
    _OverLimitMockProvider,
    build_product_fixture,
    build_store_context,
)
from agents.content.validation import ensure_valid_content_suggestions
from agents.shared.llm import MockProvider
from agents.shared.schemas import ContentSuggestions

ALLOWED_CONTENT_ACTION_TYPES = frozenset(
    {"content.instagram_draft", "content.product_description"}
)
CONTENT_AGENT_SOURCE_ROOT = Path(__file__).resolve().parents[1]


def build_prestia_style_product_fixture(**overrides: object) -> dict[str, Any]:
    """Prestia-style bag catalog row for acceptance tests only (not agent logic)."""
    product: dict[str, Any] = {
        "product_id": "00000000-0000-4000-8000-000000000001",
        "title": "Milano Leather Tote",
        "category": "Bags",
        "price": "129.00",
        "currency": "USD",
        "image_url": "https://cdn.example.test/products/milano-tote.jpg",
    }
    product.update(overrides)
    return product


class Phase8AcceptancePipelineTests(unittest.TestCase):
    def test_produces_instagram_draft_for_prestia_style_product_fixture(self) -> None:
        result = run_content_analysis(
            products=[build_prestia_style_product_fixture()],
            store_context=build_store_context(display_name="Demo Bag Store"),
            campaign_angle="New arrivals",
            output_language="en",
            llm_provider=MockProvider(),
        )

        instagram_drafts = [
            draft
            for draft in result.drafts
            if draft.action_type == "content.instagram_draft"
        ]
        self.assertGreaterEqual(len(instagram_drafts), 1)
        self.assertIn("Milano Leather Tote", instagram_drafts[0].draft_text)

    def test_supports_product_description_drafts(self) -> None:
        result = run_content_analysis(
            products=[build_prestia_style_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        description_drafts = [
            draft
            for draft in result.drafts
            if draft.action_type == "content.product_description"
        ]
        self.assertGreaterEqual(len(description_drafts), 1)
        self.assertEqual(
            description_drafts[0].product_id,
            "00000000-0000-4000-8000-000000000001",
        )

    def test_generated_result_validates_against_content_suggestions(self) -> None:
        result = run_content_analysis(
            products=[build_prestia_style_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        self.assertIsInstance(result, ContentSuggestions)
        revalidated = ensure_valid_content_suggestions(result.model_dump())
        self.assertIsInstance(revalidated, ContentSuggestions)

    def test_respects_configured_max_draft_limit(self) -> None:
        result = run_content_analysis(
            products=[build_prestia_style_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            max_drafts_per_run=1,
            llm_provider=_OverLimitMockProvider(),
        )

        self.assertEqual(len(result.drafts), 1)

    @patch.dict(os.environ, {"AI_OUTPUT_LANGUAGE": "fa"}, clear=False)
    def test_persian_default_output_path_end_to_end(self) -> None:
        result = run_content_analysis(
            products=[build_prestia_style_product_fixture(title="کیف چرم میلانو")],
            store_context=build_store_context(),
            llm_provider=MockProvider(),
        )

        self.assertEqual(result.output_language, "fa")
        self.assertIn("پیشنهادهای محتوای قابل بررسی", result.summary)
        self.assertTrue(all(draft.requires_approval for draft in result.drafts))

    @patch.dict(os.environ, {"AI_OUTPUT_LANGUAGE": "en"}, clear=False)
    def test_english_output_with_env_language_end_to_end(self) -> None:
        result = run_content_analysis(
            products=[build_prestia_style_product_fixture()],
            store_context=build_store_context(),
            llm_provider=MockProvider(),
        )

        self.assertEqual(result.output_language, "en")
        self.assertIn("Reviewable content drafts", result.summary)
        self.assertTrue(any("Introducing" in draft.draft_text for draft in result.drafts))

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    @patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}, clear=False)
    def test_no_real_llm_api_key_required(self) -> None:
        result = run_content_analysis(
            products=[build_prestia_style_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
        )

        self.assertGreaterEqual(len(result.drafts), 1)


class Phase8AcceptanceRunEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "AI_OUTPUT_LANGUAGE": "fa"}, clear=False)
    def test_run_endpoint_persian_default_path(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "products": [build_prestia_style_product_fixture()],
                "store_context": build_store_context(),
                "campaign_angle": "New arrivals",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["output_language"], "fa")
        self.assertGreaterEqual(len(body["drafts"]), 1)

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "AI_OUTPUT_LANGUAGE": "en"}, clear=False)
    def test_run_endpoint_english_path(self) -> None:
        response = self.client.post(
            "/run",
            json={
                "products": [build_prestia_style_product_fixture()],
                "store_context": build_store_context(),
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["output_language"], "en")
        self.assertIn("Reviewable content drafts", body["summary"])


class Phase8AcceptanceActionMappingTests(unittest.TestCase):
    def test_mapped_content_actions_remain_approval_required(self) -> None:
        result = run_content_analysis(
            products=[build_prestia_style_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        action_bodies = map_content_suggestions_to_actions(result)

        self.assertGreaterEqual(len(action_bodies), 1)
        for body in action_bodies:
            self.assertTrue(body["requires_approval"])
            self.assertIn(body["action_type"], ALLOWED_CONTENT_ACTION_TYPES)

    def test_only_allowed_content_action_types_are_accepted(self) -> None:
        result = run_content_analysis(
            products=[build_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        for draft in result.drafts:
            self.assertIn(draft.action_type, ALLOWED_CONTENT_ACTION_TYPES)
            mapped = map_content_draft_to_action_payload(draft)
            self.assertIn(mapped["action_type"], ALLOWED_CONTENT_ACTION_TYPES)

        with self.assertRaises(ContentActionMappingError):
            map_content_draft_to_action_payload(
                {
                    "action_type": "content.publish_instagram",
                    "title": "Unsupported",
                    "description": "Should fail.",
                    "draft_text": "No publish path.",
                    "rationale": "Unsupported action type.",
                    "requires_approval": True,
                }
            )


class Phase8AcceptanceArchitectureTests(unittest.TestCase):
    def test_agent_code_does_not_hardcode_prestia_business_logic(self) -> None:
        prompt = build_content_draft_system_prompt(output_language="en")
        self.assertNotIn("Prestia", prompt)
        self.assertNotIn("prestia", prompt.lower())

        scanned_sources: list[str] = []
        for path in sorted(CONTENT_AGENT_SOURCE_ROOT.rglob("*.py")):
            if path.name.startswith("test_") or path.parts[-2] == "tests":
                continue
            scanned_sources.append(path.read_text(encoding="utf-8"))

        combined = "\n".join(scanned_sources)
        self.assertNotIn("prestia", combined.lower())

    def test_no_external_publish_paths_in_action_mapping_module(self) -> None:
        from agents.content import action_mapping

        source = inspect.getsource(action_mapping)
        lowered = source.lower()
        self.assertNotIn("content.publish", lowered)
        self.assertNotIn("instagram.com", lowered)
        self.assertNotIn("/publish", lowered)
        self.assertNotIn("auto_execute", lowered)


class Phase8AcceptanceExampleArtifactTests(unittest.TestCase):
    def test_content_output_example_file_exists(self) -> None:
        example_path = (
            Path(__file__).resolve().parents[3] / "docs" / "examples" / "content_output.json"
        )
        self.assertTrue(example_path.is_file(), f"Missing example file: {example_path}")


if __name__ == "__main__":
    unittest.main()
