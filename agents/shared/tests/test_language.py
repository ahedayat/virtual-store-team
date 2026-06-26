import os
import unittest
from unittest.mock import patch

from agents.shared.language import (
    DEFAULT_OUTPUT_LANGUAGE,
    build_language_prompt_prefix,
    get_language_instruction,
    get_output_language,
    normalize_output_language,
)


class NormalizeOutputLanguageTests(unittest.TestCase):
    def test_missing_value_defaults_to_fa(self):
        self.assertEqual(normalize_output_language(None), "fa")

    def test_empty_string_defaults_to_fa(self):
        self.assertEqual(normalize_output_language(""), "fa")
        self.assertEqual(normalize_output_language("   "), "fa")

    def test_fa_returns_persian_canonical_code(self):
        self.assertEqual(normalize_output_language("fa"), "fa")

    def test_en_returns_english_canonical_code(self):
        self.assertEqual(normalize_output_language("en"), "en")

    def test_aliases_normalize_to_fa(self):
        for alias in ("fa-IR", "Persian", "FARSI"):
            with self.subTest(alias=alias):
                self.assertEqual(normalize_output_language(alias), "fa")

    def test_aliases_normalize_to_en(self):
        for alias in ("en-US", "English", "EN"):
            with self.subTest(alias=alias):
                self.assertEqual(normalize_output_language(alias), "en")

    def test_unsupported_value_raises_value_error(self):
        with self.assertRaises(ValueError) as context:
            normalize_output_language("de")

        self.assertIn("Unsupported AI output language", str(context.exception))
        self.assertIn("de", str(context.exception))


class GetOutputLanguageTests(unittest.TestCase):
    def test_reads_ai_output_language_from_environment(self):
        with patch.dict(os.environ, {"AI_OUTPUT_LANGUAGE": "en"}, clear=False):
            self.assertEqual(get_output_language(), "en")

    def test_missing_env_defaults_to_fa(self):
        env = os.environ.copy()
        env.pop("AI_OUTPUT_LANGUAGE", None)
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(get_output_language(), DEFAULT_OUTPUT_LANGUAGE)

    def test_empty_env_defaults_to_fa(self):
        with patch.dict(os.environ, {"AI_OUTPUT_LANGUAGE": ""}, clear=False):
            self.assertEqual(get_output_language(), DEFAULT_OUTPUT_LANGUAGE)

    def test_unsupported_env_value_falls_back_to_fa(self):
        with patch.dict(os.environ, {"AI_OUTPUT_LANGUAGE": "de"}, clear=False):
            self.assertEqual(get_output_language(), DEFAULT_OUTPUT_LANGUAGE)


class GetLanguageInstructionTests(unittest.TestCase):
    def test_fa_returns_persian_instruction(self):
        instruction = get_language_instruction("fa")
        self.assertIn("Persian (fa)", instruction)
        self.assertIn("user-facing AI output", instruction)
        self.assertIn("schema field", instruction)

    def test_en_returns_english_instruction(self):
        instruction = get_language_instruction("en")
        self.assertIn("English (en)", instruction)
        self.assertIn("user-facing AI output", instruction)
        self.assertIn("schema field", instruction)

    def test_default_uses_environment(self):
        with patch.dict(os.environ, {"AI_OUTPUT_LANGUAGE": "en"}, clear=False):
            instruction = get_language_instruction()
        self.assertIn("English (en)", instruction)

    def test_instruction_text_is_stable(self):
        first = get_language_instruction("fa")
        second = get_language_instruction("fa")
        self.assertEqual(first, second)

    def test_build_language_prompt_prefix_matches_instruction(self):
        self.assertEqual(
            build_language_prompt_prefix("en"),
            get_language_instruction("en"),
        )


if __name__ == "__main__":
    unittest.main()
