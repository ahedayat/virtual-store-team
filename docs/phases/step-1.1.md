# Step 1.1 — Tenant Model

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Define the foundational `Tenant` model for the multi-tenant Django backend. Every future business record will be tenant-scoped; this step establishes the root entity without Prestia-specific logic or later-phase features.

---

## Scope implemented

- Created the Django `tenants` app under `backend/tenants/`
- Defined the `Tenant` model with `id`, `slug`, `name`, and `settings`
- Registered `Tenant` in Django admin
- Added `tenants` to `INSTALLED_APPS`
- Created initial migration `0001_initial`
- Added focused model tests in `tenants/tests/test_models.py`
- Added Cursor scope rule at `.cursor/rules/step-1.1-tenant-model.mdc`

---

## Files changed

| Path | Action |
|------|--------|
| `.cursor/rules/step-1.1-tenant-model.mdc` | Created — Step 1.1 scope rule |
| `backend/tenants/__init__.py` | Created |
| `backend/tenants/apps.py` | Created — `TenantsConfig` |
| `backend/tenants/models.py` | Created — `Tenant` model |
| `backend/tenants/admin.py` | Created — `TenantAdmin` |
| `backend/tenants/migrations/__init__.py` | Created |
| `backend/tenants/migrations/0001_initial.py` | Created — initial `Tenant` migration |
| `backend/tenants/tests/__init__.py` | Created |
| `backend/tenants/tests/test_models.py` | Created — model unit tests |
| `backend/config/settings.py` | Updated — added `tenants` to `INSTALLED_APPS` |
| `docs/phases/step-1.1.md` | Created — this document |

---

## Tenant model fields and rationale

| Field | Type | Rationale |
|-------|------|-----------|
| `id` | `UUIDField` (PK) | No existing business-model ID convention in the codebase; UUIDs are SaaS-safe for public references and stable across environments. |
| `slug` | `SlugField(max_length=63, unique=True)` | Stable, URL-safe tenant identifier for lookup (subdomain routing and admin search in later steps). `unique=True` enforces uniqueness and indexes the column. |
| `name` | `CharField(max_length=255)` | Human-readable tenant display name. |
| `settings` | `JSONField(default=dict, blank=True)` | Per-tenant configuration (language, integrations, policies) without schema changes for each new setting. Defaults to an empty dict. |

**Not included:** `created_at` / `updated_at`. The backend has no timestamp mixin or existing models using audit fields yet; they can be added in a later step if a shared convention is introduced.

**Behavior:**

- `__str__` returns `name` for readable admin and shell output.
- `Meta.ordering = ["name"]` for predictable admin list ordering.

---

## Admin registration summary

`Tenant` is registered with a minimal `ModelAdmin`:

- **List display:** `name`, `slug`
- **Search:** `name`, `slug`

No Prestia-specific defaults or custom actions.

---

## Migration summary

**Migration:** `tenants/migrations/0001_initial.py`

Creates the `tenants_tenant` table with:

- UUID primary key (`id`)
- Unique `slug`
- `name` (varchar 255)
- `settings` (JSON, default `{}`)

Apply with:

```bash
python manage.py migrate tenants
```

In Docker (full stack):

```bash
docker compose up -d postgres
docker compose run --rm backend python manage.py migrate tenants
```

The backend entrypoint runs `migrate --noinput` on startup when using `docker compose up`.

---

## Tests added and how to run them

**File:** `backend/tenants/tests/test_models.py`

| Test | Coverage |
|------|----------|
| `test_create_tenant_with_slug_name_and_default_settings` | Create tenant with slug and name; settings default to `{}` |
| `test_settings_defaults_to_empty_dict` | Persisted tenant has empty dict settings when unset |
| `test_slug_uniqueness_is_enforced` | Duplicate slug raises `IntegrityError` |
| `test_str_returns_readable_name` | `__str__` returns the tenant name |

**Run locally** (from `backend/` with Django installed):

```bash
python manage.py test tenants
```

**Run via Docker:**

```bash
docker compose run --rm --entrypoint "" backend python manage.py test tenants
```

**Other checks:**

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

---

## Explicit out-of-scope items

- `Store` model (Step 1.2)
- Custom `User` model
- `TenantMiddleware`
- `TenantScopedModel` base mixin
- `seed_prestia` management command
- Service JWT authentication
- Internal AI APIs
- Cross-tenant queryset filtering (Step 1.4)
- Dashboard APIs
- Prestia-specific business logic or hardcoded tenant data
- Django Postgres engine wiring (still sqlite3 in settings; Postgres wiring is a later infrastructure step)

---

## Notes for Step 1.2

- Add a `stores` Django app with a `Store` model.
- `Store` should include a **foreign key to `Tenant`** (`tenant` → `tenants.Tenant`).
- Expected `Store` fields per Phase 1 plan: `tenant`, `name`, `slug`, `timezone`, `currency`.
- Keep `Store` generic; do not embed Prestia-specific defaults in the model.
- Register `Store` in Django admin with tenant-aware list display and filters where useful.
