"""Defensive brand voice extraction from tenant/store settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

DEFAULT_BRAND_VOICE_TONE = "friendly, clear, professional"
DEFAULT_BRAND_VOICE_AUDIENCE = "online shoppers"
DEFAULT_BRAND_VOICE_STYLE_NOTES = (
    "keep claims factual and concise; avoid exaggerated marketing language"
)


@dataclass(frozen=True, slots=True)
class BrandVoice:
    """Normalized brand voice values for Content Agent prompts."""

    tone: str
    audience: str
    style_notes: str
    language: str | None
    is_fallback: bool

    def as_prompt_lines(self) -> list[str]:
        """Return manager-facing brand voice lines for prompt injection."""
        lines = [
            f"- Tone: {self.tone}",
            f"- Target audience: {self.audience}",
            f"- Style notes: {self.style_notes}",
        ]
        if self.language:
            lines.append(f"- Preferred brand language hint: {self.language}")
        if self.is_fallback:
            lines.append(
                "- Brand voice source: generic fallback (no brand_voice in store settings)"
            )
        else:
            lines.append("- Brand voice source: store settings")
        return lines


def _coerce_non_empty_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _extract_brand_voice_mapping(settings: Any) -> Mapping[str, Any] | None:
    if not isinstance(settings, Mapping):
        return None

    brand_voice = settings.get("brand_voice")
    if isinstance(brand_voice, Mapping):
        return brand_voice

    return None


def extract_brand_voice(settings: Mapping[str, Any] | None) -> BrandVoice:
    """Extract brand voice from ``store.settings`` with a deterministic fallback.

    Tolerates missing keys, ``None``, malformed settings, and non-dict values.
    Never raises for bad input.
    """
    brand_voice = _extract_brand_voice_mapping(settings)

    if brand_voice is None:
        return BrandVoice(
            tone=DEFAULT_BRAND_VOICE_TONE,
            audience=DEFAULT_BRAND_VOICE_AUDIENCE,
            style_notes=DEFAULT_BRAND_VOICE_STYLE_NOTES,
            language=None,
            is_fallback=True,
        )

    tone = _coerce_non_empty_string(brand_voice.get("tone")) or DEFAULT_BRAND_VOICE_TONE
    audience = (
        _coerce_non_empty_string(brand_voice.get("audience"))
        or DEFAULT_BRAND_VOICE_AUDIENCE
    )
    style_notes = (
        _coerce_non_empty_string(brand_voice.get("style_notes"))
        or DEFAULT_BRAND_VOICE_STYLE_NOTES
    )
    language = _coerce_non_empty_string(brand_voice.get("language"))

    has_any_configured_value = any(
        _coerce_non_empty_string(brand_voice.get(key)) is not None
        for key in ("tone", "audience", "style_notes", "language")
    )

    return BrandVoice(
        tone=tone,
        audience=audience,
        style_notes=style_notes,
        language=language,
        is_fallback=not has_any_configured_value,
    )
