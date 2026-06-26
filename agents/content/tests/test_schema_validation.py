"""Unit tests for Content Agent schema validation (Step 8.3)."""

from __future__ import annotations

import json
import unittest
from typing import Any

from agents.content.analysis import normalize_content_agent_output
from agents.content.validation import (
    ContentLLMOutputError,
    ensure_valid_content_suggestions,
    parse_llm_json_output,
    validate_content_suggestions_output,
)
from agents.shared.schemas import AgentSchemaValidationError, ContentSuggestions


def build_instagram_draft(**overrides: object) -> dict[str, Any]:
    draft: dict[str, Any] = {
        "action_type": "content.instagram_draft",
        "title": "Summer caption",
        "description": "Instagram caption draft for seasonal promo.",
        "draft_text": "کاپشن نمونه برای اینستاگرام — مناسب فصل تابستان.",
        "product_id": "00000000-0000-4000-8000-000000000001",
        "rationale": "Seasonal campaign angle fits the featured product.",
        "requires_approval": True,
    }
    draft.update(overrides)
    return draft


def build_product_description_draft(**overrides: object) -> dict[str, Any]:
    draft: dict[str, Any] = {
        "action_type": "content.product_description",
        "title": "Product page copy",
        "description": "Short description for the product detail page.",
        "draft_text": "A durable everyday tote with a clean, modern silhouette.",
        "product_id": "00000000-0000-4000-8000-000000000002",
        "rationale": "Product metadata supports factual feature-led copy.",
        "requires_approval": True,
    }
    draft.update(overrides)
    return draft


def build_valid_content_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "metadata": {
            "agent_name": "content-agent",
            "report_run_id": "run-valid-1",
        },
        "summary": "Generated reviewable content drafts.",
        "drafts": [build_instagram_draft()],
        "warnings": [],
        "output_language": "fa",
    }
    payload.update(overrides)
    return payload


class ContentSchemaValidationTests(unittest.TestCase):
    def test_valid_instagram_draft_passes_validation(self) -> None:
        payload = build_valid_content_payload()

        validated = validate_content_suggestions_output(payload)

        self.assertIsInstance(validated, ContentSuggestions)
        self.assertEqual(validated.drafts[0].action_type, "content.instagram_draft")
        self.assertTrue(validated.drafts[0].requires_approval)

    def test_valid_product_description_draft_passes_validation(self) -> None:
        payload = build_valid_content_payload(
            drafts=[build_product_description_draft()],
        )

        validated = validate_content_suggestions_output(payload)

        self.assertEqual(validated.drafts[0].action_type, "content.product_description")
        self.assertEqual(
            validated.drafts[0].product_id,
            "00000000-0000-4000-8000-000000000002",
        )

    def test_multiple_valid_suggestions_pass_validation(self) -> None:
        payload = build_valid_content_payload(
            drafts=[
                build_instagram_draft(title="Caption A"),
                build_product_description_draft(title="Description B"),
            ],
        )

        validated = validate_content_suggestions_output(payload)

        self.assertEqual(len(validated.drafts), 2)

    def test_persian_output_is_accepted(self) -> None:
        payload = build_valid_content_payload(
            summary="پیشنهادهای محتوای قابل بررسی تولید شد.",
            output_language="fa",
            drafts=[
                build_instagram_draft(
                    draft_text="کیف چرم با دوام برای استفاده روزمره.",
                ),
            ],
        )

        validated = validate_content_suggestions_output(payload)

        self.assertEqual(validated.output_language, "fa")
        self.assertIn("چرم", validated.drafts[0].draft_text)

    def test_english_output_is_accepted_when_output_language_is_en(self) -> None:
        payload = build_valid_content_payload(
            summary="Reviewable English content drafts were generated.",
            output_language="en",
            drafts=[
                build_instagram_draft(
                    draft_text="Everyday leather tote with a clean modern silhouette.",
                ),
            ],
        )

        validated = validate_content_suggestions_output(payload)

        self.assertEqual(validated.output_language, "en")
        self.assertIn("leather", validated.drafts[0].draft_text)

    def test_unsupported_action_type_fails_validation(self) -> None:
        payload = build_valid_content_payload(
            drafts=[build_instagram_draft(action_type="content.publish_instagram")],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_content_suggestions_output(payload)

        self.assertTrue(
            any("action_type" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_missing_draft_text_fails_validation(self) -> None:
        payload = build_valid_content_payload(
            drafts=[build_instagram_draft(draft_text="")],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_content_suggestions_output(payload)

        self.assertTrue(
            any("draft_text" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_missing_product_id_for_product_description_fails_validation(self) -> None:
        payload = build_valid_content_payload(
            drafts=[build_product_description_draft(product_id=None)],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_content_suggestions_output(payload)

        error_fields = " ".join(item["field"] for item in ctx.exception.field_errors)
        self.assertTrue("product_id" in error_fields or "drafts" in error_fields)

    def test_malformed_payload_extra_fields_are_rejected(self) -> None:
        payload = build_valid_content_payload(extra_field="forbidden")

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_content_suggestions_output(payload)

        self.assertTrue(
            any(item["field"] == "extra_field" for item in ctx.exception.field_errors)
        )

    def test_non_list_drafts_container_fails_validation(self) -> None:
        payload = build_valid_content_payload(drafts="not-a-list")

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_content_suggestions_output(payload)

        self.assertTrue(
            any("drafts" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_invalid_priority_fails_validation(self) -> None:
        payload = build_valid_content_payload(
            drafts=[build_instagram_draft(priority=0)],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_content_suggestions_output(payload)

        self.assertTrue(
            any("priority" in item["field"] for item in ctx.exception.field_errors)
        )

    def test_requires_approval_false_fails_validation(self) -> None:
        payload = build_valid_content_payload(
            drafts=[build_instagram_draft(requires_approval=False)],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_content_suggestions_output(payload)

        error_text = str(ctx.exception).lower()
        self.assertTrue(
            "requires_approval" in error_text or "approval" in error_text
        )

    def test_extra_unknown_fields_on_draft_are_rejected(self) -> None:
        payload = build_valid_content_payload(
            drafts=[build_instagram_draft(unexpected_field="forbidden")],
        )

        with self.assertRaises(AgentSchemaValidationError) as ctx:
            validate_content_suggestions_output(payload)

        self.assertTrue(
            any("unexpected_field" in item["field"] for item in ctx.exception.field_errors)
        )


class ContentDraftLimitWithValidationTests(unittest.TestCase):
    def test_draft_limit_is_enforced_after_schema_validation(self) -> None:
        drafts = [
            build_instagram_draft(title=f"Caption {index}")
            for index in range(1, 6)
        ]
        raw = build_valid_content_payload(drafts=drafts)

        validated = normalize_content_agent_output(raw, request_max_drafts=2)

        self.assertIsInstance(validated, ContentSuggestions)
        self.assertEqual(len(validated.drafts), 2)
        self.assertEqual(validated.drafts[0].title, "Caption 1")
        self.assertEqual(validated.drafts[1].title, "Caption 2")

    def test_trimmed_output_still_requires_approval(self) -> None:
        drafts = [
            build_product_description_draft(title=f"Description {index}")
            for index in range(1, 4)
        ]
        raw = build_valid_content_payload(drafts=drafts)

        validated = normalize_content_agent_output(raw, request_max_drafts=1)

        self.assertEqual(len(validated.drafts), 1)
        self.assertTrue(validated.drafts[0].requires_approval)


class ContentLLMParsingTests(unittest.TestCase):
    def test_valid_json_response_parses_into_schema(self) -> None:
        payload = build_valid_content_payload()

        parsed = parse_llm_json_output(json.dumps(payload))
        validated = ensure_valid_content_suggestions(parsed)

        self.assertEqual(validated.summary, payload["summary"])

    def test_invalid_json_is_handled_deterministically(self) -> None:
        with self.assertRaises(ContentLLMOutputError) as ctx:
            parse_llm_json_output("{not valid json")

        self.assertIn("malformed JSON", str(ctx.exception))

    def test_mock_provider_dict_output_uses_same_validation_path(self) -> None:
        payload = build_valid_content_payload()

        parsed = parse_llm_json_output(payload)
        validated = ensure_valid_content_suggestions(parsed)

        self.assertEqual(validated.metadata.agent_name, "content-agent")

    def test_non_object_json_is_rejected(self) -> None:
        with self.assertRaises(ContentLLMOutputError):
            parse_llm_json_output('["not", "an", "object"]')

    def test_normalize_rejects_invalid_json_before_validation(self) -> None:
        with self.assertRaises(ContentLLMOutputError):
            normalize_content_agent_output("{not valid json")


if __name__ == "__main__":
    unittest.main()
