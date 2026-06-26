"""Validate the documented Sales Agent example output (Step 7.4)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agents.sales.validation import validate_sales_analysis_output
from agents.shared.schemas import SalesAnalysisResult

ALLOWED_ACTION_TYPES = frozenset(
    {"sales.restock", "sales.discount", "sales.follow_up"}
)
REQUIRED_RECOMMENDATION_FIELDS = frozenset(
    {
        "priority",
        "action_type",
        "title",
        "description",
        "rationale",
        "payload",
    }
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_OUTPUT_PATH = REPO_ROOT / "docs" / "examples" / "sales_output.json"


class SalesOutputExampleTests(unittest.TestCase):
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
                f"docs/examples/sales_output.json contains malformed JSON: {exc}"
            )

    def test_example_validates_against_sales_analysis_result(self) -> None:
        validated = validate_sales_analysis_output(self.payload)

        self.assertIsInstance(validated, SalesAnalysisResult)
        self.assertEqual(validated.metadata.agent_name, "sales-agent")
        self.assertTrue(validated.summary.strip())

    def test_example_includes_required_recommendation_fields(self) -> None:
        recommendations = self.payload["recommendations"]

        self.assertGreaterEqual(len(recommendations), 1)

        for index, recommendation in enumerate(recommendations):
            missing = REQUIRED_RECOMMENDATION_FIELDS - recommendation.keys()
            self.assertFalse(
                missing,
                f"recommendations[{index}] is missing required fields: {sorted(missing)}",
            )

    def test_example_uses_allowed_action_types_and_priority_range(self) -> None:
        recommendations = self.payload["recommendations"]
        action_types = {item["action_type"] for item in recommendations}

        for index, recommendation in enumerate(recommendations):
            action_type = recommendation["action_type"]
            priority = recommendation["priority"]

            self.assertIn(
                action_type,
                ALLOWED_ACTION_TYPES,
                f"recommendations[{index}].action_type is not allowed: {action_type}",
            )
            self.assertIsInstance(priority, int)
            self.assertGreaterEqual(
                priority,
                1,
                f"recommendations[{index}].priority must be >= 1",
            )
            self.assertLessEqual(
                priority,
                5,
                f"recommendations[{index}].priority must be <= 5",
            )

        self.assertTrue(
            action_types.intersection({"sales.restock", "sales.discount"}),
            "Example must include at least one sales.restock or sales.discount recommendation",
        )


if __name__ == "__main__":
    unittest.main()
