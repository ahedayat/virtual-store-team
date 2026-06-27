# Step 9.8 — Phase 9 Acceptance Proof and Closure

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented — Phase 9 complete

---

## Objective

Prove all Phase 9 Support Agent acceptance criteria with deterministic tests, a canonical schema-valid example output, full Support Agent test-suite verification, and final closure documentation.

This step is acceptance validation and documentation only. It does not add major new Support Agent features, coordinator orchestration, frontend changes, or real external side effects.

---

## Scope

### In scope

- Canonical example output: `docs/examples/support_output.json`
- Example validation test: `agents/support/tests/test_support_output_example.py`
- Final Phase 9 acceptance tests: `agents/support/tests/test_phase9_acceptance.py`
- Full Support Agent test-suite verification (Steps 9.1–9.8)
- Phase 9 closure documentation (this file)
- Optional Phase 9 status update in `docs/phases/step-0.0.md`

### Out of scope (explicit non-goals)

| Area | Deferred work |
|------|----------------|
| Phase 10 | Coordinator/LangGraph orchestration |
| — | Daily report orchestration |
| — | Frontend dashboard changes |
| — | Real Instagram send |
| — | Refunds, order mutation, payment handling |
| — | Price or inventory changes |
| — | Content publishing |
| — | Real external side effects |
| — | Real LLM API calls or API keys |
| — | Direct database access from agents |
| — | Prestia-specific hardcoded business logic in agent code |
| — | Raw PII in examples, fixtures, tests, logs, warnings, docs, or payloads |

---

## Files created/updated

| File | Change |
|------|--------|
| `docs/examples/support_output.json` | Created — canonical Support Agent output example |
| `agents/support/tests/test_support_output_example.py` | Created — loads and validates the example file |
| `agents/support/tests/test_phase9_acceptance.py` | Created — Phase 9 acceptance criteria coverage |
| `docs/phases/step-9.8.md` | Created — this document |
| `docs/phases/step-0.0.md` | Updated — Phase 9 status marked complete |

**Reused unchanged modules:** Steps 9.1–9.7 implementation (`run_support_analysis`, `POST /run`, `SupportInsights`, approval policy, refusal, injection guardrails, Django fetch/merge, action mapping, MockProvider).

---

## Phase 9 subphase summary (9.1–9.8)

| Subphase | Name | Summary | Documentation |
|----------|------|---------|---------------|
| **9.1** | Support approval policy table | Deterministic auto-vs-approval classification for low-risk FAQ vs sensitive support cases | `docs/phases/step-9.1.md` |
| **9.2** | Refusal behavior | Out-of-scope sales/content/pricing/inventory/refund-execution/order-mutation requests refused deterministically | `docs/phases/step-9.2.md` |
| **9.3** | Prompt-injection safety | Customer message text treated as untrusted; injection cannot bypass policy, scope, or PII boundaries | `docs/phases/step-9.3.md` |
| **9.4** | `SupportInsights` schema | Final output contract with `reply_drafts[]` and per-draft approval/safety metadata | `docs/phases/step-9.4.md` |
| **9.5** | Sanitized thread consumption | Django internal API fetch, deterministic merge, safe fetch-failure warnings | `docs/phases/step-9.5.md` |
| **9.6** | Full runtime pipeline | `run_support_analysis()` with themes/sentiment, guardrails, and schema validation | `docs/phases/step-9.6.md` |
| **9.7** | Action mapping/persistence | `support.reply_draft` / `support.escalate` mapping with dry-run and mocked Django persistence | `docs/phases/step-9.7.md` |
| **9.8** | Acceptance proof and closure | Example output, acceptance tests, full suite verification, closure documentation | `docs/phases/step-9.8.md` |

---

## Canonical example output summary

**Path:** `docs/examples/support_output.json`

**Schema:** `SupportInsights` (`agents/shared/schemas/support.py`)

| Field | Notes |
|-------|-------|
| `metadata` | `agent_name: support-agent`, placeholder `report_run_id` |
| `summary` | Non-PII manager-facing summary of recent support themes |
| `themes` | Safe policy/theme labels (`generic_faq`, `refund_request`) |
| `sentiment` | Aggregate `label` + `confidence` without customer identifiers |
| `reply_drafts` | Two drafts: low-risk `support.reply_draft` (`requires_approval: false`) and sensitive refund draft (`requires_approval: true`) |
| `warnings` | Empty list |
| `output_language` | `en` |

The example uses opaque `thread_ref` values (`thread-demo-001`, `thread-demo-002`), contains no raw PII, and does not claim any message was sent or any refund/order/payment action was executed.

---

## `docs/examples/support_output.json` validation result

Validated via `validate_support_insights()` (Step 9.4 validation gate).

| Check | Result |
|-------|--------|
| Parses as JSON | Pass |
| Validates against `SupportInsights` | Pass |
| `reply_drafts[]` present (min length 1) | Pass — 2 drafts |
| Allowed action types only | Pass — `support.reply_draft` |
| Required per-draft metadata present | Pass |
| Theme/sentiment summary fields present | Pass |
| No obvious raw PII | Pass |
| No executed-action claims | Pass |

---

## Final acceptance test coverage

### Example output validation

`agents/support/tests/test_support_output_example.py` (6 tests)

- Loads `docs/examples/support_output.json`
- Validates against `SupportInsights`
- Asserts required draft fields, allowed action types, theme/sentiment fields
- Asserts no obvious PII or executed-action claims

### Phase 9 acceptance proof

`agents/support/tests/test_phase9_acceptance.py` (18 tests)

| Test class | Coverage |
|------------|----------|
| `Phase9AcceptanceThreadConsumptionTests` | Step 9.5 sanitized context merge; mocked Django fetch normalization |
| `Phase9AcceptancePipelineTests` | Schema-valid `SupportInsights`, theme/sentiment without PII, Step 9.1 low-risk vs sensitive approval |
| `Phase9AcceptanceRefusalAndInjectionTests` | Step 9.2 sales/content/approval-bypass refusal; Step 9.3 injection resistance |
| `Phase9AcceptanceActionMappingTests` | `support.reply_draft` / `support.escalate` mapping; unsupported types rejected; sensitive persistence preserves `pending_approval` intent |
| `Phase9AcceptanceNoSideEffectsTests` | Dry-run persistence; no external side-effect claims; `/run` dry-run |
| `Phase9AcceptanceArchitectureTests` | No Prestia hardcoding; no direct side-effect paths in mapper |
| `Phase9AcceptanceExampleArtifactTests` | Example file exists |

---

## Full Support Agent verification commands and results

### Step 9.8 tests only

```bash
PYTHONPATH=. python -m unittest \
  agents.support.tests.test_phase9_acceptance \
  agents.support.tests.test_support_output_example \
  -v
```

**Result:** `Ran 24 tests in 0.051s — OK`

### Full Support Agent regression suite (Steps 9.1–9.8)

```bash
PYTHONPATH=. python -m unittest \
  agents.support.tests.test_phase9_acceptance \
  agents.support.tests.test_support_output_example \
  agents.support.tests.test_action_mapping \
  agents.support.tests.test_runtime_pipeline \
  agents.support.tests.test_support_insights_schema \
  agents.support.tests.test_django_fetch \
  agents.support.tests.test_message_thread_context \
  agents.support.tests.test_approval_policy \
  agents.support.tests.test_refusal \
  agents.support.tests.test_prompt_injection \
  agents.support.tests.test_run_endpoint \
  -v
```

**Result:** `Ran 131 tests in 0.197s — OK`

### Package discovery (also works in this repository)

```bash
PYTHONPATH=. python -m unittest discover agents/support/tests -v
```

**Result:** `Ran 131 tests in 0.187s — OK`

All tests use MockProvider, synthetic sanitized fixtures, and mocked `DjangoClient` HTTP transports. No real LLM API keys or external services are required.

---

## PII safety verification

| Area | Evidence |
|------|----------|
| Example output | `test_support_output_example.py::test_example_does_not_contain_obvious_raw_pii` |
| Runtime pipeline | `test_runtime_pipeline.py::test_output_does_not_leak_synthetic_pii` |
| Acceptance pipeline | `test_phase9_acceptance.py::test_theme_and_sentiment_summarized_without_pii_leakage` |
| Injection guard | `test_prompt_injection.py` suite; `test_phase9_acceptance.py::test_prompt_injection_cannot_bypass_policy_or_leak_pii` |
| Action mapping payloads | `test_action_mapping.py::test_mapped_payloads_do_not_contain_raw_pii` |
| Refusal output | `test_refusal.py::test_refusal_output_does_not_include_raw_pii_from_input` |

---

## Approval policy verification

| Criterion | Evidence |
|-----------|----------|
| Low-risk FAQ may be auto-eligible | `test_approval_policy.py`; `test_phase9_acceptance.py::test_low_risk_faq_follows_step_9_1_policy` |
| Refund/sensitive drafts approval-required | `test_runtime_pipeline.py::test_refund_thread_requires_approval`; `test_phase9_acceptance.py::test_sensitive_refund_draft_remains_approval_required` |
| Sensitive persistence preserves approval | `test_phase9_acceptance.py::test_sensitive_draft_persistence_preserves_pending_approval_intent` |
| Escalations always approval-required | `test_support_insights_schema.py::test_escalate_without_approval_fails_validation` |

---

## Refusal/scope verification

| Criterion | Evidence |
|-----------|----------|
| Sales/content/manager-only tasks refused | `test_refusal.py`; `test_phase9_acceptance.py::test_sales_content_and_manager_only_tasks_are_refused_or_escalated` |
| Refusal produces `support.escalate` draft | `test_runtime_pipeline.py::test_sales_analysis_request_is_refused` |
| Schema-valid refusal output | `test_refusal.py::test_refusal_output_is_schema_valid` |

---

## Prompt-injection verification

| Criterion | Evidence |
|-----------|----------|
| Injection cannot bypass approval/policy | `test_prompt_injection.py` (full suite) |
| Customer text marked untrusted in prompts | `test_prompt_injection.py::test_prompt_marks_customer_message_as_untrusted` |
| Acceptance end-to-end injection case | `test_phase9_acceptance.py::test_prompt_injection_cannot_bypass_policy_or_leak_pii` |

---

## Sanitized thread consumption verification

| Criterion | Evidence |
|-----------|----------|
| Django fetch normalization | `test_django_fetch.py` |
| Caller/Django merge | `test_message_thread_context.py` |
| Merged context accepted by pipeline | `test_runtime_pipeline.py::test_step_9_5_merged_context_shape_is_accepted` |
| Acceptance stitched path | `test_phase9_acceptance.py::test_step_9_5_sanitized_thread_context_is_accepted_by_pipeline` |

---

## Runtime pipeline verification

| Criterion | Evidence |
|-----------|----------|
| Schema-valid `SupportInsights` | `test_runtime_pipeline.py`; `test_phase9_acceptance.py::test_runtime_returns_schema_valid_support_insights_with_reply_drafts` |
| Themes and sentiment | `test_runtime_pipeline.py::test_multiple_threads_produce_themes_and_sentiment` |
| Empty threads handled deterministically | `test_runtime_pipeline.py::test_empty_thread_context_is_deterministic` |
| Persian/English language paths | `test_runtime_pipeline.py::test_persian_output_language_path` |

---

## Action mapping and mocked persistence verification

| Criterion | Evidence |
|-----------|----------|
| `support.reply_draft` / `support.escalate` mapping | `test_action_mapping.py` |
| Dry-run without POST | `test_action_mapping.py::test_dry_run_maps_without_posting` |
| Mocked persistence to `/internal/ai/actions/` | `test_action_mapping.py::test_successful_action_persistence_posts_to_internal_actions` |
| Persistence failure preserves insights | `test_action_mapping.py::test_persistence_failure_preserves_support_insights` |
| `/run` dry-run and failure warnings | `test_action_mapping.py` endpoint tests |

---

## Acceptance criteria checklist

| Criterion | Status | Evidence |
|-----------|--------|----------|
| All Phase 9 subphases 9.1–9.8 documented | Met | `docs/phases/step-9.1.md` through `docs/phases/step-9.8.md` |
| `docs/examples/support_output.json` exists and validates | Met | Example file + `test_support_output_example.py` |
| Sanitized thread consumption verified | Met | Thread consumption acceptance tests + Step 9.5 tests |
| Theme/sentiment without PII | Met | Pipeline + acceptance tests |
| Safe `reply_drafts[]` with correct `requires_approval` | Met | Pipeline, schema, acceptance tests |
| Sensitive drafts approval-required when persisted | Met | Action mapping + acceptance persistence test |
| Out-of-scope refusal/escalation | Met | Refusal + acceptance tests |
| Prompt-injection resistance | Met | Step 9.3 + acceptance tests |
| Action mapping and mocked persistence | Met | Step 9.7 + acceptance tests |
| No real external side effects | Met | Dry-run tests; no send/refund/publish paths |
| Full Support Agent test suite passes | Met | 131 tests OK |
| No raw PII in examples/fixtures/docs | Met | PII safety tests across suite |

---

## Known limitations

- Acceptance tests use MockProvider and mocked Django HTTP transports, not live LLM providers or Django containers.
- `docs/examples/support_output.json` is a static contract example; runtime MockProvider wording may differ while remaining schema-valid.
- `POST /run` persistence is opt-in (`persist_actions`); coordinator orchestration remains Phase 10.
- Persian reply quality with real LLM providers is not evaluated in this phase.

---

## Final completion decision

**Phase 9 — Support Agent is complete.**

All subphases 9.1–9.8 are implemented, tested, and documented. All final Phase 9 acceptance criteria pass. No open Phase 9 acceptance gaps remain for MVP scope.

**Phase 10 — Coordinator & LangGraph may proceed.**

Recommended next steps:

1. Wire coordinator star-topology HTTP calls to sales, content, and support agents.
2. Merge specialist outputs into a daily report payload.
3. Persist intermediate `AgentOutput` records and final report via Django client.
