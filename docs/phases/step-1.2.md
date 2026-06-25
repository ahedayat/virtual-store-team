# Step 1.2 — Store Model

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Define the foundational `Store` model linked to the existing `Tenant` model. Each store belongs to exactly one tenant and carries locale settings (`timezone`, `currency`) for future store-scoped business data.

---

## Scope implemented

- Created the Django `stores` app under `backend/stores/`
- Defined the `Store` model with `id`, `tenant`, `name`, `slug`, `timezone`, and `currency`
- Enforced `tenant + slug` uniqueness at the database level
- Registered `Store` in Django admin with tenant-aware list display, search, and filters
- Added `stores` to `INSTALLED_APPS`
- Created initial migration `0001_initial` (depends on `tenants.0001_initial`)
- Added focused model tests in `stores/tests/test_models.py`
- Added Cursor scope rule at `.cursor/rules/step-1.2-store-model.mdc`

---

## Files changed

| Path | Action |
|------|--------|
| `.cursor/rules/step-1.2-store-model.mdc` | Created — Step 1.2 scope rule |
| `backend/stores/__init__.py` | Created |
| `backend/stores/apps.py` | Created — `StoresConfig` |
| `backend/stores/models.py` | Created — `Store` model |
| `backend/stores/admin.py` | Created — `StoreAdmin` |
| `backend/stores/migrations/__init__.py` | Created |
| `backend/stores/migrations/0001_initial.py` | Created — initial `Store` migration |
| `backend/stores/tests/__init__.py` | Created |
| `backend/stores/tests/test_models.py` | Created — model unit tests |
| `backend/config/settings.py` | Updated — added `stores` to `INSTALLED_APPS` |
| `docs/phases/step-1.2.md` | Created — this document |

---

## Store model fields and rationale

| Field | Type | Rationale |
|-------|------|-----------|
| `id` | `UUIDField` (PK) | Matches the `Tenant` model convention from Step 1.1 for stable, SaaS-safe identifiers. |
| `tenant` | `ForeignKey(Tenant, on_delete=PROTECT, related_name="stores")` | Every store belongs to one tenant. `PROTECT` prevents accidental tenant deletion while stores still reference it. `related_name="stores"` enables `tenant.stores.all()`. |
| `name` | `CharField(max_length=255)` | Human-readable store display name. |
| `slug` | `SlugField(max_length=63)` | Stable, URL-safe store identifier scoped within a tenant (not globally unique). |
| `timezone` | `CharField(max_length=63, default="UTC")` | IANA timezone name for store-local scheduling and reporting. Defaults to `UTC` when unset at creation. |
| `currency` | `CharField(max_length=3)` | ISO 4217 currency code (e.g. `USD`, `EUR`). Required at creation; no default to avoid implicit locale assumptions. |

**Not included:** `created_at` / `updated_at`. Step 1.1 deliberately omitted timestamp fields because the backend has no shared audit mixin yet; the same convention applies here.

**Behavior:**

- `__str__` returns `"{name} ({tenant.name})"` for readable admin and shell output.
- `Meta.ordering = ["name"]` for predictable admin list ordering.

---

## Tenant relationship design

- `Store.tenant` is a required foreign key to `tenants.Tenant`.
- `on_delete=models.PROTECT` ensures tenants with stores cannot be deleted without first removing or reassigning those stores — appropriate for SaaS data safety.
- Reverse access: `tenant.stores` returns the related `Store` queryset.

---

## Slug uniqueness decision

Store slugs are **unique per tenant**, not globally unique:

- `Meta.constraints` includes `UniqueConstraint(fields=["tenant", "slug"], name="stores_store_unique_tenant_slug")`.
- Two tenants may each have a store with slug `main`.
- Within one tenant, duplicate slugs raise `IntegrityError`.

This matches multi-tenant SaaS expectations: slugs are stable identifiers within a tenant's namespace, while tenant slugs remain globally unique (from Step 1.1).

---

## Admin registration summary

`Store` is registered with a minimal `ModelAdmin`:

- **List display:** `name`, `slug`, `tenant`, `timezone`, `currency`
- **Search:** `name`, `slug`, `tenant__name`, `tenant__slug`
- **List filters:** `tenant`, `currency`

No Prestia-specific defaults or custom actions.

---

## Migration summary

**Migration:** `stores/migrations/0001_initial.py`

**Depends on:** `tenants/migrations/0001_initial.py`

Creates the `stores_store` table with:

- UUID primary key (`id`)
- Foreign key to `tenants_tenant` (`tenant_id`, `ON DELETE PROTECT`)
- `name` (varchar 255)
- `slug` (varchar 63)
- `timezone` (varchar 63, default `UTC`)
- `currency` (varchar 3)
- Unique constraint on `(tenant_id, slug)`

Apply with:

```bash
python manage.py migrate stores
```

In Docker (rebuild image first so the new app is included):

```bash
docker compose build backend
docker compose up -d postgres
docker compose run --rm --entrypoint "" backend python manage.py migrate stores
```

The backend entrypoint runs `migrate --noinput` on startup when using `docker compose up`.

---

## Tests added and how to run them

**File:** `backend/stores/tests/test_models.py`

| Test | Coverage |
|------|----------|
| `test_create_store_for_tenant` | Store can be created with name, slug, timezone, and currency |
| `test_store_is_linked_to_correct_tenant` | FK and `tenant.stores` reverse relation |
| `test_tenant_slug_uniqueness_is_enforced` | Duplicate `tenant + slug` raises `IntegrityError` |
| `test_same_slug_can_be_used_under_different_tenants` | Same slug allowed across different tenants |
| `test_timezone_and_currency_values_are_stored_correctly` | Explicit timezone and currency persist |
| `test_timezone_defaults_to_utc` | Omitted timezone defaults to `UTC` |
| `test_str_returns_readable_value` | `__str__` includes store name and tenant name |

**Run locally** (from `backend/` with Django installed):

```bash
python manage.py test stores
```

**Run via Docker:**

```bash
docker compose build backend
docker compose run --rm --entrypoint "" backend python manage.py test stores
```

**Other checks:**

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test tenants
```

---

## Explicit out-of-scope items

- Custom `User` model
- `TenantMiddleware` (Step 1.3)
- `TenantScopedModel` base mixin
- Automatic tenant queryset filtering (Step 1.4)
- `seed_prestia` management command
- Service JWT authentication
- Internal AI APIs
- Dashboard APIs
- Product, order, inventory, message, report, action, or agent models
- Prestia-specific business logic or hardcoded store data
- Cross-tenant access denial tests (Step 1.4)

---

## Notes for Step 1.3

- Add `TenantMiddleware` to resolve the active tenant from the incoming request (e.g. subdomain or header).
- Attach resolved tenant to the request object for downstream views and services.
- Store-scoped context (selecting the active store within a tenant) may follow in a later step; Step 1.2 only defines the data model.
- No request-level tenant filtering exists yet — all queryset scoping remains manual until Step 1.4.
