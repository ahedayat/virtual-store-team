# Sales Agent APIs

APIs required by the **Sales Agent** for sales performance analysis, inventory alerts, and recommendations.

## Agent summary

The Sales Agent (`agents/sales/`) produces `SalesAnalysisResult` with recommendations:

- `sales.restock` — low stock / high demand
- `sales.discount` — discount candidates
- `sales.follow_up` — follow-up opportunities

Priority rubric 1 (urgent) to 5 (informational) (`agents/sales/prompts.py`). Coordinator passes `sales_summary` and `inventory` from context bundle with `fetch_from_django: False` (`agents/coordinator/nodes.py`).

**Sales summary, best sellers, low-stock insights, discount candidates, and recommendations are computed inside Botkonak** from raw Prestia order and product data — Prestia does not expose a sales summary API.

## Data flow

```
GET /v1/orders + GET /v1/products (on demand)
       ↓
Botkonak aggregates sales summary + inventory signals locally
       ↓
Context bundle → Sales Agent POST /run
```

Timezone and currency for period boundaries come from **Botkonak tenant settings**, not Prestia ([02-store-profile-apis.md](./02-store-profile-apis.md)).

## Required Prestia APIs

| Prestia API | Sales Agent input | Priority |
|-------------|-------------------|----------|
| [GET /v1/orders](./04-order-and-sales-apis.md) | Raw orders for sales aggregation | P0 |
| [GET /v1/products](./03-product-and-inventory-apis.md) | Product titles, `inventories[]` for stock signals | P0 |

## Sales summary (computed by Botkonak)

Botkonak builds `sales_summary.today` and `sales_summary.last_7_days` from `GET /v1/orders` using store timezone from tenant settings (`backend/catalog/services.py`).

| Period field | Source |
|--------------|--------|
| `total_revenue` | Sum of revenue-countable order `total` |
| `order_count` | Count of revenue-countable orders |
| `units_sold` | Sum of `items[].quantity` |
| `average_order_value` | `total_revenue / order_count` |
| `top_products[]` | Grouped by `items[].product_slug` |

Each `top_products` item (computed locally):

| Field | Source |
|-------|--------|
| `product_slug` | Order line item |
| `name` | `items[].product_name` |
| `quantity_sold` | Aggregated quantity |
| `revenue` | Aggregated `line_total` |
| `category` | From matching product in `/v1/products` |

## Inventory fields used

From product `inventories[]` on [GET /v1/products](./03-product-and-inventory-apis.md):

| Field | Usage |
|-------|-------|
| `slug`, `title` | Restock recommendations |
| `inventories[].num` | Stockout risk |
| `inventories[].metadata` | Variant context |
| `category.title` | Grouping in LLM payload |

## Signal types built internally

| Signal | Source | Prestia API |
|--------|--------|-------------|
| Low stock products | `inventories[].num` below threshold | `GET /v1/products` |
| High sellers with low stock | Cross-reference top products + inventories | Orders + products |
| Slow movers | LLM from weak top products | Orders (computed) |
| Discount candidates | LLM from sales trends + inventory | Orders + products |

## Empty sales behavior

If both `today` and `last_7_days` have zero revenue and zero orders, agent skips LLM (`agents/sales/empty_sales.py`). Botkonak aggregation must return numeric zeros, not omit periods.

## Optional Prestia APIs

| API | Why | Priority |
|-----|-----|----------|
| [GET /v1/customer/{id}/orders](./05-customer-apis.md) | Customer purchase history for follow-up | P1 |
| Abandoned cart / `status=draft` orders | Mock UI follow-up only | Future |

## APIs NOT required

| API | Reason |
|-----|--------|
| `GET /v1/sales/summary` | Computed by Botkonak from orders |
| `GET /v1/store` | Timezone/currency in Botkonak tenant settings |
| `GET /v1/inventory/low-stock` | Stock data in product `inventories[]` |

## Write APIs (not required)

Sales agent can `persist_actions` to Django `POST /internal/ai/actions/` when enabled. **No Prestia write** for discounts or restock exists.

## Evidence from codebase

| File | Relevance |
|------|-----------|
| `agents/sales/analysis.py` | Main pipeline |
| `agents/sales/django_fetch.py` | Django fetch pattern (maps to Prestia equivalents) |
| `agents/sales/inventory_signals.py` | Signal construction |
| `agents/sales/empty_sales.py` | Empty sales handling |
| `agents/sales/prompts.py` | Priority rubric |
| `backend/catalog/services.py` | Aggregation logic |
| `docs/agents/sales.md` | Agent documentation |

## Open questions

1. Whether Prestia can flag "discount-eligible" products natively vs LLM inference.
2. Real-time inventory accuracy during high-traffic periods.
3. Low-stock threshold — Botkonak tenant setting vs Prestia metadata.
