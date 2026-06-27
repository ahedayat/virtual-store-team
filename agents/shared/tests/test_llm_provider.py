"""Unit tests for shared LLM provider abstraction (Phase 6.5)."""

from __future__ import annotations

import json
import os
import unittest
from typing import Any
from unittest.mock import patch

from agents.shared.llm import LLMProvider, MockProvider, get_llm_provider
from agents.sales.prompts import build_sales_analysis_messages


class GetLLMProviderTests(unittest.TestCase):
    @patch.dict(os.environ, {"LLM_PROVIDER": "mock"}, clear=False)
    def test_default_mock_provider_when_env_is_mock(self) -> None:
        provider = get_llm_provider()

        self.assertIsInstance(provider, MockProvider)
        self.assertTrue(isinstance(provider, LLMProvider))

    @patch.dict(os.environ, {}, clear=True)
    def test_defaults_to_mock_when_env_missing(self) -> None:
        provider = get_llm_provider()

        self.assertIsInstance(provider, MockProvider)

    @patch.dict(os.environ, {"LLM_PROVIDER": "  MOCK  "}, clear=False)
    def test_mock_provider_name_is_case_insensitive(self) -> None:
        provider = get_llm_provider()

        self.assertIsInstance(provider, MockProvider)

    @patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=False)
    def test_unimplemented_provider_raises_not_implemented(self) -> None:
        with self.assertRaises(NotImplementedError) as ctx:
            get_llm_provider()

        self.assertIn("openai", str(ctx.exception))
        self.assertIn("LLM_PROVIDER=mock", str(ctx.exception))

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_mock_provider_works_without_external_api_keys(self) -> None:
        provider = get_llm_provider()
        messages = build_sales_analysis_messages(
            output_language="en",
            user_context=json.dumps(
                {
                    "today": {
                        "order_count": 3,
                        "total_revenue": "120.00",
                        "top_products": [{"sku": "SKU-1"}],
                    }
                }
            ),
        )

        result = provider.complete(messages)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["metadata"]["agent_name"], "sales-agent")


class MockProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockProvider()

    def test_sales_agent_marker_returns_sales_analysis_shape(self) -> None:
        messages = build_sales_analysis_messages(
            output_language="en",
            user_context=json.dumps(
                {
                    "today": {
                        "order_count": 2,
                        "total_revenue": "80.00",
                        "top_products": [{"sku": "SKU-9"}],
                    }
                }
            ),
        )

        result = self.provider.complete(messages)

        self.assertEqual(result["metadata"]["agent_name"], "sales-agent")
        self.assertIn("recommendations", result)
        self.assertGreaterEqual(len(result["recommendations"]), 1)

    def test_content_agent_marker_returns_content_suggestions_shape(self) -> None:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Content Agent for a multi-tenant virtual store "
                    "management platform.\n"
                    "Generate all user-facing AI output in English (en)."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "products": [{"product_id": "p-1", "title": "Demo Bag"}],
                        "store": {"report_run_id": "run-content-1"},
                    }
                ),
            },
        ]

        result = self.provider.complete(messages)

        self.assertEqual(result["metadata"]["agent_name"], "content-agent")
        self.assertIn("drafts", result)
        self.assertGreaterEqual(len(result["drafts"]), 1)

    def test_support_agent_marker_returns_support_insights_shape(self) -> None:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Support Agent for a multi-tenant virtual store "
                    "management platform.\n"
                    "Generate all user-facing AI output in Persian (fa)."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "customer_message": "سلام، سفارش من کجاست؟",
                        "channel": "instagram_dm",
                        "request_id": "req-support-1",
                    }
                ),
            },
        ]

        result = self.provider.complete(messages)

        self.assertEqual(result["metadata"]["agent_name"], "support-agent")
        self.assertIn("reply_drafts", result)
        self.assertGreaterEqual(len(result["reply_drafts"]), 1)
        self.assertIn("summary", result)
        self.assertIn("sentiment", result)
        draft = result["reply_drafts"][0]
        self.assertIn(draft["action_type"], {"support.reply_draft", "support.escalate"})
        self.assertEqual(draft["thread_ref"], "req-support-1")

    def test_support_refund_message_requires_human_review(self) -> None:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are the Support Agent for a multi-tenant virtual store "
                    "management platform.\n"
                    "Generate all user-facing AI output in English (en)."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "customer_message": "I need a refund for order 123",
                        "channel": "instagram_dm",
                    }
                ),
            },
        ]

        result = self.provider.complete(messages)

        self.assertEqual(result["reply_drafts"][0]["matched_policy_code"], "refund_request")
        self.assertTrue(result["reply_drafts"][0]["requires_approval"])

    def test_unrecognized_prompt_returns_warning_envelope(self) -> None:
        result = self.provider.complete(
            [{"role": "system", "content": "Unknown agent"}, {"role": "user", "content": "{}"}]
        )

        self.assertEqual(result["metadata"]["agent_name"], "unknown-agent")
        self.assertGreaterEqual(len(result["warnings"]), 1)

    def test_mock_output_is_deterministic(self) -> None:
        messages = build_sales_analysis_messages(
            output_language="en",
            user_context=json.dumps({"today": {"top_products": [{"sku": "SKU-1"}]}}),
        )

        first = self.provider.complete(messages)
        second = self.provider.complete(messages)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
