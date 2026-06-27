# Step 9.1 — Support Agent Approval Policy Table

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Goal

Define a deterministic, code-level Support Agent approval classification policy table that decides whether a support reply draft can be treated as low-risk/auto-executable or must require manager approval.

This step establishes classification metadata only. It does not execute replies, send messages, mutate orders, or integrate the full Phase 9 runtime pipeline.

---

## Scope of this step

- Support approval policy module: `agents/support/approval_policy.py`
- Shared policy schemas: `agents/shared/schemas/support.py`
- Focused unit tests: `agents/support/tests/test_approval_policy.py`
- This documentation file

**Not in scope:**

- Step 9.2 — refusal behavior for out-of-scope requests
- Step 9.3 — prompt-injection safety tests
- Full Support Agent runtime pipeline wiring beyond the policy helper
- Real DM sending, refunds, order changes, publishing, or external API writes
- Prestia-specific business logic

---

## Files added/changed

| File | Change |
|------|--------|
| `agents/support/approval_policy.py` | Created — policy table data and `evaluate_support_approval_policy()` |
| `agents/shared/schemas/support.py` | Updated — `SupportDraftSafetySignals`, `SupportApprovalPolicyDecision` |
| `agents/shared/schemas/__init__.py` | Updated — export new support policy schemas |
| `agents/support/tests/test_approval_policy.py` | Created — focused policy classification tests |
| `docs/phases/step-9.1.md` | Created — this document |

The existing Phase 6 Support Agent `/run` scaffold endpoint was **not** expanded. Policy classification is exposed as a standalone helper for future pipeline steps.

---

## Policy table categories

Each row in `SUPPORT_APPROVAL_POLICY_TABLE` maps one `policy_key` to one category with base risk and approval behavior.

| Category | Risk | Default action | Base approval | May auto when safe |
|----------|------|----------------|---------------|-------------------|
| `generic_faq` | low | `support.reply_draft` | no | yes |
| `product_question` | low | `support.reply_draft` | no | yes |
| `shipping_policy_question` | low | `support.reply_draft` | no | yes |
| `return_policy_question` | medium | `support.reply_draft` | no | yes |
| `order_status_question` | medium | `support.reply_draft` | yes | no |
| `refund_request` | high | `support.reply_draft` | yes | no |
| `cancellation_request` | high | `support.reply_draft` | yes | no |
| `address_change_request` | high | `support.reply_draft` | yes | no |
| `payment_issue` | high | `support.reply_draft` | yes | no |
| `order_dispute` | high | `support.reply_draft` | yes | no |
| `angry_or_escalated_customer` | high | `support.escalate` | yes | no |
| `legal_or_safety_claim` | high | `support.escalate` | yes | no |
| `sensitive_personal_data` | high | `support.reply_draft` | yes | no |
| `account_or_identity_issue` | high | `support.reply_draft` | yes | no |
| `unsupported_external_action` | high | `support.reply_draft` | yes | no |
| `unknown_or_ambiguous` | medium | `support.reply_draft` | yes | no |

Unknown category strings fall back to the `unknown_or_ambiguous` policy row.

---

## Auto vs approval rules

### Classification vs execution

`evaluate_support_approval_policy()` returns classification metadata only. Nothing is executed, sent, or persisted in this step.

### Low-risk auto-eligible categories

`generic_faq`, `product_question`, `shipping_policy_question`, and `return_policy_question` may be classified as auto-executable **only when all draft safety signals are false**:

- `includes_pii`
- `includes_order_specific_facts`
- `includes_refund_or_payment_promise`
- `includes_policy_exception`
- `requires_external_side_effect`
- `includes_private_account_or_order_data`

If any signal is true, approval is required even for otherwise low-risk categories.

### Always approval-required categories

Refund, cancellation, address change, payment issue, order dispute, angry/escalated tone, legal/safety claims, sensitive personal data, account/identity issues, unsupported external actions, order-status questions, and unknown/ambiguous cases always require approval.

### Policy helper output

`evaluate_support_approval_policy(category, *, safety=None)` returns:

| Field | Meaning |
|-------|---------|
| `category` | Resolved policy category |
| `risk_level` | `low`, `medium`, or `high` |
| `requires_approval` | Whether manager approval is required |
| `default_action_type` | `support.reply_draft` or `support.escalate` |
| `reason` | Human-readable rationale |
| `allowed_auto_executable` | Whether the draft may be queued without approval under policy |
| `matched_policy_code` | Stable policy key for tests/debugging |

### Django action workflow alignment

Django `ActionService` already supports low-risk `support.reply_draft` actions via a `low_risk` payload flag (Phase 4). The Support Agent policy helper is the agent-side source of truth for when that flag may be set in later Phase 9 steps. This step does not write actions.

---

## Non-goals

- No Step 9.2 refusal behavior for out-of-scope requests
- No Step 9.3 prompt-injection tests
- No real DM sending, refunds, or order mutation
- No raw PII in fixtures, logs, or test snapshots
- No Prestia-specific hardcoded business rules

---

## Verification commands run

```bash
cd /Users/user/Documents/Work/virtual_store_team

PYTHONPATH=. python -m unittest agents.support.tests.test_approval_policy -v

PYTHONPATH=. python -m unittest agents.support.tests.test_run_endpoint -v
```

---

## Acceptance criteria checklist

- [x] A code-level Support Agent policy table exists in `agents/support/approval_policy.py`
- [x] Low-risk generic FAQ can be auto-executable only under safe draft signals
- [x] Sensitive support cases require approval
- [x] Unknown or ambiguous cases require approval
- [x] No external side effects introduced
- [x] No raw PII logged or included in snapshots
- [x] Focused tests pass
- [x] `docs/phases/step-9.1.md` documents the step

---

## Completion decision

**Phase 9.1 is complete.** The approval policy table and deterministic classification helper are implemented, schema-validated, and covered by focused unit tests. Step 9.2 (refusal behavior) and Step 9.3 (prompt-injection tests) remain deferred.

---

## Next steps

- **Step 9.2** — Refusal behavior for out-of-scope customer requests
- **Step 9.3** — Unsafe prompt-injection tests from message text
- **Later Phase 9 steps** — Wire policy evaluation into the Support Agent runtime pipeline and Django action mapping
