# Step 7.5 — Django Sales/Inventory Data Fetching

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Wire the Sales Agent to fetch sales and inventory data from Django internal APIs using the shared `DjangoClient`, merge that data with caller-supplied context deterministically, and preserve the Step 7.2 empty-sales bypass when there is no meaningful sales signal.

---

## Files changed

| File | Change |
|------|--------|
| `agents/shared/django_client/client.py` | Added `get_sales_summary()` and `get_low_stock_inventory()` helpers |
| `agents/sales/sales_context.py` | Context extraction, normalization, and merge rules |
| `agents/sales/django_fetch.py` | Django fetch with failure fallback warnings |
| `agents/sales/analysis.py` | Integrated fetch/merge into `run_sales_analysis()` |
| `agents/sales/app/schemas.py` | Added `store_id`, `inventory`, `fetch_from_django`, `service_token` |
| `agents/sales/tests/test_django_fetch.py` | Fetch, merge, empty-sales, and client path tests |

---

## Runtime behavior

1. When `fetch_from_django=True`, the pipeline calls:
   - `GET /internal/ai/stores/{store_id}/sales/summary/`
   - `GET /internal/ai/stores/{store_id}/inventory/low-stock/`
2. Django responses are normalized into the same flat shapes used by coordinator context bundles.
3. Caller-supplied `context`, `sales_summary`, and `inventory` are merged using deterministic rules documented in `agents/sales/sales_context.py`:
   - Django data forms the base.
   - Explicit `sales_summary` / `inventory` arguments override bundle sections.
   - Caller `inventory.items` merge by SKU/product_id; caller wins duplicates.
4. Empty-sales detection (Step 7.2) still runs on the merged sales summary only. If both periods are empty, the deterministic fallback is returned and the LLM is not called — even when inventory data exists.
5. Django fetch failures add a warning with code `django_fetch_failed` and continue with caller context only.

---

## Test coverage

`agents/sales/tests/test_django_fetch.py`:

- Successful Django sales/inventory fetch
- Empty/no-data deterministic result without LLM call
- Django client failure fallback warning
- Caller context combined with Django-fetched context
- Shared client helper endpoint paths

---

## Verification commands

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_django_fetch -v
PYTHONPATH=. python -m unittest discover -s agents/sales/tests -p 'test_*.py' -v
```

---

## Known limitations

- Only sales summary and low-stock inventory endpoints are fetched. Full AI context bundles and product catalogs are not fetched directly in this step.
- Slow-moving/overstock heuristics are derived in Step 7.6 from merged sales + inventory data; Django does not expose a dedicated slow-mover endpoint yet.
- `/run` requires `service_token` or `Authorization: Bearer ...` when `fetch_from_django=True`.
