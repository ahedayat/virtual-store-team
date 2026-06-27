"""Unit tests for Support Agent SupportInsights schema validation (Step 9.4)."""

from __future__ import annotations

import json
import os
import unittest
from typing import Any
from unittest.mock import patch

from agents.shared.llm import MockProvider
from agents.shared.schemas import AgentSchemaValidationError, SupportInsights
from agents.support.prompts import build_support_reply_messages
from agents.support.validation import (
    SupportLLMOutputError,
    ensure_valid_support_insights,
    parse_llm_json_output,
    validate_support_insights,
)


def build_reply_draft(**overrides: object) -> dict[str, Any]:
    draft: dict[str, Any] = {
        "thread_ref": "thread-ref-001",
        "reply_text": "Thank you for your message. We prepared a reviewable support reply draft.",
        "action_type": "support.reply_draft",
        "requires_approval": False,
        "risk_level": "low",
        "matched_policy_code": "generic_faq",
        "safety_notes": [],
        "rationale": "Generic FAQ reply may be auto-drafted when safe.",
        "language": "en",
    }
    draft.update(overrides)
    return draft


def build_valid_support_insights_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "metadata": {
            "agent_name": "support-agent",
            "report_run_id": "run-support-1",
        },
        "summary": "Support message analyzed with a reviewable reply draft.",
        "themes": ["generic_faq"],
        "sentiment": {"label": "neutral", "confidence": 0.9},
        "reply_drafts": [build_reply_draft()],
        "warnings": [],
        "output_language": "en",
    }
    payload.update(overrides)
    return payload


class SupportInsightsSchemaValidationTests(unittest.TestCase):
    def test_valid_low_risk_reply_draft_passes_validation(self) -> None:
        payload = build_valid_support_insights_payload()

        validated = validate_support_insights(payload)

        self.assertIsInstance(validated, SupportInsights)
        self.assertEqual(validated.reply_drafts[0].action_type, "support.reply_draft")
        self.assertEqual(validated.reply_drafts[0].risk_level, "low")
        self.assertFalse(validated.reply_drafts[0].requires_approval)

    def test_valid_escalate_draft_passes_validation(self) -> None:
        payload = build_valid_support_insights_payload(
            themes=["angry_or_escalated_customer"],
            sentiment={"label": "negative", "confidence": 0.88},
            reply_drafts=[
                build_reply_draft(
                    action_type="support.escalate",
                    requires_approval=True,
                    risk_level="high",
                    matched_policy_code="angry_or_escalated_customer",
                    reply_text="A manager will review this conversation shortly.",
                    safety_notes=["Manager approval is required before escalation."],
                )
            ],
        )

        validated = validate_support_insights(payload)

        self.assertEqual(validated.reply_drafts[0].action_type, "support.escalate")
        self.assertTrue(validated.reply_drafts[0].requires_approval)

    def test_missing_reply_drafts_field_fails_validation(self) -> None:
        payload = build_valid_support_insights_payload()
        del payload["reply_drafts"]

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_support_insights(payload)

        self.assertTrue(
            any("reply_drafts" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_empty_reply_drafts_list_fails_validation(self) -> None:
        payload = build_valid_support_insights_payload(reply_drafts=[])

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_support_insights(payload)

        self.assertTrue(
            any("reply_drafts" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_unsupported_action_type_fails_validation(self) -> None:
        payload = build_valid_support_insights_payload(
            reply_drafts=[build_reply_draft(action_type="support.send_dm")],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_support_insights(payload)

        self.assertTrue(
            any("action_type" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_missing_required_draft_field_fails_validation(self) -> None:
        payload = build_valid_support_insights_payload(
            reply_drafts=[build_reply_draft(thread_ref="")],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_support_insights(payload)

        self.assertTrue(
            any("thread_ref" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_escalate_without_approval_fails_validation(self) -> None:
        payload = build_valid_support_insights_payload(
            reply_drafts=[
                build_reply_draft(
                    action_type="support.escalate",
                    requires_approval=False,
                    risk_level="high",
                    matched_policy_code="angry_or_escalated_customer",
                )
            ],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_support_insights(payload)

        error_text = str(ctx.exception).lower()
        self.assertTrue("requires_approval" in error_text or "approval" in error_text)

    def test_high_risk_without_approval_fails_validation(self) -> None:
        payload = build_valid_support_insights_payload(
            reply_drafts=[
                build_reply_draft(
                    requires_approval=False,
                    risk_level="high",
                    matched_policy_code="refund_request",
                )
            ],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_support_insights(payload)

        error_text = str(ctx.exception).lower()
        self.assertTrue("high-risk" in error_text or "approval" in error_text)

    def test_invalid_risk_level_fails_validation(self) -> None:
        payload = build_valid_support_insights_payload(
            reply_drafts=[build_reply_draft(risk_level="critical")],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_support_insights(payload)

        self.assertTrue(
            any("risk_level" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_extra_unknown_fields_are_rejected(self) -> None:
        payload = build_valid_support_insights_payload(extra_field="forbidden")

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_support_insights(payload)

        self.assertTrue(
            any(item["field"] == "extra_field" for item in ctx.exception.field_errors)
        )

    @patch.dict(os.environ, {"LLM_PROVIDER": "mock", "OPENAI_API_KEY": ""}, clear=False)
    def test_mock_provider_support_output_validates(self) -> None:
        messages = build_support_reply_messages(
            customer_message="Where is my order?",
            channel="instagram_dm",
            output_language="en",
            request_id="req-mock-1",
        )

        raw = MockProvider().complete(messages)
        validated = ensure_valid_support_insights(raw)

        self.assertEqual(validated.metadata.agent_name, "support-agent")
        self.assertGreaterEqual(len(validated.reply_drafts), 1)
        self.assertIn(
            validated.reply_drafts[0].action_type,
            {"support.reply_draft", "support.escalate"},
        )

    def test_valid_json_response_parses_into_schema(self) -> None:
        payload = build_valid_support_insights_payload()

        parsed = parse_llm_json_output(json.dumps(payload))
        validated = ensure_valid_support_insights(parsed)

        self.assertEqual(validated.summary, payload["summary"])

    def test_invalid_json_is_handled_deterministically(self) -> None:
        with self.assertRaises(SupportLLMOutputError) as ctx:
            parse_llm_json_output("{not valid json")

        self.assertIn("malformed JSON", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
