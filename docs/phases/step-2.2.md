# Step 2.2 — Internal AI Authentication

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Implement the first version of Django REST Framework authentication for internal AI service routes. FastAPI AI agents must access Django internal APIs only through short-lived service JWTs that identify the calling service and carry tenant/store context.

This step does **not** implement Phase 3 internal business APIs and does **not** give agents direct database access.

---

## Scope

- Service registry constants for allowed AI service names
- `AIServiceIdentity` dataclass for DRF auth return values
- `decode_service_jwt` / `mint_service_jwt` helpers (minting is minimal — full lifecycle tests are Phase 2.4)
- `InternalAIAuthentication` DRF class validating `Authorization: Bearer <service_jwt>`
- Minimal protected test endpoint: `GET /internal/ai/auth-check/`
- JWT-related Django settings and `.env.example` placeholders
- Focused authentication tests
- Cursor scope rule at `.cursor/rules/phase-2.2-internal-ai-auth.mdc`

---

## Explicit non-goals

- Phase 2.3 hardening (explicit expired/wrong-audience test coverage beyond decoder behavior)
- Phase 2.4 full token mint/verify test suite
- Phase 3 internal commerce/read APIs (products, orders, sales summary, context bundles)
- Actions, reports, PII sanitizer, or agent workflows
- Celery token issuance (future Phase 5 wiring)
- Prestia-specific logic or hardcoded tenant data
- Global registration of `InternalAIAuthentication` as the default DRF auth class
- Allowing dashboard session auth on `/internal/ai/*` routes

---

## Files changed

| File | Purpose |
|------|---------|
| `backend/accounts/constants.py` | Allowed AI service name registry |
| `backend/accounts/service_identity.py` | `AIServiceIdentity` dataclass |
| `backend/accounts/service_jwt.py` | JWT decode/mint helpers and validation errors |
| `backend/accounts/authentication.py` | `InternalAIAuthentication` class |
| `backend/accounts/internal_views.py` | `InternalAIAuthCheckView` |
| `backend/accounts/internal_urls.py` | `/internal/ai/` URL routing |
| `backend/accounts/tests/test_internal_ai_auth.py` | Phase 2.2 auth tests |
| `backend/config/settings.py` | JWT service settings |
| `backend/config/urls.py` | Include internal AI URLs |
| `backend/requirements.txt` | Added `PyJWT` |
| `.env.example` | JWT service env var placeholders |
| `.cursor/rules/phase-2.2-internal-ai-auth.mdc` | Cursor scope rule |

---

## Auth flow

```
FastAPI agent                    Django /internal/ai/*
     |                                    |
     |  Authorization: Bearer <service_jwt> |
     |----------------------------------->|
     |                                    | InternalAIAuthentication
     |                                    |   - require Bearer scheme
     |                                    |   - decode_service_jwt()
     |                                    |   - validate claims + service name
     |                                    |   - set request.ai_service, tenant_id, store_id
     |                                    | InternalAIAuthCheckView (or future internal APIs)
     |<-----------------------------------|
     |  200 + service/tenant/store ids   |
```

Human dashboard users authenticate via Django session on `/api/auth/*`. That session is **not** accepted on `/internal/ai/*` because those views use only `InternalAIAuthentication`.

---

## Required JWT claims

| Claim | Description |
|-------|-------------|
| `sub` | Service name (must be in allowed registry) |
| `tenant_id` | Tenant identifier (UUID or int as string) |
| `store_id` | Store identifier (UUID or int as string) |
| `iat` | Issued-at timestamp |
| `exp` | Expiration timestamp |
| `aud` | Audience (must match `JWT_SERVICE_AUDIENCE`) |

Optional (reserved for later workflows):

| Claim | Description |
|-------|-------------|
| `report_run_id` | Correlates token to a report run (mint helper supports it; not required for auth-check) |

Example payload:

```json
{
  "sub": "coordinator-agent",
  "tenant_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "store_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "iat": 1719300000,
  "exp": 1719301800,
  "aud": "ai-services"
}
```

---

## Allowed service names

| Constant | Value |
|----------|-------|
| `AI_SERVICE_COORDINATOR` | `coordinator-agent` |
| `AI_SERVICE_SALES` | `sales-agent` |
| `AI_SERVICE_CONTENT` | `content-agent` |
| `AI_SERVICE_SUPPORT` | `support-agent` |

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SERVICE_SECRET` | *(required in production)* | HMAC signing secret shared with AI services |
| `JWT_SERVICE_AUDIENCE` | `ai-services` | Expected `aud` claim |
| `JWT_SERVICE_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_SERVICE_TOKEN_LIFETIME_MINUTES` | `30` | Default TTL when minting tokens |

`.env.example` placeholders:

```env
JWT_SERVICE_SECRET=change-me-in-local-dev
JWT_SERVICE_AUDIENCE=ai-services
JWT_SERVICE_ALGORITHM=HS256
JWT_SERVICE_TOKEN_LIFETIME_MINUTES=30
```

When `DEBUG=False`, Django raises `ImproperlyConfigured` at startup if `JWT_SERVICE_SECRET` is missing. Tests use `@override_settings` with an explicit test secret — no insecure silent default.

---

## Protected test endpoint

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/internal/ai/auth-check/` | Service JWT only | Verifies internal AI authentication |

### Example request

```http
GET /internal/ai/auth-check/
Authorization: Bearer <service_jwt>
```

### Example success response (`200 OK`)

```json
{
  "detail": "Internal AI authentication successful.",
  "service_name": "coordinator-agent",
  "tenant_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "store_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```

### Expected failure behavior

| Condition | HTTP status |
|-----------|-------------|
| Missing `Authorization` header | `401 Unauthorized` |
| Non-Bearer scheme (e.g. `Token ...`) | `401 Unauthorized` |
| Malformed or invalid JWT | `401 Unauthorized` |
| Unknown `sub` service name | `401 Unauthorized` |
| Expired token | `401 Unauthorized` (via PyJWT decoder) |
| Wrong `aud` | `401 Unauthorized` (via PyJWT decoder) |
| Session-authenticated human without service JWT | `401 Unauthorized` |

Responses do not include raw token values, signing secrets, or full JWT claim payloads.

---

## Request context attached on success

`InternalAIAuthentication` sets:

- `request.user` → `AIServiceIdentity` (DRF convention)
- `request.ai_service` → `AIServiceIdentity`
- `request.service_name` → service name string
- `request.tenant_id` → tenant id string
- `request.store_id` → store id string

---

## Tests added

`backend/accounts/tests/test_internal_ai_auth.py`:

1. Valid service JWT can access `GET /internal/ai/auth-check/`
2. Missing Authorization header is rejected
3. Non-Bearer Authorization header is rejected
4. Malformed Bearer token is rejected
5. Unknown service name is rejected
6. Session-authenticated human user cannot access without a valid service JWT
7. Another allowed service name (`sales-agent`) is accepted

### How to run tests

```bash
cd backend
pip install -r requirements.txt
python manage.py test accounts.tests.test_internal_ai_auth
```

Run all account tests:

```bash
python manage.py test accounts
```

---

## Security notes

- Internal AI routes use `InternalAIAuthentication` **explicitly** — not the global default session auth.
- Human dashboard sessions do not grant access to `/internal/ai/*`.
- Raw JWT values and secrets must not appear in logs or API responses.
- `JWT_SERVICE_SECRET` must be set in production (`DEBUG=False` enforces this at startup).
- Agents must call Django HTTP APIs only; they do not receive database credentials or ORM access.

---

## Next steps (Phase 2.3)

- Explicit hardening and test coverage for expired tokens and wrong-audience tokens
- Consistent 401 error response shapes across all internal AI auth failures
- Optional middleware or shared permission class for `/internal/ai/*` namespace
- Reject tokens when `tenant_id` / `store_id` do not match route parameters (when internal business APIs exist in Phase 3)

## Next steps (Phase 2.4)

- Full unit tests for `mint_service_jwt` and `decode_service_jwt` edge cases
- Integration with Celery report-run token issuance

## Next steps (Phase 3)

- Internal read APIs (sales, products, messages) protected by `InternalAIAuthentication`
- PII sanitizer before data crosses the AI boundary

---

*End of Step 2.2 documentation.*
