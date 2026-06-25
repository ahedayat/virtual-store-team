# Step 3.2 — Sales Aggregation Queries (Today & Last 7 Days)

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Add generic tenant/store-scoped order data, sales aggregation for **today** and the **last 7 days**, and a protected internal AI sales summary endpoint. This step enables future sales-agent consumption without exposing raw customer PII.

---

## Summary of implemented changes

- Added `Order` and `OrderItem` models to the `catalog` app (matching migration `0002_order_orderitem`)
- Defined `OrderStatus` choices and `REVENUE_COUNTABLE_ORDER_STATUSES` (`paid`, `completed`, `fulfilled`)
- Implemented `catalog/services.py` for timezone-aware sales aggregation
- Added `GET /internal/ai/stores/<store_id>/sales/summary/` protected by `InternalAIAuthentication`
- Registered `Order` and `OrderItem` in Django admin with `OrderItem` inline on `Order`
- Extended `seed_prestia` with realistic demo orders spanning today and the last 7 days
- Added model, service, API, and seed tests
- Cursor scope rule at `.cursor/rules/step-3.2-sales-aggregation.mdc`

---

## Files created/modified

| Path | Action |
|------|--------|
| `.cursor/rules/step-3.2-sales-aggregation.mdc` | Created — Step 3.2 scope rule |
| `backend/catalog/models.py` | Updated — `Order`, `OrderItem`, `OrderStatus` |
| `backend/catalog/services.py` | Created — sales aggregation logic |
| `backend/catalog/internal_views.py` | Created — `InternalSalesSummaryView` |
| `backend/catalog/admin.py` | Updated — `OrderAdmin`, `OrderItemAdmin`, inline |
| `backend/catalog/migrations/0002_order_orderitem.py` | Existing — order schema migration |
| `backend/catalog/tests/test_models.py` | Updated — order model tests |
| `backend/catalog/tests/test_services.py` | Created — aggregation tests |
| `backend/catalog/tests/test_internal_sales_summary.py` | Created — internal API tests |
| `backend/catalog/tests/test_seed_prestia.py` | Updated — order seed tests |
| `backend/accounts/internal_urls.py` | Updated — sales summary route |
| `backend/tenants/management/commands/seed_prestia.py` | Updated — demo orders |
| `docs/phases/step-3.2.md` | Created — this document |

---

## Order and OrderItem model design

### Order

| Field | Type | Rationale |
|-------|------|-----------|
| `id` | `UUIDField` (PK) | Matches existing model convention. |
| `tenant` | `ForeignKey(Tenant, PROTECT)` | Tenant-scoped via `TenantScopedModel`. |
| `store` | `ForeignKey(Store, PROTECT)` | Store-scoped within tenant. |
| `order_number` | `CharField` | Human/system order identifier; unique per `(tenant, store)`. |
| `external_id` | `CharField(blank=True)` | Optional upstream reference. |
| `status` | `CharField` with `OrderStatus` choices | Drives revenue eligibility. |
| `currency` | `CharField(3)` | ISO currency code (typically from store). |
| `subtotal_amount` | `DecimalField` | Pre-discount subtotal. |
| `discount_amount` | `DecimalField` | Discount applied to order. |
| `total_amount` | `DecimalField` | Revenue amount used in aggregation. |
| `placed_at` | `DateTimeField` | Order placement timestamp for period filtering. |
| `external_customer_ref` | `CharField(blank=True)` | Opaque non-PII customer reference only. |
| `metadata` | `JSONField` | Flexible agent context. |

Indexes: `(tenant, store, placed_at)`, `(tenant, store, status)`.

### OrderItem

| Field | Type | Rationale |
|-------|------|-----------|
| `id` | `UUIDField` (PK) | Matches existing model convention. |
| `tenant`, `store` | `ForeignKey` | Explicit scoping consistent with `Product`. |
| `order` | `ForeignKey(Order, CASCADE)` | Parent order. |
| `product` | `ForeignKey(Product, PROTECT)` | Linked catalog product. |
| `product_name_snapshot` | `CharField` | Denormalized name at order time. |
| `sku_snapshot` | `CharField` | Denormalized SKU at order time. |
| `quantity` | `PositiveIntegerField` | Units sold. |
| `unit_price` | `DecimalField` | Price per unit at order time. |
| `line_total` | `DecimalField` | `quantity * unit_price`. |

Unique constraint: `(order, sku_snapshot)`.

---

## Sales aggregation design

Module: `backend/catalog/services.py`

- `get_period_bounds(store, reference)` — computes UTC boundaries using the store timezone (`store.timezone`, fallback `UTC`)
- `build_sales_summary(store, reference)` — returns today and last-7-days metrics

**Today:** start of current calendar day in store TZ through start of next day (exclusive end).

**Last 7 days:** start of day 6 days before today through start of tomorrow (7 calendar days including today).

Metrics per period:

- `total_revenue` — sum of `Order.total_amount` for revenue-countable orders
- `order_count` — count of revenue-countable orders
- `units_sold` — sum of `OrderItem.quantity` on countable orders
- `average_order_value` — `total_revenue / order_count` (0 when no orders)
- `top_products` — top 5 products by revenue with `product_id`, `name`, `sku`, `quantity_sold`, `revenue`, optional `category`

---

## Revenue-countable order status rules

**Included in revenue:**

- `paid`
- `completed`
- `fulfilled`

**Excluded from revenue:**

- `draft`
- `pending`
- `cancelled`
- `refunded`
- `failed`

---

## Internal AI sales summary endpoint contract

| Property | Value |
|----------|-------|
| Method | `GET` |
| Path | `/internal/ai/stores/<store_id>/sales/summary/` |
| Auth | `Authorization: Bearer <service_jwt>` via `InternalAIAuthentication` |
| Name | `internal-ai-sales-summary` |

**Authorization rules:**

- Missing/invalid JWT → `401 Unauthorized`
- JWT `store_id` does not match URL `store_id` → `403 Forbidden`
- Store not found for JWT tenant → `404 Not Found`
- Response must not include raw customer PII

---

## Example response shape

```json
{
  "generated_at": "2026-06-25T18:00:00+00:00",
  "store_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "currency": "USD",
  "periods": {
    "today": {
      "from": "2026-06-25T04:00:00+00:00",
      "to": "2026-06-26T04:00:00+00:00",
      "total_revenue": "447.00",
      "order_count": 2,
      "units_sold": 4,
      "average_order_value": "223.50",
      "top_products": [
        {
          "product_id": "…",
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
      "total_revenue": "1247.00",
      "order_count": 6,
      "units_sold": 12,
      "average_order_value": "207.83",
      "top_products": []
    }
  }
}
```

---

## Tenant/store scoping decisions

- `Order` and `OrderItem` inherit `TenantScopedModel` with explicit `tenant` and `store` FKs
- `order_number` uniqueness is scoped to `(tenant, store)`
- Internal API validates JWT `tenant_id` and `store_id` against the requested store
- Aggregation queries filter by `tenant` and `store` from the resolved `Store` record
- No Prestia-specific branches in models, services, or views

---

## Prestia seed data behavior

`seed_prestia` creates 8 demo orders (6 revenue-countable, 1 cancelled, 1 draft) with items across multiple bag products. Order `placed_at` values are computed relative to **now** in the Prestia store timezone (`America/New_York`) so data falls in today and the last 7 days.

Idempotency:

- Orders: `get_or_create` on `(tenant, store, order_number)`
- Order items: `get_or_create` on `(order, sku_snapshot)`

---

## Tests added

| File | Coverage |
|------|----------|
| `catalog/tests/test_models.py` | Order/OrderItem creation, order_number uniqueness |
| `catalog/tests/test_services.py` | Today/last-7-days metrics, non-countable exclusion |
| `catalog/tests/test_internal_sales_summary.py` | JWT required, valid access, cross-store/tenant denial, no PII |
| `catalog/tests/test_seed_prestia.py` | Orders created, seed idempotency |

---

## How to run the seed command

```bash
cd backend
python manage.py migrate
python manage.py seed_prestia
```

---

## How to run relevant tests

```bash
cd backend
python manage.py test catalog.tests.test_models catalog.tests.test_services catalog.tests.test_internal_sales_summary catalog.tests.test_seed_prestia
```

Or run the full catalog app:

```bash
python manage.py test catalog
```

---

## Explicit out-of-scope items (deferred)

- Low-stock inventory query (Step 3.3)
- Message ingest model (Step 3.4)
- PII sanitizer (Step 3.4+)
- Full AI context endpoint (Step 3.5)
- Reports and actions
- Celery orchestration
- Agent implementation
