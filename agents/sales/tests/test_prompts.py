"""Unit tests for Sales Agent prompt templates (Step 7.1)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agents.sales.prompts import (
    ALLOWED_SALES_ACTION_TYPES,
    MAX_PRIORITY,
    MIN_PRIORITY,
    RECOMMENDATION_REQUIRED_FIELDS,
    build_sales_analysis_messages,
    build_sales_analysis_system_prompt,
)


class SalesAnalysisPromptTests(unittest.TestCase):
    def test_prompt_includes_full_priority_scale(self) -> None:
        prompt = build_sales_analysis_system_prompt(output_language="en")

        for priority in range(MIN_PRIORITY, MAX_PRIORITY + 1):
            with self.subTest(priority=priority):
                self.assertIn(f"Priority {priority}", prompt)

    def test_priority_one_is_highest_urgency(self) -> None:
        prompt = build_sales_analysis_system_prompt(output_language="en")

        self.assertIn("1 = highest urgency", prompt)
        self.assertIn("Priority 1 — Urgent / highest business impact", prompt)
        self.assertRegex(
            prompt,
            r"priority: integer from 1 \(highest urgency\) to 5",
        )

    def test_priority_five_is_informational_lowest_urgency(self) -> None:
        prompt = build_sales_analysis_system_prompt(output_language="en")

        self.assertIn("5 = lowest / informational", prompt)
        self.assertIn(
            "Priority 5 — Informational / no immediate action",
            prompt,
        )
        self.assertIn("insufficient evidence", prompt.lower())

    def test_allowed_sales_action_types_are_present(self) -> None:
        prompt = build_sales_analysis_system_prompt(output_language="en")

        for action_type in ALLOWED_SALES_ACTION_TYPES:
            with self.subTest(action_type=action_type):
                self.assertIn(action_type, prompt)

    def test_required_recommendation_fields_are_present(self) -> None:
        prompt = build_sales_analysis_system_prompt(output_language="en")

        for field_name in RECOMMENDATION_REQUIRED_FIELDS:
            with self.subTest(field_name=field_name):
                self.assertIn(field_name, prompt)

    def test_pii_safety_instructions_are_present(self) -> None:
        prompt = build_sales_analysis_system_prompt(output_language="en")

        self.assertIn("phone numbers", prompt.lower())
        self.assertIn("emails", prompt.lower())
        self.assertIn("customer names", prompt.lower())
        self.assertIn("do not invent", prompt.lower())
        self.assertIn("django action workflow", prompt.lower())
        self.assertIn("do not claim that an action has already been executed", prompt.lower())

    def test_prompt_generation_does_not_require_llm_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            prompt = build_sales_analysis_system_prompt()

        self.assertTrue(prompt.strip())
        self.assertNotIn("OPENAI", prompt.upper())
        self.assertNotIn("ANTHROPIC", prompt.upper())

    def test_messages_scaffold_for_shared_llm_abstraction(self) -> None:
        messages = build_sales_analysis_messages(
            output_language="en",
            user_context='{"store_id": "example", "products": []}',
        )

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("Priority 1", messages[0]["content"])
        self.assertEqual(
            messages[1]["content"],
            '{"store_id": "example", "products": []}',
        )

    def test_default_output_language_is_persian(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            prompt = build_sales_analysis_system_prompt()

        self.assertIn("Persian (fa)", prompt)

    def test_english_output_language_instruction(self) -> None:
        prompt = build_sales_analysis_system_prompt(output_language="en")

        self.assertIn("English (en)", prompt)

    def test_no_direct_database_or_execution_instructions(self) -> None:
        prompt = build_sales_analysis_system_prompt(output_language="en")

        self.assertIn("do not access the database directly", prompt.lower())
        self.assertIn("do not execute actions", prompt.lower())
        self.assertIn("do not change prices", prompt.lower())
        self.assertIn("post to social media", prompt.lower())


if __name__ == "__main__":
    unittest.main()
