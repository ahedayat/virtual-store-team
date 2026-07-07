# Authentication and Token Usage

How Botkonak must authenticate when calling Prestia APIs.

## Overview

Botkonak connects to Prestia using **OAuth 2.0**. After authorization, Botkonak calls Prestia REST APIs with a **Bearer access token** in the `Authorization` header. This matches how Botkonak agents already call Django internal APIs (`agents/shared/django_client/client.py`).

**Requirement type:** Inferred — no Prestia OAuth or connector code exists in the repository today. The pattern is required for the stated integration goal and aligns with existing `Authorization: Bearer` usage.

## Required request headers

Every Prestia API request from Botkonak **must** include:

```http
Authorization: Bearer <access_token>
Accept: application/json
Content-Type: application/json
```

Optional correlation header (Botkonak already sends this to Django):

```http
X-Request-ID: <uuid-or-trace-id>
```

## Tenant identification

In a proper OAuth 2.0 integration:

- The **access token represents the authorized Prestia store/tenant**.
- Prestia **resolves tenant and store scope server-side** from the token.
- Botkonak **must not** pass store IDs or tenant secrets in query parameters for authentication.
- Path parameters such as `/products` apply to the store implied by the token unless Prestia documents multi-store tokens.

This mirrors Botkonak's internal model: Django `InternalAIAuthentication` derives `tenant_id` and `store_id` from the service JWT, not from request body fields (`backend/catalog/internal_views.py`).

## OAuth concepts

### Access token

- Short-lived credential used on every Prestia API call.
- Sent only in the `Authorization` header using the Bearer scheme.
- Must not appear in URLs, query strings, or browser-visible logs.

### Refresh token

- **Recommended (P1)** for long-lived Botkonak connections without repeated manager consent.
- Botkonak exchanges it at Prestia's token endpoint for a new access token.
- Not referenced in current Botkonak code (service JWTs are minted per report run).

### Token expiration

- Prestia should return `expires_in` (seconds) on token issuance.
- Botkonak should refresh or re-authorize before expiry.
- Expired token → Prestia returns `401 Unauthorized` with a machine-readable error body.

### Token scopes

Scopes should be **derived from read APIs Botkonak actually needs**. Suggested scope list:

| Scope | Maps to Prestia API group | Required by codebase |
|-------|---------------------------|----------------------|
| `read:products` | Products, categories | Yes — content agent, sales agent, context bundle |
| `read:orders` | Orders | Yes — sales aggregation (computed locally) |
| `read:customers` | Customer list | Yes — Support CRM sync |
| `read:faqs` | FAQ list | Yes — support agent |
| `write:support_replies` | Post support replies | **Not required** — no outbound Prestia write in code |
| `write:content_drafts` | Publish content | **Not required** — drafts stay in Botkonak |
| `write:recommendations` | Apply discounts/restock | **Not required** — actions are approval stubs |

**Not required:** `read:store` (Botkonak tenant settings), `read:analytics` (no Prestia sales summary), `read:inventory` (inventories on products), `read:support_messages` (webhook ingestion).

### Token revocation

- Prestia should support revocation when a manager disconnects Botkonak.
- After revocation, previously issued access and refresh tokens must be rejected (`401`).

### How Prestia should validate tokens

1. Verify signature (JWT) or lookup (opaque token) on every request.
2. Check expiration and revocation status.
3. Enforce scopes per endpoint.
4. Bind the token to exactly one store (and tenant) for Botkonak's use case.
5. Return `403 Forbidden` when the token is valid but lacks scope.

### Why Botkonak must not send tokens in query parameters

- Query strings appear in proxy logs, browser history, and referrer headers.
- OAuth 2.0 Bearer Token Usage (RFC 6750) specifies the `Authorization` header.
- Botkonak's `DjangoClient` already uses header-based auth only (`agents/shared/django_client/client.py`).

### Why HTTPS is required

- Bearer tokens are equivalent to passwords for API access.
- All Prestia OAuth and API endpoints must use TLS (`https://`).

## OAuth endpoints (Prestia must expose)

### 1. Authorization endpoint

| Property | Value |
|----------|-------|
| **API name** | OAuth 2.0 Authorization |
| **HTTP method** | `GET` (browser redirect) |
| **Suggested path** | `https://prestia.ir/oauth/authorize` |
| **Botkonak consumer** | Admin onboarding / Background sync (token acquisition) |
| **Requirement type** | Inferred |
| **Priority** | P0 |

**Query parameters:** `client_id`, `redirect_uri`, `response_type=code`, `scope`, `state`

**Successful result:** Redirect to Botkonak with `code` and `state`.

### 2. Token endpoint

| Property | Value |
|----------|-------|
| **API name** | OAuth 2.0 Token Exchange |
| **HTTP method** | `POST` |
| **Suggested path** | `https://api.prestia.ir/v1/oauth/token` |
| **Botkonak consumer** | Background sync, Coordinator (via stored credentials) |
| **Requirement type** | Inferred |
| **Priority** | P0 |

**Request body (authorization code grant):**

```json
{
  "grant_type": "authorization_code",
  "code": "<authorization_code>",
  "redirect_uri": "https://botkonak.example/oauth/callback",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>"
}
```

**Request body (refresh grant):**

```json
{
  "grant_type": "refresh_token",
  "refresh_token": "<refresh_token>",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>"
}
```

**Successful response:**

```json
{
  "access_token": "prestia_at_abc123",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "prestia_rt_xyz789",
  "scope": "read:products read:orders read:customers read:faqs"
}
```

**Error cases:** `400` invalid_grant, `401` invalid_client

### 3. Token revocation endpoint

| Property | Value |
|----------|-------|
| **API name** | OAuth 2.0 Token Revocation |
| **HTTP method** | `POST` |
| **Suggested path** | `https://api.prestia.ir/v1/oauth/revoke` |
| **Botkonak consumer** | Admin Dashboard (disconnect store) |
| **Requirement type** | Inferred |
| **Priority** | P1 |

## Example authenticated API request

```http
GET /v1/products?is_active=true&limit=100 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
X-Request-ID: 7c9e6679-7425-40de-944b-e07fc1f90ae7
```

## Security notes

- Store `client_secret`, access tokens, and refresh tokens only on Botkonak backend; never in Next.js client bundles.
- Rotate tokens on scope changes or store ownership transfer.
- Log `X-Request-ID` for cross-service debugging; never log full tokens (Botkonak coordinator already avoids logging JWTs — `docs/agents/coordinator.md`).

## Evidence from codebase

- `agents/shared/django_client/client.py` — `_build_headers()` sets `Authorization: Bearer`, `Accept`, `Content-Type`
- `backend/accounts/authentication.py`, `backend/accounts/service_jwt.py` — internal JWT pattern for AI services
- `docs/phases/step-2.2.md` — internal AI auth design
- `backend/catalog/internal_views.py` — store scope from token identity, not URL alone

## Open questions

1. Exact OAuth flow Prestia supports (authorization code vs client credentials for server-to-server).
2. Whether Prestia issues JWT or opaque access tokens.
3. Whether a single Prestia account can authorize multiple stores (Botkonak `Store` is per-tenant scoped).
