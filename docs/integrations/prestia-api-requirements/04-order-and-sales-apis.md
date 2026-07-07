# Order and Sales APIs

APIs for orders and raw sales data. **Sales summaries, best sellers, low-stock insights, discount candidates, and sales recommendations are computed by Botkonak's Sales Agent** from orders and product/inventory data — Prestia does not expose a sales summary API.

---

## API: List Orders

| Property | Value |
|----------|-------|
| **API name** | List Orders |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/orders` |
| **Botkonak consumer** | Sales Agent, Coordinator Agent, on-demand fetch |
| **Why Botkonak needs this** | Botkonak computes sales summary, best sellers, and recommendation signals from `Order` + line items locally (`backend/catalog/services.py`). Raw order data is the Prestia source of truth for sales analysis. |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Required request headers

`Authorization: Bearer <access_token>`, `Accept: application/json`

### Query parameters — pagination

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | Yes | Page size (default 50, max 100) |
| `offset` | integer | Yes | Pagination offset (default 0) |

### Query parameters — filters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `created_at_from` | datetime | No | Order date range start (inclusive) |
| `created_at_to` | datetime | No | Order date range end (inclusive) |
| `customer_id` | string | No | Filter by customer |
| `product_slug` | string | No | Orders containing this product |
| `total_min` | number | No | Minimum order `total` (inclusive) |
| `total_max` | number | No | Maximum order `total` (inclusive) |
| `status` | string | No | Filter by order status |

### Path parameters

None.

### Request body

Not applicable.

### Successful response shape

```json
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "order_id": "PRS-ORD-001",
      "status": "paid",
      "currency": "USD",
      "subtotal": 247.00,
      "discount_amount": 0.00,
      "tax": 0.00,
      "shipping_price": 0.00,
      "total": 247.00,
      "customer_id": "66666666-6666-6666-6666-666666666666",
      "items": [
        {
          "product_slug": "milano-leather-tote",
          "product_name": "Milano Leather Tote",
          "quantity": 1,
          "unit_price": 189.00,
          "line_total": 189.00
        }
      ],
      "metadata": {},
      "created_at": "2026-06-25T14:00:00+00:00",
      "updated_at": "2026-06-25T14:05:00+00:00"
    }
  ]
}
```

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | string | Stable order identifier |
| `status` | string | Order status (map to Botkonak `OrderStatus` — see [01-shared-data-contracts.md](./01-shared-data-contracts.md)) |
| `currency` | string | ISO 4217 code |
| `subtotal` | number | Pre-discount subtotal |
| `discount_amount` | number | Total discounts applied |
| `tax` | number | Tax amount |
| `shipping_price` | number | Shipping charge |
| `total` | number | Final order total |
| `customer_id` | string | Maps to the corresponding customer record |
| `items` | array | Line items (list of objects) |
| `items[].product_slug` | string | Product slug |
| `items[].product_name` | string | Product name at time of order |
| `items[].quantity` | integer | Quantity ordered |
| `items[].unit_price` | number | Unit price |
| `items[].line_total` | number | Line total |
| `metadata` | object | Additional order-level information |
| `created_at` | datetime | Order creation time |
| `updated_at` | datetime | Last update time |

### Revenue-countable order statuses

Only orders in `paid`, `completed`, or `fulfilled` status count toward Botkonak sales summary (`REVENUE_COUNTABLE_ORDER_STATUSES` in `catalog/models.py`).

### Pagination

Required: `limit` and `offset`.

### Error cases

`401`, `403`, `429`, `500`

### Example request

```http
GET /v1/orders?limit=50&offset=0&created_at_from=2026-06-01T00:00:00+00:00&created_at_to=2026-06-30T23:59:59+00:00&status=paid HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

### Related files

- `backend/catalog/models.py` — `Order`, `OrderItem`, `OrderStatus`
- `backend/catalog/services.py` — `build_sales_summary`
- `agents/sales/django_fetch.py` — `get_sales_summary`
- `seed_prestia.py` — `PRESTIA_ORDERS`

---

## API: Get Order Detail

| Property | Value |
|----------|-------|
| **API name** | Get Order Detail |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/orders/{order_id}` |
| **Botkonak consumer** | Support Agent |
| **Why Botkonak needs this** | Support threads reference order numbers (e.g. `PRS-ORD-001` in seed messages). Agent may need order details for order-status replies. |
| **Requirement type** | Inferred |
| **Priority** | P2 |

### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `order_id` | string | Prestia order identifier |

### Successful response

Single order object — **same schema as one item from `GET /v1/orders`**.

### Related files

- `seed_prestia.py` — `prestia-thread-order-followup` message references `PRS-ORD-001`
- `agents/support/refusal.py` — order mutation requests refused (read-only still useful)

---

## Sales analytics (Botkonak responsibility)

Prestia does **not** expose `GET /v1/sales/summary` or similar pre-aggregated sales endpoints.

Botkonak's Sales Agent derives the following from `GET /v1/orders` and `GET /v1/products`:

| Insight | Source |
|---------|--------|
| Sales summary (today, last 7 days) | Aggregated from orders in store timezone |
| Best-selling products | Order line items grouped by `product_slug` |
| Low-stock insights | Product `inventories[].num` cross-referenced with sales velocity |
| Discount candidates | LLM interpretation of sales trends + inventory (`agents/sales/inventory_signals.py`) |
| Slow movers | LLM interpretation of weak sales velocity |

---

## Abandoned / pending orders

| Property | Value |
|----------|-------|
| **API name** | List Draft or Pending Orders |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/orders?status=draft,pending` |
| **Botkonak consumer** | Sales Agent |
| **Why Botkonak needs this** | Mock UI shows "abandoned cart" follow-up (`frontend/types/mock-data.ts`). **No backend implementation** uses abandoned-cart data today. |
| **Requirement type** | Optional (Future) |
| **Priority** | Future |

---

## Evidence from codebase

See per-API sections.

## Open questions

1. Abandoned cart data availability in Prestia.
2. Order status mapping from Prestia native states to Botkonak enum.
3. Whether `order_id` is human-readable (`PRS-ORD-001`) or UUID — connector must map to `external_id`.
