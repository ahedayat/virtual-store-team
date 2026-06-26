"""Validate the documented Content Agent example output (Step 8.7)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.content.draft_limit import DEFAULT_MAX_DRAFTS_PER_RUN
from agents.content.validation import validate_content_suggestions_output
from agents.shared.schemas import ContentSuggestions

ALLOWED_ACTION_TYPES = frozenset(
    {"content.instagram_draft", "content.product_description"}
)
REQUIRED_DRAFT_FIELDS = frozenset(
    {
        "action_type",
        "title",
        "description",
        "draft_text",
        "rationale",
        "requires_approval",
    }
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_OUTPUT_PATH = REPO_ROOT / "docs" / "examples" / "content_output.json"


class ContentOutputExampleTests(unittest.TestCase):
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
                f"docs/examples/content_output.json contains malformed JSON: {exc}"
            )

    def test_example_validates_against_content_suggestions(self) -> None:
        validated = validate_content_suggestions_output(self.payload)

        self.assertIsInstance(validated, ContentSuggestions)
        self.assertEqual(validated.metadata.agent_name, "content-agent")
        self.assertTrue(validated.summary.strip())

    def test_example_includes_required_draft_fields(self) -> None:
        drafts = self.payload["drafts"]

        self.assertGreaterEqual(len(drafts), 1)

        for index, draft in enumerate(drafts):
            missing = REQUIRED_DRAFT_FIELDS - draft.keys()
            self.assertFalse(
                missing,
                f"drafts[{index}] is missing required fields: {sorted(missing)}",
            )

    def test_example_uses_allowed_action_types_and_requires_approval(self) -> None:
        drafts = self.payload["drafts"]
        action_types = {item["action_type"] for item in drafts}

        for index, draft in enumerate(drafts):
            action_type = draft["action_type"]

            self.assertIn(
                action_type,
                ALLOWED_ACTION_TYPES,
                f"drafts[{index}].action_type is not allowed: {action_type}",
            )
            self.assertTrue(
                draft["requires_approval"],
                f"drafts[{index}].requires_approval must be true",
            )

        self.assertIn("content.instagram_draft", action_types)
        self.assertIn("content.product_description", action_types)

    def test_example_product_description_includes_product_id(self) -> None:
        description_drafts = [
            draft
            for draft in self.payload["drafts"]
            if draft["action_type"] == "content.product_description"
        ]

        self.assertGreaterEqual(len(description_drafts), 1)
        for index, draft in enumerate(description_drafts):
            product_id = draft.get("product_id")
            self.assertTrue(
                isinstance(product_id, str) and product_id.strip(),
                f"content.product_description drafts[{index}] must include product_id",
            )

    def test_example_respects_default_max_draft_limit(self) -> None:
        drafts = self.payload["drafts"]

        self.assertLessEqual(
            len(drafts),
            DEFAULT_MAX_DRAFTS_PER_RUN,
            (
                "Example must respect the default max draft limit "
                f"({DEFAULT_MAX_DRAFTS_PER_RUN})"
            ),
        )


if __name__ == "__main__":
    unittest.main()
