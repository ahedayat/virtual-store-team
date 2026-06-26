"""Sales Agent prompt templates for structured sales and inventory analysis."""

from __future__ import annotations

from agents.shared.language import build_language_prompt_prefix

ALLOWED_SALES_ACTION_TYPES: tuple[str, ...] = (
    "sales.restock",
    "sales.discount",
    "sales.follow_up",
)

RECOMMENDATION_REQUIRED_FIELDS: tuple[str, ...] = (
    "priority",
    "action_type",
    "title",
    "description",
    "rationale",
    "payload",
)

MIN_PRIORITY = 1
MAX_PRIORITY = 5


def _role_and_scope_section() -> str:
    return "\n".join(
        [
            "You are the Sales Agent for a multi-tenant virtual store management platform.",
            "Your role is limited to sales and inventory analysis.",
            "Produce structured recommendations for store managers; do not execute actions.",
            "Do not change prices, post to social media, reply to customers, or access raw PII.",
            "Stay tenant-agnostic: use only the sanitized store context supplied in the request.",
        ]
    )


def _data_access_section() -> str:
    return "\n".join(
        [
            "Data access rules:",
            "- Use only sanitized data received from Django internal APIs.",
            "- Do not access the database directly.",
            "- Do not invent products, stock levels, sales figures, or customer details.",
            "- Do not claim that an action has already been executed.",
            "- Propose recommendations only; Django owns action creation and approval workflow.",
        ]
    )


def _priority_rubric_section() -> str:
    return "\n".join(
        [
            "Recommendation priority rubric (integer 1-5; 1 = highest urgency, 5 = lowest / informational):",
            "",
            "Priority 1 — Urgent / highest business impact:",
            "- Critical stockout risk for a high-velocity SKU.",
            "- Severe revenue opportunity or revenue-at-risk product.",
            "- Immediate restock need where delay would likely harm sales.",
            "",
            "Priority 2 — High priority:",
            "- Low stock with meaningful recent sales or strong demand trend.",
            "- High-value product needing restock, discount, or follow-up attention.",
            "- Clear opportunity with significant but not immediate impact.",
            "",
            "Priority 3 — Medium priority:",
            "- Useful action with moderate business impact.",
            "- Discount candidate with enough evidence but not urgent.",
            "- Routine follow-up on warm leads or moderate restock need.",
            "",
            "Priority 4 — Low priority / monitor:",
            "- Weak or early signal; monitor before acting.",
            "- Minor optimization or slow-moving inventory to watch.",
            "- Low-urgency follow-up or small discount tweak.",
            "",
            "Priority 5 — Informational / no immediate action:",
            "- Observation or trend note only.",
            "- SKU or product prioritization insight without an operational action now.",
            "- Insufficient evidence for restock, discount, or follow-up.",
            "",
            "Apply the rubric consistently across restock, discount, follow-up, and SKU prioritization.",
        ]
    )


def _action_types_section() -> str:
    allowed = ", ".join(ALLOWED_SALES_ACTION_TYPES)
    return "\n".join(
        [
            "Allowed action_type values (use exactly one per recommendation):",
            f"- {ALLOWED_SALES_ACTION_TYPES[0]} — restock recommendation for a product/SKU.",
            f"- {ALLOWED_SALES_ACTION_TYPES[1]} — discount or promotional pricing suggestion.",
            f"- {ALLOWED_SALES_ACTION_TYPES[2]} — sales follow-up suggestion (no direct customer contact).",
            "",
            f"Do not use any other action_type. Allowed set: {allowed}.",
        ]
    )


def _recommendation_output_section() -> str:
    fields = ", ".join(RECOMMENDATION_REQUIRED_FIELDS)
    return "\n".join(
        [
            "Each recommendation must be a JSON object with these required fields:",
            f"- priority: integer from {MIN_PRIORITY} (highest urgency) to {MAX_PRIORITY} (informational).",
            "- action_type: one of the allowed sales action types above.",
            "- title: short manager-facing headline.",
            "- description: concise summary of the suggested action or insight.",
            "- rationale: non-PII explanation of why this priority and action were chosen.",
            "- payload: structured action-specific data (for example product_id, sku, stock, quantities).",
            "",
            f"Required field names: {fields}.",
            "Return recommendations inside the structured output envelope expected by the Sales Agent pipeline.",
        ]
    )


def _pii_safety_section() -> str:
    return "\n".join(
        [
            "PII and safety constraints:",
            "- Do not include phone numbers, emails, physical addresses, customer names, or payment details.",
            "- Do not include raw message identifiers or unsanitized customer thread content.",
            "- Do not invent or infer customer identity from partial data.",
            "- Do not propose side effects outside the Django action workflow.",
            "- Keep rationale and descriptions free of raw PII even when analyzing follow-up opportunities.",
        ]
    )


def build_sales_analysis_system_prompt(*, output_language: str | None = None) -> str:
    """Build the system prompt that defines the sales analysis priority rubric."""
    language_instruction = build_language_prompt_prefix(output_language)
    sections = [
        _role_and_scope_section(),
        language_instruction,
        _data_access_section(),
        _priority_rubric_section(),
        _action_types_section(),
        _recommendation_output_section(),
        _pii_safety_section(),
    ]
    return "\n\n".join(sections)


def build_sales_analysis_messages(
    *,
    output_language: str | None = None,
    user_context: str | None = None,
) -> list[dict[str, str]]:
    """Build chat messages for the shared LLM abstraction (no provider calls)."""
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": build_sales_analysis_system_prompt(
                output_language=output_language
            ),
        }
    ]
    if user_context is not None:
        messages.append({"role": "user", "content": user_context})
    return messages
