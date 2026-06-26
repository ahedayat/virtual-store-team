# Step 7.7 — Sales Action Mapping

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Map validated Sales Agent recommendations to Django-compatible action payloads following the Content Agent action-mapping pattern.

---

## Mapping rules

Module: `agents/sales/action_mapping.py`

| Function | Purpose |
|----------|---------|
| `map_sales_recommendation_to_action_payload()` | Map one recommendation |
| `map_sales_analysis_to_actions()` | Map all recommendations in a result |
| `persist_sales_actions()` | POST mapped actions via Django client (Step 7.8) |

Each mapped action body includes:

- `action_type`
- `title`
- `description`
- `priority`
- `requires_approval: true`
- `payload` (with recommendation rationale copied into inner payload)
- optional `report_run_id`

---

## Supported action types

| `action_type` | Required inner payload fields |
|---------------|-------------------------------|
| `sales.restock` | `sku` |
| `sales.discount` | `sku` |
| `sales.follow_up` | `follow_up_reason` (or legacy `reason`) |

---

## Validation behavior

- Unsupported `action_type` values raise `SalesActionMappingError`.
- Missing/blank `title`, `description`, or `rationale` raise `SalesActionMappingError`.
- Non-integer or out-of-range `priority` values raise `SalesActionMappingError`.
- Missing required inner payload fields raise `SalesActionMappingError` deterministically.

---

## Files changed

| File | Change |
|------|--------|
| `agents/sales/action_mapping.py` | Mapping and persistence helpers |
| `agents/sales/tests/test_action_mapping.py` | Mapping validation tests |

---

## Test coverage

- Valid restock mapping
- Valid discount mapping
- Valid follow-up mapping
- Unsupported action type rejection
- Missing required payload field rejection
- Report run ID propagation from result metadata

---

## Verification commands

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_action_mapping -v
PYTHONPATH=. python -m unittest discover -s agents/sales/tests -p 'test_*.py' -v
```
