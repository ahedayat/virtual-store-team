from __future__ import annotations

import re
import uuid

EMAIL_REDACTED = "[EMAIL_REDACTED]"
PHONE_REDACTED = "[PHONE_REDACTED]"

_PERSIAN_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_ARABIC_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


class PiiSanitizer:
    """Minimal PII redaction for AI-facing message output."""

    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        re.IGNORECASE,
    )

    # Iranian mobile: 09xx, +98, 0098, optional separators
    IRANIAN_PHONE_PATTERN = re.compile(
        r"(?<!\d)(?:"
        r"(?:\+|00)?98[\s\-]*(?:0)?9[\s\-]*\d{2}[\s\-]*\d{3}[\s\-]*\d{4}"
        r"|"
        r"0?9[\s\-]*\d{2}[\s\-]*\d{3}[\s\-]*\d{4}"
        r")(?!\d)",
    )

    # International phone-like numbers (7-15 digits with optional + prefix)
    INTERNATIONAL_PHONE_PATTERN = re.compile(
        r"(?<!\w)(?:\+[\d\s\-\(\)]{7,20}|\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4})(?!\d)",
    )

    @classmethod
    def _normalize_digits(cls, text: str) -> str:
        return text.translate(_PERSIAN_DIGIT_TRANSLATION).translate(_ARABIC_DIGIT_TRANSLATION)

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        if not text:
            return text
        normalized = cls._normalize_digits(text)
        sanitized = cls.EMAIL_PATTERN.sub(EMAIL_REDACTED, normalized)
        sanitized = cls.IRANIAN_PHONE_PATTERN.sub(PHONE_REDACTED, sanitized)
        sanitized = cls.INTERNATIONAL_PHONE_PATTERN.sub(PHONE_REDACTED, sanitized)
        return sanitized

    @classmethod
    def customer_ref(cls, customer_id: uuid.UUID | str) -> str:
        return f"customer-{customer_id}"
