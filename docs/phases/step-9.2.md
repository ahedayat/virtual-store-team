# Step 9.2 — Support Agent Refusal Behavior

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Objective

Add deterministic, schema-valid refusal behavior to the Support Agent so it refuses requests outside the support domain — especially tasks that belong to the Sales Agent, Content Agent, Coordinator, backend/admin operations, or manager-only approval workflows — while preserving Step 9.1 approval classification for in-scope sensitive support cases.

---

## Scope

This step implements:

- Deterministic out-of-scope request classification (`agents/support/refusal.py`)
- Structured scope/refusal output schema (`SupportScopeEvaluation`)
- Scope guardrails in the Support Agent system prompt (`agents/support/prompts.py`)
- Minimal `/run` pipeline wiring: out-of-scope messages return `status="refused"` before LLM invocation
- Focused unit tests (`agents/support/tests/test_refusal.py`)
- This documentation file

**Not in scope:**

- Step 9.3 — unsafe prompt-injection tests
- Real Instagram sending, refunds, order mutation, payment handling, pricing changes, inventory changes, or publishing
- Full coordinator/LangGraph integration
- Frontend dashboard changes
- Redesign of Step 9.1 approval policy table

---

## Files created/updated

| File | Change |
|------|--------|
| `agents/support/refusal.py` | Created — pattern-based scope/refusal classification and localized safe messages |
| `agents/shared/schemas/support.py` | Updated — `SupportScopeStatus`, `SupportRefusalCode`, `SupportScopeEvaluation` |
| `agents/shared/schemas/__init__.py` | Updated — export `SupportScopeEvaluation` |
| `agents/support/prompts.py` | Updated — role/scope and safety guardrails sections |
| `agents/support/analysis.py` | Updated — early refusal return before LLM for out-of-scope messages |
| `agents/support/tests/test_refusal.py` | Created — focused refusal and scope routing tests |
| `docs/phases/step-9.2.md` | Created — this document |

---

## How refusal classification works

`evaluate_support_scope(message, *, output_language=None)` is the main entry point. It performs **classification only** — no LLM calls, no external side effects, no action execution.

### Three-way routing

| Route | `scope_status` | `is_refusal` | Behavior |
|-------|----------------|--------------|----------|
| Safe in-scope support | `in_scope` | `false` | May proceed to reply drafting; Step 9.1 policy may allow auto-executable drafts when safe |
| Sensitive in-scope support | `approval_required` | `false` | Reuses Step 9.1 `evaluate_support_approval_policy()` — manager approval required, not refused |
| Out-of-scope agent task | `out_of_scope` | `true` | Structured refusal with polite `safe_message`; no actions created |

### Classification order

1. **Out-of-scope patterns first** — agent-task requests (sales analysis, content generation, direct DB access, approval bypass, etc.)
2. **In-scope support category detection** — customer support inquiries mapped to Step 9.1 policy categories
3. **Step 9.1 approval policy** — applied for in-scope categories to set `requires_approval` and escalation metadata

Out-of-scope patterns take precedence so operator-style commands (e.g. "process the refund now") are refused, while customer inquiries (e.g. "I need a refund") remain in-scope with `approval_required`.

---

## Out-of-scope request families

| `refusal_code` | Example intent |
|----------------|----------------|
| `sales_analysis_request` | Run sales/revenue analysis or reports |
| `marketing_or_content_request` | Generate Instagram/marketing copy |
| `pricing_or_discount_request` | Change prices or apply discounts |
| `inventory_or_restock_request` | Restock SKUs or update inventory |
| `refund_or_payment_action` | Execute refunds or payment processor actions |
| `order_mutation_request` | Directly mutate order records in backend/database |
| `legal_or_medical_advice` | Provide legal or medical guidance |
| `credential_or_secret_request` | Disclose API keys, passwords, or secrets |
| `direct_database_or_internal_api_request` | Run SQL or call internal APIs directly |
| `approval_bypass_request` | Skip or override manager approval |
| `impersonate_other_agent_request` | Act as Sales/Content/Coordinator agent |
| `unknown_out_of_scope` | Reserved for future fallback (not used by current pattern table) |

Refusal messages are localized via `AI_OUTPUT_LANGUAGE` (`fa` default, `en` supported).

---

## Relationship to Step 9.1 approval policy

Step 9.2 **reuses** Step 9.1 without redesign:

- In-scope messages call `detect_in_scope_support_category()` then `evaluate_support_approval_policy(category)`
- Sensitive categories (`refund_request`, `payment_issue`, `angry_or_escalated_customer`, etc.) return `approval_required`, not refusal
- Escalation metadata uses `action_type="support.escalate"` only when Step 9.1 policy requires it; refusals never set executable action types

Refusal and approval are distinct: a customer refund **inquiry** is approval-required support work; an operator command to **execute** a refund is refused.

---

## Structured refusal output

`SupportScopeEvaluation` fields:

| Field | Meaning |
|-------|---------|
| `is_refusal` | Whether the message was refused as out-of-scope |
| `scope_status` | `in_scope`, `approval_required`, or `out_of_scope` |
| `refusal_code` | Out-of-scope family code when refused |
| `reason` | Internal/coordinator rationale (non-PII) |
| `safe_message` | Polite user-facing refusal or scope note |
| `suggested_next_step` | Optional routing hint for coordinator |
| `requires_approval` | From Step 9.1 for in-scope cases; `false` for refusals |
| `action_type` | Only `support.escalate` when escalation is needed; `null` for refusals |
| `warnings` | Non-blocking notes (e.g. escalation requires approval) |
| `support_category` | Step 9.1 category when in-scope |

The `/run` endpoint maps refusals to `SupportRunResponse` with `status="refused"`, `intent=<refusal_code>`, and `reply=<safe_message>` without calling the LLM.

---

## What is intentionally not implemented

- Step 9.3 prompt-injection safety tests
- Full Phase 9 production pipeline (thread ingestion, Django action mapping, coordinator orchestration)
- Real external side effects of any kind
- Prestia-specific business logic
- Raw PII in fixtures, logs, or test snapshots

---

## Verification commands run

```bash
cd /Users/user/Documents/Work/virtual_store_team

PYTHONPATH=. python -m unittest agents.support.tests.test_refusal -v

PYTHONPATH=. python -m unittest agents.support.tests.test_approval_policy -v

PYTHONPATH=. python -m unittest agents.support.tests.test_run_endpoint -v
```

---

## Acceptance criteria checklist

- [x] Support Agent has deterministic refusal behavior for out-of-scope requests
- [x] Sales tasks requested through support messages are refused
- [x] Content/marketing tasks requested through support messages are refused
- [x] Manager-only or side-effectful operations are refused or escalated safely
- [x] In-scope support questions are not falsely refused
- [x] Sensitive support cases still require approval per Step 9.1
- [x] Refusal outputs are schema-valid and PII-safe
- [x] No external side effects are introduced
- [x] Focused tests pass
- [x] `docs/phases/step-9.2.md` exists and documents the step

---

## Completion decision

**Phase 9.2 is complete.** Deterministic scope/refusal classification, schema-valid structured output, prompt guardrails, minimal `/run` wiring, and focused tests are implemented. Step 9.3 (prompt-injection tests) and full Phase 9 runtime pipeline integration remain deferred.

---

## Next steps

- **Step 9.3** — Unsafe prompt-injection tests from message text
- **Later Phase 9 steps** — Wire scope evaluation and approval policy into the full Support Agent runtime pipeline and Django action mapping
