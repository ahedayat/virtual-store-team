# Step 7.6 — Inventory-aware Sales Analysis

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Make inventory and low-stock data a real runtime input to the Sales Agent analysis pipeline so recommendations can be driven by inventory signals — not only prompt text — while remaining schema-valid under `SalesAnalysisResult`.

---

## Inventory signal model

Module: `agents/sales/inventory_signals.py`

| Signal bucket | Source | Used for |
|---------------|--------|----------|
| `low_stock_products` | Django low-stock inventory items | `sales.restock` |
| `slow_moving_products` | Top products with `quantity_sold <= 1` in recent periods | `sales.discount` |
| `overstock_products` | Inventory items not in top sellers with high available quantity | `sales.discount` |
| `promotion_eligible_products` | Union of slow-moving and overstock items | `sales.discount` |

The pipeline builds `inventory_signals` via `build_inventory_signals()` and includes them in the LLM/mock user payload through `build_sales_analysis_payload()`.

---

## Recommendation behavior

- **Non-empty sales path:** inventory signals are passed to the LLM/mock provider alongside sales periods and inventory items.
- **`sales.restock`:** produced when low-stock products are present in inventory signals.
- **`sales.discount`:** produced when slow-moving or promotion-eligible products are present.
- **Empty sales path (Step 7.2):** unchanged — no recommendations are emitted when sales periods are empty, even if inventory exists.
- Allowed action types remain: `sales.restock`, `sales.discount`, `sales.follow_up`.

Mock provider behavior in `agents/shared/llm/mock.py` was updated to honor `inventory` and `inventory_signals` in the user payload.

---

## Files changed

| File | Change |
|------|--------|
| `agents/sales/inventory_signals.py` | Signal model and analysis payload builder |
| `agents/sales/analysis.py` | Passes inventory-aware payload to LLM path |
| `agents/shared/llm/mock.py` | Inventory-aware deterministic recommendations |
| `agents/sales/tests/test_inventory_signals.py` | Signal and pipeline influence tests |

---

## Test coverage

- Low-stock products identified in signal model
- Slow-moving products identified from sales top products
- Analysis payload includes `inventory_signals`
- Low stock produces `sales.restock` recommendation
- Slow movers produce `sales.discount` recommendation
- Mock LLM user payload contains inventory signals

---

## Verification commands

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_inventory_signals -v
PYTHONPATH=. python -m unittest discover -s agents/sales/tests -p 'test_*.py' -v
```
