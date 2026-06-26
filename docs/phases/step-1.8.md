# Step 1.8 — Tenant Scoping Contract Finalization

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Finalize and document the MVP tenant scoping contract. Resolve the wording mismatch between “automatic tenant filtering” (as stated in early planning) and the implemented explicit scoped-access model (`for_tenant`, `get_for_tenant`, `for_request`).

This step does **not** close Phase 1. Subphase **1.9** (final verification and sign-off) remains required.

---

## Scope

- Audit tenant-facing access paths in `tenants`, `stores`, and `accounts`
- Verify the Phase 1.6 Store read API uses approved scoped accessors
- Document the accepted MVP contract and admin/system escape hatch policy
- Fix unsafe tenant-facing unscoped lookups only if found (none required)
- Add Phase 1.8 Cursor rule guardrail
- Run tenant isolation, Store API, and migration verification

**Out of scope:** Phase 1.9, Phase 2 auth, `seed_prestia` changes, frontend, agents, architecture rewrite to automatic default-manager filtering, unrelated app refactors.

---

## Background / ambiguity being resolved

Early planning (`docs/phases/step-0.0.md`, Section 4.2) states:

> Django middleware / queryset managers enforce tenant filtering on all ORM access.

Phase 1.4 implemented a different, explicit model:

- `TenantScopedModel` assigns `TenantScopedManager` but does **not** override default manager behavior to auto-filter every queryset.
- Tenant isolation is enforced when code uses approved scoped accessors.
- Unscoped `Model.objects.all()` / `.get()` remain available for Django admin and system operations.

Phase 1.8 resolves this by adopting the **explicit scoped-access contract** as the accepted Phase 1 MVP policy:

| Planning phrase | MVP interpretation |
|-----------------|-------------------|
| “Automatic tenant filtering” | Tenant isolation enforced through **approved scoped access paths**, not implicit default-manager filtering |
| “Enforce tenant filtering on all ORM access” | **Tenant-facing** code must use scoped accessors; admin/system may use intentional unscoped access |

The project does **not** require fully automatic default-manager filtering for Phase 1 MVP unless a future phase explicitly adopts it with clear safety guarantees.

---

## Final tenant scoping contract

1. **Tenant-facing paths** (dashboard/public APIs reachable by authenticated users or external clients) must use explicit scoped accessors:
   - `Model.objects.for_tenant(tenant)`
   - `Model.objects.get_for_tenant(tenant, **lookup)`
   - `Model.objects.for_request(request)`
   - Equivalent helpers that guarantee tenant filtering before `.get()` / `.filter()`

2. **Direct unscoped access** to tenant-owned models (`Store.objects.get(id=...)`, `Store.objects.filter(...)`, `Store.objects.all()` for business lookups) is **not allowed** in tenant-facing API/public code.

3. **Admin/system escape hatch:** Unscoped ORM access is permitted only where intentional and not exposed through tenant-facing request paths:
   - Django admin registrations
   - Management commands (`seed_prestia`, imports)
   - Test fixtures and setup
   - Platform-level `Tenant` lookups (Tenant is not a `TenantScopedModel`)
   - Middleware tenant resolution from trusted user/session context

4. **Missing tenant context:** Scoped accessors return `.none()` for list queries and raise `DoesNotExist` for single-object fetches when `tenant` is `None` — never unrestricted data.

5. **Cross-tenant ID in URLs:** Tenant-facing detail endpoints map scoped `DoesNotExist` to `404 Not Found` to avoid information leakage (convention established in Phase 1.6).

---

## Approved tenant-facing access patterns

### Primitives (`backend/tenants/managers.py`)

| Method | Use when |
|--------|----------|
| `for_tenant(tenant)` | List or filter rows for a known tenant |
| `get_for_tenant(tenant, **lookup)` | Fetch one row by PK, slug, etc., within tenant scope |
| `for_request(request)` | List/filter using `request.tenant` from middleware |

### Abstract base (`backend/tenants/models.py`)

`TenantScopedModel` assigns `objects = TenantScopedManager()`. Subclasses (`Store`, and later catalog/operations models) inherit scoped helpers without changing default manager auto-filter behavior.

### Middleware (`backend/tenants/middleware.py`)

`TenantMiddleware` sets `request.tenant` from authenticated `user.tenant` or session `active_tenant_id`. `Tenant.objects.get(pk=...)` is acceptable here because `Tenant` is the platform root entity, not tenant-owned business data.

### Store API (`backend/stores/views.py`)

```python
store = Store.objects.get_for_tenant(tenant, pk=store_id)
```

### User-bound store context (`accounts` auth responses)

`AuthenticatedUserSerializer` exposes `user.store` via the user's foreign key. No additional Store lookup is performed in auth views. The `User.clean()` validation ensures `user.store.tenant_id == user.tenant_id`.

### Preferred patterns for new tenant-facing code

```python
# List for current request tenant
Store.objects.for_request(request)

# Detail lookup in a view
Store.objects.get_for_tenant(request.user.tenant, pk=store_id)

# Service layer with explicit tenant
ReportRun.objects.filter(tenant=tenant)  # acceptable when tenant is a required parameter from trusted context
```

Prefer `for_tenant` / `get_for_tenant` over raw `.filter(tenant=tenant)` for consistency, but explicit `filter(tenant=trusted_tenant)` from server-side trusted context is acceptable when the tenant value is never taken from untrusted request input alone.

---

## Admin/system escape hatch policy

| Location | Access pattern | Classification |
|----------|----------------|----------------|
| `backend/stores/admin.py` | Unscoped `Store` admin | Intentional — platform operators manage all tenants |
| `backend/tenants/admin.py` | Unscoped `Tenant` admin | Intentional — platform entity |
| `backend/accounts/admin.py` | Unscoped `User` admin | Intentional — cross-tenant user management |
| `backend/tenants/management/commands/seed_prestia.py` | Unscoped `Tenant`/`Store` create/get | Intentional — system bootstrap (not modified in 1.8) |
| `backend/tenants/tests/`, `backend/stores/tests/` | `Store.objects.create`, unscoped assertions | Intentional — test setup and contract verification |
| `backend/tenants/middleware.py` | `Tenant.objects.get(pk=...)` | Intentional — resolve platform tenant from trusted session/user |

Unscoped access in these paths must not be copied into tenant-facing API views.

---

## Audit of tenant-facing access paths

Audit date: 2026-06-26. Searched for `Store.objects.get(`, `Store.objects.filter(`, `Store.objects.all(`, and reviewed API views, serializers, middleware, and admin.

### Phase 1 tenant-facing surface

| Path | Pattern | Classification |
|------|---------|----------------|
| `backend/stores/views.py` — `StoreDetailView` | `Store.objects.get_for_tenant(tenant, pk=store_id)` | **Safe** — scoped accessor |
| `backend/accounts/views.py` — Login/Logout/Me | No direct `Store` ORM lookup; uses `user` FK | **Safe** — no unscoped store access |
| `backend/accounts/serializers.py` — `AuthenticatedUserSerializer` | Serializes `user.store` from FK | **Safe** — store bound at user model |
| `backend/tenants/middleware.py` | `Tenant.objects.get(pk=...)` | **Safe** — platform tenant resolution, not tenant-owned model |
| `backend/stores/serializers.py` | Serializes already-fetched `Store` instance | **Safe** — no ORM lookup |

### Internal AI paths (post–Phase 1; verified for consistency)

| Path | Pattern | Classification |
|------|---------|----------------|
| `backend/catalog/internal_views.py` | `Store.objects.get_for_tenant(tenant, pk=store_id)` | **Safe** — scoped accessor |
| `backend/operations/internal_utils.py` | `Store.objects.get_for_tenant(tenant, pk=...)` | **Safe** — scoped accessor |

### Later dashboard paths (not Phase 1; no unsafe Store lookup found)

| Path | Pattern | Classification |
|------|---------|----------------|
| `backend/operations/views.py` — `ReportGenerateView` | `user.store` FK + `store.tenant_id` check | **Safe** — no unscoped `Store.objects.get` |
| `backend/operations/views.py` — `HistoryFeedView` | Delegates to `HistoryFeedService.list_for_user` | **Safe** — service filters by `user.tenant` |
| `backend/operations/history_service.py` | `Model.objects.filter(tenant=tenant)` | **Safe** — explicit tenant from trusted user |

### Unsafe tenant-facing paths found

**None.** No code changes were required.

---

## Files changed

| Path | Action |
|------|--------|
| `.cursor/rules/phase-1-8-tenant-scoping-contract.mdc` | Created — Phase 1.8 scope guardrail |
| `docs/phases/step-1.8.md` | Created — this document |

No application code, test, or migration changes were required. The existing Phase 1.4 primitives and Phase 1.6 Store API already satisfy the finalized contract.

---

## Tests added or verified

No new tests were added. Existing coverage is sufficient for the Phase 1 MVP surface:

| Test module | Tests | Coverage |
|-------------|-------|----------|
| `stores.tests.test_tenant_isolation` | 12 | `for_tenant`, `get_for_tenant`, `for_request`, cross-tenant denial, unscoped manager baseline |
| `stores.tests.test_store_api` | 6 | HTTP-level same-tenant success, cross-tenant `404`, Prestia isolation, unauthenticated `401` |
| `tenants.tests` | (suite) | Tenant model, middleware |
| `accounts.tests` | (suite) | Auth endpoints, user/tenant binding |

---

## Verification commands

**Run via Docker** (project convention):

```bash
docker compose run --rm --entrypoint "" backend python manage.py test stores.tests.test_tenant_isolation stores.tests.test_store_api stores tenants accounts
docker compose run --rm --entrypoint "" backend python manage.py makemigrations --check --dry-run
```

**Run locally** (from `backend/`):

```bash
python manage.py test stores.tests.test_tenant_isolation stores.tests.test_store_api stores tenants accounts
python manage.py makemigrations --check --dry-run
```

---

## Verification results

| Check | Result |
|-------|--------|
| `stores.tests.test_tenant_isolation` | 12 tests — **OK** |
| `stores.tests.test_store_api` | 6 tests — **OK** |
| `stores tenants accounts` (full suite) | 102 tests — **OK** |
| `makemigrations --check --dry-run` | Exit code 0 — `No changes detected` |

Recorded after verification run on 2026-06-26.

---

## Acceptance criteria checklist

- [x] Final MVP tenant scoping contract is explicit (explicit scoped access, not ambiguous automatic filtering)
- [x] Tenant-facing access paths are required to use scoped accessors (documented and verified)
- [x] Admin/system unscoped access is intentional and documented
- [x] Wording mismatch between “automatic tenant filtering” and explicit scoped access is resolved
- [x] No unsafe tenant-facing unscoped access found; no fixes required
- [x] Tenant isolation and Store API tests pass
- [x] `python manage.py makemigrations --check --dry-run` passes
- [x] `docs/phases/step-1.8.md` exists and documents contract, audit, and verification
- [x] Working tree contains only Phase 1.8-related changes

---

## Non-goals

- Phase 1.9 — Phase 1 final verification and closure
- Phase 2 — login/logout/JWT/service JWT (beyond documenting existing session auth patterns)
- Converting the ORM layer to automatic default-manager tenant filtering
- Modifying `seed_prestia`, frontend, or agent code
- Broad refactors of `catalog`, `operations`, or other later-phase apps
- Adding new CRUD APIs or business features

---

## Next step

**Phase 1.9 — Phase 1 Final Verification & Closure**

Final review after completing subphases 1.5–1.8. Confirm all Phase 1 acceptance criteria, run full verification, and record sign-off in `docs/phases/step-1.9.md` before starting Phase 2.
