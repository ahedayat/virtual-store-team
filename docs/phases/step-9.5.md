# Step 9.5 — Sanitized Message Thread Consumption

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Objective

Allow the Support Agent to consume sanitized recent message threads from Django internal APIs and merge them deterministically with coordinator-provided or caller-provided context.

This step adds the data-consumption layer only. It does not implement the full runtime analysis pipeline, reply drafting from threads, action mapping, or Django persistence.

---

## Scope

This step implements:

- Shared `DjangoClient.get_recent_messages()` helper
- Support message-thread schemas (`SupportSanitizedMessage`, `SupportSanitizedThread`, `SupportMessageThreadContext`)
- `agents/support/django_fetch.py` — Django fetch with safe failure warnings
- `agents/support/support_context.py` — normalization and deterministic merge
- Minimal `/run` request fields and context preparation hook (no Step 9.6 pipeline changes)
- Focused deterministic tests with mocked Django responses
- This documentation file

**Not in scope:**

- Step 9.6 — full support runtime pipeline (`run_support_analysis()` thread consumption)
- Step 9.7 — support action mapping or Django persistence
- Step 9.8 — acceptance closure and `docs/examples/support_output.json`
- Real LLM calls, external side effects, or direct database access from agents
- Coordinator, frontend, or Prestia-specific business logic

---

## Files created/updated

| File | Change |
|------|--------|
| `agents/shared/django_client/client.py` | Added `get_recent_messages()` |
| `agents/shared/schemas/support.py` | Added sanitized thread/message context schemas |
| `agents/shared/schemas/__init__.py` | Exported new support context schemas |
| `agents/support/django_fetch.py` | Created — Django fetch + fallback warnings |
| `agents/support/support_context.py` | Created — normalization and merge helpers |
| `agents/support/app/schemas.py` | Extended `SupportRunRequest` with fetch/context fields |
| `agents/support/app/main.py` | Minimal context preparation on `/run` |
| `agents/support/tests/test_django_fetch.py` | Created — fetch and endpoint tests |
| `agents/support/tests/test_message_thread_context.py` | Created — merge and failure tests |
| `docs/phases/step-9.5.md` | Created — this document |

---

## Django endpoint/client behavior

| Property | Value |
|----------|-------|
| Method | `GET` |
| Path | `/internal/ai/stores/{store_id}/messages/recent/` |
| Client helper | `DjangoClient.get_recent_messages(store_id, thread_limit=..., messages_per_thread=...)` |
| Auth | `Authorization: Bearer <service_jwt>` via shared client |
| Correlation ID | `X-Request-ID` forwarded when configured on `DjangoClient` |
| Scope | Tenant/store scope enforced by Django from service JWT |

Support fetch entry points:

- `fetch_message_threads_from_django(django_client, store_id)`
- `fetch_message_threads_with_fallback(..., fetch_recent_messages=True)`

On Django client failure, the helper returns `None` plus a `django_fetch_failed` warning with a safe generic message. Raw HTTP bodies are not logged or propagated.

---

## Sanitized message thread context shape

### `SupportSanitizedMessage`

| Field | Notes |
|-------|-------|
| `message_ref` | Opaque message identifier |
| `sender_role` | `customer`, `store`, `staff`, or `system` |
| `text` | Sanitized message body |
| `created_at` | Optional ISO timestamp string |

Django fields are normalized on ingest: `message_id` → `message_ref`, `sender_type` → `sender_role`, `body` → `text`, `sent_at` → `created_at`.

### `SupportSanitizedThread`

| Field | Notes |
|-------|-------|
| `thread_ref` | Opaque thread identifier |
| `messages` | List of sanitized messages (may be empty when malformed entries are skipped) |
| `channel` | Optional channel/platform label |
| `status` | Optional thread status |
| `last_message_at` | Optional ISO timestamp string |
| `metadata` | Optional safe dict (`customer_ref`, `subject`, etc.) |

Django fields are normalized: `thread_id` → `thread_ref`, `platform` → `channel`.

### `SupportMessageThreadContext`

Resolved bundle used by merge helpers:

- `store_id`, `thread_count`, `message_threads`, `django_fetched`, `generated_at`

---

## Context merge behavior

`merge_support_message_context()` and `resolve_support_message_context()` apply deterministic rules:

1. Django-fetched threads form the base when available.
2. Caller `context.message_threads` overlays Django threads by `thread_ref`.
3. Explicit `message_threads` request argument overlays both sources.
4. Other caller `context` keys overlay top-level fields.
5. Duplicate `thread_ref` values: later overlay wins (explicit > caller > django base ordering).
6. Merged threads are sorted by `last_message_at` descending, then `thread_ref`.

When `fetch_recent_messages` is false, caller-provided threads/context are preserved without Django fetch.

---

## Fetch failure behavior

| Scenario | Result |
|----------|--------|
| `fetch_recent_messages=false` | No Django call; caller context only |
| Missing Django client/token | `django_fetch_failed` warning; continue with caller context |
| Missing `store_id` | `django_fetch_failed` warning; no fetch |
| Django HTTP/connection/timeout error | `django_fetch_failed` warning; continue with caller context |
| Malformed optional Django payload | `message_thread_parse_warning`; empty/safe normalized threads |

Fetch failure does not crash context preparation or the existing `/run` scaffold response.

---

## PII/logging safeguards

- Django internal API responses are treated as already sanitized.
- No raw PII in tests, fixtures, warnings, or docs — synthetic placeholders only (`[PHONE_REDACTED]`, `customer_123@redacted.local`).
- Fetch failure warnings use generic safe messages, not raw HTTP response bodies.
- `/run` logs warning codes and thread counts only — not full message bodies.
- Agents do not access the database directly.

---

## Relationship to Step 9.1 approval policy

Unchanged. Approval policy classification remains in `approval_policy.py` and is not driven by message-thread fetch in this step.

---

## Relationship to Step 9.2 refusal behavior

Unchanged. Out-of-scope refusal still runs before mock LLM output on `/run`. Thread context preparation does not bypass refusal.

---

## Relationship to Step 9.3 prompt-injection safety

Unchanged. Customer message text remains untrusted input for the scaffold pipeline. Thread fetch does not inject thread bodies into system prompts in this step.

---

## Relationship to Step 9.4 SupportInsights schema

Unchanged. `SupportInsights` / `SupportReplyDraft` validation and scaffold coercion remain as implemented in Step 9.4. New context schemas are input-side only.

---

## Explicit non-goals

- No Step 9.6 full runtime pipeline
- No Step 9.7 action mapping or persistence
- No Step 9.8 final acceptance closure
- No real external side effects
- No real LLM calls
- No raw PII in fixtures/logs/docs
- No direct database access from agents

---

## Verification commands run

```bash
python -m unittest agents.support.tests.test_django_fetch -v
python -m unittest agents.support.tests.test_message_thread_context -v
python -m unittest agents.support.tests.test_support_insights_schema -v
python -m unittest agents.support.tests.test_approval_policy agents.support.tests.test_refusal agents.support.tests.test_prompt_injection agents.support.tests.test_run_endpoint -v
```

---

## Acceptance criteria checklist

- [x] Support Agent has a Django fetch helper for sanitized recent message threads
- [x] Fetch uses the shared `DjangoClient` and internal API conventions
- [x] Caller/coordinator-provided message context merges deterministically with fetched Django context
- [x] Fetch failure returns safe warnings and does not crash context preparation
- [x] No raw PII introduced into logs, warnings, fixtures, prompts, or outputs
- [x] Existing Step 9.1–9.4 behavior remains passing
- [x] No future-step functionality implemented
- [x] `docs/phases/step-9.5.md` exists and documents the step

---

## Completion decision

**Step 9.5 is complete.** The Support Agent can fetch and merge sanitized message-thread context from Django internal APIs with safe failure handling. Step 9.6 will consume this context in the full runtime pipeline.

**Next step:** Step 9.6 — Full Support Runtime Pipeline
