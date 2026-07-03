# Sales Agent APIs

APIs required by the **Sales Agent** for sales performance analysis, inventory alerts, and recommendations.

## Agent summary

The Sales Agent (`agents/sales/`) produces `SalesAnalysisResult` with recommendations:

- `sales.restock` — low stock / high demand
- `sales.discount` — discount candidates
- `sales.follow_up` — follow-up opportunities

Priority rubric 1 (urgent) to 5 (informational) (`agents/sales/prompts.py`). Coordinator passes `sales_summary` and `inventory` from context bundle with `fetch_from_django: False` (`agents/coordinator/nodes.py`).

## Data flow

```
Prestia GET /sales/summary + GET /inventory/low-stock
       ↓
Botkonak sync / connector
       ↓
Context bundle → Sales Agent POST /run
```

Optional direct path (implemented but disabled by coordinator): Sales Agent `fetch_from_django=True` calls Django internal endpoints (`agents/sales/django_fetch.py`).

## Required Prestia APIs

| Prestia API | Sales Agent input | Priority |
|-------------|-------------------|----------|
| [GET /v1/sales/summary](./04-order-and-sales-apis.md) | `sales_summary.today`, `sales_summary.last_7_days` | P0 |
| [GET /v1/inventory/low-stock](./03-product-and-inventory-apis.md) | `inventory.items` | P0 |
| [GET /v1/products](./03-product-and-inventory-apis.md) | Product names/SKUs for cross-reference | P0 (via sync) |
| [GET /v1/store](./02-store-profile-apis.md) | `currency`, `timezone` for period boundaries | P0 |

## Sales summary fields used

From `agents/sales/empty_sales.py`, `agents/sales/inventory_signals.py`:

| Period field | Usage |
|--------------|-------|
| `total_revenue` | Empty sales detection |
| `order_count` | Empty sales detection |
| `units_sold` | Demand signals |
| `average_order_value` | Insights |
| `top_products[]` | Best sellers; cross-ref with inventory for restock/discount |

Each `top_products` item:

| Field | Usage |
|-------|-------|
| `product_id` | Recommendation `payload` |
| `sku` | Recommendation `payload` |
| `name` | Titles and descriptions |
| `quantity_sold` | Velocity |
| `revenue` | Prioritization |
| `category` | Context |

## Inventory fields used

From `build_low_stock_summary` / `agents/sales/inventory_signals.py`:

| Field | Usage |
|-------|-------|
| `product_id`, `sku`, `product_name` | Restock recommendations |
| `available_quantity` | Stockout risk |
| `low_stock_threshold` | Alert boundary |
| `shortage_units` | Urgency sizing |
| `suggested_reorder_quantity` | `payload.suggested_order_qty` |
| `category` | Grouping in LLM payload |

## Signal types built internally

| Signal | Source | Prestia API |
|--------|--------|-------------|
| Low stock products | `inventory.items` | `GET /inventory/low-stock` |
| High sellers with low stock | Cross-reference `top_products` + inventory | Summary + low-stock |
| Slow movers | LLM from weak `top_products` / sales | Summary (no dedicated API) |
| Discount candidates | LLM from sales trends + inventory | Summary (no dedicated API) |

## Empty sales behavior

If both `today` and `last_7_days` have zero revenue and zero orders, agent skips LLM (`agents/sales/empty_sales.py`). Prestia must return numeric zeros, not omit periods.

## Optional Prestia APIs

| API | Why | Priority |
|-----|-----|----------|
| `GET /v1/orders` | Recompute summary locally; reconcile Prestia vs Botkonak | P1 |
| `GET /v1/inventory` | Full stock levels beyond low-stock | P1 |
| Abandoned cart / `status=draft` orders | Mock UI follow-up only | Future |

## Write APIs (not required)

Sales agent can `persist_actions` to Django `POST /internal/ai/actions/` when enabled. **No Prestia write** for discounts or restock exists.

`agents/sales/action_mapping.py` maps to internal actions only.

## Evidence from codebase

| File | Relevance |
|------|-----------|
| `agents/sales/analysis.py` | Main pipeline |
| `agents/sales/django_fetch.py` | Django fetch pattern (maps to Prestia equivalents) |
| `agents/sales/inventory_signals.py` | Signal construction |
| `agents/sales/empty_sales.py` | Empty sales handling |
| `agents/sales/prompts.py` | Priority rubric |
| `backend/catalog/services.py` | Aggregation logic Prestia should mirror |
| `docs/agents/sales.md` | Agent documentation |
| `docs/examples/sales_output.json` | Output contract |

## Open questions

1. Whether Prestia can flag "discount-eligible" products natively vs LLM inference.
2. Real-time inventory reservation accuracy during high-traffic periods.
