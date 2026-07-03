# Store Profile APIs

APIs needed to fetch store identity, brand profile, settings, and business metadata.

## API: Get Store Profile

| Property | Value |
|----------|-------|
| **API name** | Get Store Profile |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/store` |
| **Botkonak consumer** | Coordinator Agent, Content Agent, Admin Dashboard, Background sync |
| **Why Botkonak needs this** | Daily report context bundle includes `tenant` and `store` metadata (name, slug, timezone, currency). Content Agent uses store display name and `settings.brand_voice` for draft tone. Sales summary uses store timezone for "today" and "last 7 days" boundaries. |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Required request headers

```http
Authorization: Bearer <access_token>
Accept: application/json
```

### Query parameters

None. Store scope is implied by the token.

### Path parameters

None.

### Request body

Not applicable.

### Successful response shape

```json
{
  "id": "22222222-2222-2222-2222-222222222222",
  "external_id": "prestia-store-main",
  "name": "Prestia Online Store",
  "slug": "main",
  "timezone": "Asia/Tehran",
  "currency": "IRR",
  "tenant": {
    "id": "11111111-1111-1111-1111-111111111111",
    "slug": "prestia",
    "name": "Prestia"
  },
  "settings": {
    "store_display_name": "پرستیا",
    "brand_voice": {
      "tone": "گرم و صمیمی",
      "audience": "خریداران آنلاین کیف و اکسسوری",
      "style_notes": "جملات کوتاه؛ ادعاهای واقعی درباره محصول",
      "language": "fa"
    },
    "content_agent_max_drafts_per_run": 3
  },
  "created_at": "2025-01-15T08:00:00+00:00",
  "updated_at": "2026-06-20T14:30:00+00:00"
}
```

### Important fields

| Field | Used by |
|-------|---------|
| `id` | Connector mapping to Botkonak `Store.id` |
| `name` | Context bundle, content prompts |
| `slug` | Tenant-scoped store identification |
| `timezone` | Sales period boundaries (`get_period_bounds` in `catalog/services.py`) |
| `currency` | Product prices, sales summary |
| `tenant` | Multi-tenant scoping |
| `settings.brand_voice` | Content Agent (`agents/content/brand_voice.py`) |
| `settings.store_display_name` | Tenant seed uses this key (`seed_prestia.py`) |

### Pagination

Not applicable (single resource).

### Filtering and sorting

Not applicable.

### Error cases

| Status | Condition |
|--------|-----------|
| `401` | Invalid or expired token |
| `403` | Token not authorized for this store |

### Security notes

- Settings may contain marketing preferences; no secrets in this response.
- Token resolves store server-side.

### Example request

```http
GET /v1/store HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

### Example response

See successful response shape above.

### Related files

- `backend/stores/models.py` — `Store` fields
- `backend/tenants/models.py` — `Tenant.settings`
- `backend/catalog/context.py` — `tenant` and `store` in context bundle
- `backend/stores/serializers.py` — `StoreReadSerializer`
- `backend/stores/views.py` — dashboard `GET /api/stores/{store_id}/`
- `agents/content/brand_voice.py` — brand voice extraction
- `agents/coordinator/nodes.py` — `_content_specialist_payload()` store_context
- `backend/tenants/management/commands/seed_prestia.py` — Prestia tenant/store defaults

---

## API: Get Tenant Settings (optional split)

| Property | Value |
|----------|-------|
| **API name** | Get Tenant Settings |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/tenant` |
| **Botkonak consumer** | Content Agent, Background sync |
| **Why Botkonak needs this** | `Tenant.settings` holds `store_display_name` in seed data. May be merged into store profile instead. |
| **Requirement type** | Inferred |
| **Priority** | P2 |

If Prestia combines tenant and store in `GET /v1/store`, this endpoint is not needed.

### Evidence from codebase

- `backend/tenants/models.py` — `Tenant.settings` JSONField
- `seed_prestia.py` — `settings: {"store_display_name": "Prestia"}`

### Open questions

- Whether Prestia distinguishes tenant-level vs store-level settings in their data model.

## Evidence from codebase

Listed under each API above.

## Open questions

1. Does Prestia expose `content_agent_max_drafts_per_run` or should Botkonak use only env defaults (`CONTENT_AGENT_MAX_DRAFTS_PER_RUN`)?
2. Canonical timezone for Iranian stores (`Asia/Tehran` vs `America/New_York` in seed).
