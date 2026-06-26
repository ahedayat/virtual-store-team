"""Deterministic mock LLM provider for tests and local development."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

_CONTENT_AGENT_MARKER = "Content Agent"
_SALES_AGENT_MARKER = "Sales Agent"
_PERSIAN_LANGUAGE_MARKER = "Persian (fa)"
_ENGLISH_LANGUAGE_MARKER = "English (en)"


def _detect_output_language(system_content: str) -> str:
    if _ENGLISH_LANGUAGE_MARKER in system_content:
        return "en"
    if _PERSIAN_LANGUAGE_MARKER in system_content:
        return "fa"
    return "fa"


def _parse_user_payload(user_content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(user_content)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed, Mapping):
        return dict(parsed)
    return {}


def _product_identifier(product: Mapping[str, Any]) -> str | None:
    for key in ("product_id", "id"):
        value = product.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _product_title(product: Mapping[str, Any]) -> str:
    for key in ("title", "name"):
        value = product.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Product"


def _product_category(product: Mapping[str, Any]) -> str | None:
    category = product.get("category")
    if isinstance(category, str) and category.strip():
        return category.strip()
    category_name = product.get("category_name")
    if isinstance(category_name, str) and category_name.strip():
        return category_name.strip()
    return None


def _build_content_mock_output(
    *,
    products: list[Mapping[str, Any]],
    output_language: str,
    report_run_id: str | None,
) -> dict[str, Any]:
    if output_language == "en":
        summary = "Reviewable content drafts were generated for the supplied products."
    else:
        summary = "پیشنهادهای محتوای قابل بررسی برای محصولات ارائه‌شده تولید شد."

    drafts: list[dict[str, Any]] = []
    for index, product in enumerate(products):
        product_id = _product_identifier(product)
        title = _product_title(product)
        category = _product_category(product)

        if output_language == "en":
            instagram_text = f"Introducing {title}"
            if category:
                instagram_text = f"{instagram_text} — {category}"
            description_text = f"{title}: quality product copy based on supplied metadata."
            instagram_title = f"Instagram caption: {title}"
            description_title = f"Product description: {title}"
            instagram_description = "Instagram caption draft for manager review."
            description_summary = "Product page description draft for manager review."
            rationale = "Mock provider draft aligned with supplied product context."
        else:
            instagram_text = f"معرفی {title}"
            if category:
                instagram_text = f"{instagram_text} — {category}"
            description_text = f"{title}: متن توضیحات محصول بر اساس اطلاعات ارائه‌شده."
            instagram_title = f"کپشن اینستاگرام: {title}"
            description_title = f"توضیحات محصول: {title}"
            instagram_description = "پیش‌نویس کپشن اینستاگرام برای بررسی مدیر."
            description_summary = "پیش‌نویس توضیحات صفحه محصول برای بررسی مدیر."
            rationale = "پیش‌نویس آزمایشی متناسب با زمینه محصول ارائه‌شده."

        drafts.append(
            {
                "action_type": "content.instagram_draft",
                "title": instagram_title,
                "description": instagram_description,
                "draft_text": instagram_text,
                "product_id": product_id,
                "rationale": rationale,
                "requires_approval": True,
            }
        )

        drafts.append(
            {
                "action_type": "content.product_description",
                "title": description_title,
                "description": description_summary,
                "draft_text": description_text,
                "product_id": product_id,
                "rationale": rationale,
                "requires_approval": True,
            }
        )

        if index >= 2:
            break

    return {
        "metadata": {
            "agent_name": "content-agent",
            "report_run_id": report_run_id,
        },
        "summary": summary,
        "drafts": drafts,
        "warnings": [],
        "output_language": output_language,
    }


def _build_sales_mock_output(
    *,
    sales_data: Mapping[str, Any],
    report_run_id: str | None,
) -> dict[str, Any]:
    top_products = []
    for period_key in ("today", "last_7_days"):
        period = sales_data.get(period_key)
        if isinstance(period, Mapping):
            candidates = period.get("top_products")
            if isinstance(candidates, list) and candidates:
                top_products = [item for item in candidates if isinstance(item, Mapping)]
                break

    recommendations: list[dict[str, Any]] = []
    if top_products:
        first = top_products[0]
        sku = first.get("sku") if isinstance(first.get("sku"), str) else "SKU-1"
        recommendations.append(
            {
                "priority": 2,
                "action_type": "sales.restock",
                "title": f"Restock: {sku}",
                "description": "Inventory attention recommended for a top seller.",
                "rationale": "Mock provider recommendation based on supplied sales context.",
                "payload": {"sku": sku},
            }
        )

    return {
        "metadata": {
            "agent_name": "sales-agent",
            "report_run_id": report_run_id,
        },
        "summary": "Mock sales analysis completed.",
        "insights": [],
        "recommendations": recommendations,
        "warnings": [],
    }


def _extract_report_run_id(payload: Mapping[str, Any]) -> str | None:
    store = payload.get("store")
    if isinstance(store, Mapping):
        report_run_id = store.get("report_run_id")
        if isinstance(report_run_id, str) and report_run_id.strip():
            return report_run_id.strip()
    return None


class MockProvider:
    """Deterministic LLM mock that infers agent output shape from prompt content."""

    def complete(self, messages: list[dict[str, str]], /) -> dict[str, Any]:
        system_content = ""
        user_content = ""
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            if role == "system" and isinstance(content, str):
                system_content = content
            elif role == "user" and isinstance(content, str):
                user_content = content

        user_payload = _parse_user_payload(user_content)
        report_run_id = _extract_report_run_id(user_payload)

        if _CONTENT_AGENT_MARKER in system_content:
            products_raw = user_payload.get("products")
            products: list[Mapping[str, Any]] = []
            if isinstance(products_raw, list):
                products = [item for item in products_raw if isinstance(item, Mapping)]

            output_language = _detect_output_language(system_content)
            return _build_content_mock_output(
                products=products,
                output_language=output_language,
                report_run_id=report_run_id,
            )

        if _SALES_AGENT_MARKER in system_content:
            return _build_sales_mock_output(
                sales_data=user_payload,
                report_run_id=report_run_id,
            )

        return {
            "metadata": {"agent_name": "unknown-agent", "report_run_id": report_run_id},
            "summary": "Mock provider received an unrecognized prompt.",
            "warnings": [
                {
                    "code": "mock_unrecognized_prompt",
                    "message": "MockProvider could not infer agent output shape.",
                }
            ],
        }
