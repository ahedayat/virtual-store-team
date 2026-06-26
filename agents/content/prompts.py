"""Content Agent prompt templates for reviewable Instagram and product copy drafts."""

from __future__ import annotations

import json
from typing import Any, Mapping

from agents.content.brand_voice import BrandVoice, extract_brand_voice
from agents.shared.language import build_language_prompt_prefix

ALLOWED_CONTENT_ACTION_TYPES: tuple[str, ...] = (
    "content.instagram_draft",
    "content.product_description",
)

DRAFT_REQUIRED_FIELDS: tuple[str, ...] = (
    "action_type",
    "title",
    "description",
    "draft_text",
    "product_id",
    "rationale",
)


def _role_and_scope_section() -> str:
    return "\n".join(
        [
            "You are the Content Agent for a multi-tenant virtual store management platform.",
            "Your role is limited to drafting Instagram-oriented captions and product description copy.",
            "Produce reviewable drafts for store managers; do not publish or send content.",
            "Do not reply to customers, change prices, or execute actions directly.",
            "Stay tenant-agnostic: use only the sanitized store and product context supplied in the request.",
            "Every draft requires manager approval before any external use.",
        ]
    )


def _brand_voice_section(brand_voice: BrandVoice) -> str:
    lines = [
        "Brand voice (from store settings):",
        *brand_voice.as_prompt_lines(),
        "",
        "Apply this brand voice to captions and product descriptions unless it conflicts",
        "with factual product data or safety rules below.",
    ]
    return "\n".join(lines)


def _data_access_section() -> str:
    return "\n".join(
        [
            "Data access rules:",
            "- Use only sanitized data received from Django internal APIs.",
            "- Do not access the database directly.",
            "- Do not invent product attributes, prices, discounts, stock levels, or policies.",
            "- Do not claim that content has been published or that an action was executed.",
            "- Propose drafts only; Django owns action creation and the approval workflow.",
        ]
    )


def _campaign_angle_section(campaign_angle: str | None) -> str:
    if not campaign_angle:
        return "\n".join(
            [
                "Campaign angle:",
                "- No specific campaign angle was provided.",
                "- Write evergreen, product-focused drafts suitable for Instagram and product pages.",
            ]
        )

    return "\n".join(
        [
            "Campaign angle:",
            f"- Incorporate this campaign angle when relevant: {campaign_angle}",
            "- Keep the angle aligned with verified product and store facts.",
            "- Do not invent promotions, deadlines, or offers not supported by the context.",
        ]
    )


def _draft_output_section() -> str:
    allowed = ", ".join(ALLOWED_CONTENT_ACTION_TYPES)
    fields = ", ".join(DRAFT_REQUIRED_FIELDS)
    return "\n".join(
        [
            "Draft output contract:",
            "- Produce concise, manager-friendly drafts intended for human review and approval.",
            "- Map each draft to one of these action_type values:",
            f"  - {ALLOWED_CONTENT_ACTION_TYPES[0]} — Instagram caption or post draft.",
            f"  - {ALLOWED_CONTENT_ACTION_TYPES[1]} — product description copy draft.",
            f"- Allowed action_type set: {allowed}.",
            "",
            "Each draft object should include:",
            "- action_type: one of the allowed content action types.",
            "- title: short manager-facing headline for the draft.",
            "- description: brief summary of what the draft is for.",
            "- draft_text: the reviewable caption or product description body.",
            "- product_id: the product UUID from the supplied context when applicable.",
            "- rationale: non-PII note on why this draft fits the product or campaign angle.",
            "",
            f"Required field names: {fields}.",
            "Return drafts inside the structured output envelope expected by the Content Agent pipeline.",
        ]
    )


def _safety_and_guardrails_section() -> str:
    return "\n".join(
        [
            "Safety, PII, and claim guardrails:",
            "- Do not publish, post, send, schedule, or upload content to Instagram or any external channel.",
            "- Do not include phone numbers, emails, physical addresses, customer names, or payment details.",
            "- Do not reference customer-specific conversations, orders, or identities.",
            "- Do not claim discounts, promotions, or sale prices unless explicit discount data is in the context.",
            "- Do not claim scarcity, low stock, or urgency unless inventory data in the context supports it.",
            "- Do not invent refunds, warranties, delivery timelines, or store policies unless provided in context.",
            "- Do not invent product materials, dimensions, colors, or features absent from product metadata.",
            "- Keep drafts factual, reviewable, and ready for manager approval before any external use.",
        ]
    )


def _store_context_section(
    *,
    store_display_name: str | None,
    currency: str | None,
) -> str:
    lines = ["Store context:"]
    if store_display_name:
        lines.append(f"- Store display name: {store_display_name}")
    else:
        lines.append("- Store display name: not provided; keep copy generic to the supplied products.")
    if currency:
        lines.append(f"- Currency for prices in copy: {currency}")
    return "\n".join(lines)


def build_content_draft_system_prompt(
    *,
    store_settings: Mapping[str, Any] | None = None,
    store_display_name: str | None = None,
    currency: str | None = None,
    campaign_angle: str | None = None,
    output_language: str | None = None,
) -> str:
    """Build the system prompt for Instagram and product description draft generation."""
    brand_voice = extract_brand_voice(store_settings)
    language_instruction = build_language_prompt_prefix(output_language)

    sections = [
        _role_and_scope_section(),
        language_instruction,
        _store_context_section(
            store_display_name=store_display_name,
            currency=currency,
        ),
        _brand_voice_section(brand_voice),
        _data_access_section(),
        _campaign_angle_section(campaign_angle),
        _draft_output_section(),
        _safety_and_guardrails_section(),
    ]
    return "\n\n".join(sections)


def _serialize_content_context(context: Mapping[str, Any]) -> str:
    return json.dumps(context, default=str, ensure_ascii=False)


def build_content_draft_messages(
    *,
    store_context: Mapping[str, Any] | None = None,
    products: list[Mapping[str, Any]] | None = None,
    campaign_angle: str | None = None,
    output_language: str | None = None,
) -> list[dict[str, str]]:
    """Build chat messages for the shared LLM abstraction (no provider calls)."""
    store_context = store_context or {}
    store_settings = store_context.get("settings")
    if store_settings is not None and not isinstance(store_settings, Mapping):
        store_settings = None

    store_display_name = store_context.get("display_name") or store_context.get("name")
    if store_display_name is not None and not isinstance(store_display_name, str):
        store_display_name = None

    currency = store_context.get("currency")
    if currency is not None and not isinstance(currency, str):
        currency = None

    system_prompt = build_content_draft_system_prompt(
        store_settings=store_settings,
        store_display_name=store_display_name,
        currency=currency,
        campaign_angle=campaign_angle,
        output_language=output_language,
    )

    user_payload: dict[str, Any] = {
        "store": {
            key: store_context[key]
            for key in ("id", "slug", "name", "display_name", "currency", "timezone")
            if key in store_context
        },
        "products": list(products or []),
    }
    if campaign_angle:
        user_payload["campaign_angle"] = campaign_angle

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _serialize_content_context(user_payload)},
    ]
