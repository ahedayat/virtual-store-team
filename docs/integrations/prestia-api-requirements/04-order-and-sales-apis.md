# Order and Sales APIs

APIs for orders, sales metrics, revenue, best sellers, and time-based sales analysis.

---

## API: Get Sales Summary

| Property | Value |
|----------|-------|
| **API name** | Get Sales Summary |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/sales/summary` |
| **Botkonak consumer** | Sales Agent, Coordinator Agent, Background sync |
| **Why Botkonak needs this** | Primary input for sales analysis. Aggregates revenue, order counts, units sold, AOV, and top products for **today** and **last 7 days** in store timezone. Empty sales → deterministic empty result without LLM (`agents/sales/empty_sales.py`). |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Required request headers

`Authorization: Bearer <access_token>`, `Accept: application/json`

### Query parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `reference_at` | ISO datetime | No | Compute periods relative to this instant (default: now). Botkonak uses server `timezone.now()` in `build_sales_summary`. |
| `top_products_limit` | integer | No | Default `5` — matches `_serialize_period` |

### Path parameters

None.

### Request body

Not applicable.

### Successful response shape

```json
{
  "generated_at": "2026-06-25T14:30:00+00:00",
  "store_id": "22222222-2222-2222-2222-222222222222",
  "currency": "USD",
  "periods": {
    "today": {
      "from": "2026-06-25T04:00:00+00:00",
      "to": "2026-06-26T04:00:00+00:00",
      "total_revenue": "318.00",
      "order_count": 2,
      "units_sold": 4,
      "average_order_value": "159.00",
      "top_products": [
        {
          "product_id": "33333333-3333-3333-3333-333333333333",
          "name": "Milano Leather Tote",
          "sku": "PRS-TOTE-001",
          "quantity_sold": 1,
          "revenue": "189.00",
          "category": "Handbags"
        }
      ]
    },
    "last_7_days": {
      "from": "2026-06-19T04:00:00+00:00",
      "to": "2026-06-26T04:00:00+00:00",
      "total_revenue": "892.00",
      "order_count": 6,
      "units_sold": 12,
      "average_order_value": "148.67",
      "top_products": []
    }
  }
}
```

**Context bundle mapping:** Botkonak maps `periods.today` → `sales_summary.today`, `periods.last_7_days` → `sales_summary.last_7_days` (`backend/catalog/context.py`).

### Important fields

| Field | Usage |
|-------|-------|
| `total_revenue` | Sum of `total_amount` for revenue-countable orders |
| `order_count` | Count of revenue-countable orders in period |
| `units_sold` | Sum of `OrderItem.quantity` |
| `average_order_value` | `total_revenue / order_count` (0 if no orders) |
| `top_products` | Best sellers by revenue then quantity — discount/slow-mover signals |

### Revenue-countable order statuses

Only orders in `paid`, `completed`, or `fulfilled` status (`REVENUE_COUNTABLE_ORDER_STATUSES` in `catalog/models.py`).

### Pagination

`top_products` is a bounded list (default 5 per period).

### Error cases

`401`, `403`, `500`

### Example request

```http
GET /v1/sales/summary?top_products_limit=5 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

### Related files

- `backend/catalog/services.py` — `build_sales_summary`, `_serialize_period`, `get_period_bounds`
- `backend/catalog/internal_views.py` — `InternalSalesSummaryView`
- `agents/sales/django_fetch.py` — `get_sales_summary`
- `agents/sales/empty_sales.py` — empty detection
- `agents/sales/inventory_signals.py` — cross-reference top products with inventory
- `docs/phases/step-3.2.md`

---

## API: List Orders

| Property | Value |
|----------|-------|
| **API name** | List Orders |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/orders` |
| **Botkonak consumer** | Background sync |
| **Why Botkonak needs this** | Botkonak computes sales summary from `Order` + `OrderItem` rows locally. Connector needs order data to populate Django if Prestia does not provide pre-aggregated summary, or for reconciliation. |
| **Requirement type** | Inferred |
| **Priority** | P1 |

### Query parameters

| Parameter | Description |
|-----------|-------------|
| `status` | Filter by order status |
| `placed_at_gte`, `placed_at_lt` | Date range (store timezone aware) |
| `updated_since` | Incremental sync |
| `limit`, `offset` | Pagination |

### Successful response shape

```json
{
  "count": 8,
  "results": [
    {
      "id": "88888888-8888-8888-8888-888888888888",
      "external_id": "prestia-ord-001",
      "order_number": "PRS-ORD-001",
      "status": "paid",
      "currency": "USD",
      "subtotal_amount": "247.00",
      "discount_amount": "0.00",
      "total_amount": "247.00",
      "placed_at": "2026-06-25T14:00:00+00:00",
      "external_customer_ref": "demo-cust-001",
      "items": [
        {
          "product_id": "33333333-3333-3333-3333-333333333333",
          "product_name_snapshot": "Milano Leather Tote",
          "sku_snapshot": "PRS-TOTE-001",
          "quantity": 1,
          "unit_price": "189.00",
          "line_total": "189.00"
        }
      ],
      "metadata": {},
      "created_at": "2026-06-25T14:00:00+00:00",
      "updated_at": "2026-06-25T14:05:00+00:00"
    }
  ]
}
```

### Important fields

Maps to `Order` and `OrderItem` in `backend/catalog/models.py`.

### Related files

- `backend/catalog/models.py` — `Order`, `OrderItem`, `OrderStatus`
- `seed_prestia.py` — `PRESTIA_ORDERS`

---

## API: Get Order Detail

| Property | Value |
|----------|-------|
| **API name** | Get Order Detail |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/orders/{order_id}` |
| **Botkonak consumer** | Support Agent |
| **Why Botkonak needs this** | Support threads reference order numbers (e.g. `PRS-ORD-001` in seed messages). Agent does not fetch order details today but may need them for order-status replies. |
| **Requirement type** | Inferred |
| **Priority** | P2 |

### Path parameters

`order_id` — Prestia order UUID or `order_number` lookup (Prestia to define).

### Successful response

Single order object with `items` array.

### Related files

- `seed_prestia.py` — `prestia-thread-order-followup` message references `PRS-ORD-001`
- `agents/support/refusal.py` — order mutation requests refused (read-only still useful)

---

## Abandoned / pending orders

| Property | Value |
|----------|-------|
| **API name** | List Draft or Pending Orders |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/orders?status=draft,pending` |
| **Botkonak consumer** | Sales Agent |
| **Why Botkonak needs this** | Mock UI shows "abandoned cart" follow-up (`frontend/types/mock-data.ts`). **No backend implementation** uses abandoned-cart data. Sales agent `sales.follow_up` action type exists but is LLM-driven from sales/inventory context only. |
| **Requirement type** | Optional (Future) |
| **Priority** | Future |

---

## Slow movers and discount candidates

No dedicated Prestia API is required by current code. The Sales Agent infers:

- **Discount candidates** — from low sales velocity in `top_products` + inventory signals (`agents/sales/inventory_signals.py`, `agents/sales/prompts.py`)
- **Slow movers** — LLM interpretation of sales summary (not a separate API)

**Requirement type:** Optional — pre-computed analytics endpoint would be Future/P2.

---

## Evidence from codebase

See per-API sections.

## Open questions

1. Whether Prestia provides aggregated `GET /sales/summary` or Botkonak must compute from raw orders.
2. Abandoned cart data availability in Prestia.
3. Order status mapping from Prestia native states to Botkonak enum.
