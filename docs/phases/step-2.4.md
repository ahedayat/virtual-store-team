# Step 2.4 — Service JWT Mint and Verify Tests

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Complete Phase 2 by thoroughly testing the service JWT minting and verification utilities used by internal AI services. The service JWT is the security boundary that allows FastAPI AI services to call Django internal AI APIs. It must carry service identity and tenant/store scope.

---

## Scope

- Focused unit tests for `mint_service_jwt` and `decode_service_jwt`
- Small refinements to the JWT helper (mint-time validation for `tenant_id` and `store_id`)
- Integration checks proving minted tokens work with `InternalAIAuthentication` and `GET /internal/ai/auth-check/`
- Cursor scope rule at `.cursor/rules/phase-2.4-service-jwt-tests.mdc`

---

## Explicit non-goals

- Phase 3 store data or internal commerce APIs (products, orders, inventory, sales summary, context bundles)
- Customer messages, PII sanitizer, report generation, actions
- Celery workflows, FastAPI agents, or coordinator orchestration
- `ReportRun`, `DailyReport`, `AgentOutput`, or `Action` models
- Prestia-specific behavior or hardcoded demo commerce data

---

## Files changed

| File | Purpose |
|------|---------|
| `backend/accounts/service_jwt.py` | `ServiceJWTMintError`; required `tenant_id`/`store_id` validation at mint time |
| `backend/accounts/tests/test_service_jwt.py` | Phase 2.4 mint, verify, and integration tests |
| `.cursor/rules/phase-2.4-service-jwt-tests.mdc` | Cursor scope rule for this step |
| `docs/phases/step-2.4.md` | This document |

Phase 2.1–2.3 files (`authentication.py`, `internal_views.py`, `test_internal_ai_auth*.py`, etc.) remain unchanged except where they consume the existing JWT utility.

---

## Service JWT lifecycle

```
┌─────────────────────┐     mint_service_jwt()      ┌──────────────────┐
│ Celery / tests /    │ ──────────────────────────► │ Signed JWT       │
│ future issuance     │   (secret + claims)         │ (Bearer token)   │
└─────────────────────┘                             └────────┬─────────┘
                                                             │
                                                             ▼
┌─────────────────────┐   Authorization: Bearer …   ┌──────────────────┐
│ FastAPI AI service  │ ──────────────────────────► │ InternalAIAuth   │
└─────────────────────┘                             └────────┬─────────┘
                                                             │
                                                             ▼
                                                    decode_service_jwt()
                                                    attach service context
                                                    to request
```

Human dashboard session authentication does **not** participate in this flow. Internal AI routes require a valid service JWT only.

---

## Required claims

| Claim | Description |
|-------|-------------|
| `sub` | AI service name (must be in the allowed registry) |
| `tenant_id` | Tenant scope (UUID or integer as string) |
| `store_id` | Store scope (UUID or integer as string) |
| `iat` | Issued-at timestamp |
| `exp` | Expiration timestamp |
| `aud` | Audience (must match `JWT_SERVICE_AUDIENCE`) |

Example payload:

```json
{
  "sub": "coordinator-agent",
  "tenant_id": "uuid-or-int",
  "store_id": "uuid-or-int",
  "iat": 1234567890,
  "exp": 1234568790,
  "aud": "ai-services"
}
```

---

## Optional claims

| Claim | Description |
|-------|-------------|
| `report_run_id` | Included only when minting for a specific report run (Phase 3+) |

---

## Allowed service names

- `coordinator-agent`
- `sales-agent`
- `content-agent`
- `support-agent`

Defined in `backend/accounts/constants.py` as `ALLOWED_AI_SERVICES`.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `JWT_SERVICE_SECRET` | *(required in production)* | HMAC signing secret shared with AI services |
| `JWT_SERVICE_AUDIENCE` | `ai-services` | Expected `aud` claim |
| `JWT_SERVICE_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_SERVICE_TOKEN_LIFETIME_MINUTES` | `30` | Default TTL when minting tokens |

`.env.example` documents:

```env
JWT_SERVICE_SECRET=change-me-in-local-dev
JWT_SERVICE_AUDIENCE=ai-services
JWT_SERVICE_ALGORITHM=HS256
JWT_SERVICE_TOKEN_LIFETIME_MINUTES=30
```

When `DEBUG=False`, Django raises `ImproperlyConfigured` at startup if `JWT_SERVICE_SECRET` is missing.

---

## Minting behavior

`mint_service_jwt()` in `backend/accounts/service_jwt.py`:

- Requires a valid `service_name` from `ALLOWED_AI_SERVICES`
- Requires non-empty `tenant_id` and `store_id`
- Includes `sub`, `tenant_id`, `store_id`, `iat`, `exp`, and `aud`
- Includes `report_run_id` only when provided
- Uses `JWT_SERVICE_SECRET`, `JWT_SERVICE_ALGORITHM`, and `JWT_SERVICE_AUDIENCE` from settings
- Uses `JWT_SERVICE_TOKEN_LIFETIME_MINUTES` unless `lifetime_minutes` is passed
- Never logs or prints the token

Mint-time validation failures raise `ServiceJWTMintError` or `UnknownServiceError`.

---

## Verification behavior

`decode_service_jwt()` in `backend/accounts/service_jwt.py`:

- Verifies signature using the configured secret and algorithm
- Verifies audience and expiration via PyJWT
- Requires all mandatory claims (`sub`, `tenant_id`, `store_id`, `iat`, `exp`, `aud`)
- Verifies `sub` is in `ALLOWED_AI_SERVICES`
- Returns the validated claims dict on success
- Raises typed `ServiceJWTError` subclasses on failure (no raw PyJWT messages to callers)

`InternalAIAuthentication` maps these exceptions to safe DRF `AuthenticationFailed` responses (Phase 2.3).

---

## Failure behavior

| Failure | Exception | API `detail` (via `InternalAIAuthentication`) |
|---------|-----------|-----------------------------------------------|
| Expired token | `ExpiredServiceJWTError` | `Internal service token has expired.` |
| Wrong audience | `InvalidServiceJWTAudienceError` | `Invalid internal service token audience.` |
| Bad signature, malformed, missing claims, unknown service | `InvalidServiceJWTError` / `UnknownServiceError` | `Invalid internal service token.` |
| Missing `tenant_id`/`store_id` at mint time | `ServiceJWTMintError` | *(not an API path — mint helper only)* |

Responses never include raw tokens, signing secrets, stack traces, or PyJWT library details.

---

## Tests added

### Mint tests (`ServiceJWTMintTests`)

1. Returns a string token
2. Required claims present after verification
3. Correct `sub`, `tenant_id`, `store_id`, `aud`
4. `iat` and `exp` present; `exp` after `iat`
5. Default lifetime from `JWT_SERVICE_TOKEN_LIFETIME_MINUTES`
6. Custom `lifetime_minutes` override
7. Optional `report_run_id` included / absent
8. Unknown service name rejected
9. Missing `tenant_id` / `store_id` rejected

### Verify tests (`ServiceJWTVerifyTests`)

1. Valid minted token verifies
2. Wrong secret, wrong audience, expired token rejected
3. Missing `sub`, `tenant_id`, `store_id`, `aud` rejected
4. Unknown `sub` rejected
5. Malformed, empty, and unexpected-algorithm tokens rejected

### Integration tests (`ServiceJWTIntegrationTests`)

1. Minted token accesses `GET /internal/ai/auth-check/`
2. Response includes `service_name`, `tenant_id`, `store_id`
3. Session-authenticated dashboard user cannot access without service JWT

Earlier Phase 2.2 and 2.3 tests in `test_internal_ai_auth.py` and `test_internal_ai_auth_401.py` remain and complement this suite.

---

## How to run tests

From the repository root (with the backend environment active):

```bash
cd backend
python manage.py test accounts.tests.test_service_jwt
```

Run all accounts tests:

```bash
python manage.py test accounts
```

---

## Security notes

- Service JWTs scope AI services to a specific tenant and store — agents must not call internal APIs outside that scope.
- Tokens are short-lived; default TTL is 30 minutes (configurable).
- Tests use `@override_settings` with explicit test secrets — no production values.
- Raw JWT values and secrets must not appear in logs, API responses, or test assertion bodies.
- Human session auth and service JWT auth are separate paths; internal AI routes use `InternalAIAuthentication` only.

---

## Known limitations

- Token issuance for production report runs is not wired to Celery yet (Phase 3+).
- Route-parameter tenant/store matching against JWT claims is deferred until Phase 3 internal business APIs exist.
- Only `HS256` is configured for MVP; algorithm allow-list is enforced at decode time.
- Mint helper is used in tests today; production issuance will share the same utility.

---

## Phase 2 completion summary

Phase 2 (Auth & Users) is now complete:

| Step | Deliverable |
|------|-------------|
| 2.1 | Manager login, logout, and `/api/auth/me/` session APIs |
| 2.2 | `InternalAIAuthentication`, service JWT utility, internal auth-check endpoint |
| 2.3 | Hardened 401 behavior for invalid service JWTs |
| 2.4 | Full mint/verify unit tests and integration proof for the token lifecycle |

The platform can authenticate human managers for the dashboard and authenticate AI services for internal routes using scoped service JWTs.

---

## Next steps for Phase 3

Phase 3 introduces **store data and internal read APIs** for AI agents:

- Tenant-scoped product, order, inventory, and customer message models
- PII sanitizer before data leaves Django for LLM calls
- Internal endpoints such as AI context bundles, sales summary, low-stock, products, and recent messages
- `ReportRun` and related report/action workflow models
- Celery-driven report generation that mints service JWTs for agent calls

Authentication infrastructure from Phase 2 remains the foundation; Phase 3 builds business data and read APIs on top of it.
