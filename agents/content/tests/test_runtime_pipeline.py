"""Unit tests for Content Agent runtime pipeline (Step 8.4)."""

from __future__ import annotations

import json
import os
import unittest
from typing import Any
from unittest.mock import patch

from agents.content.analysis import run_content_analysis
from agents.content.validation import ContentLLMOutputError
from agents.shared.llm import MockProvider
from agents.shared.schemas import AgentSchemaValidationError, ContentSuggestions


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


class _CapturingMockProvider:
    def __init__(self, delegate: MockProvider | None = None) -> None:
        self.delegate = delegate or MockProvider()
        self.messages: list[dict[str, str]] = []

    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        self.messages = messages
        return self.delegate.complete(messages)


class _OverLimitMockProvider:
    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = MockProvider().complete(messages)
        extra_drafts = []
        for index in range(4, 8):
            extra_drafts.append(
                {
                    "action_type": "content.instagram_draft",
                    "title": f"Extra draft {index}",
                    "description": "Overflow draft for limit testing.",
                    "draft_text": f"Overflow body {index}",
                    "product_id": "00000000-0000-4000-8000-000000000099",
                    "rationale": "Synthetic overflow draft.",
                    "requires_approval": True,
                }
            )
        payload["drafts"] = list(payload.get("drafts", [])) + extra_drafts
        return payload


class _InvalidMockProvider:
    def complete(self, messages: list[dict[str, str]]) -> str:
        return json.dumps(
            {
                "metadata": {"agent_name": "content-agent", "report_run_id": "run-invalid"},
                "summary": "Invalid draft payload.",
                "drafts": [
                    {
                        "action_type": "content.publish_instagram",
                        "title": "Bad draft",
                        "description": "Invalid action type.",
                        "draft_text": "Should fail validation.",
                        "rationale": "Invalid action type test.",
                        "requires_approval": True,
                    }
                ],
                "warnings": [],
            }
        )


class ContentRuntimePipelineTests(unittest.TestCase):
    def test_run_content_analysis_returns_validated_result_for_product_fixtures(self) -> None:
        result = run_content_analysis(
            context=build_context_bundle(),
            report_run_id="run-valid-1",
            output_language="en",
            llm_provider=MockProvider(),
        )

        self.assertIsInstance(result, ContentSuggestions)
        self.assertEqual(result.metadata.report_run_id, "run-valid-1")
        self.assertGreaterEqual(len(result.drafts), 1)

    def test_generates_instagram_draft_for_product_fixture(self) -> None:
        result = run_content_analysis(
            products=[build_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        instagram_drafts = [
            draft for draft in result.drafts if draft.action_type == "content.instagram_draft"
        ]
        self.assertGreaterEqual(len(instagram_drafts), 1)
        self.assertIn("Everyday Leather Tote", instagram_drafts[0].draft_text)

    def test_generates_product_description_draft_when_supported(self) -> None:
        result = run_content_analysis(
            products=[build_product_fixture()],
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

    def test_prompt_builder_uses_brand_voice_from_store_settings(self) -> None:
        provider = _CapturingMockProvider()

        run_content_analysis(
            products=[build_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            llm_provider=provider,
        )

        self.assertEqual(len(provider.messages), 2)
        system_prompt = provider.messages[0]["content"]
        self.assertIn("luxury, warm, concise", system_prompt)
        self.assertIn("modern shoppers", system_prompt)
        self.assertIn("avoid exaggerated claims", system_prompt)
        self.assertIn("Brand voice source: store settings", system_prompt)

    def test_draft_limit_is_applied_inside_runtime_pipeline(self) -> None:
        result = run_content_analysis(
            products=[build_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            max_drafts_per_run=1,
            llm_provider=_OverLimitMockProvider(),
        )

        self.assertEqual(len(result.drafts), 1)

    def test_over_limit_mock_output_is_limited_and_validated(self) -> None:
        result = run_content_analysis(
            products=[build_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            max_drafts_per_run=2,
            llm_provider=_OverLimitMockProvider(),
        )

        self.assertEqual(len(result.drafts), 2)
        self.assertTrue(all(draft.requires_approval for draft in result.drafts))

    def test_invalid_mock_output_raises_validation_error(self) -> None:
        with self.assertRaises(AgentSchemaValidationError):
            run_content_analysis(
                products=[build_product_fixture()],
                store_context=build_store_context(),
                output_language="en",
                llm_provider=_InvalidMockProvider(),
            )

    def test_empty_product_context_returns_empty_valid_result(self) -> None:
        result = run_content_analysis(
            context={"store": build_store_context(), "products": []},
            report_run_id="run-empty-1",
            output_language="en",
            llm_provider=MockProvider(),
        )

        self.assertEqual(result.drafts, [])
        self.assertEqual(result.summary, "No products were available for content draft generation.")
        self.assertEqual(result.metadata.report_run_id, "run-empty-1")

    def test_empty_products_do_not_hallucinate_catalog_items(self) -> None:
        provider = _CapturingMockProvider()

        result = run_content_analysis(
            products=[],
            store_context=build_store_context(),
            output_language="en",
            llm_provider=provider,
        )

        self.assertEqual(result.drafts, [])
        self.assertEqual(provider.messages, [])

    @patch.dict(os.environ, {"AI_OUTPUT_LANGUAGE": "fa"}, clear=False)
    def test_persian_output_language_path(self) -> None:
        result = run_content_analysis(
            products=[build_product_fixture(title="کیف چرم روزمره")],
            store_context=build_store_context(),
            llm_provider=MockProvider(),
        )

        self.assertEqual(result.output_language, "fa")
        self.assertIn("پیشنهادهای محتوای قابل بررسی", result.summary)
        self.assertTrue(any("معرفی" in draft.draft_text for draft in result.drafts))

    def test_english_output_language_path(self) -> None:
        result = run_content_analysis(
            products=[build_product_fixture()],
            store_context=build_store_context(),
            output_language="en",
            llm_provider=MockProvider(),
        )

        self.assertEqual(result.output_language, "en")
        self.assertIn("Reviewable content drafts", result.summary)
        self.assertTrue(any("Introducing" in draft.draft_text for draft in result.drafts))

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_no_real_llm_api_key_required(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": ""}, clear=False):
            result = run_content_analysis(
                products=[build_product_fixture()],
                store_context=build_store_context(),
                output_language="en",
            )

        self.assertGreaterEqual(len(result.drafts), 1)

    @patch("agents.content.analysis.log_content_validation_failure")
    def test_validation_failure_logs_safe_summary_only(
        self,
        mock_log_failure,
    ) -> None:
        with self.assertRaises(AgentSchemaValidationError):
            run_content_analysis(
                products=[build_product_fixture()],
                store_context=build_store_context(),
                report_run_id="run-log-1",
                request_id="req-log-1",
                output_language="en",
                llm_provider=_InvalidMockProvider(),
            )

        mock_log_failure.assert_called_once()
        logged_exc = mock_log_failure.call_args.args[0]
        self.assertIsInstance(logged_exc, AgentSchemaValidationError)

    def test_malformed_mock_json_raises_content_llm_output_error(self) -> None:
        class _MalformedProvider:
            def complete(self, messages: list[dict[str, str]]) -> str:
                return "{not valid json"

        with self.assertRaises(ContentLLMOutputError):
            run_content_analysis(
                products=[build_product_fixture()],
                store_context=build_store_context(),
                output_language="en",
                llm_provider=_MalformedProvider(),
            )

    def test_context_bundle_products_are_consumed(self) -> None:
        result = run_content_analysis(
            context=build_context_bundle(
                products=[
                    build_product_fixture(),
                    build_product_fixture(
                        product_id="00000000-0000-4000-8000-000000000002",
                        title="Weekend Crossbody",
                    ),
                ]
            ),
            output_language="en",
            llm_provider=MockProvider(),
        )

        product_ids = {draft.product_id for draft in result.drafts}
        self.assertIn("00000000-0000-4000-8000-000000000001", product_ids)
        self.assertIn("00000000-0000-4000-8000-000000000002", product_ids)


if __name__ == "__main__":
    unittest.main()
