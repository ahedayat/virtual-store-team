# Step 9.4 — SupportInsights Schema and Validation

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Objective

Define and validate the final Support Agent output contract using `SupportInsights` and `reply_drafts[]`. Each reply draft carries per-draft approval and safety metadata aligned with Step 9.1 policy classification.

This step establishes the schema contract and validation gate only. It does not implement message-thread fetching, the full runtime pipeline, action mapping, or Django persistence.

---

## Scope

This step implements:

- `SupportInsights` and `SupportReplyDraft` shared schemas
- `validate_support_insights()` validation gate following Sales/Content patterns
- MockProvider support output compatible with `SupportInsights`
- Minimal scaffold compatibility shim so the existing Phase 6 `/run` endpoint keeps working
- Focused schema validation tests
- This documentation file

**Not in scope:**

- Step 9.5 — sanitized Django message thread fetching
- Step 9.6 — full support runtime pipeline returning `SupportInsights` from `/run`
- Step 9.7 — support action mapping and Django persistence
- Step 9.8 — acceptance closure and `docs/examples/support_output.json`
- Real LLM API calls, external side effects, or Django database access from agents
- Coordinator, frontend, or Prestia-specific business logic

---

## Files created/updated

| File | Change |
|------|--------|
| `agents/shared/schemas/support.py` | Updated — `SupportAggregateSentiment`, `SupportReplyDraft`, `SupportInsights` |
| `agents/shared/schemas/__init__.py` | Updated — export new support insight schemas |
| `agents/support/validation.py` | Updated — `validate_support_insights()`, `ensure_valid_support_insights()`, scaffold `coerce_support_output_to_run_response()` |
| `agents/support/analysis.py` | Updated — coerce `SupportInsights` mock output to legacy `SupportRunResponse` for scaffold `/run` |
| `agents/shared/llm/mock.py` | Updated — emit schema-valid `SupportInsights` using Step 9.1 approval policy |
| `agents/support/tests/test_support_insights_schema.py` | Created — focused schema validation tests |
| `agents/support/tests/test_run_endpoint.py` | Updated — intent expectation uses policy category code |
| `agents/shared/tests/test_llm_provider.py` | Updated — mock support output assertions for `SupportInsights` |
| `docs/phases/step-9.4.md` | Created — this document |

---

## Schema contract summary

Support Agent final output is a `SupportInsights` envelope extending `BaseAgentResponse`:

- Top-level analysis fields: `summary`, `themes`, `sentiment`
- Required `reply_drafts[]` with at least one draft
- Optional `output_language`
- Inherited `metadata` and `warnings`

Each `SupportReplyDraft` is a per-thread draft with approval/safety metadata. Only `support.reply_draft` and `support.escalate` action types are accepted.

---

## `SupportInsights` fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `metadata` | `AgentResponseMetadata` | yes | `agent_name`, optional `report_run_id` |
| `warnings` | `list[AgentWarning]` | no | defaults to `[]` |
| `summary` | `str` | yes | non-empty manager-facing summary |
| `themes` | `list[str]` | no | safe theme/category labels |
| `sentiment` | `SupportAggregateSentiment` | yes | aggregate non-PII sentiment |
| `reply_drafts` | `list[SupportReplyDraft]` | yes | minimum length 1 |
| `output_language` | `str \| null` | no | e.g. `fa` or `en` |

---

## `SupportReplyDraft` fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `thread_ref` | `str` | yes | opaque thread reference (no raw PII) |
| `reply_text` | `str` | yes | reviewable draft text |
| `action_type` | literal | yes | `support.reply_draft` or `support.escalate` |
| `requires_approval` | `bool` | yes | manager approval flag |
| `risk_level` | literal | yes | `low`, `medium`, or `high` |
| `matched_policy_code` | `str` | yes | Step 9.1 policy key |
| `safety_notes` | `list[str]` | no | human-readable safety notes |
| `reason` | `str \| null` | no | optional short reason |
| `rationale` | `str \| null` | no | optional classification rationale |
| `language` | `str \| null` | no | draft language hint |

---

## Allowed action types

| Action type | Meaning |
|-------------|---------|
| `support.reply_draft` | Reviewable customer reply draft |
| `support.escalate` | Manager escalation draft (must require approval) |

Any other action type fails strict schema validation.

---

## Validation behavior

Validation follows Step 6.3 strict schema policy (`extra="forbid"`) and Sales/Content Agent gate patterns:

1. Parse LLM/mock JSON with `parse_llm_json_output()`.
2. Validate with `validate_support_insights(payload)` or `ensure_valid_support_insights(result)`.
3. Reject:
   - missing `reply_drafts`
   - empty `reply_drafts`
   - unsupported `action_type`
   - missing required draft fields
   - invalid `risk_level`
   - `support.escalate` with `requires_approval=false`
   - `high` risk with `requires_approval=false`
   - unknown extra fields at any level
4. Log validation failures via `log_support_validation_failure()` without raw LLM payloads.

### Scaffold compatibility

The Phase 6 `/run` endpoint still returns `SupportRunResponse`. `coerce_support_output_to_run_response()` accepts either:

- new `SupportInsights` mock output (validated, then mapped to scaffold shape), or
- legacy `SupportRunResponse`-shaped payloads

This preserves Step 9.1–9.3 runtime behavior without implementing Step 9.6.

---

## MockProvider changes

`_build_support_mock_output()` now returns `SupportInsights`:

- Classifies the customer message into a Step 9.1 policy category
- Calls `evaluate_support_approval_policy()` for deterministic approval metadata
- Emits one `reply_draft` with `matched_policy_code`, `risk_level`, `requires_approval`, and `action_type`
- Uses `request_id` as `thread_ref` when provided, otherwise `thread-mock-1`
- Sets `metadata.agent_name = support-agent`
- No raw PII, no real LLM key, deterministic output

---

## Relationship to Step 9.1 approval policy

- `matched_policy_code` aligns with `SupportApprovalPolicyDecision.matched_policy_code`
- `risk_level`, `requires_approval`, and `action_type` follow policy table defaults
- MockProvider uses `evaluate_support_approval_policy()` directly
- Step 9.1 policy table and tests are unchanged

---

## Relationship to Step 9.2 refusal behavior

- Refusal path in `run_support_analysis()` still returns `SupportRunResponse` with `status="refused"` before LLM/mock output
- `SupportScopeEvaluation` schema is unchanged
- Step 9.2 refusal tests continue to pass

---

## Relationship to Step 9.3 prompt-injection safety

- Output sanitization in `analysis.py` still runs on scaffold `reply` text after coercion
- Injection guardrails and tests are unchanged
- MockProvider reads `untrusted_customer_message` from prompt payload (Step 9.3 behavior preserved)

---

## Explicit non-goals

- No Step 9.5 Django message fetch
- No Step 9.6 full runtime pipeline returning `SupportInsights` from `/run`
- No Step 9.7 action mapping/persistence
- No Step 9.8 final acceptance closure or example output file
- No real external side effects
- No real LLM calls
- No raw PII in fixtures, logs, or docs

---

## Verification commands run

```bash
python -m unittest agents.support.tests.test_support_insights_schema -v
python -m unittest agents.support.tests.test_approval_policy agents.support.tests.test_refusal agents.support.tests.test_prompt_injection agents.support.tests.test_run_endpoint -v
python -m unittest agents.shared.tests.test_llm_provider agents.shared.tests.test_phase6_scaffold -v
```

**Results:** All targeted tests passed (81 support-related tests + 6 Phase 6 scaffold tests).

---

## Acceptance criteria checklist

- [x] `SupportInsights` schema exists and validates valid support output
- [x] `SupportReplyDraft` schema exists with per-draft approval/safety metadata
- [x] `reply_drafts[]` is required and schema-validated (minimum one draft)
- [x] Only `support.reply_draft` and `support.escalate` are accepted
- [x] Invalid action types, malformed drafts, missing fields, and invalid approval metadata are rejected
- [x] MockProvider emits schema-valid `SupportInsights`
- [x] Step 9.1 approval policy tests still pass
- [x] Step 9.2 refusal tests still pass
- [x] Step 9.3 prompt-injection tests still pass
- [x] No future-step functionality implemented
- [x] `docs/phases/step-9.4.md` documents the step

---

## Completion decision

**Step 9.4 is complete.** The Support Agent now has a strict, validated `SupportInsights` output contract with `reply_drafts[]` and per-draft approval metadata. Steps 9.5–9.8 remain before Phase 9 can close.

**Next step:** Step 9.5 — Sanitized Message Thread Consumption
