# Step 7.2 — Handle Empty Sales Gracefully

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Handle empty or zero-sales input in the Sales Agent with a deterministic, schema-valid fallback that avoids LLM calls, prevents hallucinated recommendations, and returns a conservative manager-facing summary.

This step adds empty-sales detection and fallback only. It does not implement the full Phase 7 pipeline, non-empty LLM analysis, or schema validation before return.

---

## Scope of this step

- Sales analysis schemas: `agents/shared/schemas/sales.py`
- Empty-sales helpers: `agents/sales/empty_sales.py`
- Analysis entry point with LLM bypass: `agents/sales/analysis.py`
- Focused unit tests: `agents/sales/tests/test_empty_sales.py`
- Cursor scope rule: `.cursor/rules/step-7.2-sales-agent-empty-sales.mdc`
- This documentation file

**Not in scope:** Step 7.3 (full JSON schema validation before return), Step 7.4 (`docs/examples/sales_output.json`), FastAPI `/run`, Django fetch wiring, non-empty LLM analysis, LangGraph, coordinator changes, or Prestia-specific business logic.

---

## Files changed

| File | Change |
|------|--------|
| `agents/shared/schemas/sales.py` | Created — `SalesRecommendation`, `SalesAnalysisResult` |
| `agents/shared/schemas/__init__.py` | Updated — export sales schemas |
| `agents/sales/empty_sales.py` | Created — detection and deterministic fallback |
| `agents/sales/analysis.py` | Created — `run_sales_analysis()` with empty-sales bypass |
| `agents/sales/tests/test_empty_sales.py` | Created — empty-sales unit tests |
| `.cursor/rules/step-7.2-sales-agent-empty-sales.mdc` | Updated — Step 7.2 scope rule |
| `docs/phases/step-7.2.md` | Created — this document |

---

## Definition of empty sales

Sales input is treated as **empty** when there is no evidence of completed orders in any known period (`today`, `last_7_days`).

A single period is empty when **all** of the following are true:

| Signal | Empty when |
|--------|------------|
| `order_count` | missing, null, or `0` |
| `total_revenue` | missing, null, or zero |
| `top_products` | missing or an empty list |

Overall sales context is empty when:

- `sales_summary` is missing or null;
- the context bundle has no extractable sales section;
- **both** `today` and `last_7_days` are empty by the rules above;
- the Django sales API returns an empty but valid payload (for example `EMPTY_SALES_SUMMARY`).

Supported input shapes:

- Context bundle: `{"sales_summary": {"today": {...}, "last_7_days": {...}}}`
- Flat summary: `{"today": {...}, "last_7_days": {...}}`
- API summary: `{"periods": {"today": {...}, "last_7_days": {...}}}`

If **either** period has orders, revenue, or top products, the context is **not** empty and this step does not produce a fallback (non-empty analysis is deferred).

---

## Empty-sales detection API

Module: `agents/sales/empty_sales.py`

| Symbol | Description |
|--------|-------------|
| `normalize_sales_summary(sales_summary)` | Normalize API/context sales shapes into flat periods |
| `extract_sales_summary(data)` | Pull `sales_summary` from a context bundle or raw payload |
| `is_empty_sales_period(period)` | True when one period has no sales evidence |
| `is_empty_sales_context(sales_data)` | True when all known periods are empty |
| `build_empty_sales_result(...)` | Build deterministic `SalesAnalysisResult` |
| `handle_empty_sales(...)` | Return fallback result when empty; otherwise `None` |

Analysis entry point: `agents/sales/analysis.py`

| Symbol | Description |
|--------|-------------|
| `run_sales_analysis(...)` | Returns deterministic fallback for empty sales; bypasses LLM |

---

## Fallback behavior

When sales data is empty:

1. `run_sales_analysis()` calls `handle_empty_sales()` before any LLM provider.
2. A deterministic `SalesAnalysisResult` is returned.
3. No LLM provider is invoked.
4. No sales metrics, trends, SKU velocity, or customer behavior are fabricated.
5. `recommendations` is an empty list.
6. `insights` is an empty list.
7. `warnings` is an empty list unless a later step adds safe operational warnings.

Summary messages respect `AI_OUTPUT_LANGUAGE`:

| Language | Summary |
|----------|---------|
| `fa` (default) | در این بازه زمانی فروشی ثبت نشده است. |
| `en` | No sales were recorded for this period. |

---

## Expected output shape

`SalesAnalysisResult` (extends `BaseAgentResponse`):

| Field | Empty-sales value |
|-------|-------------------|
| `metadata.agent_name` | `"sales-agent"` |
| `metadata.report_run_id` | caller-provided ID or `null` |
| `summary` | localized no-sales message |
| `insights` | `[]` |
| `recommendations` | `[]` |
| `warnings` | `[]` |

Example (English):

```json
{
  "metadata": {
    "agent_name": "sales-agent",
    "report_run_id": "run-empty-1"
  },
  "summary": "No sales were recorded for this period.",
  "insights": [],
  "recommendations": [],
  "warnings": []
}
```

---

## Recommendation policy in no-sales scenarios

- Do **not** emit `sales.restock` only because inventory is low or sales data is missing.
- Do **not** emit `sales.discount` without evidence of underperformance.
- Do **not** emit `sales.follow_up` without sanitized, API-provided support/sales context.
- Low stock without sales velocity must **not** be treated as urgent in this step.
- Empty-sales output is useful but conservative: a clear summary and no speculative actions.

---

## PII and logging constraints

- Do not include raw phone numbers, emails, addresses, customer names, payment details, or external raw identifiers in outputs.
- Do not log full context payloads.
- Use only sanitized data from Django APIs or the existing context object.
- Do not execute actions directly or claim that an action has been executed.

---

## Tests added

`agents/sales/tests/test_empty_sales.py` (stdlib `unittest`):

- Zero `order_count` is detected as empty
- Zero or missing `total_revenue` is detected as empty
- Missing or null sales summary is empty
- Empty `top_products` with no other signals is empty
- Partially missing optional fields still treated as empty
- Valid `SalesAnalysisResult` shape via Pydantic validation
- `recommendations` is empty for no-sales cases
- No fabricated revenue, SKU velocity, or demand language in fallback output
- Persian and English summary messages
- LLM provider is not called when deterministic fallback is used
- API `periods` shape is supported
- Non-empty `last_7_days` prevents empty fallback

No real LLM providers or Django APIs are called in tests.

---

## Validation commands

Run focused empty-sales tests:

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_empty_sales -v
```

Run all Sales Agent tests (Step 7.1 + 7.2):

```bash
PYTHONPATH=. python -m unittest discover -s agents/sales/tests -p 'test_*.py' -v
```

Run all agent unit tests:

```bash
PYTHONPATH=. python -m unittest discover -s agents -p 'test_*.py' -v
```

---

## What is intentionally not implemented in this step

| Item | Deferred to |
|------|-------------|
| Non-empty sales LLM analysis | Later Phase 7 pipeline |
| Full JSON schema validation before return | Step 7.3 |
| Example output at `docs/examples/sales_output.json` | Step 7.4 |
| FastAPI `/run` on `sales-agent` | Later Phase 7 work |
| Django client fetch wiring | Later Phase 7 work |
| Action persistence to Django | Later Phase 7 work |
| Restock/discount/follow-up from low stock alone | Requires sales evidence in later steps |

---

## Acceptance checklist

- [x] Dedicated Cursor rule exists at `.cursor/rules/step-7.2-sales-agent-empty-sales.mdc`
- [x] Empty or zero-sales input returns a valid `SalesAnalysisResult`
- [x] Sales Agent does not crash on missing or empty sales fields
- [x] No hallucinated recommendations in empty-sales cases
- [x] Empty-sales output is conservative and useful
- [x] Deterministic empty-sales fallback avoids LLM calls
- [x] Unit tests cover empty-sales scenarios
- [x] `docs/phases/step-7.2.md` documents the behavior
- [x] Step 7.3 validation and Step 7.4 example output doc are not implemented

---

## Next steps

| Step | Focus |
|------|-------|
| **7.3** | Validate Sales Agent JSON output against schema before return |
| **7.4** | Document example output in `docs/examples/sales_output.json` |
