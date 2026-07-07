# Customer APIs

APIs for customer information and order history.

## Current Botkonak need assessment

Customer data exists in Botkonak (`backend/catalog/models.py` — `Customer`) and is seeded for Prestia support demos. The Support Agent maintains a **tenant-level CRM** in Botkonak that unifies customers from website, Instagram, Telegram, and future channels.

- **AI-facing APIs never expose raw PII** — messages use opaque `customer_ref` (`catalog/pii.py`)
- **Sales Agent** explicitly avoids customer PII in prompts (`agents/sales/prompts.py`)
- Customer records from Prestia sync supplement Botkonak CRM context

---

## API: List Customers

| Property | Value |
|----------|-------|
| **API name** | List Customers |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/customers` |
| **Botkonak consumer** | Support Agent CRM, on-demand fetch |
| **Why Botkonak needs this** | Populate and reconcile `Customer` rows in Botkonak tenant database. Links `platform` + `platform_user_id` to support threads. |
| **Requirement type** | Direct |
| **Priority** | P1 |

### Required request headers

`Authorization: Bearer <access_token>`, `Accept: application/json`

### Query parameters — pagination

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | Yes | Page size (default 50, max 100) |
| `offset` | integer | Yes | Pagination offset (default 0) |

### Query parameters — filters and search

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `platform` | string | No | Filter by source platform (e.g. `website`, `instagram`, `telegram`) |
| `search` | string | No | Search by `phone`, `email`, or `display_name` |

### Successful response shape

```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "botkonak_customer_id": "bk-cust-001",
      "tenant_user_id": "prestia-cust-001",
      "display_name": "Sara Jamali",
      "email": "sara.jamali@example.com",
      "phone": "09121234567",
      "platform": "instagram",
      "platform_user_id": "ig-prestia-001",
      "metadata": {},
      "created_at": "2025-06-01T10:00:00+00:00",
      "updated_at": "2026-06-20T12:00:00+00:00"
    }
  ]
}
```

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| `botkonak_customer_id` | string | Botkonak-assigned customer identifier when linked |
| `tenant_user_id` | string | Prestia tenant-scoped customer identifier |
| `display_name` | string | Customer display name |
| `email` | string \| null | Email address |
| `phone` | string \| null | Phone number |
| `platform` | string | Source platform — `website`, `instagram`, `telegram`, etc. |
| `platform_user_id` | string \| null | Customer identifier on the external platform when available |
| `metadata` | object | Additional customer-level information |
| `created_at` | datetime | Record creation time |
| `updated_at` | datetime | Last update time |

### Important fields — Botkonak mapping

| Field | Botkonak model field | AI exposure |
|-------|---------------------|-------------|
| `platform` | `Customer.platform` | Thread metadata only |
| `platform_user_id` | `Customer.platform_user_id` | Not in AI APIs |
| `display_name`, `email`, `phone` | same | **Admin only** — redacted in agent paths |

### Security notes

- Botkonak must **not** forward email/phone to agents.
- PII stored in Django/Postgres; AI APIs sanitize message bodies only.

### Example request

```http
GET /v1/customers?limit=50&offset=0&platform=instagram&search=sara HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

### Related files

- `backend/catalog/models.py` — `Customer`
- `seed_prestia.py` — `PRESTIA_CUSTOMERS`
- `backend/catalog/management/commands/import_messages_json.py` — customer import

---

## API: Get Customer Order History

| Property | Value |
|----------|-------|
| **API name** | Get Customer Order History |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/customer/{tenant_customer_id}/orders` |
| **Botkonak consumer** | Support Agent, Sales Agent, Admin Dashboard |
| **Why Botkonak needs this** | Order history for a specific customer. Support replies and sales follow-up may reference past purchases. |
| **Requirement type** | Inferred |
| **Priority** | P1 |

### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `tenant_customer_id` | string | Prestia tenant-scoped customer id (`tenant_user_id`) |

### Query parameters

Same pagination and filters as [List Orders](./04-order-and-sales-apis.md):

- `limit`, `offset`
- `created_at_from`, `created_at_to`
- `customer_id` (redundant when scoped by path — optional)
- `product_slug`
- `total_min`, `total_max`
- `status`

### Successful response

Paginated list of order objects — **same schema as `GET /v1/orders`**.

### Related files

- `frontend/types/mock-data.ts` — `mockRecommendations` follow-up payload
- `agents/shared/schemas/sales.py` — `sales.follow_up` action type

---

## Customer segmentation / analytics

**Not required by existing code.** No segmentation models or APIs in Botkonak.

**Requirement type:** Optional (Future)

---

## Evidence from codebase

- `backend/catalog/models.py` — `Customer` with platform-scoped unique constraint
- `backend/catalog/pii.py` — PII not exported to AI
- `docs/phases/step-3.4.md` — customer model rationale
- `frontend/hooks/use-customers.ts` — mock data only

## Open questions

1. Whether Prestia exposes Instagram `platform_user_id` for DM customers.
2. GDPR/consent for storing customer PII in Botkonak after sync.
3. Mapping between `tenant_user_id` and `botkonak_customer_id` during onboarding.
