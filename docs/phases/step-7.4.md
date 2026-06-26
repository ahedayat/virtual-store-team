# Step 7.4 — Document Example Sales Agent Output

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Publish a canonical, schema-valid example of Sales Agent output so integrators, reviewers, and future agent work can reference a stable contract without calling the live service or an LLM.

This step is documentation and contract-focused. It does not add new sales analysis heuristics, coordinator wiring, or action execution.

---

## Scope of this step

- Canonical example file: `docs/examples/sales_output.json`
- Focused validation test: `agents/sales/tests/test_sales_output_example.py`
- Cursor scope rule: `.cursor/rules/step-7.4-sales-output-example.mdc`
- This documentation file

**Not in scope:** Phase 8, Content Agent, Support Agent, Coordinator/LangGraph integration, Django action persistence, real external action execution, Prestia-specific hardcoding, or schema redesign.

---

## Files changed

| File | Change |
|------|--------|
| `docs/examples/sales_output.json` | Created — canonical Sales Agent output example |
| `agents/sales/tests/test_sales_output_example.py` | Created — loads and validates the example file |
| `.cursor/rules/step-7.4-sales-output-example.mdc` | Step 7.4 scope rule |
| `docs/phases/step-7.4.md` | Created — this document |

**Reused unchanged modules:** `agents/shared/schemas/sales.py` (`SalesAnalysisResult`, `SalesRecommendation`), `agents/shared/schemas/validation.py` (`validate_agent_response`), `agents/sales/validation.py` (`validate_sales_analysis_output`).

---

## Purpose of `docs/examples/sales_output.json`

The example file is the human-readable reference for what a successful Sales Agent response looks like after Steps 7.1–7.3:

- It shows the full response envelope (`metadata`, `summary`, `insights`, `recommendations`, `warnings`).
- It demonstrates realistic `sales.restock` and `sales.discount` recommendations with priority, rationale, and structured payloads.
- It uses only generic demo SKUs and placeholder UUIDs — no raw PII or claims that actions were executed.
- It must stay in sync with the runtime schema; the Step 7.4 test fails if the file drifts.

The Sales Agent **recommends** actions only. The example wording describes proposed next steps, not completed approvals, queueing, publishing, or external mutations.

---

## Schema / model used for validation

| Model | Module | Purpose |
|-------|--------|---------|
| `SalesAnalysisResult` | `agents/shared/schemas/sales.py` | Top-level Sales Agent response envelope |
| `SalesRecommendation` | `agents/shared/schemas/sales.py` | Nested recommendation shape |
| `SalesActionType` | `agents/shared/schemas/sales.py` | Allowed `action_type` literals |
| `BaseAgentResponse` | `agents/shared/schemas/base.py` | Shared `metadata` and `warnings` fields |
| `validate_agent_response` | `agents/shared/schemas/validation.py` | Shared strict validator (Step 6.3) |
| `validate_sales_analysis_output` | `agents/sales/validation.py` | Sales-specific wrapper used by runtime and tests |

Schemas use `extra="forbid"` via `StrictAgentModel` (Step 6.3). Unknown fields at any level are rejected.

### `SalesAnalysisResult` fields

| Field | Required | Notes |
|-------|----------|-------|
| `metadata` | Yes | Includes `agent_name`; optional `report_run_id` |
| `summary` | Yes | Manager-facing analysis summary |
| `insights` | No | List of non-PII observations (default `[]`) |
| `recommendations` | No | List of `SalesRecommendation` (default `[]`) |
| `warnings` | No | List of `AgentWarning` (default `[]`) |

---

## Recommendation fields

Every recommendation in the example includes:

| Field | Type | Rules |
|-------|------|-------|
| `priority` | `int` | Integer from **1** (highest urgency) to **5** (informational) |
| `action_type` | `string` | One of the allowed literals below |
| `title` | `string` | Short manager-facing headline |
| `description` | `string` | Concise summary of the proposed action |
| `rationale` | `string` | Non-PII explanation of priority and action choice |
| `payload` | `object` | Action-specific structured data (may be `{}`) |

### Allowed action types

- `sales.restock`
- `sales.discount`
- `sales.follow_up`

### Priority rules

| Value | Meaning |
|-------|---------|
| **1** | Highest urgency / greatest business impact |
| **2** | High priority |
| **3** | Medium priority |
| **4** | Low priority / monitor |
| **5** | Informational / lowest urgency |

Validation rejects `priority < 1`, `priority > 5`, and non-integer values.

### Example recommendation (from `docs/examples/sales_output.json`)

```json
{
  "priority": 2,
  "action_type": "sales.restock",
  "title": "Restock: SKU-DEMO-001",
  "description": "Reorder the top-selling SKU before projected stockout.",
  "rationale": "On-hand units are below the seven-day sales velocity threshold. Restocking reduces lost-revenue risk using aggregate sales signals only.",
  "payload": {
    "product_id": "00000000-0000-4000-8000-000000000001",
    "sku": "SKU-DEMO-001",
    "current_stock": 3,
    "suggested_order_qty": 24,
    "days_of_cover": 2
  }
}
```

---

## PII-safety constraints

The example must remain safe for documentation and CI:

- No phone numbers, emails, or postal addresses
- No customer full names or payment details
- No raw Instagram or other external platform identifiers
- No raw message text from customers
- Use generic SKUs and placeholder UUIDs only when IDs are needed
- Do not imply that recommendations were already executed

---

## Example validation test

`agents/sales/tests/test_sales_output_example.py`:

- Loads `docs/examples/sales_output.json` from the repository root
- Parses JSON and fails on malformed content
- Validates the payload with `validate_sales_analysis_output()` (same gate as Step 7.3)
- Asserts at least one recommendation is present
- Asserts at least one recommendation uses `sales.restock` or `sales.discount`
- Asserts each recommendation has required fields and allowed `action_type` / `priority` values

No real LLM providers or Django APIs are called.

---

## How to run the validation test

Run the focused Step 7.4 test:

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_sales_output_example -v
```

Run Sales Agent schema tests (Step 7.3):

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_schema_validation -v
```

Run all Sales Agent tests (Steps 7.1–7.4):

```bash
PYTHONPATH=. python -m unittest discover -s agents/sales/tests -p 'test_*.py' -v
```

---

## Integration with prior steps

| Step | Integration |
|------|-------------|
| **6.3** | Example validates through `validate_agent_response` with strict `extra="forbid"` |
| **7.1** | Example reflects prompt/rubric fields (`priority`, `action_type`, rationale, payload) |
| **7.2** | Example represents a realistic non-empty analysis (not the empty-sales fallback) |
| **7.3** | Example uses the same `SalesAnalysisResult` schema and validation wrapper as runtime |

---

## What is intentionally not implemented in this step

| Item | Deferred to |
|------|-------------|
| Content Agent example output | Phase 8 |
| Support Agent example output | Phase 9 |
| Coordinator / LangGraph orchestration | Phase 10 |
| Django action persistence or execution | Later phases |
| New sales analysis business logic | Out of scope for 7.4 |
| Real LLM provider wiring for `/run` | Later Phase 7 work |
| Prestia-specific demo data or rules | Never in agent code |

---

## Acceptance checklist

- [x] Dedicated Cursor rule exists at `.cursor/rules/step-7.4-sales-output-example.mdc`
- [x] `docs/examples/sales_output.json` exists
- [x] Example JSON is valid JSON with no comments or markdown fences
- [x] Example validates against `SalesAnalysisResult`
- [x] Example contains at least one valid sales recommendation
- [x] Recommendations include `priority`, `action_type`, `title`, `description`, `rationale`, and `payload`
- [x] Example uses only allowed `sales.*` action types
- [x] Example contains no raw PII and does not claim executed actions
- [x] Focused test validates the example file against the schema
- [x] `docs/phases/step-7.4.md` documents the step
