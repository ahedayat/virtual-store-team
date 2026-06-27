# Step 9.7 — Support Action Mapping and Django Persistence

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Objective

Map validated `SupportReplyDraft` items from `SupportInsights` to Django-compatible internal action payloads, and optionally persist those actions through the shared Django internal action workflow with dry-run support.

This step adds the action layer on top of the Step 9.6 runtime pipeline. It does not implement Step 9.8 acceptance closure or example output proof.

---

## Scope

### In scope

- Support action mapping module for validated reply drafts and escalations
- Supported action types: `support.reply_draft`, `support.escalate`
- Preservation of Step 9.1 approval metadata (`requires_approval`, `matched_policy_code`, `risk_level`, `safety_notes`)
- Dry-run mapping without POSTing to Django
- Optional persistence via `DjangoClient.create_action()` → `POST /internal/ai/actions/`
- Safe persistence failure warnings without discarding validated `SupportInsights`
- `/run` request fields `persist_actions` and `dry_run` (defaults: no persistence)
- Focused mapping/persistence tests
- This documentation file

### Out of scope (Step 9.8 and beyond)

- `docs/examples/support_output.json`
- Final Phase 9 acceptance proof
- Real Instagram send, refunds, order mutation, payments, publishing, or other external side effects
- Real LLM API calls
- Direct database access from agents
- Coordinator or frontend changes
- Prestia-specific business logic

---

## Files created/updated

| File | Change |
|------|--------|
| `agents/support/action_mapping.py` | Created — mapping and persistence helpers |
| `agents/support/tests/test_action_mapping.py` | Created — Step 9.7 mapping/persistence tests |
| `agents/support/app/schemas.py` | Updated — `persist_actions`, `dry_run` request fields |
| `agents/support/app/main.py` | Updated — optional persistence wiring on `/run` |
| `agents/shared/schemas/support.py` | Updated — `SupportRunResponse.warnings` for persistence feedback |
| `agents/support/validation.py` | Updated — propagate `SupportInsights.warnings` into `/run` response |
| `docs/phases/step-9.7.md` | Created — this document |

---

## Action mapping module summary

Module: `agents/support/action_mapping.py`

| Function | Purpose |
|----------|---------|
| `map_support_reply_draft_to_action_payload(draft, *, report_run_id=None)` | Map one validated draft to a Django internal action request body |
| `map_support_insights_to_actions(insights, *, report_run_id=None)` | Map all drafts in a `SupportInsights` object |
| `persist_support_actions(insights, *, django_client, report_run_id=None, agent_output_id=None, dry_run=False)` | Map and optionally POST actions to Django |

`SupportActionMappingError` is raised for unsupported action types or missing required mapping fields before any POST occurs.

---

## Supported action types

| Action type | Purpose |
|-------------|---------|
| `support.reply_draft` | Manager-reviewable support reply draft (may be low-risk/auto-eligible when policy allows) |
| `support.escalate` | Manager-reviewable escalation draft (always approval-required) |

Unsupported action types are rejected deterministically by the mapper.

---

## Mapped payload shape

### Common action envelope

```json
{
  "action_type": "support.reply_draft",
  "title": "Support reply draft for manager review",
  "description": "Reviewable reply draft for policy generic_faq: ...",
  "priority": 4,
  "requires_approval": false,
  "report_run_id": "run-support-1",
  "payload": {
    "thread_ref": "thread-ref-001",
    "reply_text": "...",
    "risk_level": "low",
    "policy_code": "generic_faq",
    "safety_notes": [],
    "source": "support-agent",
    "low_risk": true
  }
}
```

### `support.escalate`

```json
{
  "action_type": "support.escalate",
  "title": "Support escalation review required",
  "description": "Escalation draft for policy angry_or_escalated_customer: ...",
  "priority": 1,
  "requires_approval": true,
  "payload": {
    "thread_ref": "thread-ref-002",
    "reason": "Customer tone requires manager review.",
    "risk_level": "high",
    "policy_code": "angry_or_escalated_customer",
    "safety_notes": ["Manager approval is required before escalation."],
    "source": "support-agent"
  }
}
```

Tenant and store scope come from the service JWT on `DjangoClient`, not from untrusted payload fields (Phase 4.3 convention).

Priority is derived from draft `risk_level`:

| Risk | Priority |
|------|----------|
| high | 1 |
| medium | 3 |
| low | 4 |

---

## Approval metadata behavior

- `requires_approval` is copied from the validated draft; the mapper does not bypass manager approval.
- Sensitive or high-risk drafts remain `requires_approval=true` and do not receive a `low_risk` payload flag.
- Low-risk auto-eligible `support.reply_draft` items (Step 9.1 policy + draft metadata) may include `payload.low_risk=true` when `requires_approval=false` and `risk_level=low`.
- `support.escalate` must remain approval-required; mapping rejects escalate drafts that omit approval.

Titles and descriptions use review/draft language only. They never claim a message was sent, a refund was issued, or an order was changed.

---

## Dry-run behavior

When `dry_run=True`:

- Drafts are mapped to Django-compatible action bodies.
- No HTTP POST is made to Django.
- `/run` adds a `dry_run` warning with the mapped action count when `persist_actions=True`.

Default `/run` behavior remains safe: `persist_actions=false`, `dry_run=false`.

---

## Persistence behavior through Django internal actions endpoint

When `persist_actions=True` and `dry_run=False`:

1. Build or reuse a `DjangoClient` from `service_token` / `Authorization` / `JWT_SERVICE_TOKEN`.
2. Map each `reply_drafts[]` item via `map_support_insights_to_actions()`.
3. POST each mapped body through `DjangoClient.create_action()` → `POST /internal/ai/actions/`.
4. Preserve `report_run_id` from the request or `SupportInsights.metadata.report_run_id`.

If no Django client can be configured, a `support_action_persistence_skipped` warning is appended and the validated `SupportInsights` result is still returned.

---

## Persistence failure behavior

On `DjangoHTTPError` or `DjangoClientError` during persistence:

- Append `support_action_persistence_failed` with a safe message from the shared client (no raw response bodies).
- Do not discard the validated `SupportInsights` summary or `reply_drafts[]`.
- Do not expose full exception bodies that may contain sensitive data.
- `/run` propagates warnings through `SupportRunResponse.warnings`.

Mapping errors (`SupportActionMappingError`) return HTTP 422 with code `support_action_mapping_failed` before partial persistence.

---

## PII/logging safeguards

- Mapped titles/descriptions avoid echoing raw customer identifiers.
- Tests use synthetic opaque refs (`thread-ref-001`, `[EMAIL_REDACTED]`, `[PHONE_REDACTED]`).
- `/run` logs warning codes only at WARNING level, not full reply bodies or action payloads at INFO level.
- No secrets, tokens, or service JWTs appear in mapped payloads or test fixtures.

---

## Relationship to prior Support Agent steps

| Step | Relationship |
|------|--------------|
| 9.1 approval policy | Preserves `requires_approval`, `matched_policy_code`, `risk_level`, and low-risk semantics |
| 9.2 refusal behavior | Not redesigned; refusal output is not mapped to customer-contact actions |
| 9.3 prompt-injection safety | Not redesigned |
| 9.4 SupportInsights schema | Consumes already-validated `SupportInsights` / `SupportReplyDraft` objects |
| 9.5 sanitized message context | Not redesigned |
| 9.6 runtime pipeline | Maps pipeline output; pipeline behavior unchanged when persistence is not requested |

Pattern alignment: Sales Agent Step 7.7/7.8 and Content Agent Step 8.6 mapping/persistence helpers.

---

## Explicit non-goals

- Step 9.8 final acceptance proof or `docs/examples/support_output.json`
- Sending customer messages or Instagram DMs
- Refunds, order mutation, payments, pricing/inventory changes, publishing
- Real external side effects, real LLM calls, direct DB access from agents
- Prestia-specific hardcoded business logic

---

## Verification commands run

```bash
python -m unittest agents.support.tests.test_action_mapping -v
python -m unittest agents.support.tests.test_runtime_pipeline -v
python -m unittest agents.support.tests.test_support_insights_schema -v
python -m unittest agents.support.tests.test_django_fetch -v
python -m unittest agents.support.tests.test_message_thread_context -v
python -m unittest agents.support.tests.test_approval_policy agents.support.tests.test_refusal agents.support.tests.test_prompt_injection agents.support.tests.test_run_endpoint -v
```

---

## Acceptance criteria checklist

- [x] Support action mapping exists for validated `SupportReplyDraft` items
- [x] `support.reply_draft` maps to a Django-compatible action payload
- [x] `support.escalate` maps to a Django-compatible action payload
- [x] Unsupported action types are rejected
- [x] Sensitive drafts remain approval-required
- [x] Low-risk drafts include `low_risk` only when policy metadata allows auto-eligibility
- [x] Dry-run mode works without posting to Django
- [x] Persistence mode posts to `POST /internal/ai/actions/` through the shared `DjangoClient`
- [x] Persistence failure creates safe warnings and does not discard validated `SupportInsights`
- [x] No direct external side effects introduced
- [x] No raw PII in fixtures, logs, docs, warnings, or payloads
- [x] Existing Step 9.1–9.6 behavior remains covered by passing tests
- [x] No Step 9.8 functionality implemented
- [x] `docs/phases/step-9.7.md` documents the step

---

## Completion decision

Step 9.7 is **complete**. Support reply drafts and escalations can be mapped to Django internal action payloads and optionally persisted with dry-run and safe failure handling. Step 9.8 (acceptance proof and example output) remains deferred.
