"""Unit tests for Content Agent prompt templates and brand voice (Step 8.1)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agents.content.brand_voice import (
    DEFAULT_BRAND_VOICE_AUDIENCE,
    DEFAULT_BRAND_VOICE_STYLE_NOTES,
    DEFAULT_BRAND_VOICE_TONE,
    extract_brand_voice,
)
from agents.content.prompts import (
    ALLOWED_CONTENT_ACTION_TYPES,
    DRAFT_REQUIRED_FIELDS,
    build_content_draft_messages,
    build_content_draft_system_prompt,
)


class BrandVoiceExtractionTests(unittest.TestCase):
    def test_extracts_configured_brand_voice_values(self) -> None:
        settings = {
            "brand_voice": {
                "tone": "luxury, warm, concise",
                "audience": "modern customers",
                "style_notes": "avoid exaggerated claims; use elegant wording",
                "language": "fa",
            }
        }
        brand_voice = extract_brand_voice(settings)

        self.assertEqual(brand_voice.tone, "luxury, warm, concise")
        self.assertEqual(brand_voice.audience, "modern customers")
        self.assertEqual(brand_voice.style_notes, "avoid exaggerated claims; use elegant wording")
        self.assertEqual(brand_voice.language, "fa")
        self.assertFalse(brand_voice.is_fallback)

    def test_fallback_when_brand_voice_missing(self) -> None:
        brand_voice = extract_brand_voice(None)

        self.assertTrue(brand_voice.is_fallback)
        self.assertEqual(brand_voice.tone, DEFAULT_BRAND_VOICE_TONE)
        self.assertEqual(brand_voice.audience, DEFAULT_BRAND_VOICE_AUDIENCE)
        self.assertEqual(brand_voice.style_notes, DEFAULT_BRAND_VOICE_STYLE_NOTES)
        self.assertIsNone(brand_voice.language)

    def test_tolerates_malformed_settings_without_crashing(self) -> None:
        for bad_settings in ("not-a-dict", 42, [], {"brand_voice": "invalid"}):
            with self.subTest(bad_settings=bad_settings):
                brand_voice = extract_brand_voice(bad_settings)  # type: ignore[arg-type]
                self.assertTrue(brand_voice.is_fallback)

    def test_partial_brand_voice_uses_defaults_for_missing_fields(self) -> None:
        brand_voice = extract_brand_voice({"brand_voice": {"tone": "playful"}})

        self.assertEqual(brand_voice.tone, "playful")
        self.assertEqual(brand_voice.audience, DEFAULT_BRAND_VOICE_AUDIENCE)
        self.assertFalse(brand_voice.is_fallback)


class ContentDraftPromptTests(unittest.TestCase):
    def test_prompt_includes_configured_brand_voice(self) -> None:
        prompt = build_content_draft_system_prompt(
            store_settings={
                "brand_voice": {
                    "tone": "luxury, warm, concise",
                    "audience": "modern customers",
                    "style_notes": "avoid exaggerated claims; use elegant wording",
                    "language": "fa",
                }
            },
            output_language="en",
        )

        self.assertIn("luxury, warm, concise", prompt)
        self.assertIn("modern customers", prompt)
        self.assertIn("avoid exaggerated claims; use elegant wording", prompt)
        self.assertIn("Preferred brand language hint: fa", prompt)
        self.assertIn("Brand voice source: store settings", prompt)

    def test_prompt_falls_back_when_brand_voice_missing(self) -> None:
        prompt = build_content_draft_system_prompt(output_language="en")

        self.assertIn(DEFAULT_BRAND_VOICE_TONE, prompt)
        self.assertIn(DEFAULT_BRAND_VOICE_AUDIENCE, prompt)
        self.assertIn(DEFAULT_BRAND_VOICE_STYLE_NOTES, prompt)
        self.assertIn("generic fallback", prompt.lower())

    def test_prompt_respects_english_output_language(self) -> None:
        prompt = build_content_draft_system_prompt(output_language="en")

        self.assertIn("English (en)", prompt)

    def test_default_output_language_is_persian(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            prompt = build_content_draft_system_prompt()

        self.assertIn("Persian (fa)", prompt)

    def test_prompt_does_not_hardcode_prestia(self) -> None:
        prompt = build_content_draft_system_prompt(output_language="en")

        self.assertNotIn("Prestia", prompt)
        self.assertNotIn("prestia", prompt.lower())

    def test_store_display_name_only_when_provided_in_input(self) -> None:
        generic_prompt = build_content_draft_system_prompt(output_language="en")
        named_prompt = build_content_draft_system_prompt(
            store_display_name="Prestia",
            output_language="en",
        )

        self.assertNotIn("Prestia", generic_prompt)
        self.assertIn("Store display name: Prestia", named_prompt)

    def test_guardrails_against_unsupported_claims_and_publishing(self) -> None:
        prompt = build_content_draft_system_prompt(output_language="en")

        self.assertIn("do not publish", prompt.lower())
        self.assertIn("do not claim discounts", prompt.lower())
        self.assertIn("do not claim scarcity", prompt.lower())
        self.assertIn("do not invent refunds", prompt.lower())
        self.assertIn("phone numbers", prompt.lower())
        self.assertIn("customer names", prompt.lower())
        self.assertIn("manager approval", prompt.lower())

    def test_allowed_content_action_types_are_present(self) -> None:
        prompt = build_content_draft_system_prompt(output_language="en")

        for action_type in ALLOWED_CONTENT_ACTION_TYPES:
            with self.subTest(action_type=action_type):
                self.assertIn(action_type, prompt)

    def test_required_draft_fields_are_present(self) -> None:
        prompt = build_content_draft_system_prompt(output_language="en")

        for field_name in DRAFT_REQUIRED_FIELDS:
            with self.subTest(field_name=field_name):
                self.assertIn(field_name, prompt)

    def test_campaign_angle_section_when_provided(self) -> None:
        prompt = build_content_draft_system_prompt(
            campaign_angle="Summer collection launch",
            output_language="en",
        )

        self.assertIn("Summer collection launch", prompt)

    def test_messages_scaffold_for_shared_llm_abstraction(self) -> None:
        messages = build_content_draft_messages(
            store_context={
                "id": "store-1",
                "name": "Demo Store",
                "currency": "USD",
                "settings": {
                    "brand_voice": {
                        "tone": "warm",
                        "audience": "shoppers",
                        "style_notes": "concise",
                    }
                },
            },
            products=[{"product_id": "p-1", "name": "Tote Bag"}],
            campaign_angle="New arrivals",
            output_language="en",
        )

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("warm", messages[0]["content"])
        self.assertIn("Demo Store", messages[0]["content"])
        self.assertIn("Tote Bag", messages[1]["content"])
        self.assertIn("New arrivals", messages[1]["content"])

    def test_prompt_generation_does_not_require_llm_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            prompt = build_content_draft_system_prompt()

        self.assertTrue(prompt.strip())
        self.assertNotIn("OPENAI", prompt.upper())
        self.assertNotIn("ANTHROPIC", prompt.upper())


if __name__ == "__main__":
    unittest.main()
