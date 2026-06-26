# Step 8.3 — Content Agent Schema Validation Tests

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Harden the Content Agent output contract with deterministic Pydantic schema validation and focused unit tests. Every parsed LLM or mock payload must pass schema validation after Step 8.2 draft limiting and before the result is returned from the Content Agent pipeline.

This step adds the `ContentSuggestions` schema, a shared validation gate, and tests only. It does not implement FastAPI `/run`, Django product fetch, real LLM provider wiring, coordinator integration, or external publishing.

---

## Scope of this step

- Shared schema: `agents/shared/schemas/content.py`
- Validation gate: `agents/content/validation.py`
- Pipeline integration: `agents/content/analysis.py`
- Focused unit tests: `agents/content/tests/test_schema_validation.py`
- Draft-limit test updates: `agents/content/tests/test_draft_limit.py`
- Cursor scope rule: `.cursor/rules/phase-8-3-content-agent-schema-validation.mdc`
- This documentation file

**Not in scope:** Phase 9 Support Agent, Phase 10 Coordinator/LangGraph, frontend dashboard, real Instagram publishing, competitor scraping, website article generation, or Prestia-specific business logic.

---

## Files changed

| File | Change |
|------|--------|
| `agents/shared/schemas/content.py` | Created — `ContentDraft`, `ContentSuggestions` |
| `agents/shared/schemas/__init__.py` | Updated — export content schemas |
| `agents/content/validation.py` | Created — parse LLM JSON, validate output, safe logging |
| `agents/content/analysis.py` | Updated — validate after draft limit in `normalize_content_agent_output()` |
| `agents/content/tests/test_schema_validation.py` | Created — valid/invalid output and parsing tests |
| `agents/content/tests/test_draft_limit.py` | Updated — `normalize_content_agent_output()` returns `ContentSuggestions` |
| `.cursor/rules/phase-8-3-content-agent-schema-validation.mdc` | Phase 8.3 scope rule |
| `docs/phases/step-8.3.md` | Created — this document |

**Reused unchanged modules:** Step 6.3 `validate_agent_response`, `StrictAgentModel`, `BaseAgentResponse`; Step 8.1 prompts; Step 8.2 `draft_limit.py`.

---

## Schema / models used

| Model | Module | Purpose |
|-------|--------|---------|
| `ContentSuggestions` | `agents/shared/schemas/content.py` | Top-level Content Agent response envelope |
| `ContentDraft` | `agents/shared/schemas/content.py` | Nested draft/suggestion validation |
| `ContentActionType` | `agents/shared/schemas/content.py` | Allowed `action_type` literals |
| `validate_agent_response` | `agents/shared/schemas/validation.py` | Shared strict validator (Step 6.3) |
| `AgentSchemaValidationError` | `agents/shared/schemas/errors.py` | Structured validation failure |
| `ContentLLMOutputError` | `agents/content/validation.py` | Malformed LLM JSON (parse failure) |

Schemas use `extra="forbid"` via `StrictAgentModel` (Step 6.3).

### `ContentDraft` fields

| Field | Type | Rules |
|-------|------|-------|
| `action_type` | `string` | `content.instagram_draft` or `content.product_description` |
| `title` | `string` | Non-empty |
| `description` | `string` | Non-empty |
| `draft_text` | `string` | Non-empty reviewable body |
| `rationale` | `string` | Non-empty, non-PII explanation |
| `product_id` | `string \| null` | Required for `content.product_description`; optional for Instagram drafts |
| `campaign_angle` | `string \| null` | Optional metadata |
| `priority` | `int \| null` | When provided, integer **1–5** |
| `requires_approval` | `bool` | Must be `true`; content suggestions are approval-required |
| `payload` | `object` | Action-specific structured data (may be `{}`) |
| `output_language` | `string \| null` | Optional per-draft language metadata |

### `ContentSuggestions` envelope

| Field | Type | Rules |
|-------|------|-------|
| `metadata` | `AgentResponseMetadata` | `agent_name`, optional `report_run_id` |
| `summary` | `string` | Non-empty manager-facing summary |
| `drafts` | `ContentDraft[]` | List of reviewable suggestions |
| `warnings` | `AgentWarning[]` | Optional warnings (default `[]`) |
| `output_language` | `string \| null` | Optional envelope-level language metadata (`fa`, `en`, etc.) |

---

## Validation boundary

```
normalize_content_agent_output(raw_llm_or_mock)
  │
  ├─ parse_llm_json_output()          # str JSON or mock dict
  ├─ apply_content_draft_limit()      # Step 8.2 trim (dict)
  └─ ensure_valid_content_suggestions()
        └─ validate_agent_response(..., ContentSuggestions)
              → return ContentSuggestions
```

**Order:** parse → **draft limit** → **schema validation** → return typed result.

Draft limiting still operates on parsed dicts (Step 8.2). Schema validation runs on the trimmed payload so excess drafts are dropped before validation, not rejected as invalid.

On validation failure, callers should use `log_content_validation_failure()` (safe summary only; no raw draft bodies at INFO) and raise `AgentSchemaValidationError` or `ContentLLMOutputError`.

There is no Content Agent `/run` endpoint yet; the boundary is `normalize_content_agent_output()` in `agents/content/analysis.py`.

---

## Valid-output test coverage

`agents/content/tests/test_schema_validation.py`:

- Valid Instagram draft passes validation
- Valid product description draft passes validation
- Multiple valid suggestions pass validation
- Persian output accepted (`output_language=fa`, Persian `draft_text`)
- English output accepted (`output_language=en`)
- Draft limit still enforced after validation (`normalize_content_agent_output` with 5 drafts → max 2)
- Trimmed output retains `requires_approval=True`

---

## Invalid-output test coverage

- Unsupported action type (`content.publish_instagram`)
- Missing/empty `draft_text`
- Missing `product_id` for `content.product_description`
- Malformed payload (extra top-level field)
- Non-list `drafts` container
- Invalid `priority` (e.g. `0`)
- `requires_approval=false`
- Extra unknown field on a draft object

---

## Preserving Step 8.1 and Step 8.2 behavior

| Step | Preserved behavior |
|------|-------------------|
| **8.1** | `agents/content/prompts.py` and `brand_voice.py` unchanged; brand voice, campaign angle, and `AI_OUTPUT_LANGUAGE` prompt injection unaffected |
| **8.2** | `resolve_max_drafts_per_run()` and `limit_content_suggestions()` unchanged; limit applied **before** validation in `normalize_content_agent_output()` |
| **8.2 tests** | `agents/content/tests/test_draft_limit.py` still passes; normalize tests updated for `ContentSuggestions` return type |

---

## Validation commands

Run focused Step 8.3 tests:

```bash
PYTHONPATH=. python -m unittest agents.content.tests.test_schema_validation -v
```

Run all Content Agent tests (8.1 + 8.2 + 8.3):

```bash
PYTHONPATH=. python -m unittest agents.content.tests -v
```

Run all agent unit tests:

```bash
PYTHONPATH=. python -m unittest discover -s agents -p 'test_*.py' -v
```

---

## Known limitations

| Limitation | Notes |
|------------|-------|
| No `/run` endpoint on content-agent | Validation gate exists in `analysis.py`; HTTP wiring is later Phase 8 / Phase 10 work |
| No trim warning in output | Excess drafts still dropped silently after parse; `warnings[]` for trim events deferred |
| No markdown-fence JSON stripping | Only raw JSON strings and mock dicts are supported (no shared fence parser exists) |
| No Django product fetch or action persistence | Schema validates agent output shape only |
| `product_id` optional for Instagram drafts | Matches Step 8.1 prompt wording (“when applicable”); required only for product descriptions |
| No real LLM provider integration | Tests use fixtures and deterministic payloads only |

---

## Deferred to Phase 9 and Phase 10

| Item | Phase |
|------|-------|
| Support Agent pipelines, reply drafts, policy tables | Phase 9 |
| Coordinator LangGraph orchestration, parallel agent calls, report merge | Phase 10 |
| FastAPI `/run` on content-agent with HTTP error mapping | Full Phase 8 / Phase 10 |
| Django product fetch and `ActionService` persistence | Full Phase 8 pipeline |
| Real LLM provider wiring (OpenAI/Anthropic) | Later Phase 8 / infrastructure |
| Trim warnings when drafts exceed resolved max | Optional follow-up |
| `docs/examples/content_output.json` | Similar to Sales Step 7.4 (not in 8.3 scope) |

---

## Acceptance checklist

- [x] Content Agent output schema-validated deterministically via `ContentSuggestions`
- [x] Invalid outputs raise `AgentSchemaValidationError` (strict `extra="forbid"`)
- [x] Valid Instagram and product-description drafts pass validation
- [x] Only allowed content action types accepted
- [x] Content suggestions require approval (`requires_approval` must be `true`)
- [x] Step 8.2 draft limit enforced before validation
- [x] No real LLM API key required for tests
- [x] No external publishing behavior introduced
- [x] No Prestia-specific business logic hardcoded
- [x] `docs/phases/step-8.3.md` documents the implementation
- [x] Existing agent tests pass
