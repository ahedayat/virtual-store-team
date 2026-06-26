"""Deterministic empty-product handling for the Content Agent."""

from __future__ import annotations

from collections.abc import Mapping

from agents.content.product_context import CONTENT_AGENT_NAME, is_empty_products_context
from agents.shared.language import get_output_language, normalize_output_language
from agents.shared.schemas.base import AgentResponseMetadata
from agents.shared.schemas.content import ContentSuggestions

EMPTY_PRODUCTS_MESSAGES: dict[str, str] = {
    "fa": "محصولی برای تولید پیش‌نویس محتوا در دسترس نیست.",
    "en": "No products were available for content draft generation.",
}


def build_empty_products_result(
    *,
    report_run_id: str | None = None,
    output_language: str | None = None,
) -> ContentSuggestions:
    """Build a deterministic, schema-valid response when product context is empty."""
    language = (
        get_output_language()
        if output_language is None
        else normalize_output_language(output_language)
    )
    summary = EMPTY_PRODUCTS_MESSAGES[language]

    return ContentSuggestions(
        metadata=AgentResponseMetadata(
            agent_name=CONTENT_AGENT_NAME,
            report_run_id=report_run_id,
        ),
        summary=summary,
        drafts=[],
        warnings=[],
        output_language=language,
    )


def handle_empty_products(
    *,
    products: list[Mapping[str, object]] | None,
    report_run_id: str | None = None,
    output_language: str | None = None,
) -> ContentSuggestions | None:
    """Return a deterministic empty-products result when no products are available."""
    if not is_empty_products_context(products):
        return None
    return build_empty_products_result(
        report_run_id=report_run_id,
        output_language=output_language,
    )
