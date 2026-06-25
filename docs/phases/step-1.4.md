# Step 1.4 — Cross-Tenant Access Denial

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Prove that one tenant cannot access another tenant's store through the tenant-scoped access path. Add the minimal queryset/manager primitives needed to make that isolation explicit and testable, without building APIs or authentication.

---

## Scope implemented

- Added `TenantScopedQuerySet` and `TenantScopedManager` in `backend/tenants/managers.py`
- Added abstract `TenantScopedModel` in `backend/tenants/models.py`
- Applied tenant-scoped manager to `Store` via `TenantScopedModel` inheritance
- Added cross-tenant denial tests in `backend/stores/tests/test_tenant_isolation.py`
- Added request-context integration tests using existing `TenantMiddleware`
- Added Cursor scope rule at `.cursor/rules/step-1.4-cross-tenant-isolation.mdc`

---

## Files changed

| Path | Action |
|------|--------|
| `.cursor/rules/step-1.4-cross-tenant-isolation.mdc` | Created — Step 1.4 scope rule |
| `backend/tenants/managers.py` | Created — `TenantScopedQuerySet`, `TenantScopedManager` |
| `backend/tenants/models.py` | Updated — added `TenantScopedModel` abstract base |
| `backend/stores/models.py` | Updated — `Store` inherits `TenantScopedModel` |
| `backend/stores/tests/test_tenant_isolation.py` | Created — cross-tenant denial and request integration tests |
| `docs/phases/step-1.4.md` | Created — this document |

No new migrations were required (`TenantScopedModel` is abstract; schema is unchanged).

---

## Tenant isolation strategy

Isolation is enforced at the **query access path**, not by replacing Django's default manager behavior:

1. Business code that must respect tenant boundaries should use `Model.objects.for_tenant(tenant)` or `Model.objects.get_for_tenant(tenant, **lookup)`.
2. When `tenant` is `None`, scoped queries return `.none()` and `get_for_tenant` raises `DoesNotExist` — never unrestricted data.
3. Unscoped access (`Store.objects.all()`, Django admin) remains available for platform administration and tests.
4. Request-level tenant context from `TenantMiddleware` (`request.tenant`) integrates via `QuerySet.for_request(request)`.

API-level authorization (rejecting cross-tenant IDs in URLs with 404/403) will be wired in Phase 2 once login and dashboard/internal endpoints exist.

---

## Queryset/manager/helper behavior

### `TenantScopedQuerySet`

| Method | Behavior |
|--------|----------|
| `for_tenant(tenant)` | Filters by `tenant=tenant`. Returns `.none()` when `tenant` is `None`. |
| `for_request(request)` | Calls `for_tenant(request.tenant)`. Returns `.none()` when middleware did not resolve a tenant. |

### `TenantScopedManager`

| Method | Behavior |
|--------|----------|
| `for_tenant(tenant)` | Delegates to queryset `for_tenant`. |
| `get_for_tenant(tenant, **lookup)` | `.get(**lookup)` within tenant scope. Raises `DoesNotExist` when `tenant` is `None` or the row belongs to another tenant. |
| `for_request(request)` | Delegates to queryset `for_request`. |

### `TenantScopedModel`

Abstract base model that assigns `objects = TenantScopedManager()`. Subclasses must define a `tenant` foreign key (as `Store` already does).

---

## How `Store` is protected through tenant-scoped access

`Store` inherits `TenantScopedModel` and keeps its existing `tenant` foreign key. Tenant-scoped retrieval examples:

```python
# List stores for the active tenant
Store.objects.for_tenant(request.tenant)

# Or directly from middleware-attached request
Store.objects.for_request(request)

# Fetch one store safely within tenant scope
Store.objects.get_for_tenant(request.tenant, slug="main")
```

Cross-tenant access through these paths fails safely:

- `Store.objects.for_tenant(tenant_a)` never includes `tenant_b` rows.
- `Store.objects.get_for_tenant(tenant_a, pk=tenant_b_store.id)` raises `Store.DoesNotExist`.

Django admin and unscoped `Store.objects.all()` are intentionally unchanged so operators can manage all tenants.

---

## Test cases added

**File:** `backend/stores/tests/test_tenant_isolation.py`

### `StoreTenantIsolationTests`

| Test | Coverage |
|------|----------|
| `test_for_tenant_includes_only_matching_tenant_stores` | Scoped list returns only tenant A stores |
| `test_for_tenant_excludes_other_tenant_stores` | Tenant B store excluded from tenant A scope |
| `test_get_for_tenant_denies_cross_tenant_access_by_id` | Cross-tenant PK lookup raises `DoesNotExist` |
| `test_get_for_tenant_denies_cross_tenant_access_by_slug` | Same slug under another tenant not visible |
| `test_get_for_tenant_returns_store_within_tenant` | Valid in-tenant lookup succeeds |
| `test_for_tenant_with_none_returns_empty_queryset` | `None` tenant returns no rows |
| `test_get_for_tenant_with_none_raises_does_not_exist` | `None` tenant denies single-object fetch |
| `test_same_slug_can_exist_under_different_tenants_with_scoped_access` | Per-tenant slug namespace preserved |
| `test_unscoped_manager_still_returns_all_stores` | Default manager remains unrestricted |

### `StoreRequestTenantIntegrationTests`

| Test | Coverage |
|------|----------|
| `test_for_request_uses_middleware_tenant_context` | Session-resolved `request.tenant` scopes stores |
| `test_for_request_excludes_other_tenant_stores` | Request context excludes other tenants |
| `test_for_request_with_no_tenant_returns_empty_queryset` | Missing tenant context returns no stores |

Same-slug-across-tenants model behavior is also covered in `stores/tests/test_models.py` from Step 1.2.

---

## Commands used to run checks/tests

**Run locally** (from `backend/`):

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test stores.tests.test_tenant_isolation
python manage.py test tenants stores
```

**Run via Docker:**

```bash
docker compose run --rm --entrypoint "" backend python manage.py check
docker compose run --rm --entrypoint "" backend python manage.py makemigrations --check --dry-run
docker compose run --rm --entrypoint "" backend python manage.py test stores.tests.test_tenant_isolation
docker compose run --rm --entrypoint "" backend python manage.py test tenants stores
```

---

## Explicit out-of-scope items

- Full dashboard APIs and DRF viewsets
- Login/logout APIs and custom `User` model
- Service JWT authentication
- Internal AI APIs
- API-level 404/403 enforcement on cross-tenant object IDs
- Full RBAC or object permission framework
- Product, order, inventory, message, report, action, or agent models
- `seed_prestia` management command
- Subdomain tenant resolution
- Prestia-specific business logic or hardcoded demo data
- Automatic restriction of `Model.objects.all()` (admin and platform ops remain unscoped)

---

## Notes for Phase 2

- Add manager login and bind `request.user.tenant` so `TenantMiddleware` resolves tenant from authenticated users without session keys.
- Dashboard and internal API views should use `for_request(request)` or `for_tenant(request.tenant)` for list/detail queries.
- API endpoints should return **404** (not 403) when a resource ID exists but belongs to another tenant, to avoid information leakage.
- Service JWT claims (`tenant_id`, `store_id`) will provide tenant context for `/internal/ai/*` routes; reuse the same scoped queryset helpers.
- Consider a view/mixin helper that combines `get_for_tenant` with consistent HTTP error mapping once endpoints exist.
- Store-level request context (active store within a tenant) remains a later step.
