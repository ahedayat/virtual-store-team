"""Deterministic Support Agent scope and refusal classification (Phase 9.2)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from agents.shared.language import normalize_output_language
from agents.shared.schemas.support import (
    SupportPolicyCategory,
    SupportRefusalCode,
    SupportScopeEvaluation,
    SupportScopeStatus,
)
from agents.support.approval_policy import evaluate_support_approval_policy
from agents.support.injection_guard import (
    detect_false_completion_instruction,
    detect_instruction_override_in_operator_text,
    detect_system_prompt_disclosure_request,
    strip_quoted_segments,
)

# ---------------------------------------------------------------------------
# Out-of-scope pattern table (checked before in-scope support classification)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _OutOfScopePatternRule:
    refusal_code: SupportRefusalCode
    patterns: tuple[re.Pattern[str], ...]
    reason: str
    suggested_next_step: str | None = None


def _compile_patterns(raw_patterns: Sequence[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in raw_patterns)


_OUT_OF_SCOPE_RULES: tuple[_OutOfScopePatternRule, ...] = (
    _OutOfScopePatternRule(
        refusal_code="approval_bypass_request",
        patterns=_compile_patterns(
            (
                r"\b(skip|bypass|ignore|override)\s+(manager\s+)?approval\b",
                r"\bauto[\s-]?approve\b(?!\s+required)",
                r"\bwithout\s+(manager|human)\s+(review|approval)\b",
                r"\bapprove\s+this\s+automatically\b",
            )
        ),
        reason="Manager approval cannot be bypassed by the Support Agent.",
        suggested_next_step="Route the request through the normal manager approval workflow.",
    ),
    _OutOfScopePatternRule(
        refusal_code="impersonate_other_agent_request",
        patterns=_compile_patterns(
            (
                r"\bact\s+as\s+(the\s+)?(sales|content|coordinator)\s+agent\b",
                r"\byou\s+are\s+(now\s+)?(the\s+)?(sales|content|coordinator)\s+agent\b",
                r"\brun\s+(the\s+)?(sales|content)\s+agent\b",
                r"\bswitch\s+to\s+(sales|content|coordinator)\s+mode\b",
            )
        ),
        reason="The Support Agent cannot impersonate or substitute for other specialist agents.",
        suggested_next_step="Forward sales or content tasks to the appropriate specialist agent workflow.",
    ),
    _OutOfScopePatternRule(
        refusal_code="credential_or_secret_request",
        patterns=_compile_patterns(
            (
                r"\b(api[\s_-]?key|access[\s_-]?token|secret[\s_-]?key|password|credentials?)\b",
                r"\b(show|share|reveal|give|send)\s+(me\s+)?(the\s+)?(api|jwt|bearer)\b",
                r"\benv(ironment)?\s+variable\b",
            )
        ),
        reason="The Support Agent cannot disclose credentials, secrets, or internal tokens.",
    ),
    _OutOfScopePatternRule(
        refusal_code="direct_database_or_internal_api_request",
        patterns=_compile_patterns(
            (
                r"\b(select|insert|update|delete)\s+.+\s+from\s+\w+\b",
                r"\bquery\s+(the\s+)?(database|db|postgres|sql)\b",
                r"\brun\s+(a\s+)?sql\b",
                r"\b(call|hit|invoke)\s+(the\s+)?internal\s+api\b",
                r"\bdirect\s+(database|db|api)\s+access\b",
            )
        ),
        reason="The Support Agent cannot access databases or internal APIs directly.",
        suggested_next_step="Use approved Django internal APIs through the coordinator workflow.",
    ),
    _OutOfScopePatternRule(
        refusal_code="sales_analysis_request",
        patterns=_compile_patterns(
            (
                r"\b(sales|revenue)\s+analysis\b",
                r"\banaly[sz]e\s+(sales|revenue|orders?)\b",
                r"\brun\s+(a\s+)?sales\s+(report|analysis)\b",
                r"\btop[\s-]?selling\s+sku\b",
                r"\bsales\s+forecast\b",
            )
        ),
        reason="Sales analysis belongs to the Sales Agent, not customer support reply drafting.",
        suggested_next_step="Route the request to the Sales Agent workflow.",
    ),
    _OutOfScopePatternRule(
        refusal_code="marketing_or_content_request",
        patterns=_compile_patterns(
            (
                r"\b(write|create|generate|draft)\s+(an?\s+)?(instagram|marketing|social\s+media)\b",
                r"\b(marketing|content)\s+(copy|campaign|post|caption)\b",
                r"\bproduct\s+description\s+draft\b",
                r"\bcontent\s+agent\b",
            )
        ),
        reason="Marketing and content generation belongs to the Content Agent.",
        suggested_next_step="Route the request to the Content Agent workflow.",
    ),
    _OutOfScopePatternRule(
        refusal_code="pricing_or_discount_request",
        patterns=_compile_patterns(
            (
                r"\b(change|update|set|lower|raise)\s+(the\s+)?price\b",
                r"\bapply\s+(a\s+)?\d+\s*%\s*discount\b",
                r"\bcreate\s+(a\s+)?(promo|promotion|discount\s+code)\b",
                r"\bpricing\s+decision\b",
            )
        ),
        reason="Pricing and discount decisions are outside Support Agent scope.",
        suggested_next_step="Route pricing changes to store management or the Sales Agent workflow.",
    ),
    _OutOfScopePatternRule(
        refusal_code="inventory_or_restock_request",
        patterns=_compile_patterns(
            (
                r"\b(restock|re[\s-]?stock)\b",
                r"\bupdate\s+inventory\b",
                r"\badjust\s+stock\b",
                r"\breorder\s+(stock|inventory|units)\b",
                r"\binventory\s+(update|mutation|change)\b",
            )
        ),
        reason="Inventory and restock operations belong to the Sales Agent or store operations.",
        suggested_next_step="Route inventory tasks to the Sales Agent or approved store operations.",
    ),
    _OutOfScopePatternRule(
        refusal_code="refund_or_payment_action",
        patterns=_compile_patterns(
            (
                r"\b(process|execute|issue|run|trigger)\s+(the\s+)?(a\s+)?refund\b",
                r"\brefund\s+(this|the)\s+(order|payment|transaction)\s+now\b",
                r"\b(charge|capture|void|reverse)\s+(the\s+)?(payment|card|transaction)\b",
                r"\brun\s+(the\s+)?payment\s+(api|processor)\b",
            )
        ),
        reason="The Support Agent cannot execute refunds or payment actions.",
        suggested_next_step="Draft a reply for manager review; refunds require approved backend workflows.",
    ),
    _OutOfScopePatternRule(
        refusal_code="order_mutation_request",
        patterns=_compile_patterns(
            (
                r"\b(mutate|modify|update|delete)\s+(the\s+)?order\s+(record|row|in\s+(the\s+)?database)\b",
                r"\bchange\s+order\s+status\s+in\s+(the\s+)?(system|database|backend)\b",
                r"\bdirectly\s+(cancel|delete|update)\s+(the\s+)?order\b",
                r"\border\s+mutation\b",
            )
        ),
        reason="The Support Agent cannot mutate orders or fulfillment records directly.",
        suggested_next_step="Draft a support reply for manager approval when a customer requests a change.",
    ),
    _OutOfScopePatternRule(
        refusal_code="legal_or_medical_advice",
        patterns=_compile_patterns(
            (
                r"\b(legal|medical|health)\s+advice\b",
                r"\bwhat\s+should\s+i\s+do\s+(legally|medically)\b",
                r"\b(diagnos(e|is)|prescri(be|ption))\b",
                r"\blawsuit|sue\s+(you|the\s+company)\b",
            )
        ),
        reason="The Support Agent cannot provide legal or medical advice.",
        suggested_next_step="Escalate sensitive claims to a manager for review.",
    ),
)

# ---------------------------------------------------------------------------
# In-scope support category detection (customer support inquiries)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _InScopeCategoryRule:
    category: SupportPolicyCategory
    patterns: tuple[re.Pattern[str], ...]


_IN_SCOPE_CATEGORY_RULES: tuple[_InScopeCategoryRule, ...] = (
    _InScopeCategoryRule(
        category="angry_or_escalated_customer",
        patterns=_compile_patterns(
            (
                r"\b(angry|furious|outraged|unacceptable|worst\s+service)\b",
                r"\bspeak\s+to\s+(a\s+)?manager\b",
                r"\bescalat(e|ion)\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="legal_or_safety_claim",
        patterns=_compile_patterns(
            (
                r"\b(injur(y|ed)|unsafe|health\s+risk|allergic\s+reaction)\b",
                r"\blegal\s+action\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="refund_request",
        patterns=_compile_patterns(
            (
                r"\b(i\s+)?(need|want|request)\s+(a\s+)?refund\b",
                r"\brefund\s+(please|request|my\s+order)\b",
                r"\breturn\s+my\s+money\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="cancellation_request",
        patterns=_compile_patterns(
            (
                r"\bcancel\s+(my\s+)?order\b",
                r"\bi\s+want\s+to\s+cancel\b",
                r"\border\s+cancellation\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="address_change_request",
        patterns=_compile_patterns(
            (
                r"\bchange\s+(my\s+)?(shipping|delivery)\s+address\b",
                r"\bupdate\s+(my\s+)?(shipping|delivery)\s+address\b",
                r"\bwrong\s+address\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="payment_issue",
        patterns=_compile_patterns(
            (
                r"\bpayment\s+(failed|declined|issue|problem)\b",
                r"\b(double[\s-]?charged|charged\s+twice)\b",
                r"\bcard\s+(declined|failed)\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="order_dispute",
        patterns=_compile_patterns(
            (
                r"\b(dispute|disputing)\s+(my\s+)?(order|charge)\b",
                r"\bnever\s+received\s+(my\s+)?order\b",
                r"\bwrong\s+item\s+(received|delivered)\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="order_status_question",
        patterns=_compile_patterns(
            (
                r"\bwhere\s+is\s+(my\s+)?order\b",
                r"\border\s+status\b",
                r"\btrack(ing)?\s+(my\s+)?(order|package|shipment)\b",
                r"\bwhen\s+will\s+(it|my\s+order)\s+(arrive|ship)\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="return_policy_question",
        patterns=_compile_patterns(
            (
                r"\breturn\s+policy\b",
                r"\bhow\s+(do|can)\s+i\s+return\b",
                r"\bcan\s+i\s+return\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="shipping_policy_question",
        patterns=_compile_patterns(
            (
                r"\bshipping\s+policy\b",
                r"\bhow\s+(long|much)\s+(does|is)\s+shipping\b",
                r"\bdo\s+you\s+ship\s+to\b",
                r"\bdelivery\s+time\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="product_question",
        patterns=_compile_patterns(
            (
                r"\b(product|item)\s+(size|color|material|availability)\b",
                r"\bdo\s+you\s+have\s+(this|the)\s+(product|item|size)\b",
                r"\bsizing\s+(chart|guide|question)\b",
            )
        ),
    ),
    _InScopeCategoryRule(
        category="generic_faq",
        patterns=_compile_patterns(
            (
                r"\bstore\s+hours\b",
                r"\bwhat\s+are\s+your\s+hours\b",
                r"\bcontact\s+(us|support)\b",
                r"\bgeneral\s+question\b",
                r"\bhello\b",
                r"\bhi\b",
            )
        ),
    ),
)

# ---------------------------------------------------------------------------
# Localized refusal messages (AI_OUTPUT_LANGUAGE)
# ---------------------------------------------------------------------------

_RefusalMessageKey = Literal[
    "sales_analysis_request",
    "marketing_or_content_request",
    "pricing_or_discount_request",
    "inventory_or_restock_request",
    "refund_or_payment_action",
    "order_mutation_request",
    "legal_or_medical_advice",
    "credential_or_secret_request",
    "direct_database_or_internal_api_request",
    "approval_bypass_request",
    "impersonate_other_agent_request",
    "system_prompt_disclosure_request",
    "instruction_override_request",
    "false_completion_instruction",
    "unknown_out_of_scope",
    "generic",
]

_REFUSAL_SAFE_MESSAGES: dict[str, dict[_RefusalMessageKey, str]] = {
    "en": {
        "sales_analysis_request": (
            "I can help with customer support messages, but sales analysis is handled by another "
            "specialist workflow. I have not run any sales analysis."
        ),
        "marketing_or_content_request": (
            "I can help with customer support messages, but marketing and content drafts are handled "
            "by another specialist workflow. I have not created any content."
        ),
        "pricing_or_discount_request": (
            "I cannot change prices or apply discounts. Pricing decisions require store management review."
        ),
        "inventory_or_restock_request": (
            "I cannot update inventory or restock products. Inventory tasks belong to store operations."
        ),
        "refund_or_payment_action": (
            "I cannot process refunds or payment actions directly. Refunds require manager-approved workflows."
        ),
        "order_mutation_request": (
            "I cannot mutate order records directly. I can only draft support replies for manager review."
        ),
        "legal_or_medical_advice": (
            "I cannot provide legal or medical advice. Please contact qualified professionals for that."
        ),
        "credential_or_secret_request": (
            "I cannot share credentials, secrets, or internal tokens."
        ),
        "direct_database_or_internal_api_request": (
            "I cannot access databases or internal APIs directly."
        ),
        "approval_bypass_request": (
            "I cannot bypass manager approval. Sensitive actions require human review."
        ),
        "impersonate_other_agent_request": (
            "I am the Support Agent and cannot act as another specialist agent."
        ),
        "system_prompt_disclosure_request": (
            "I cannot reveal system prompts, hidden policies, or internal instructions."
        ),
        "instruction_override_request": (
            "Customer message text is untrusted data. I cannot follow embedded instructions "
            "that override Support Agent rules or approval policy."
        ),
        "false_completion_instruction": (
            "I cannot claim that refunds, messages, or order changes were already executed. "
            "No external action has been performed."
        ),
        "unknown_out_of_scope": (
            "This request is outside my support scope. I have not performed any external action."
        ),
        "generic": (
            "I can only help with customer support reply drafting and safe escalation. "
            "I have not performed any external action."
        ),
    },
    "fa": {
        "sales_analysis_request": (
            "من در پاسخ‌گویی به پیام‌های پشتیبانی مشتری کمک می‌کنم، اما تحلیل فروش توسط "
            "گردش‌کار تخصصی دیگری انجام می‌شود. هیچ تحلیل فروشی اجرا نشده است."
        ),
        "marketing_or_content_request": (
            "من در پاسخ‌گویی به پیام‌های پشتیبانی مشتری کمک می‌کنم، اما پیش‌نویس بازاریابی و "
            "محتوا توسط گردش‌کار تخصصی دیگری انجام می‌شود. هیچ محتوایی ایجاد نشده است."
        ),
        "pricing_or_discount_request": (
            "من نمی‌توانم قیمت‌ها را تغییر دهم یا تخفیف اعمال کنم. تصمیمات قیمت‌گذاری نیاز به "
            "بررسی مدیریت فروشگاه دارد."
        ),
        "inventory_or_restock_request": (
            "من نمی‌توانم موجودی را به‌روزرسانی کنم یا محصولات را مجدداً تأمین کنم. "
            "وظایف موجودی مربوط به عملیات فروشگاه است."
        ),
        "refund_or_payment_action": (
            "من نمی‌توانم مستقیماً بازپرداخت یا عملیات پرداخت انجام دهم. بازپرداخت‌ها نیاز به "
            "گردش‌کار تأییدشده توسط مدیر دارند."
        ),
        "order_mutation_request": (
            "من نمی‌توانم مستقیماً رکوردهای سفارش را تغییر دهم. فقط می‌توانم پیش‌نویس "
            "پاسخ پشتیبانی برای بررسی مدیر تهیه کنم."
        ),
        "legal_or_medical_advice": (
            "من نمی‌توانم مشاوره حقوقی یا پزشکی ارائه دهم. لطفاً برای این موارد با "
            "متخصصان مرتبط تماس بگیرید."
        ),
        "credential_or_secret_request": (
            "من نمی‌توانم اعتبارنامه، رمز یا توکن‌های داخلی را به اشتراک بگذارم."
        ),
        "direct_database_or_internal_api_request": (
            "من نمی‌توانم مستقیماً به پایگاه داده یا APIهای داخلی دسترسی داشته باشم."
        ),
        "approval_bypass_request": (
            "من نمی‌توانم تأیید مدیر را دور بزنم. اقدامات حساس نیاز به بررسی انسانی دارند."
        ),
        "impersonate_other_agent_request": (
            "من عامل پشتیبانی هستم و نمی‌توانم نقش عامل تخصصی دیگری را ایفا کنم."
        ),
        "system_prompt_disclosure_request": (
            "من نمی‌توانم پرامپت سیستم، سیاست‌های پنهان یا دستورالعمل‌های داخلی را فاش کنم."
        ),
        "instruction_override_request": (
            "متن پیام مشتری داده غیرقابل‌اعتماد است. من نمی‌توانم دستورالعمل‌های جاسازی‌شده "
            "که قوانین عامل پشتیبانی یا سیاست تأیید را لغو می‌کنند دنبال کنم."
        ),
        "false_completion_instruction": (
            "من نمی‌توانم ادعا کنم که بازپرداخت، پیام یا تغییر سفارش قبلاً انجام شده است. "
            "هیچ اقدام خارجی انجام نشده است."
        ),
        "unknown_out_of_scope": (
            "این درخواست خارج از حوزه پشتیبانی من است. هیچ اقدام خارجی انجام نشده است."
        ),
        "generic": (
            "من فقط در درک پیام‌های پشتیبانی مشتری، تهیه پیش‌نویس پاسخ امن و "
            "ارجاع پشتیبانی کمک می‌کنم. هیچ اقدام خارجی انجام نشده است."
        ),
    },
}

_PII_ECHO_PATTERNS: tuple[re.Pattern[str], ...] = _compile_patterns(
    (
        r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
        r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
        r"\b\d{10,}\b",
    )
)


def _normalize_message(message: str) -> str:
    return " ".join(message.strip().split())


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def classify_out_of_scope_request(message: str) -> SupportRefusalCode | None:
    """Return a refusal code when the message is an out-of-scope agent task request."""
    normalized = _normalize_message(message)
    if not normalized:
        return None

    for rule in _OUT_OF_SCOPE_RULES:
        if _matches_any(normalized, rule.patterns):
            return rule.refusal_code
    return None


def resolve_injection_aware_refusal(message: str) -> SupportRefusalCode | None:
    """Classify injection attempts using quote-aware operator matching."""
    normalized = _normalize_message(message)
    if not normalized:
        return None

    if detect_system_prompt_disclosure_request(normalized):
        return "system_prompt_disclosure_request"

    if detect_false_completion_instruction(normalized):
        return "false_completion_instruction"

    operator_text = strip_quoted_segments(normalized)

    if detect_instruction_override_in_operator_text(normalized):
        override_refusal = classify_out_of_scope_request(operator_text)
        if override_refusal is not None:
            return override_refusal

    return classify_out_of_scope_request(operator_text)


def detect_in_scope_support_category(message: str) -> SupportPolicyCategory:
    """Classify an in-scope customer support inquiry using keyword rules."""
    normalized = _normalize_message(message)
    if not normalized:
        return "unknown_or_ambiguous"

    for rule in _IN_SCOPE_CATEGORY_RULES:
        if _matches_any(normalized, rule.patterns):
            return rule.category
    return "unknown_or_ambiguous"


def _get_out_of_scope_rule(refusal_code: SupportRefusalCode) -> _OutOfScopePatternRule | None:
    for rule in _OUT_OF_SCOPE_RULES:
        if rule.refusal_code == refusal_code:
            return rule
    return None


def _build_refusal_safe_message(
    refusal_code: SupportRefusalCode,
    *,
    output_language: str,
) -> str:
    language = normalize_output_language(output_language)
    messages = _REFUSAL_SAFE_MESSAGES[language]
    key: _RefusalMessageKey = refusal_code if refusal_code in messages else "generic"
    return messages[key]


def _build_scope_status(
    *,
    is_refusal: bool,
    requires_approval: bool,
) -> SupportScopeStatus:
    if is_refusal:
        return "out_of_scope"
    if requires_approval:
        return "approval_required"
    return "in_scope"


def _resolve_action_type_for_scope(
    *,
    is_refusal: bool,
    requires_approval: bool,
    default_action_type: str,
) -> str | None:
    if is_refusal:
        return None
    if requires_approval and default_action_type == "support.escalate":
        return "support.escalate"
    return None


def evaluate_support_scope(
    message: str,
    *,
    output_language: str | None = None,
) -> SupportScopeEvaluation:
    """Classify a customer message for in-scope support, approval, or out-of-scope refusal.

    Classification only — this helper does not execute actions, send messages, or call LLMs.
    """
    language = normalize_output_language(output_language)
    warnings: list[str] = []

    refusal_code = resolve_injection_aware_refusal(message)
    if refusal_code is not None:
        rule = _get_out_of_scope_rule(refusal_code)
        reason = rule.reason if rule is not None else "Request is outside Support Agent scope."
        suggested_next_step = rule.suggested_next_step if rule is not None else None
        safe_message = _build_refusal_safe_message(refusal_code, output_language=language)

        return SupportScopeEvaluation(
            is_refusal=True,
            scope_status="out_of_scope",
            refusal_code=refusal_code,
            reason=reason,
            safe_message=safe_message,
            suggested_next_step=suggested_next_step,
            requires_approval=False,
            action_type=None,
            warnings=warnings,
            support_category=None,
        )

    support_category = detect_in_scope_support_category(message)
    policy = evaluate_support_approval_policy(support_category)
    scope_status = _build_scope_status(
        is_refusal=False,
        requires_approval=policy.requires_approval,
    )
    action_type = _resolve_action_type_for_scope(
        is_refusal=False,
        requires_approval=policy.requires_approval,
        default_action_type=policy.default_action_type,
    )

    if scope_status == "in_scope":
        safe_message = (
            "This is an in-scope support request that may receive a safe reply draft."
            if language == "en"
            else "این یک درخواست پشتیبانی در حوزه مجاز است که می‌تواند پیش‌نویس پاسخ امن دریافت کند."
        )
    else:
        safe_message = (
            "This support request requires manager approval before any customer-facing reply."
            if language == "en"
            else "این درخواست پشتیبانی قبل از هر پاسخ به مشتری نیاز به تأیید مدیر دارد."
        )

    if policy.requires_approval and action_type == "support.escalate":
        warnings.append("Escalation requires manager approval; no action has been executed.")

    return SupportScopeEvaluation(
        is_refusal=False,
        scope_status=scope_status,
        refusal_code=None,
        reason=policy.reason,
        safe_message=safe_message,
        suggested_next_step=None,
        requires_approval=policy.requires_approval,
        action_type=action_type,
        warnings=warnings,
        support_category=support_category,
    )


def refusal_safe_message_excludes_pii(message: str, safe_message: str) -> bool:
    """Return True when safe_message does not echo detected PII patterns from the input."""
    normalized = _normalize_message(message)
    for pattern in _PII_ECHO_PATTERNS:
        for match in pattern.finditer(normalized):
            fragment = match.group(0)
            if fragment and fragment in safe_message:
                return False
    return True
