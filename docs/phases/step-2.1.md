# Step 2.1 — Manager Authentication API

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Provide human dashboard authentication endpoints so a store manager can log in, retrieve their profile with tenant/store context, and log out. This step establishes session-based manager auth only; service JWT and internal AI authentication are deferred to Phase 2.2+.

---

## Scope of this step

- Added `accounts` app with custom `User` model (tenant-bound, optional store scope, role field)
- `POST /api/auth/login/` — email/password login for manager users
- `POST /api/auth/logout/` — end the current Django session
- `GET /api/auth/me/` — return the authenticated manager profile
- DRF serializers for login validation and safe user responses
- Session authentication via Django's built-in session framework
- Auth endpoint tests with tenant-scoped fixture data
- Cursor scope rule at `.cursor/rules/phase-2.1-auth-users.mdc`

### Prerequisite note

Phase 1 planned a custom `User` model in `accounts` but deferred it until auth work. Step 2.1 introduces that model as the foundation for login. `TenantMiddleware` already resolves `request.tenant` from `user.tenant`, so authenticated requests automatically receive tenant context.

---

## Explicit non-goals

- Phase 2.2 `InternalAIAuthentication`
- Phase 2.3 service JWT validation middleware for `/internal/ai/*`
- Phase 2.4 service token mint/verify tests
- JWT or token auth for the dashboard frontend (session auth is used)
- `seed_prestia` management command
- Prestia-specific logic or hardcoded demo credentials
- Full RBAC beyond the `role` field on `User`
- CORS / httpOnly cookie wiring for the Next.js frontend (frontend integration is a later step)

---

## Endpoints implemented

| Method | Path | Auth required | Description |
|--------|------|---------------|-------------|
| `POST` | `/api/auth/login/` | No | Authenticate manager by email/password |
| `POST` | `/api/auth/logout/` | Yes | Destroy current session |
| `GET` | `/api/auth/me/` | Yes | Return current user + tenant/store context |

Base URL in development: `http://localhost:8000`

---

## Request/response examples

### Login

**Request:**

```http
POST /api/auth/login/
Content-Type: application/json

{
  "email": "manager@example.com",
  "password": "your-password"
}
```

**Success (`200 OK`):**

```json
{
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "manager@example.com",
    "full_name": "Manager Name",
    "role": "manager",
    "tenant": {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "slug": "acme",
      "name": "Acme Corp"
    },
    "store": {
      "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "slug": "main",
      "name": "Main Store"
    }
  }
}
```

**Invalid credentials (`401 Unauthorized`):**

```json
{
  "detail": "Invalid email or password."
}
```

**Inactive account (`401 Unauthorized`):**

```json
{
  "detail": "This account is inactive."
}
```

### Logout

**Request:**

```http
POST /api/auth/logout/
Cookie: sessionid=...
```

**Success (`200 OK`):**

```json
{
  "detail": "Logged out successfully."
}
```

### Me

**Request:**

```http
GET /api/auth/me/
Cookie: sessionid=...
```

**Success (`200 OK`):** same `user` object shape as login.

**Anonymous (`401 Unauthorized`):**

```json
{
  "detail": "Authentication credentials were not provided."
}
```

---

## Authentication mechanism

**Django session authentication** is used for dashboard managers:

1. `POST /api/auth/login/` calls `django.contrib.auth.login()` and sets the `sessionid` cookie.
2. Subsequent requests send the session cookie; DRF `SessionAuthentication` attaches `request.user`.
3. `POST /api/auth/logout/` calls `django.contrib.auth.logout()` and clears the session.
4. `TenantMiddleware` resolves `request.tenant` from `user.tenant` on authenticated requests.

DRF's default `SessionAuthentication` returns `403` for unauthenticated requests (no `WWW-Authenticate` header). This project uses `accounts.authentication.SessionAuthentication`, which sets `WWW-Authenticate: Session` so anonymous and failed-auth requests correctly receive `401`.

No JWT or refresh tokens are issued in this step. The frontend should send credentials (`credentials: "include"`) once CORS is wired in a later step.

### Safe response fields

User responses include only: `id`, `email`, `full_name`, `role`, and nested `tenant` / `store` summaries (`id`, `slug`, `name`). Password hashes, `tenant.settings`, and other sensitive fields are never exposed.

### `store` field

`store` is optional on `User`. Managers without a store assignment receive `"store": null` in the payload.

---

## Files changed

| Path | Action |
|------|--------|
| `.cursor/rules/phase-2.1-auth-users.mdc` | Created/updated — Phase 2.1 scope rule |
| `backend/requirements.txt` | Updated — added `djangorestframework` |
| `backend/config/settings.py` | Updated — `accounts`, DRF, `AUTH_USER_MODEL`, session auth defaults |
| `backend/config/urls.py` | Updated — mounted `/api/auth/` |
| `backend/accounts/authentication.py` | Created — session auth with proper `401` responses |
| `backend/accounts/managers.py` | Created — email-based `UserManager` |
| `docs/phases/step-2.1.md` | Created — this document |

---

## User model summary

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `email` | Email | Unique; used as `USERNAME_FIELD` |
| `full_name` | string | Display name for dashboard |
| `role` | choice | `manager` or `viewer` (MVP focuses on managers) |
| `tenant` | FK → `Tenant` | Required; drives tenant isolation |
| `store` | FK → `Store` | Optional; must belong to the user's tenant |
| `is_active` | bool | Inactive users cannot log in |

---

## Tests added

**File:** `backend/accounts/tests/test_auth.py`

| Test | Coverage |
|------|----------|
| `test_manager_can_login_with_valid_credentials` | Successful login returns user + tenant + store |
| `test_login_fails_with_invalid_password` | Wrong password returns `401` |
| `test_inactive_user_cannot_login` | Inactive account returns `401` |
| `test_authenticated_user_can_call_me` | `GET /api/auth/me/` works when logged in |
| `test_anonymous_user_cannot_call_me` | Anonymous `GET /me/` returns `401` |
| `test_authenticated_user_can_logout` | Logout returns success message |
| `test_after_logout_session_user_cannot_access_me` | Session cleared after logout |
| `test_login_does_not_expose_password_or_sensitive_tenant_settings` | No secrets in response |

Tests use generic tenant/store fixtures (`acme`, `other`) — no Prestia hardcoding.

---

## How to run tests

**Locally** (from `backend/`):

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py test accounts.tests.test_auth
python manage.py test accounts tenants stores
```

**Via Docker:**

```bash
docker compose run --rm --entrypoint "" backend python manage.py migrate
docker compose run --rm --entrypoint "" backend python manage.py test accounts.tests.test_auth
docker compose run --rm --entrypoint "" backend python manage.py test accounts tenants stores
```

---

## Known limitations / next steps (Phase 2.2+)

- **Service JWT** — `ServiceJWT` minting utility and short-lived tokens for AI agents are Phase 2.2.
- **Internal AI auth** — `InternalAIAuthentication` and `/internal/ai/*` middleware are Phase 2.2–2.3.
- **Token tests** — mint/verify unit tests are Phase 2.4.
- **Frontend CORS/cookies** — Next.js must send session cookies with `credentials: "include"`; CORS allowed origins are configured in `.env.example` but not yet wired in Django settings.
- **CSRF** — `SessionAuthentication` enforces CSRF on unsafe methods; the frontend must obtain and send the CSRF token for login/logout from a browser context.
- **Viewer role** — `viewer` exists on the model but dashboard permissions are not enforced yet.
- **Password reset / registration** — out of scope; managers are created via Django admin for MVP.

---

## Creating a test manager (admin)

```bash
python manage.py createsuperuser
# Or use Django admin at /admin/ after creating a user with tenant + store assigned
```

Assign `tenant` and optionally `store` when creating users in admin so login responses include full context and `TenantMiddleware` resolves the active tenant.
