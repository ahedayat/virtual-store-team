# Step 1.6 — Tenant-Scoped Store API Acceptance

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Add a minimal tenant-scoped Store read API path and prove at the HTTP/API layer that an authenticated user from one tenant cannot read another tenant's store by direct ID.

This step closes the Phase 1 API acceptance gap left after Phase 1.4 queryset/middleware isolation work. It does **not** implement Phase 1.7, 1.8, 1.9, or Phase 2 authentication.

---

## Scope

- Add a read-only dashboard-facing Store detail endpoint
- Scope lookups through `Store.objects.get_for_tenant(request.user.tenant, ...)`
- Return `404 Not Found` for cross-tenant direct ID access (matching internal AI API convention)
- Add HTTP-level tests for same-tenant success, cross-tenant denial, Prestia user denial, and unauthenticated rejection
- Document the work in this file

---

## Background / gap being closed

Phase 1.4 added `TenantScopedModel`, `for_tenant`, `get_for_tenant`, and `for_request` with queryset-level cross-tenant denial tests. Phase 1.5 closed accounts migration drift.

The Phase 1 completion gate still required HTTP/API-level proof that a Prestia user cannot read another tenant's store ID. No dashboard-facing Store read endpoint existed before this step.

---

## API endpoint added

### `GET /api/stores/<store_id>/`

| Item | Value |
|------|-------|
| Auth | Session (`SessionAuthentication`) |
| Permission | Authenticated users only |
| Lookup | `Store.objects.get_for_tenant(request.user.tenant, pk=store_id)` |
| Cross-tenant ID | `404` with `{"detail": "Store not found."}` |
| Unauthenticated | `401 Unauthorized` |

### Example success response (`200 OK`)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "slug": "prestia",
    "name": "Prestia"
  },
  "name": "Prestia Main",
  "slug": "main",
  "timezone": "Asia/Tehran",
  "currency": "IRR"
}
```

The response is intentionally minimal. Tenant `settings` and unrelated store data are not exposed.

---

## Tenant isolation behavior

1. The authenticated user's `tenant` is the sole authority for store lookup.
2. Direct access to another tenant's store UUID does not use unscoped `Store.objects.get(id=...)`.
3. Cross-tenant access raises `Store.DoesNotExist` from `get_for_tenant`, which the view maps to `404 Not Found`.
4. The `404` response does not include the other tenant's store fields, avoiding information leakage.

---

## Files changed

| Path | Action |
|------|--------|
| `backend/stores/serializers.py` | Created — `StoreReadSerializer`, `TenantSummarySerializer` |
| `backend/stores/views.py` | Created — `StoreDetailView` |
| `backend/stores/urls.py` | Created — `GET /api/stores/<store_id>/` route |
| `backend/stores/tests/test_store_api.py` | Created — HTTP-level tenant isolation tests |
| `backend/config/urls.py` | Updated — include `stores.urls` under `/api/` |
| `.cursor/rules/phase-1-6-tenant-scoped-store-api.mdc` | Present — Phase 1.6 scope guardrail |
| `docs/phases/step-1.6.md` | Created — this document |

No migrations were required. No changes to `seed_prestia`, frontend, agents, or unrelated apps.

---

## Tests added

`backend/stores/tests/test_store_api.py`:

| Test | Assertion |
|------|-----------|
| `test_authenticated_user_can_read_same_tenant_store` | Tenant A user reads Tenant A store → `200` with expected fields |
| `test_authenticated_user_cannot_read_other_tenant_store_by_id` | Tenant A user requests Tenant B store ID → `404` |
| `test_prestia_user_cannot_read_other_tenant_store_by_id` | Prestia user requests another tenant's store ID → `404` |
| `test_prestia_user_can_read_prestia_store` | Prestia user reads Prestia store → `200` |
| `test_unauthenticated_request_is_rejected` | Anonymous request → `401` |
| `test_cross_tenant_response_does_not_leak_other_store_data` | `404` body contains no store name/slug/currency |

Tests use `APITestCase` and `force_login`, consistent with existing `accounts` API tests.

---

## Verification commands

**Run via Docker** (project convention):

```bash
docker compose run --rm --entrypoint "" backend python manage.py test stores.tests.test_store_api stores.tests.test_tenant_isolation stores tenants accounts
docker compose run --rm --entrypoint "" backend python manage.py makemigrations --check --dry-run
```

**Run locally** (from `backend/`):

```bash
python manage.py test stores.tests.test_store_api stores.tests.test_tenant_isolation stores tenants accounts
python manage.py makemigrations --check --dry-run
```

---

## Verification results

| Check | Result |
|-------|--------|
| `test stores.tests.test_store_api` | 6 tests — **OK** |
| `test stores.tests.test_tenant_isolation` | 12 tests — **OK** |
| `test stores tenants accounts` | 97 tests total — **OK** |
| `makemigrations --check --dry-run` | Exit code 0 — `No changes detected` |

---

## Acceptance criteria checklist

- [x] Minimal tenant-scoped Store read API path exists (`GET /api/stores/<store_id>/`)
- [x] Same-tenant authenticated Store read succeeds
- [x] Cross-tenant Store read by direct ID is denied at HTTP/API level (`404`)
- [x] Prestia user cannot read another tenant's store ID
- [x] Endpoint uses `get_for_tenant` rather than unsafe unscoped lookup
- [x] Relevant tests pass
- [x] `python manage.py makemigrations --check --dry-run` passes
- [x] `docs/phases/step-1.6.md` documents the work
- [x] Scope limited to Phase 1.6 (no Phase 1.7+ work)

---

## Non-goals

- Phase 1.7 — `seed_prestia` baseline alignment
- Phase 1.8 — tenant scoping contract finalization
- Phase 1.9 — Phase 1 final verification
- Phase 2 login/logout/JWT/service JWT changes beyond existing session auth reuse
- Store write/update/delete APIs
- Frontend or agent changes
- Broad CRUD or list endpoints

---

## Next step

**Phase 1.7 — Phase 1 Seed Prestia Baseline Alignment**

Clarify the Phase 1 baseline responsibility of `seed_prestia`: idempotent Prestia tenant and main store creation, with later catalog seeding attributed to later phases.
