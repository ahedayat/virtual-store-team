# Step 9.6 — Full Support Runtime Pipeline

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Objective

Implement the main Support Agent runtime pipeline that consumes sanitized support thread context and returns schema-valid `SupportInsights` with safe `reply_drafts[]`, theme/sentiment summaries, and correct per-draft approval metadata.

This step completes the end-to-end analysis path. It does not implement action mapping, Django persistence, or Phase 9 acceptance closure.

---

## Scope

This step implements:

- `run_support_analysis()` full runtime pipeline returning `SupportInsights`
- Step 9.5 context fetch/merge integration inside the pipeline
- Deterministic theme and sentiment summarization heuristics
- Safe multi-thread `reply_drafts[]` generation via MockProvider/LLM abstraction
- Step 9.1 approval policy application on every draft
- Step 9.2 refusal/scope guardrails before draft generation
- Step 9.3 prompt-injection sanitization on draft text
- Step 9.4 `ensure_valid_support_insights()` validation gate before return
- Empty/no-message deterministic handling
- `/run` endpoint wiring with legacy `SupportRunResponse` adapter
- Focused runtime pipeline tests
- This documentation file

**Not in scope:**

- Step 9.7 — support action mapping or Django persistence
- Step 9.8 — acceptance closure and `docs/examples/support_output.json`
- Real LLM API calls, external side effects, or direct database access from agents
- Coordinator, frontend, or Prestia-specific business logic

---

## Files created/updated

| File | Change |
|------|--------|
| `agents/support/analysis.py` | Rewritten — full `run_support_analysis()` runtime pipeline |
| `agents/support/prompts.py` | Added `build_support_analysis_messages()`; scaffold builder delegates to thread-aware prompts |
| `agents/support/validation.py` | Added `support_insights_to_run_response()` for `/run` backward compatibility |
| `agents/support/app/main.py` | Wired pipeline + legacy response adapter + warning logging |
| `agents/shared/llm/mock.py` | Thread-aware support mock extraction from `message_threads` |
| `agents/support/tests/test_runtime_pipeline.py` | Created — focused Step 9.6 pipeline tests |
| `agents/support/tests/test_prompt_injection.py` | Updated — pipeline tests use `SupportInsights` fields |
| `docs/phases/step-9.6.md` | Created — this document |

---

## Pipeline entry point

`agents/support/analysis.py`:

```python
run_support_analysis(
    *,
    customer_message: str,
    channel: str,
    tenant_id: str | None = None,
    store_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    report_run_id: str | None = None,
    output_language: str | None = None,
    request_id: str | None = None,
    llm_provider: LLMProvider | None = None,
    context: Mapping[str, Any] | None = None,
    message_threads: list[Mapping[str, Any]] | None = None,
    django_client: DjangoClient | None = None,
    fetch_recent_messages: bool = False,
) -> SupportInsights
```

### End-to-end flow

1. Resolve output language (`AI_OUTPUT_LANGUAGE` / request override).
2. Fetch and merge sanitized thread context (Step 9.5).
3. Synthesize a single thread from `customer_message` only when no explicit thread input was provided.
4. Return deterministic empty output when no customer messages are available.
5. Scan all thread customer messages for Step 9.2 refusal/scope violations.
6. Build thread-aware prompts with Step 9.3 untrusted-message wrapping.
7. Call `get_llm_provider()` / injected `MockProvider`.
8. Parse LLM JSON, re-apply Step 9.1 approval policy and Step 9.3 reply sanitization per draft.
9. Validate/coerce final output via Step 9.4 `ensure_valid_support_insights()`.
10. Attach fetch/merge warnings and return `SupportInsights`.

---

## Input/context shape

The pipeline accepts:

- Legacy single-message input via `customer_message` (backward compatible with `/run`).
- Step 9.5 merged context via `context`, `message_threads`, and optional Django fetch (`fetch_recent_messages`, `django_client`, `store_id`).

Explicit empty `message_threads=[]` (or equivalent caller context) suppresses single-message synthesis and triggers empty-thread handling.

---

## Theme and sentiment summarization behavior

Deterministic heuristics (no real LLM required for classification):

- **Themes:** derived from `detect_in_scope_support_category()` across thread customer messages (e.g. `generic_faq`, `refund_request`, `shipping_policy_question`).
- **Sentiment:** aggregate label from category mix — `positive`, `neutral`, `negative`, `mixed`, or `unknown`.
- **Summary:** manager-facing text based on thread count and primary theme; localized for `fa` / `en`.

No raw PII is included in themes, sentiment, or summaries. Customer facts are not invented.

---

## Reply draft generation behavior

- One or more `SupportReplyDraft` items in `reply_drafts[]`.
- Drafts are support-scoped review text only — no claims that refunds, sends, or order mutations were executed.
- Valid `action_type` values: `support.reply_draft`, `support.escalate`.
- Per-draft metadata: `requires_approval`, `risk_level`, `matched_policy_code`, `safety_notes`, `thread_ref`, `language`.
- MockProvider generates schema-compatible `SupportInsights`; pipeline re-applies policy and sanitization before validation.

---

## Approval policy integration (Step 9.1)

Every draft passes through `evaluate_support_approval_policy()` using the detected in-scope category and draft safety signals. Sensitive categories (refunds, cancellations, payment issues, etc.) remain approval-required. Low-risk generic FAQ drafts may be auto-eligible when safe.

---

## Refusal/scope guardrail integration (Step 9.2)

Before LLM draft generation, each thread's latest customer message is evaluated with `evaluate_support_scope()`. Any out-of-scope request produces a schema-valid `SupportInsights` refusal envelope:

- `support.escalate` draft with `requires_approval=True`
- Warning code `support_out_of_scope_refusal`
- No unsafe executable side effects

The `/run` adapter maps this to legacy `status="refused"` for coordinator compatibility.

---

## Prompt-injection safety integration (Step 9.3)

- Customer message text is wrapped as untrusted data in thread-aware prompts.
- `sanitize_support_reply_output()` redacts echoed PII and softens false completion claims on every draft.
- Multi-thread injection attempts are refused when any thread contains out-of-scope operator instructions.

---

## SupportInsights validation integration (Step 9.4)

All normal and refusal paths return through `ensure_valid_support_insights()`. Invalid LLM/mock JSON is logged safely and raises `AgentSchemaValidationError` or `SupportLLMOutputError` — never returned as-is.

---

## Sanitized thread context integration (Step 9.5)

The pipeline reuses:

- `fetch_message_threads_with_fallback()`
- `resolve_support_message_context()`

Fetch failures attach `django_fetch_failed` warnings and continue with caller-provided context when available.

---

## Empty/no-message behavior

When no customer messages are present after merge (explicit empty thread input):

- Warning code: `no_support_threads_available`
- Schema-valid `SupportInsights` with empty `themes`, `sentiment.label="unknown"`, and a safe informational escalate draft
- Deterministic output (no hallucinated customer facts)

---

## PII/logging safeguards

- No raw phone numbers, emails, addresses, tokens, or real Instagram IDs in tests/fixtures.
- Synthetic placeholders only (`customer_123@redacted.local`, `[PHONE_REDACTED]`).
- Full message bodies, prompt bodies, and draft bodies are not logged at INFO level.
- Validation failures log schema/field summaries only.

---

## `/run` endpoint integration

`POST /run` calls `run_support_analysis()` and adapts the result to legacy `SupportRunResponse` via `support_insights_to_run_response()` for backward compatibility with existing coordinator/scaffold consumers.

---

## Explicit non-goals

- No Step 9.7 action mapping or Django persistence
- No Step 9.8 final acceptance proof or `docs/examples/support_output.json`
- No real external side effects (Instagram send, refunds, order mutation, payments, publishing, pricing, inventory)
- No raw PII in fixtures/logs/docs
- No direct database access from agents

---

## Verification commands run

```bash
python -m unittest agents.support.tests.test_runtime_pipeline -v
python -m unittest agents.support.tests.test_support_insights_schema -v
python -m unittest agents.support.tests.test_django_fetch -v
python -m unittest agents.support.tests.test_message_thread_context -v
python -m unittest agents.support.tests.test_approval_policy agents.support.tests.test_refusal agents.support.tests.test_prompt_injection agents.support.tests.test_run_endpoint -v
python -m unittest agents.shared.tests.test_llm_provider -v
```

All commands passed during Step 9.6 implementation.

---

## Acceptance criteria checklist

- [x] `run_support_analysis()` implements the full Support Agent runtime pipeline
- [x] Pipeline consumes sanitized support thread context, not only a single `customer_message`
- [x] Pipeline returns schema-valid `SupportInsights`
- [x] Pipeline summarizes themes and sentiment without PII leakage
- [x] Pipeline generates safe `reply_drafts[]` with per-draft approval metadata
- [x] Step 9.1 approval policy is applied to every draft
- [x] Step 9.2 refusal/scope guardrails are preserved
- [x] Step 9.3 prompt-injection defenses are preserved
- [x] Step 9.4 schema validation is used before final return
- [x] Step 9.5 sanitized context shape is accepted
- [x] Empty/no-message cases are deterministic and safe
- [x] Tests are deterministic and require no real LLM keys or external services
- [x] No Step 9.7 or 9.8 functionality is implemented
- [x] `docs/phases/step-9.6.md` exists and documents the step

---

## Completion decision

**Phase 9.6 is complete.** The Support Agent runtime pipeline produces schema-valid `SupportInsights` from sanitized thread context with safe drafts, theme/sentiment summaries, and integrated policy/refusal/injection/validation guardrails.

**Next step:** Phase 9.7 — Support Action Mapping and Django Persistence
