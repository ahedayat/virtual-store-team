# Step 2.3 — Service JWT 401 Hardening

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Harden the internal AI authentication layer so invalid service JWTs consistently fail with safe `401 Unauthorized` responses. FastAPI AI services must present valid Bearer service JWTs to access `/internal/ai/*` routes; expired, wrong-audience, malformed, or otherwise invalid tokens must be rejected without leaking secrets or low-level JWT library details.

---

## Scope

- Normalize service JWT validation errors into typed internal exceptions
- Map validation failures to safe, consistent DRF `AuthenticationFailed` responses
- Ensure all listed authentication failure cases return HTTP **401**
- Return `WWW-Authenticate: Bearer` on Bearer authentication failures
- Add focused Phase 2.3 tests for rejection behavior
- Cursor scope rule at `.cursor/rules/phase-2.3-service-jwt-401-hardening.mdc`

---

## Explicit non-goals

- Phase 2.4 full token mint/verify lifecycle test suite
- Phase 3 internal commerce/read APIs (products, orders, sales summary, context bundles)
- PII sanitizer, report generation, actions, or agent workflows
- Celery token issuance wiring
- Prestia-specific logic or hardcoded tenant data
- Global registration of `InternalAIAuthentication` as the default DRF auth class
- Route-parameter tenant/store matching (deferred until Phase 3 internal business APIs exist)

---

## Files changed

| File | Purpose |
|------|---------|
| `backend/accounts/service_jwt.py` | Typed JWT exceptions; PyJWT error mapping without leaking library messages |
| `backend/accounts/authentication.py` | Safe client-facing 401 messages; `WWW-Authenticate: Bearer` |
| `backend/accounts/tests/test_internal_ai_auth_401.py` | Phase 2.3 focused 401 rejection tests |
| `.cursor/rules/phase-2.3-service-jwt-401-hardening.mdc` | Cursor scope rule for this step |
| `docs/phases/step-2.3.md` | This document |

Phase 2.2 files (`internal_views.py`, `internal_urls.py`, `constants.py`, etc.) remain unchanged except where they consume the hardened auth layer.

---

## JWT failure cases covered

| Failure | HTTP status | `detail` message |
|---------|-------------|------------------|
| Missing `Authorization` header | `401` | `Authorization header is required.` |
| Non-Bearer scheme | `401` | `Invalid authorization header. Expected Bearer token.` |
| `Bearer` without token value | `401` | `Invalid internal service token.` |
| Empty Bearer token | `401` | `Invalid internal service token.` |
| Malformed JWT | `401` | `Invalid internal service token.` |
| Expired JWT | `401` | `Internal service token has expired.` |
| Wrong `aud` audience | `401` | `Invalid internal service token audience.` |
| Invalid signature | `401` | `Invalid internal service token.` |
| Missing required claim (`sub`, `tenant_id`, `store_id`, `exp`, `aud`, `iat`) | `401` | `Invalid internal service token.` |
| Unknown/disallowed `sub` service name | `401` | `Invalid internal service token.` |
| Session-authenticated human without service JWT | `401` | *(header-related or generic auth failure)* |

Internal exception types in `service_jwt.py`:

- `ExpiredServiceJWTError`
- `InvalidServiceJWTAudienceError`
- `InvalidServiceJWTError` (malformed, bad signature, missing claims, unsupported algorithm)
- `UnknownServiceError` (unregistered service name)

---

## Expected 401 behavior

All failures on `/internal/ai/*` routes protected by `InternalAIAuthentication` return **401 Unauthorized**, not **403 Forbidden**.

Responses include:

```http
WWW-Authenticate: Bearer
```

Response bodies use DRF's standard `{"detail": "..."}` format. Raw token values, signing secrets, stack traces, and PyJWT exception strings are never included.

### Example expired-token response

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer
Content-Type: application/json

{
  "detail": "Internal service token has expired."
}
```

### Example wrong-audience response

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer
Content-Type: application/json

{
  "detail": "Invalid internal service token audience."
}
```

### Example generic invalid-token response

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer
Content-Type: application/json

{
  "detail": "Invalid internal service token."
}
```

---

## Security notes

- API responses do **not** echo the submitted Bearer token.
- Signing secrets (`JWT_SERVICE_SECRET`) never appear in responses or test assertion bodies.
- PyJWT error messages and stack traces are caught internally and replaced with safe `detail` strings.
- Human dashboard sessions do **not** grant access to `/internal/ai/*` — those views use only `InternalAIAuthentication`.
- Raw token values must not be logged (no logging of Authorization header values was added in this step).

---

## Tests added

`backend/accounts/tests/test_internal_ai_auth_401.py`:

1. Expired service JWT returns 401 with safe expired message
2. Wrong-audience service JWT returns 401 with safe audience message
3. Invalid signature returns 401
4. Missing required claim returns 401 (parameterized over `sub`, `tenant_id`, `store_id`, `exp`, `aud`)
5. Unknown service name returns 401
6. Malformed token returns 401
7. Empty Bearer token returns 401
8. `Bearer` keyword without token returns 401
9. Session-authenticated manager cannot access without a valid service JWT
10. Valid service JWT still succeeds after hardening
11. Error responses do not echo the raw token value

Phase 2.2 tests in `test_internal_ai_auth.py` continue to pass and cover the original auth-check behavior.

### How to run tests

```bash
cd backend
pip install -r requirements.txt
python manage.py test accounts.tests.test_internal_ai_auth_401
```

Run all internal AI auth tests (Phase 2.2 + 2.3):

```bash
python manage.py test accounts.tests.test_internal_ai_auth accounts.tests.test_internal_ai_auth_401
```

Run all account tests:

```bash
python manage.py test accounts
```

---

## Known limitations

- `mint_service_jwt` / `decode_service_jwt` unit-level edge cases (clock skew, custom lifetimes, `report_run_id` round-trip) are deferred to **Phase 2.4**.
- Missing `JWT_SERVICE_SECRET` at runtime raises `ImproperlyConfigured` (server misconfiguration); production startup already enforces the secret when `DEBUG=False`.
- Tenant/store ID validation against URL route parameters is not implemented until Phase 3 internal business APIs exist.
- Only the minimal `GET /internal/ai/auth-check/` endpoint is protected; Phase 3 will add further internal routes using the same auth class.

---

## Next steps (Phase 2.4)

- Full unit tests for `mint_service_jwt` and `decode_service_jwt` edge cases
- Token lifetime and `report_run_id` claim round-trip coverage
- Integration with Celery report-run token issuance (Phase 5)

## Next steps (Phase 3)

- Internal read APIs (sales, products, messages) protected by `InternalAIAuthentication`
- Reject tokens when `tenant_id` / `store_id` do not match route parameters
- PII sanitizer before data crosses the AI boundary

---

*End of Step 2.3 documentation.*
