"""Validate the documented Support Agent example output (Step 9.8)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from agents.shared.schemas import SupportInsights
from agents.support.validation import validate_support_insights

ALLOWED_ACTION_TYPES = frozenset({"support.reply_draft", "support.escalate"})
REQUIRED_DRAFT_FIELDS = frozenset(
    {
        "thread_ref",
        "reply_text",
        "action_type",
        "requires_approval",
        "risk_level",
        "matched_policy_code",
    }
)
PII_PATTERNS = (
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
)
EXECUTED_ACTION_PHRASES = (
    "message sent",
    "refund issued",
    "order updated",
    "order cancelled",
    "payment processed",
    "instagram dm sent",
    "already sent",
    "has been executed",
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_OUTPUT_PATH = REPO_ROOT / "docs" / "examples" / "support_output.json"


class SupportOutputExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(
            EXAMPLE_OUTPUT_PATH.is_file(),
            f"Example output file is missing: {EXAMPLE_OUTPUT_PATH}",
        )
        raw = EXAMPLE_OUTPUT_PATH.read_text(encoding="utf-8")
        try:
            self.payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.fail(
                f"docs/examples/support_output.json contains malformed JSON: {exc}"
            )

    def test_example_validates_against_support_insights(self) -> None:
        validated = validate_support_insights(self.payload)

        self.assertIsInstance(validated, SupportInsights)
        self.assertEqual(validated.metadata.agent_name, "support-agent")
        self.assertTrue(validated.summary.strip())
        self.assertGreaterEqual(len(validated.reply_drafts), 1)

    def test_example_includes_required_draft_fields(self) -> None:
        drafts = self.payload["reply_drafts"]

        for index, draft in enumerate(drafts):
            missing = REQUIRED_DRAFT_FIELDS - draft.keys()
            self.assertFalse(
                missing,
                f"reply_drafts[{index}] is missing required fields: {sorted(missing)}",
            )

    def test_example_uses_allowed_action_types_only(self) -> None:
        drafts = self.payload["reply_drafts"]
        action_types = {item["action_type"] for item in drafts}

        for index, draft in enumerate(drafts):
            action_type = draft["action_type"]
            self.assertIn(
                action_type,
                ALLOWED_ACTION_TYPES,
                f"reply_drafts[{index}].action_type is not allowed: {action_type}",
            )

        self.assertIn("support.reply_draft", action_types)

    def test_example_includes_theme_and_sentiment_summary_fields(self) -> None:
        self.assertIsInstance(self.payload["themes"], list)
        self.assertGreaterEqual(len(self.payload["themes"]), 1)
        self.assertIn("label", self.payload["sentiment"])

    def test_example_does_not_contain_obvious_raw_pii(self) -> None:
        serialized = json.dumps(self.payload)

        for pattern in PII_PATTERNS:
            self.assertIsNone(
                pattern.search(serialized),
                f"Example appears to contain raw PII matching {pattern.pattern}",
            )

    def test_example_does_not_claim_executed_actions(self) -> None:
        serialized = json.dumps(self.payload).lower()

        for phrase in EXECUTED_ACTION_PHRASES:
            self.assertNotIn(
                phrase,
                serialized,
                f"Example must not claim executed action: {phrase}",
            )


if __name__ == "__main__":
    unittest.main()
