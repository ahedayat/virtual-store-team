"""AI output language helpers for agent prompt construction."""

from __future__ import annotations

import os
import re

DEFAULT_OUTPUT_LANGUAGE = "fa"
SUPPORTED_OUTPUT_LANGUAGES = frozenset({"fa", "en"})

_ENV_VAR_NAME = "AI_OUTPUT_LANGUAGE"

_LANGUAGE_ALIASES: dict[str, str] = {
    "fa": "fa",
    "fa-ir": "fa",
    "persian": "fa",
    "farsi": "fa",
    "en": "en",
    "en-us": "en",
    "english": "en",
}

_LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "fa": (
        "Generate all user-facing AI output in Persian (fa). "
        "Use clear, natural Persian unless a schema field explicitly requires another language."
    ),
    "en": (
        "Generate all user-facing AI output in English (en). "
        "Use clear, natural English unless a schema field explicitly requires another language."
    ),
}


def _is_blank(value: str | None) -> bool:
    return value is None or not str(value).strip()


def normalize_output_language(value: str | None) -> str:
    """Normalize a language code or alias to a supported output language.

    Missing, empty, or whitespace-only values default to ``fa``.
    Unsupported values raise ``ValueError``.
    """
    if _is_blank(value):
        return DEFAULT_OUTPUT_LANGUAGE

    normalized_key = re.sub(r"\s+", "", str(value).strip().lower())
    canonical = _LANGUAGE_ALIASES.get(normalized_key)
    if canonical is None:
        supported = ", ".join(sorted(SUPPORTED_OUTPUT_LANGUAGES))
        raise ValueError(
            f"Unsupported AI output language: {value!r}. Supported languages: {supported}."
        )
    return canonical


def get_output_language() -> str:
    """Read ``AI_OUTPUT_LANGUAGE`` from the environment.

    Missing, empty, or whitespace values default to ``fa``.
    Unsupported environment values fall back to ``fa`` so a typo does not
    break agent startup; use ``normalize_output_language`` when explicit
    validation is required.
    """
    raw_value = os.environ.get(_ENV_VAR_NAME)
    if _is_blank(raw_value):
        return DEFAULT_OUTPUT_LANGUAGE

    try:
        return normalize_output_language(raw_value)
    except ValueError:
        return DEFAULT_OUTPUT_LANGUAGE


def get_language_instruction(language: str | None = None) -> str:
    """Return a stable system-prompt instruction for the given language."""
    canonical = (
        get_output_language()
        if language is None
        else normalize_output_language(language)
    )
    return _LANGUAGE_INSTRUCTIONS[canonical]


def build_language_prompt_prefix(language: str | None = None) -> str:
    """Return a reusable language directive suitable for prepending to prompts."""
    return get_language_instruction(language)
