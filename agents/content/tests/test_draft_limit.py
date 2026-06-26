"""Unit tests for Content Agent draft limit resolution and enforcement (Step 8.2)."""

from __future__ import annotations

import os
import unittest
from typing import Any
from unittest.mock import patch

from agents.content.analysis import (
    apply_content_draft_limit,
    normalize_content_agent_output,
)
from agents.content.draft_limit import (
    DEFAULT_MAX_DRAFTS_PER_RUN,
    HARD_MAX_DRAFTS_PER_RUN,
    limit_content_suggestions,
    resolve_max_drafts_per_run,
)
from agents.content.prompts import build_content_draft_messages, build_content_draft_system_prompt


def _build_draft(action_type: str, index: int) -> dict[str, str]:
    return {
        "action_type": action_type,
        "title": f"Draft {index}",
        "description": f"Description {index}",
        "draft_text": f"Body {index}",
        "product_id": f"product-{index}",
        "rationale": f"Rationale {index}",
    }


def _build_content_result(draft_count: int) -> dict[str, Any]:
    drafts = [
        _build_draft(
            "content.instagram_draft" if index % 2 == 0 else "content.product_description",
            index,
        )
        for index in range(1, draft_count + 1)
    ]
    return {
        "metadata": {"agent_name": "content-agent", "report_run_id": "run-1"},
        "summary": "Generated reviewable drafts.",
        "drafts": drafts,
        "warnings": [],
    }


class ResolveMaxDraftsPerRunTests(unittest.TestCase):
    def test_default_limit_is_three_when_no_setting_exists(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            resolved = resolve_max_drafts_per_run()

        self.assertEqual(resolved, DEFAULT_MAX_DRAFTS_PER_RUN)
        self.assertEqual(resolved, 3)

    def test_store_setting_can_change_the_limit(self) -> None:
        settings = {"content_agent": {"max_drafts_per_run": 2}}
        self.assertEqual(resolve_max_drafts_per_run(store_settings=settings), 2)

    def test_request_override_takes_precedence_over_store_setting(self) -> None:
        settings = {"content_agent": {"max_drafts_per_run": 2}}
        self.assertEqual(
            resolve_max_drafts_per_run(request_max_drafts=4, store_settings=settings),
            4,
        )

    def test_invalid_store_setting_falls_back_safely(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            for bad_settings in (
                {"content_agent": {"max_drafts_per_run": "bad"}},
                {"content_agent": "invalid"},
                {"content_agent": {"max_drafts_per_run": None}},
            ):
                with self.subTest(bad_settings=bad_settings):
                    self.assertEqual(
                        resolve_max_drafts_per_run(store_settings=bad_settings),
                        DEFAULT_MAX_DRAFTS_PER_RUN,
                    )

    def test_invalid_request_value_falls_through_to_store_setting(self) -> None:
        settings = {"content_agent": {"max_drafts_per_run": 2}}
        self.assertEqual(
            resolve_max_drafts_per_run(request_max_drafts="bad", store_settings=settings),
            2,
        )

    def test_value_below_one_clamps_to_one(self) -> None:
        self.assertEqual(resolve_max_drafts_per_run(request_max_drafts=0), 1)
        self.assertEqual(resolve_max_drafts_per_run(request_max_drafts=-3), 1)

    def test_value_above_hard_maximum_clamps_to_five(self) -> None:
        self.assertEqual(resolve_max_drafts_per_run(request_max_drafts=99), HARD_MAX_DRAFTS_PER_RUN)
        self.assertEqual(resolve_max_drafts_per_run(request_max_drafts=6), 5)

    def test_environment_setting_is_used_when_store_setting_missing(self) -> None:
        with patch.dict(os.environ, {"CONTENT_AGENT_MAX_DRAFTS_PER_RUN": "4"}, clear=True):
            self.assertEqual(resolve_max_drafts_per_run(), 4)

    def test_request_override_takes_precedence_over_environment(self) -> None:
        with patch.dict(os.environ, {"CONTENT_AGENT_MAX_DRAFTS_PER_RUN": "4"}, clear=True):
            self.assertEqual(resolve_max_drafts_per_run(request_max_drafts=2), 2)


class LimitContentSuggestionsTests(unittest.TestCase):
    def test_trims_output_to_resolved_max(self) -> None:
        result = _build_content_result(6)
        limited = limit_content_suggestions(result, 3)

        self.assertEqual(len(limited["drafts"]), 3)
        self.assertEqual(limited["drafts"][0]["title"], "Draft 1")
        self.assertEqual(limited["drafts"][2]["title"], "Draft 3")
        self.assertEqual(limited["summary"], "Generated reviewable drafts.")

    def test_preserves_non_draft_fields(self) -> None:
        result = _build_content_result(4)
        limited = apply_content_draft_limit(result, request_max_drafts=2)

        self.assertEqual(len(limited["drafts"]), 2)
        self.assertEqual(limited["metadata"]["agent_name"], "content-agent")

    def test_leaves_result_unchanged_when_drafts_missing(self) -> None:
        result = {"summary": "No drafts yet."}
        limited = limit_content_suggestions(result, 3)

        self.assertEqual(limited, result)

    def test_normalize_content_agent_output_trims_mock_llm_payload(self) -> None:
        raw = _build_content_result(5)
        normalized = normalize_content_agent_output(
            raw,
            request_max_drafts=2,
        )

        self.assertEqual(len(normalized.drafts), 2)

    def test_draft_action_types_remain_approval_compatible(self) -> None:
        normalized = normalize_content_agent_output(_build_content_result(4), request_max_drafts=2)

        for draft in normalized.drafts:
            self.assertIn(
                draft.action_type,
                ("content.instagram_draft", "content.product_description"),
            )
            self.assertTrue(draft.draft_text)


class ContentDraftPromptLimitTests(unittest.TestCase):
    def test_prompt_includes_resolved_max_draft_count(self) -> None:
        prompt = build_content_draft_system_prompt(
            store_settings={"content_agent": {"max_drafts_per_run": 2}},
            output_language="en",
        )

        self.assertIn("at most 2 draft suggestion(s)", prompt)
        self.assertIn("no more than 2 draft object(s)", prompt)

    def test_messages_use_request_level_max_override_in_prompt(self) -> None:
        messages = build_content_draft_messages(
            store_context={
                "settings": {"content_agent": {"max_drafts_per_run": 5}},
            },
            max_drafts_per_run=2,
            output_language="en",
        )

        self.assertIn("at most 2 draft suggestion(s)", messages[0]["content"])

    def test_prompt_generation_does_not_require_llm_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            prompt = build_content_draft_system_prompt()

        self.assertIn(f"at most {DEFAULT_MAX_DRAFTS_PER_RUN} draft suggestion(s)", prompt)


if __name__ == "__main__":
    unittest.main()
