"""Unit tests for Support Agent approval policy table (Phase 9.1)."""

from __future__ import annotations

import unittest

from agents.shared.schemas.support import SupportApprovalPolicyDecision, SupportDraftSafetySignals
from agents.shared.schemas.validation import validate_agent_response
from agents.support.approval_policy import (
    ALL_SUPPORT_POLICY_CATEGORIES,
    SUPPORT_APPROVAL_POLICY_TABLE,
    evaluate_support_approval_policy,
    get_support_policy_entry,
    validate_support_policy_table,
)


class SupportApprovalPolicyTableTests(unittest.TestCase):
    def test_policy_table_contains_all_expected_categories_without_duplicate_keys(self) -> None:
        validate_support_policy_table()

        table_categories = {entry.category for entry in SUPPORT_APPROVAL_POLICY_TABLE.values()}
        table_keys = set(SUPPORT_APPROVAL_POLICY_TABLE.keys())

        self.assertEqual(table_categories, set(ALL_SUPPORT_POLICY_CATEGORIES))
        self.assertEqual(table_keys, set(ALL_SUPPORT_POLICY_CATEGORIES))
        self.assertEqual(len(SUPPORT_APPROVAL_POLICY_TABLE), len(ALL_SUPPORT_POLICY_CATEGORIES))

    def test_generic_faq_is_low_risk_and_auto_executable_when_safe(self) -> None:
        decision = evaluate_support_approval_policy("generic_faq")

        self.assertEqual(decision.category, "generic_faq")
        self.assertEqual(decision.risk_level, "low")
        self.assertFalse(decision.requires_approval)
        self.assertTrue(decision.allowed_auto_executable)
        self.assertEqual(decision.default_action_type, "support.reply_draft")
        self.assertEqual(decision.matched_policy_code, "generic_faq")

    def test_refund_request_requires_approval(self) -> None:
        decision = evaluate_support_approval_policy("refund_request")

        self.assertEqual(decision.category, "refund_request")
        self.assertEqual(decision.risk_level, "high")
        self.assertTrue(decision.requires_approval)
        self.assertFalse(decision.allowed_auto_executable)

    def test_cancellation_request_requires_approval(self) -> None:
        decision = evaluate_support_approval_policy("cancellation_request")

        self.assertTrue(decision.requires_approval)
        self.assertFalse(decision.allowed_auto_executable)

    def test_address_change_request_requires_approval(self) -> None:
        decision = evaluate_support_approval_policy("address_change_request")

        self.assertTrue(decision.requires_approval)
        self.assertFalse(decision.allowed_auto_executable)

    def test_payment_issue_requires_approval(self) -> None:
        decision = evaluate_support_approval_policy("payment_issue")

        self.assertTrue(decision.requires_approval)
        self.assertFalse(decision.allowed_auto_executable)

    def test_angry_or_escalated_customer_requires_approval_and_escalates(self) -> None:
        decision = evaluate_support_approval_policy("angry_or_escalated_customer")

        self.assertTrue(decision.requires_approval)
        self.assertFalse(decision.allowed_auto_executable)
        self.assertEqual(decision.default_action_type, "support.escalate")

    def test_order_specific_private_data_reply_requires_approval_even_for_generic_faq(self) -> None:
        decision = evaluate_support_approval_policy(
            "generic_faq",
            safety=SupportDraftSafetySignals(
                includes_private_account_or_order_data=True,
            ),
        )

        self.assertTrue(decision.requires_approval)
        self.assertFalse(decision.allowed_auto_executable)
        self.assertIn("private account or order data", decision.reason.lower())

    def test_order_specific_facts_require_approval_for_low_risk_category(self) -> None:
        decision = evaluate_support_approval_policy(
            "shipping_policy_question",
            safety={"includes_order_specific_facts": True},
        )

        self.assertTrue(decision.requires_approval)
        self.assertIn("order-specific facts", decision.reason.lower())

    def test_unknown_or_ambiguous_request_requires_approval(self) -> None:
        explicit = evaluate_support_approval_policy("unknown_or_ambiguous")
        fallback = evaluate_support_approval_policy("not_a_real_category")

        self.assertTrue(explicit.requires_approval)
        self.assertFalse(explicit.allowed_auto_executable)
        self.assertTrue(fallback.requires_approval)
        self.assertEqual(fallback.category, "unknown_or_ambiguous")
        self.assertEqual(
            get_support_policy_entry("not_a_real_category").policy_key,
            "unknown_or_ambiguous",
        )

    def test_policy_output_is_schema_valid(self) -> None:
        decision = evaluate_support_approval_policy("product_question")
        validated = validate_agent_response(
            decision.model_dump(),
            SupportApprovalPolicyDecision,
        )

        self.assertIsInstance(validated, SupportApprovalPolicyDecision)
        self.assertEqual(validated.category, "product_question")


if __name__ == "__main__":
    unittest.main()
