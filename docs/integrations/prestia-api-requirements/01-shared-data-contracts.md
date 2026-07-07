# Shared Data Contracts

Common conventions for Prestia APIs consumed by Botkonak.

## Design principles

1. **Match Botkonak's normalized shapes** where they already exist in `backend/catalog/services.py` and `backend/catalog/context.py`.
2. **Stable field names** — use Prestia-native names in Prestia responses; document mapping to Botkonak internal names.
3. **PII minimization for AI paths** — support message bodies may contain customer text; Prestia may return raw text and Botkonak will redact emails/phones (`backend/catalog/pii.py`) before agents consume data.
4. **JSON only** — `Content-Type: application/json` for requests and responses.

## Identifiers

| Concept | Prestia field (suggested) | Botkonak internal field | Notes |
|---------|---------------------------|-------------------------|-------|
| Store | `id` (UUID or stable string) | `store.id` | Mapped at connector onboarding |
| Tenant | `tenant_id` or implicit from token | `tenant.id` | Botkonak creates local tenant |
| Product | `slug` | `product_id` in AI bundle | Primary identifier; also map to local UUID |
| Category | `slug` | `category.slug` | Nested under product in context bundle |
| Order | `order_id` | `order_number`, `external_id` | `external_id` stores Prestia order id |
| Customer | `tenant_user_id` | opaque `customer-{uuid}` in AI APIs | Raw PII not passed to agents |
| Message thread | `id`, `external_thread_id` | `thread_id` | |
| Message | `id`, `external_message_id` | `message_id` | |

## Timestamps

- ISO 8601 with timezone offset, e.g. `"2026-06-25T12:00:00+00:00"`.
- Botkonak fields: `created_at`, `updated_at`, `placed_at`, `sent_at`, `last_message_at`, `generated_at`.

## Money and currency

- Monetary amounts as **numbers** (e.g. `189.00`) or decimal strings — Prestia should document which format is used; Botkonak normalizes on ingest.
- `currency` as ISO 4217 code, e.g. `"USD"`, `"IRR"`.
- Default currency configured in **Botkonak tenant settings**, not fetched from Prestia.

## Order status enum

Botkonak `OrderStatus` (`backend/catalog/models.py`):

| Status | Revenue counted in sales summary? |
|--------|-----------------------------------|
| `paid` | Yes |
| `completed` | Yes |
| `fulfilled` | Yes |
| `pending` | No |
| `draft` | No |
| `cancelled` | No |
| `refunded` | No |
| `failed` | No |

Prestia should map its order states to these values (or document a mapping table in the connector).

## Platform enum (support)

Botkonak `Platform` choices: `instagram`, `whatsapp`, `email`, `web`, `telegram`, `manual`.

Support agent coordinator defaults channel to `instagram_dm` when deriving messages from context (`agents/coordinator/nodes.py`). Prestia should use `platform: "instagram"` for Instagram DMs, `platform: "telegram"` for Telegram, `platform: "website"` for website chat.

## Message direction and sender

| Prestia (suggested) | Botkonak | Support agent alias |
|-----------------------|----------|---------------------|
| `direction: "inbound"` | `MessageDirection.INBOUND` | — |
| `direction: "outbound"` | `MessageDirection.OUTBOUND` | — |
| `sender_type: "customer"` | `SenderType.CUSTOMER` | `sender_role: "customer"` |
| `sender_type: "staff"` | `SenderType.STAFF` | `sender_role: "staff"` |
| `sender_type: "system"` | `SenderType.SYSTEM` | `sender_role: "system"` |

Support agent normalizes `body` → `text`, `sent_at` → `created_at` (`agents/support/support_context.py`).

## Pagination

**Requirement type:** Inferred for list endpoints — internal Botkonak AI endpoints return full bounded lists today (e.g. all active products, top 10 threads).

Suggested Prestia convention:

| Parameter | Type | Default | Max |
|-----------|------|---------|-----|
| `limit` | integer | 50 | 100 |
| `offset` | integer | 0 | — |
| `cursor` | string | — | optional cursor-based alternative |

**Response wrapper:**

```json
{
  "count": 120,
  "next": "https://api.prestia.ir/v1/products?cursor=eyJpZCI6MTIzfQ",
  "previous": null,
  "results": []
}
```

For AI-critical endpoints with fixed windows (recent messages), cursor pagination is optional if defaults match Botkonak limits (`thread_limit=10`, `messages_per_thread=5`).

## Filtering and sorting

Common query parameters Botkonak may need:

| Parameter | Applies to | Purpose |
|-----------|------------|---------|
| `is_active` | products | Content agent uses active products only |
| `search` | products, customers | Search by title/slug or phone/email/name |
| `category` | products | Filter by category slug |
| `price_min`, `price_max` | products | Price range filter |
| `currency` | products | Currency filter |
| `has_discount` | products | Discount filter |
| `inventory_lte`, `inventory_gte` | products | Variant quantity filters |
| `status` | orders | Filter by order status |
| `created_at_from`, `created_at_to` | orders | Order date range |
| `customer_id` | orders | Filter by customer |
| `product_slug` | orders | Orders containing product |
| `total_min`, `total_max` | orders | Order total range |
| `platform` | customers | Filter by message source |

Default sort:
- Products: `title` ascending
- Orders: `-created_at`
- Customers: `-updated_at`

## Error response shape

Align with Django REST Framework style used in Botkonak:

```json
{
  "detail": "Human-readable error message."
}
```

| HTTP status | When |
|-------------|------|
| `400` | Invalid query parameters |
| `401` | Missing or invalid Bearer token |
| `403` | Valid token but insufficient scope or wrong store |
| `404` | Resource not found |
| `429` | Rate limit exceeded |
| `500` | Server error |

Botkonak `DjangoClient` retries transient `502`, `503`, `504` on GET (`agents/shared/django_client/client.py`). Prestia should avoid using these for auth failures.

## Warnings pattern (aggregated responses)

Botkonak context bundle includes `warnings: []` for partial failures (`backend/catalog/context.py`). If Prestia offers an aggregated context endpoint, it may use the same pattern.

## Brand voice settings shape

Content Agent reads `store_context.settings.brand_voice` from **Botkonak tenant settings** (`agents/content/brand_voice.py`):

```json
{
  "brand_voice": {
    "tone": "warm, approachable",
    "audience": "fashion-conscious online shoppers",
    "style_notes": "short sentences; factual product claims only",
    "language": "fa"
  }
}
```

Configured in Botkonak tenant/store settings UI — not fetched from Prestia (see [02-store-profile-apis.md](./02-store-profile-apis.md)).

## Evidence from codebase

- `backend/catalog/models.py` — enums and field names
- `backend/catalog/context.py` — context bundle top-level keys
- `backend/catalog/pii.py` — PII redaction rules
- `agents/content/product_context.py` — field aliases (`name`/`title`, `image`/`image_url`)
- `agents/support/support_context.py` — message/thread field aliases
- `docs/phases/step-3.5.md` — example context bundle JSON

## Open questions

1. Whether Prestia uses UUIDs or integer IDs (Botkonak uses UUIDs locally; connector must map).
2. Standard rate limits for sync vs interactive calls.
3. Whether Prestia returns Persian digits in prices and whether normalization is needed before Django import.
