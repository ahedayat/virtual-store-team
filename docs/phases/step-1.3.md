# Step 1.3 — Tenant Middleware

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Resolve the active tenant on every Django request through `TenantMiddleware`, attaching it to `request.tenant` for downstream views and services. For MVP, resolution is session-based (with optional support for a future tenant-aware user model). Subdomain-based resolution is documented as a future extension only.

---

## Scope implemented

- Added `TenantMiddleware` in `backend/tenants/middleware.py`
- Added small helper functions for tenant lookup and resolution
- Registered middleware in `MIDDLEWARE` after `SessionMiddleware` and `AuthenticationMiddleware`
- Added focused middleware tests in `backend/tenants/tests/test_middleware.py`
- Added Cursor scope rule at `.cursor/rules/step-1.3-tenant-middleware.mdc`

---

## Files changed

| Path | Action |
|------|--------|
| `.cursor/rules/step-1.3-tenant-middleware.mdc` | Created — Step 1.3 scope rule |
| `backend/tenants/middleware.py` | Created — `TenantMiddleware` and helpers |
| `backend/tenants/tests/test_middleware.py` | Created — middleware unit tests |
| `backend/config/settings.py` | Updated — registered `TenantMiddleware` |
| `docs/phases/step-1.3.md` | Created — this document |

---

## Middleware behavior

On every request, `TenantMiddleware`:

1. Initializes `request.tenant = None` and `request.tenant_id = None`
2. Attempts tenant resolution using the order below
3. When a tenant is found, sets `request.tenant` to the `Tenant` instance and `request.tenant_id` to its UUID
4. Never raises HTTP errors or `PermissionDenied` for missing or invalid tenant context
5. Always calls the next middleware/view in the chain

Anonymous users, requests without sessions, missing tenant IDs, invalid UUIDs, and deleted tenant IDs all result in `request.tenant = None` without crashing the request.

---

## Tenant resolution order

1. **Authenticated user** — If `request.user` exists, is authenticated, and has a usable `tenant` attribute (FK instance), use it.
2. **Authenticated user `tenant_id`** — If the user has a `tenant_id` attribute but no `tenant` object, look up the tenant by ID.
3. **Session** — If the session contains `active_tenant_id`, look up the tenant by that UUID.
4. **Fallback** — Keep `request.tenant = None`.

User-based resolution takes precedence over session-based resolution when both are present.

**Future extension:** Subdomain or hostname-based tenant lookup can be added as an earlier resolution step without changing the session/user fallback behavior.

---

## Session key used

`active_tenant_id`

Store the tenant's UUID (as a string) in the session under this key to activate a tenant for unauthenticated or multi-tenant session flows.

---

## Middleware ordering in Django settings

`TenantMiddleware` is registered immediately after `AuthenticationMiddleware` and after `SessionMiddleware`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "tenants.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

This ensures `request.session` and `request.user` are available before tenant resolution runs.

---

## Tests added and how to run them

**File:** `backend/tenants/tests/test_middleware.py`

| Test | Coverage |
|------|----------|
| `test_sets_tenant_none_when_no_tenant_is_available` | Default `request.tenant` and `request.tenant_id` are `None` |
| `test_resolves_tenant_from_session` | Session `active_tenant_id` resolves to the correct tenant |
| `test_handles_invalid_session_tenant_id_safely` | Invalid UUID in session does not crash |
| `test_handles_unknown_session_tenant_id_safely` | Unknown/deleted tenant UUID in session returns `None` |
| `test_resolves_tenant_from_authenticated_user_tenant_attribute` | User with `tenant` attribute resolves correctly |
| `test_resolves_tenant_from_authenticated_user_tenant_id_attribute` | User with only `tenant_id` resolves correctly |
| `test_user_tenant_takes_precedence_over_session` | User tenant wins over session tenant |
| `test_does_not_crash_for_anonymous_requests_without_session` | Anonymous request without session is safe |
| `test_middleware_is_registered_after_session_and_auth` | Middleware ordering in settings |
| Helper tests | `get_tenant_by_id`, `resolve_tenant_from_user`, `resolve_tenant_from_session` edge cases |

**Run locally** (from `backend/` with Django installed):

```bash
python manage.py test tenants.tests.test_middleware
```

**Run all tenants tests:**

```bash
python manage.py test tenants
```

**Run via Docker:**

```bash
docker compose run --rm --entrypoint "" backend python manage.py test tenants.tests.test_middleware
```

**Other checks:**

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

---

## Explicit out-of-scope items

- Custom `User` model
- `TenantScopedModel` base mixin
- Automatic queryset filtering (Step 1.4)
- Cross-tenant access denial tests (Step 1.4)
- Object-level permissions
- Service JWT authentication
- Internal AI APIs
- Dashboard APIs
- `seed_prestia` management command
- Subdomain tenant resolution
- Product, order, inventory, report, action, or agent models
- Prestia-specific business logic or hardcoded tenant data
- API endpoints for tenant switching

---

## Notes for Step 1.4

- Introduce `TenantScopedModel` (or equivalent) so business models inherit tenant scoping conventions.
- Add automatic queryset filtering tied to `request.tenant` so list/detail queries are tenant-scoped by default.
- Add cross-tenant access denial: views and querysets must reject access when the requested object belongs to a different tenant than `request.tenant`.
- A custom `User` model with a `tenant` foreign key may be added in a later step; `TenantMiddleware` already supports `user.tenant` and `user.tenant_id` when present.
- Store-level request context (active store within a tenant) remains out of scope until a dedicated step defines it.
