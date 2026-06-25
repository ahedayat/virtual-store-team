# Step 3.3 — Low-Stock Inventory Query (`inventory < threshold`)

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Add generic tenant/store-scoped inventory levels and a low-stock query where **available quantity is strictly below the configured threshold**. Expose the result through a protected internal AI endpoint for future sales-agent consumption, without exposing raw customer PII.

---

## Summary of implemented changes

- Added `InventoryLevel` model to the `catalog` app (migration `0003_inventorylevel`)
- Implemented `build_low_stock_summary()` in `catalog/services.py`
- Added `GET /internal/ai/stores/<store_id>/inventory/low-stock/` protected by `InternalAIAuthentication`
- Registered `InventoryLevel` in Django admin
- Extended `seed_prestia` with realistic demo inventory levels (below, at, above threshold, and out-of-stock)
- Added model, service, API, and seed tests
- Cursor scope rule at `.cursor/rules/step-3.3-low-stock-inventory.mdc`

---

## Files created/modified

| Path | Action |
|------|--------|
| `.cursor/rules/step-3.3-low-stock-inventory.mdc` | Created — Step 3.3 scope rule |
| `backend/catalog/models.py` | Updated — `InventoryLevel` model |
| `backend/catalog/services.py` | Updated — `build_low_stock_summary()` |
| `backend/catalog/internal_views.py` | Updated — `InternalLowStockInventoryView` |
| `backend/catalog/admin.py` | Updated — `InventoryLevelAdmin` |
| `backend/catalog/migrations/0003_inventorylevel.py` | Created — inventory schema migration |
| `backend/catalog/tests/test_models.py` | Updated — inventory model tests |
| `backend/catalog/tests/test_services.py` | Updated — low-stock query tests |
| `backend/catalog/tests/test_internal_low_stock.py` | Created — internal API tests |
| `backend/catalog/tests/test_seed_prestia.py` | Updated — inventory seed tests |
| `backend/accounts/internal_urls.py` | Updated — low-stock route |
| `backend/tenants/management/commands/seed_prestia.py` | Updated — demo inventory levels |
| `docs/phases/step-3.3.md` | Created — this document |

---

## InventoryLevel model design

| Field | Type | Rationale |
|-------|------|-----------|
| `id` | `UUIDField` (PK) | Matches existing model convention. |
| `tenant` | `ForeignKey(Tenant, PROTECT)` | Tenant-scoped via `TenantScopedModel`. |
| `store` | `ForeignKey(Store, PROTECT)` | Store-scoped within tenant. |
| `product` | `ForeignKey(Product, PROTECT)` | Linked catalog product. |
| `quantity_on_hand` | `PositiveIntegerField` | Physical stock on hand. |
| `reserved_quantity` | `PositiveIntegerField` | Units reserved (e.g. pending orders). |
| `low_stock_threshold` | `PositiveIntegerField` | Threshold for low-stock detection. |
| `reorder_target` | `PositiveIntegerField(null=True)` | Optional target level for reorder suggestions. |
| `location_name` | `CharField(blank=True)` | Optional location label for future flexibility. |
| `is_active` | `BooleanField` | Exclude inactive records from queries. |
| `metadata` | `JSONField` | Flexible agent context. |
| `updated_at` | `DateTimeField(auto_now=True)` | Last inventory update for API `last_updated`. |

Unique constraint: `(tenant, store, product)` — one inventory record per product per store for MVP.

Indexes: `(tenant, store, is_active)`, `(tenant, store, product)`.

---

## Low-stock query design

Module: `backend/catalog/services.py`

- `build_low_stock_summary(store, reference)` — returns low-stock items and summary metadata

### Available quantity calculation

```
available_quantity = quantity_on_hand - reserved_quantity
```

Implemented as a model property for single-record use and as a queryset annotation (`available_qty`) for filtering.

### Strict threshold rule

A product is low stock only when:

```
available_quantity < low_stock_threshold
```

Products **exactly at** the threshold are **not** returned.

### Query filters

- `InventoryLevel.is_active = True`
- `Product.is_active = True`
- Tenant and store match the requested store
- Results ordered by available quantity ascending, then product name

### Item fields

Each item includes: `product_id`, `product_name`, `sku`, `category`, `quantity_on_hand`, `reserved_quantity`, `available_quantity`, `low_stock_threshold`, `shortage_units`, `reorder_target`, `suggested_reorder_quantity`, `last_updated`.

- `shortage_units = max(0, low_stock_threshold - available_quantity)`
- `suggested_reorder_quantity = max(0, reorder_target - available_quantity)` when `reorder_target` is set

---

## Internal AI low-stock endpoint contract

| Property | Value |
|----------|-------|
| Method | `GET` |
| Path | `/internal/ai/stores/<store_id>/inventory/low-stock/` |
| Auth | `Authorization: Bearer <service_jwt>` via `InternalAIAuthentication` |
| Scope | JWT `tenant_id` and `store_id` must match the requested store |
| Errors | `401` missing/invalid JWT; `403` cross-store token mismatch; `404` store not found for token tenant |

### Example response shape

```json
{
  "generated_at": "2026-06-25T18:00:00+00:00",
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "low_stock_count": 2,
  "items": [
    {
      "product_id": "660e8400-e29b-41d4-a716-446655440001",
      "product_name": "Milano Leather Tote",
      "sku": "PRS-TOTE-001",
      "category": "Handbags",
      "quantity_on_hand": 5,
      "reserved_quantity": 2,
      "available_quantity": 3,
      "low_stock_threshold": 10,
      "shortage_units": 7,
      "reorder_target": 25,
      "suggested_reorder_quantity": 22,
      "last_updated": "2026-06-25T17:30:00+00:00"
    }
  ]
}
```

No customer names, emails, phone numbers, addresses, Instagram handles, or `external_customer_ref` appear in the response.

---

## Tenant/store scoping decisions

- `InventoryLevel` extends `TenantScopedModel` with explicit `tenant` and `store` foreign keys, consistent with `Product` and `Order`.
- `clean()` validates store/tenant and product/store alignment.
- Internal API uses the same pattern as Step 3.2 sales summary: JWT store must match URL `store_id`; store is loaded via `Store.objects.get_for_tenant(tenant, pk=store_id)`.
- Cross-tenant access returns `403` when the token store does not match the URL; missing store for the token tenant returns `404`.

---

## Prestia inventory seed behavior

Command: `python manage.py seed_prestia` (from `backend/`)

- Creates one `InventoryLevel` per Prestia product, keyed on `(tenant, store, product)` via `get_or_create`
- Idempotent: repeated runs do not duplicate inventory records
- Variation for low-stock validation:
  - **Below threshold:** `PRS-TOTE-001` (available 3, threshold 10), `PRS-WLT-007`, `PRS-ACC-009`, `PRS-HB-010`
  - **Exactly at threshold:** `PRS-CROSS-002` (available 10, threshold 10) — excluded from low-stock results
  - **Above threshold:** `PRS-SHLD-003`, `PRS-BPK-005`, `PRS-WLT-006`, `PRS-ACC-008`
  - **Out of stock:** `PRS-BPK-004` (available 0, threshold 5)

---

## Tests added

| File | Coverage |
|------|----------|
| `catalog/tests/test_models.py` | InventoryLevel creation, available quantity, uniqueness |
| `catalog/tests/test_services.py` | Low-stock query: below/at/above threshold, inactive inventory/product exclusion |
| `catalog/tests/test_internal_low_stock.py` | JWT required/accepted, cross-tenant/store rejection, no PII |
| `catalog/tests/test_seed_prestia.py` | Inventory seed creation and idempotency |

### How to run relevant tests

From `backend/`:

```bash
python manage.py test catalog.tests.test_models.InventoryLevelModelTests
python manage.py test catalog.tests.test_services.LowStockInventoryTests
python manage.py test catalog.tests.test_internal_low_stock
python manage.py test catalog.tests.test_seed_prestia
```

Or run the full catalog suite:

```bash
python manage.py test catalog
```

---

## How to run the seed command

```bash
cd backend
python manage.py seed_prestia
```

---

## Explicit out-of-scope items (deferred to later steps)

- Message ingest model (Step 3.4)
- PII sanitizer (Step 3.5 or later)
- Full AI context endpoint (Step 3.5)
- Reports and actions (Phase 4)
- Celery orchestration
- Agent implementation
- Real external inventory synchronization
- Supplier purchase orders
- Warehouse workflows and stock movement history
