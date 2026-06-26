# Step 7.3 — Validate JSON Against Schema Before Return

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Ensure every Sales Agent output is validated against the official `SalesAnalysisResult` schema before it is returned from the analysis pipeline, mock/real LLM paths, empty-sales fallback, or the FastAPI `/run` endpoint. Invalid LLM JSON and malformed recommendations must never be returned as-is.

This step adds the validation gate only. It does not implement Step 7.4 example output documentation or full non-empty production LLM integration.

---

## Scope of this step

- Shared validation gate: `agents/sales/validation.py`
- Pipeline integration: `agents/sales/analysis.py`
- FastAPI `/run` endpoint: `agents/sales/app/main.py`
- Request model: `agents/sales/app/schemas.py`
- Focused unit tests: `agents/sales/tests/test_schema_validation.py`
- Cursor scope rule: `.cursor/rules/step-7.3-sales-agent-schema-validation.mdc`
- This documentation file

**Not in scope:** Step 7.4 (`docs/examples/sales_output.json`), real OpenAI/Anthropic provider wiring, Django fetch integration, LangGraph orchestration, coordinator changes, or Prestia-specific business logic.

---

## Files changed

| File | Change |
|------|--------|
| `agents/sales/validation.py` | Created — parse LLM JSON, validate output, safe logging |
| `agents/sales/analysis.py` | Updated — validation gate on all return paths; LLM path parses and validates |
| `agents/sales/app/schemas.py` | Created — `SalesRunRequest` |
| `agents/sales/app/main.py` | Updated — `POST /run` returns validated output; maps errors to HTTP 422/501 |
| `agents/sales/tests/test_schema_validation.py` | Created — validation and endpoint tests |
| `.cursor/rules/step-7.3-sales-agent-schema-validation.mdc` | Step 7.3 scope rule |
| `docs/phases/step-7.3.md` | Created — this document |

**Reused unchanged schemas:** `agents/shared/schemas/sales.py` (`SalesAnalysisResult`, `SalesRecommendation`), `agents/shared/schemas/validation.py` (`validate_agent_response`).

---

## Validation flow

```
POST /run (or run_sales_analysis())
  │
  ├─ empty sales? → handle_empty_sales() → build_empty_sales_result()
  │                                      → ensure_valid_sales_analysis_result()
  │                                      → return SalesAnalysisResult
  │
  └─ non-empty + llm_provider
        → build_sales_analysis_messages()
        → llm_provider.complete()
        → parse_llm_json_output()     # str JSON or mock dict
        → ensure_valid_sales_analysis_result()
        → return SalesAnalysisResult

On validation failure:
  → log_sales_validation_failure()   # safe summary only
  → raise AgentSchemaValidationError or SalesLLMOutputError
  → /run maps to HTTP 422 with structured detail (no stack trace)
```

All paths share `ensure_valid_sales_analysis_result()`, which round-trips through `validate_agent_response(..., SalesAnalysisResult)` from Step 6.3.

---

## Schema / models used

| Model | Module | Purpose |
|-------|--------|---------|
| `SalesAnalysisResult` | `agents/shared/schemas/sales.py` | Top-level Sales Agent response envelope |
| `SalesRecommendation` | `agents/shared/schemas/sales.py` | Nested recommendation validation |
| `SalesActionType` | `agents/shared/schemas/sales.py` | Allowed `action_type` literals |
| `validate_agent_response` | `agents/shared/schemas/validation.py` | Shared strict validator |
| `AgentSchemaValidationError` | `agents/shared/schemas/errors.py` | Structured validation failure |
| `SalesLLMOutputError` | `agents/sales/validation.py` | Malformed LLM JSON (parse failure) |

Schemas use `extra="forbid"` via `StrictAgentModel` (Step 6.3).

---

## Recommendation field requirements

Every recommendation must include:

| Field | Type | Rules |
|-------|------|-------|
| `priority` | `int` | Integer from **1** (highest urgency) to **5** (informational) |
| `action_type` | `string` | One of the allowed literals below |
| `title` | `string` | Short manager-facing headline |
| `description` | `string` | Concise summary |
| `rationale` | `string` | Non-PII explanation |
| `payload` | `object` | Action-specific structured data (may be `{}`) |

### Allowed action types

- `sales.restock`
- `sales.discount`
- `sales.follow_up`

### Priority validation rules

- `priority < 1` → validation error
- `priority > 5` → validation error
- Non-integer values → validation error

Step 7.1 prompt rubric semantics are unchanged; this step enforces the same constraints programmatically.

### Valid recommendation example

```json
{
  "priority": 2,
  "action_type": "sales.restock",
  "title": "Restock: Example SKU",
  "description": "Short manager-facing summary.",
  "rationale": "Low stock with recent sales velocity (non-PII).",
  "payload": {
    "product_id": "uuid",
    "sku": "SKU-001",
    "current_stock": 2,
    "suggested_order_qty": 20
  }
}
```

### Invalid examples (rejected)

- Missing `rationale` or any required field
- `action_type`: `"sales.promote"`
- `priority`: `0`, `6`, or non-integer
- Extra unknown fields at any level

---

## Malformed JSON handling

| Input | Behavior |
|-------|----------|
| Valid JSON object | Parsed and validated |
| Mock provider `dict` | Validated directly (no `json.loads`) |
| Invalid JSON text | `SalesLLMOutputError` — not returned to clients |
| JSON array/primitive | `SalesLLMOutputError` — root must be an object |
| Valid JSON, invalid schema | `AgentSchemaValidationError` with field paths |

Raw malformed LLM output is never returned from `run_sales_analysis()` or `/run`.

---

## Validation error behavior

| Layer | Behavior |
|-------|----------|
| `run_sales_analysis()` | Raises `AgentSchemaValidationError` or `SalesLLMOutputError` after safe logging |
| `POST /run` | HTTP **422** with `detail.code` of `schema_validation_failed` or `llm_output_invalid` |
| Non-empty without LLM | HTTP **501** with `detail.code` `not_implemented` |
| API responses | No stack traces; no raw LLM payloads |

422 response shape (schema failure):

```json
{
  "detail": {
    "code": "schema_validation_failed",
    "message": "Agent response failed validation against schema 'SalesAnalysisResult': ...",
    "schema_name": "SalesAnalysisResult",
    "field_errors": [
      {
        "field": "recommendations[0].priority",
        "message": "Input should be less than or equal to 5",
        "type": "less_than_equal"
      }
    ]
  }
}
```

---

## PII-safe logging rules

`log_sales_validation_failure()` logs at **WARNING** with:

- `service` (`sales-agent`)
- `report_run_id`
- `request_id` / correlation ID
- `schema_name`
- `error_summary` (safe validation message)
- `invalid_fields` (field paths only)

**Not logged:**

- Raw LLM responses
- Full prompt context
- Customer PII
- Authorization tokens

`/run` request logging uses the same safe `extra` fields at INFO level.

---

## Integration with prior steps

| Step | Integration |
|------|-------------|
| **6.3** | Reuses `validate_agent_response`, `AgentSchemaValidationError`, strict `extra="forbid"` |
| **7.1** | LLM path uses `build_sales_analysis_messages()`; programmatic validation mirrors prompt contract |
| **7.2** | Empty-sales fallback passes through `ensure_valid_sales_analysis_result()` — no validation bypass |

---

## Tests added

`agents/sales/tests/test_schema_validation.py` (stdlib `unittest`):

- Valid Sales Agent output passes validation
- Missing required recommendation field fails validation
- Invalid `action_type` fails validation
- `priority` below 1 fails validation
- `priority` above 5 fails validation
- Malformed LLM JSON is handled safely
- Non-object JSON root is rejected
- Mock provider dict output validated on same path
- Empty-sales fallback passes validation via `run_sales_analysis()`
- Mock LLM JSON output validated through pipeline
- Invalid mock LLM output raises `AgentSchemaValidationError`
- Extra unknown fields rejected
- Validation failure logging uses safe summary (no PII)
- `POST /run` returns validated empty-sales output
- `POST /run` maps validation errors to HTTP 422
- `POST /run` does not expose stack traces

No real LLM providers or Django APIs are called in tests.

---

## Test commands

Run focused schema validation tests:

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_schema_validation -v
```

Run all Sales Agent tests (Steps 7.1–7.3):

```bash
PYTHONPATH=. python -m unittest discover -s agents/sales/tests -p 'test_*.py' -v
```

Run shared schema validation tests:

```bash
PYTHONPATH=. python -m unittest agents.shared.tests.test_schemas_validation -v
```

Run all agent unit tests:

```bash
PYTHONPATH=. python -m unittest discover -s agents -p 'test_*.py' -v
```

---

## What is intentionally not implemented in this step

| Item | Deferred to |
|------|-------------|
| Example output at `docs/examples/sales_output.json` | Step 7.4 |
| Real OpenAI/Anthropic provider integration | Later Phase 7 work |
| Django client fetch wiring for `/run` | Later Phase 7 work |
| LangGraph orchestration | Phase 10 |
| Action persistence to Django | Later Phase 7 work |
| Production service JWT validation on `/run` | Later hardening |

---

## Acceptance checklist

- [x] Dedicated Cursor rule exists at `.cursor/rules/step-7.3-sales-agent-schema-validation.mdc`
- [x] Sales Agent validates every final output before return
- [x] Empty-sales fallback passes the same schema validation gate
- [x] Invalid action types are rejected
- [x] Missing required fields are rejected
- [x] Out-of-range priorities are rejected
- [x] Malformed LLM JSON is handled safely
- [x] No raw invalid LLM output is returned directly
- [x] No PII is logged or exposed in API responses
- [x] Tests cover valid and invalid output cases
- [x] `docs/phases/step-7.3.md` documents the implementation
- [x] Step 7.4 example output doc is not implemented

---

## Next steps

| Step | Focus |
|------|-------|
| **7.4** | Document example output in `docs/examples/sales_output.json` |
