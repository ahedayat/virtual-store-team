# Step 6.6 — Support Agent Mock `/run` Scaffold

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Scope

Add a minimal scaffold `POST /run` endpoint to `support-agent` that returns deterministic structured JSON via the shared `MockProvider`. This is not full support automation (Phase 9).

---

## Files changed

| Path | Change |
|------|--------|
| `agents/support/app/main.py` | Added `POST /run` with validation and error mapping |
| `agents/support/app/schemas.py` | `SupportRunRequest` request model |
| `agents/support/analysis.py` | Scaffold pipeline entry point |
| `agents/support/prompts.py` | Support Agent prompt builder with agent marker |
| `agents/support/validation.py` | Parse and validate scaffold output |
| `agents/shared/schemas/support.py` | `SupportRunResponse` schema |
| `agents/shared/schemas/__init__.py` | Export `SupportRunResponse` |
| `agents/shared/llm/mock.py` | Support-agent mock output shape |
| `agents/support/tests/test_run_endpoint.py` | Endpoint tests |
| `agents/support/tests/__init__.py` | Test package marker |
| `docs/phases/step-6.6.md` | This document |

---

## Endpoint contract

### `POST /run`

**Request (required fields):**

| Field | Type | Notes |
|-------|------|-------|
| `customer_message` | string | Non-empty customer text |
| `channel` | string | e.g. `instagram_dm` |

**Optional:** `tenant_id`, `store_id`, `metadata`, `report_run_id`, `output_language`, `request_id`

**Response fields:**

| Field | Type |
|-------|------|
| `agent` | string (`support-agent`) |
| `status` | string (`ok`) |
| `language` | string (`fa` or `en`) |
| `reply` | string |
| `intent` | string |
| `confidence` | float (0–1) |
| `requires_human_review` | boolean |
| `request_id` | string or null |

---

## Tests added

`agents/support/tests/test_run_endpoint.py`:

- `/health` and `/` endpoints
- Valid `/run` returns structured mock output
- Invalid `/run` (missing/empty fields) returns 422
- `LLM_PROVIDER=mock` works without external API keys
- Deterministic output across repeated calls
- Refund messages require human review
- Validation errors map to 422

---

## Commands run

```bash
PYTHONPATH=. python -m unittest agents.support.tests.test_run_endpoint -v
PYTHONPATH=. python -m unittest agents.shared.tests.test_llm_provider -v
```

**Result:** All support and LLM tests passed.

---

## Acceptance criteria

- [x] `support-agent` exposes `POST /run` scaffold endpoint
- [x] Request validation via Pydantic
- [x] Response validation via `SupportRunResponse`
- [x] Uses shared `MockProvider` with Support Agent marker
- [x] No external LLM/API dependencies required with `LLM_PROVIDER=mock`
- [x] Deterministic structured JSON output
- [x] Tests cover health, valid/invalid runs, and mock-only behavior
- [x] No Phase 9 business workflows implemented

---

## Known limitations

- No Django message-thread fetch or action persistence.
- Intent classification is deterministic keyword matching in `MockProvider`, not real NLP.
- Full support policy table, refusal behavior, and prompt-injection tests belong to Phase 9.
