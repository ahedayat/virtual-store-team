"""Deterministic mock LLM provider for tests and local development."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

_CONTENT_AGENT_MARKER = "Content Agent"
_SALES_AGENT_MARKER = "Sales Agent"
_SUPPORT_AGENT_MARKER = "Support Agent"
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
    recommendations: list[dict[str, Any]] = []

    inventory = sales_data.get("inventory")
    if isinstance(inventory, Mapping):
        low_stock_items = inventory.get("items")
    else:
        low_stock_items = None

    signals = sales_data.get("inventory_signals")
    if not isinstance(signals, Mapping):
        signals = {}

    low_stock_products = signals.get("low_stock_products")
    if not isinstance(low_stock_products, list):
        low_stock_products = []
        if isinstance(low_stock_items, list):
            low_stock_products = [
                item for item in low_stock_items if isinstance(item, Mapping)
            ]

    if low_stock_products:
        first = low_stock_products[0]
        sku = first.get("sku") if isinstance(first.get("sku"), str) else "SKU-1"
        product_id = first.get("product_id")
        current_stock = first.get("available_quantity")
        suggested_qty = first.get("suggested_reorder_quantity")
        payload: dict[str, Any] = {"sku": sku}
        if isinstance(product_id, str) and product_id.strip():
            payload["product_id"] = product_id.strip()
        if isinstance(current_stock, int):
            payload["current_stock"] = current_stock
        if isinstance(suggested_qty, int):
            payload["suggested_order_qty"] = suggested_qty

        recommendations.append(
            {
                "priority": 2,
                "action_type": "sales.restock",
                "title": f"Restock: {sku}",
                "description": "Inventory attention recommended for a low-stock product.",
                "rationale": (
                    "Available inventory is below the configured threshold using "
                    "sanitized inventory signals only."
                ),
                "payload": payload,
            }
        )

    promotion_candidates = signals.get("promotion_eligible_products")
    if not isinstance(promotion_candidates, list):
        promotion_candidates = []

    slow_moving = signals.get("slow_moving_products")
    if isinstance(slow_moving, list) and slow_moving:
        promotion_candidates = list(promotion_candidates) + [
            item for item in slow_moving if isinstance(item, Mapping)
        ]

    if promotion_candidates:
        candidate = promotion_candidates[0]
        sku = candidate.get("sku") if isinstance(candidate.get("sku"), str) else "SKU-2"
        product_id = candidate.get("product_id")
        payload = {"sku": sku, "suggested_discount_pct": 10}
        if isinstance(product_id, str) and product_id.strip():
            payload["product_id"] = product_id.strip()

        recommendations.append(
            {
                "priority": 3,
                "action_type": "sales.discount",
                "title": f"Discount review: {sku}",
                "description": "Promotional pricing may help move slow-selling inventory.",
                "rationale": (
                    "Recent sales velocity is weak relative to available inventory "
                    "using aggregate sales and inventory signals only."
                ),
                "payload": payload,
            }
        )

    if not recommendations:
        top_products = []
        for period_key in ("today", "last_7_days"):
            period = sales_data.get(period_key)
            if isinstance(period, Mapping):
                candidates = period.get("top_products")
                if isinstance(candidates, list) and candidates:
                    top_products = [item for item in candidates if isinstance(item, Mapping)]
                    break

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


def _build_support_mock_output(
    *,
    customer_message: str,
    channel: str,
    output_language: str,
    request_id: str | None,
) -> dict[str, Any]:
    normalized_message = customer_message.strip().lower()
    if "refund" in normalized_message or "return" in normalized_message:
        intent = "refund_request"
        requires_human_review = True
        confidence = 0.85
    elif "order" in normalized_message or "shipping" in normalized_message:
        intent = "order_status"
        requires_human_review = False
        confidence = 0.9
    else:
        intent = "general_inquiry"
        requires_human_review = False
        confidence = 0.92

    if output_language == "en":
        reply = (
            f"Thank you for reaching out via {channel}. "
            "We received your message and will follow up shortly."
        )
    else:
        reply = (
            f"از پیام شما از طریق {channel} سپاسگزاریم. "
            "پیام شما دریافت شد و به‌زودی پاسخ داده می‌شود."
        )

    return {
        "agent": "support-agent",
        "status": "ok",
        "language": output_language,
        "reply": reply,
        "intent": intent,
        "confidence": confidence,
        "requires_human_review": requires_human_review,
        "request_id": request_id,
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

        if _SUPPORT_AGENT_MARKER in system_content:
            customer_message = user_payload.get("customer_message")
            channel = user_payload.get("channel")
            request_id = user_payload.get("request_id")
            if not isinstance(customer_message, str):
                customer_message = ""
            if not isinstance(channel, str):
                channel = "unknown"
            if isinstance(request_id, str):
                normalized_request_id = request_id.strip() or None
            else:
                normalized_request_id = None

            output_language = _detect_output_language(system_content)
            return _build_support_mock_output(
                customer_message=customer_message,
                channel=channel,
                output_language=output_language,
                request_id=normalized_request_id,
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
