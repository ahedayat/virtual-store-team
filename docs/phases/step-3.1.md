# Step 3.1 — Product & Category CRUD via Admin + Seed Command

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Establish generic, tenant/store-scoped `Category` and `Product` models with Django admin CRUD and idempotent Prestia demo seed data. This is the first Phase 3 deliverable — store catalog foundations only, with no orders, inventory, messages, PII sanitizer, or internal AI read APIs.

---

## Scope implemented

- Created the Django `catalog` app under `backend/catalog/`
- Defined `Category` and `Product` models inheriting `TenantScopedModel`
- Enforced `tenant + store + slug` uniqueness for categories and products
- Enforced `tenant + store + sku` uniqueness for products
- Registered both models in Django admin with tenant/store-aware list views
- Created `seed_prestia` management command (tenant + store skeleton plus demo categories and bag products)
- Added `catalog` to `INSTALLED_APPS`
- Created initial migration `catalog/migrations/0001_initial.py`
- Added focused model and seed command tests
- Cursor scope rule at `.cursor/rules/step-3.1-product-category.mdc`

---

## Files changed

| Path | Action |
|------|--------|
| `.cursor/rules/step-3.1-product-category.mdc` | Created — Step 3.1 scope rule |
| `backend/catalog/__init__.py` | Created |
| `backend/catalog/apps.py` | Created — `CatalogConfig` |
| `backend/catalog/models.py` | Created — `Category`, `Product` models |
| `backend/catalog/admin.py` | Created — `CategoryAdmin`, `ProductAdmin` |
| `backend/catalog/migrations/__init__.py` | Created |
| `backend/catalog/migrations/0001_initial.py` | Created — initial catalog migration |
| `backend/catalog/tests/__init__.py` | Created |
| `backend/catalog/tests/test_models.py` | Created — model unit tests |
| `backend/catalog/tests/test_seed_prestia.py` | Created — seed command tests |
| `backend/tenants/management/__init__.py` | Created |
| `backend/tenants/management/commands/__init__.py` | Created |
| `backend/tenants/management/commands/seed_prestia.py` | Created — idempotent Prestia seed command |
| `backend/config/settings.py` | Updated — added `catalog` to `INSTALLED_APPS` |
| `docs/phases/step-3.1.md` | Created — this document |

---

## Product and Category model design

### Category

| Field | Type | Rationale |
|-------|------|-----------|
| `id` | `UUIDField` (PK) | Matches existing `Tenant` / `Store` convention. |
| `tenant` | `ForeignKey(Tenant, PROTECT)` | Required for `TenantScopedModel` and tenant-scoped queries. |
| `store` | `ForeignKey(Store, PROTECT)` | Categories are store-scoped within a tenant. |
| `name` | `CharField(max_length=255)` | Human-readable category name. |
| `slug` | `SlugField(max_length=63)` | Stable identifier unique per tenant/store. |
| `description` | `TextField(blank=True)` | Optional category copy for admin and future agent context. |
| `is_active` | `BooleanField(default=True)` | Soft visibility toggle without deletion. |
| `metadata` | `JSONField(default=dict, blank=True)` | Flexible agent context (material, tags, etc.). |

### Product

| Field | Type | Rationale |
|-------|------|-----------|
| `id` | `UUIDField` (PK) | Matches existing model convention. |
| `tenant` | `ForeignKey(Tenant, PROTECT)` | Required for `TenantScopedModel`. |
| `store` | `ForeignKey(Store, PROTECT)` | Products are store-scoped within a tenant. |
| `category` | `ForeignKey(Category, SET_NULL, null=True)` | Optional category link; category removal does not delete products. |
| `name` | `CharField(max_length=255)` | Product display name. |
| `slug` | `SlugField(max_length=63)` | Stable identifier unique per tenant/store. |
| `sku` | `CharField(max_length=63)` | Stock-keeping unit unique per tenant/store. |
| `description` | `TextField(blank=True)` | Product copy for admin and future agent context. |
| `price` | `DecimalField(max_digits=10, decimal_places=2)` | Unit price; currency comes from the parent store. |
| `image_url` | `URLField(blank=True)` | External image reference; no media storage setup in this step. |
| `is_active` | `BooleanField(default=True)` | Soft visibility toggle. |
| `metadata` | `JSONField(default=dict, blank=True)` | Flexible agent context (material, color, etc.). |

**Not included:** `created_at` / `updated_at` (no shared audit mixin yet), inventory quantity, sales metrics, order references, or currency on the product (uses `store.currency`).

**Validation:** `clean()` ensures `store.tenant == tenant` and, for products, `category.store == store`.

---

## Tenant/store scoping decisions

- Both models inherit `TenantScopedModel` and use `objects.for_tenant()` / `get_for_tenant()` like `Store`.
- Every record carries explicit `tenant` and `store` foreign keys for queryset scoping and future internal APIs.
- Uniqueness constraints are scoped to `(tenant, store, slug)` for categories and products, and `(tenant, store, sku)` for products.
- The same slug or SKU may exist under different stores (even within the same tenant).
- Prestia appears only as seeded data (`Tenant(slug='prestia')`); no Prestia branches in models, admin, or business logic.

---

## Admin CRUD behavior

### CategoryAdmin

- **List display:** `name`, `slug`, `tenant`, `store`, `is_active`
- **List filters:** `tenant`, `store`, `is_active`
- **Search:** `name`, `slug`, `description`, `tenant__name`, `tenant__slug`
- **Readonly:** `id`

### ProductAdmin

- **List display:** `name`, `sku`, `slug`, `tenant`, `store`, `category`, `price`, `is_active`
- **List filters:** `tenant`, `store`, `category`, `is_active`
- **Search:** `name`, `slug`, `sku`, `description`, `tenant__name`, `tenant__slug`
- **Readonly:** `id`

Admin uses standard unscoped `ModelAdmin` querysets (platform operator pattern from Phase 1). No Prestia-specific defaults.

---

## Prestia seed data behavior

**Command:** `python manage.py seed_prestia`  
**Location:** `backend/tenants/management/commands/seed_prestia.py`

The command is **idempotent** — safe to run multiple times:

1. `get_or_create` `Tenant(slug='prestia', name='Prestia')` with minimal settings JSON.
2. `get_or_create` `Store(slug='main')` under Prestia with `currency='USD'`, `timezone='America/New_York'`.
3. `get_or_create` five categories: Handbags, Shoulder Bags, Backpacks, Wallets, Accessories.
4. `get_or_create` ten sample bag products keyed by SKU with name, slug, price, description, category, `image_url`, and metadata.

Re-running does not duplicate tenants, stores, categories, or products.

---

## Tests added and how to run them

### Model tests (`backend/catalog/tests/test_models.py`)

| Test | Coverage |
|------|----------|
| `test_create_category_for_tenant_store` | Category creation under tenant/store |
| `test_category_slug_uniqueness_within_tenant_store` | Duplicate category slug raises `IntegrityError` |
| `test_same_category_slug_allowed_across_stores` | Same slug allowed in different stores |
| `test_create_product_for_tenant_store` | Product creation with optional category |
| `test_product_sku_uniqueness_within_tenant_store` | Duplicate SKU raises `IntegrityError` |
| `test_same_product_sku_allowed_across_stores` | Same SKU allowed in different stores |
| `test_product_slug_uniqueness_within_tenant_store` | Duplicate product slug raises `IntegrityError` |
| `test_same_product_slug_allowed_across_stores` | Same slug allowed in different stores |

### Seed command tests (`backend/catalog/tests/test_seed_prestia.py`)

| Test | Coverage |
|------|----------|
| `test_seed_prestia_creates_categories_and_products` | Command creates 5 categories and 10 products |
| `test_seed_prestia_is_idempotent` | Second run does not increase record counts |

**Run locally** (from `backend/`):

```bash
python manage.py test catalog
python manage.py seed_prestia
```

**Run via Docker:**

```bash
docker compose build backend
docker compose run --rm --entrypoint "" backend python manage.py test catalog
docker compose run --rm --entrypoint "" backend python manage.py seed_prestia
```

**Other checks:**

```bash
python manage.py check
python manage.py migrate catalog
```

---

## Migration summary

**Migration:** `catalog/migrations/0001_initial.py`

**Depends on:** `stores/migrations/0001_initial.py`, `tenants/migrations/0001_initial.py`

Creates `catalog_category` and `catalog_product` tables with UUID PKs, tenant/store FKs, and unique constraints on `(tenant_id, store_id, slug)` and `(tenant_id, store_id, sku)` for products.

Apply with:

```bash
python manage.py migrate catalog
```

---

## Explicit out-of-scope items

Deferred to later Phase 3 steps:

- Sales aggregation queries (Step 3.2)
- Inventory levels and low-stock query (Step 3.3)
- Message ingest models (Step 3.4)
- PII sanitizer module
- Internal AI context endpoint (`GET /internal/ai/context/{report_run_id}/`)
- Order, order item, customer models
- Product/category REST APIs (admin-only CRUD in this step)
- Inventory quantity on `Product`
- Prestia-specific application logic outside the seed command

---

## Notes for Step 3.2

- Orders and order items will build on `Product` for line-item references.
- Sales aggregation will query orders, not product-level metrics.
- Internal read APIs should use `TenantScopedModel` query helpers and service JWT tenant/store context from Phase 2.
