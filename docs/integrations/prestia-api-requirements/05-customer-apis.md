# Customer APIs

APIs for customer information, order history, and segmentation.

## Current Botkonak need assessment

Customer data exists in Botkonak (`backend/catalog/models.py` — `Customer`) and is seeded for Prestia support demos. However:

- **AI-facing APIs never expose raw PII** — messages use opaque `customer_ref` (`catalog/pii.py`)
- **Sales Agent** explicitly avoids customer PII in prompts (`agents/sales/prompts.py`)
- **Frontend** uses mock customers only (`frontend/hooks/use-customers.ts`)
- **No customer analytics or segmentation** code exists

Customer APIs are primarily needed for **background sync** to populate `Customer` rows linked to message threads, not for direct agent consumption.

---

## API: List Customers

| Property | Value |
|----------|-------|
| **API name** | List Customers |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/customers` |
| **Botkonak consumer** | Background sync |
| **Why Botkonak needs this** | Populate `Customer` when importing support threads. Links `platform` + `platform_user_id` to threads. |
| **Requirement type** | Inferred |
| **Priority** | P2 |

### Required request headers

`Authorization: Bearer <access_token>`, `Accept: application/json`

### Query parameters

| Parameter | Description |
|-----------|-------------|
| `platform` | e.g. `instagram` |
| `updated_since` | Incremental sync |
| `limit`, `offset` | Pagination |

### Successful response shape

```json
{
  "count": 5,
  "results": [
    {
      "id": "66666666-6666-6666-6666-666666666666",
      "external_id": "ig-prestia-001",
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

### Important fields

| Field | Botkonak model field | AI exposure |
|-------|---------------------|-------------|
| `platform` | `Customer.platform` | Thread metadata only |
| `platform_user_id` | `Customer.platform_user_id` | Not in AI APIs |
| `display_name`, `email`, `phone` | same | **Admin only** — redacted in agent paths |

### Security notes

- Botkonak must **not** forward email/phone to agents.
- Sync stores PII in Django/Postgres; AI APIs sanitize message bodies only.

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
| **Suggested endpoint path** | `/v1/customers/{customer_id}/orders` |
| **Botkonak consumer** | Sales Agent (future), Admin Dashboard |
| **Why Botkonak needs this** | Mock UI `sales.follow_up` references VIP customer purchase history (`frontend/types/mock-data.ts`). **Not implemented** in sales agent backend logic. |
| **Requirement type** | Optional (Future) |
| **Priority** | Future |

### Successful response

Paginated list of order summary objects (no PII beyond opaque customer ref).

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

1. Does Prestia expose Instagram `platform_user_id` for DM customers?
2. GDPR/consent for storing customer PII in Botkonak after sync.
3. Whether VIP / repeat-buyer flags exist on Prestia side for future `sales.follow_up`.
