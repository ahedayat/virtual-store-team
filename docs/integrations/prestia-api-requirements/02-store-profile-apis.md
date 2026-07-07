# Store Profile Configuration

Store profile settings, brand tone, store metadata, and similar configuration are **not part of the Prestia API contract** for Botkonak.

## Botkonak responsibility

The following are configured and maintained inside **Botkonak tenant/store settings UI**, not fetched from Prestia:

| Setting | Used by | Notes |
|---------|---------|-------|
| Store display name | Content Agent, Coordinator context | e.g. `store_display_name` in tenant settings |
| Brand voice / tone | Content Agent | `settings.brand_voice` — tone, audience, style notes, language |
| Content agent limits | Content Agent | e.g. `content_agent_max_drafts_per_run` |
| Timezone | Sales Agent | Period boundaries for "today" and "last 7 days" |
| Default currency | Content Agent, Sales Agent | Display and aggregation context |

Botkonak agents read these values from the local Django `Store` and `Tenant.settings` models after the manager configures them in the dashboard.

## Prestia responsibility

Prestia does **not** need to expose:

- `GET /v1/store`
- `GET /v1/tenant`
- Any store profile or brand-settings API for Botkonak

OAuth token scope still resolves **which Prestia store** is connected; store identity for agents comes from Botkonak configuration plus Prestia catalog/order/customer data APIs.

## Related Botkonak files

- `backend/stores/models.py` — `Store` fields
- `backend/tenants/models.py` — `Tenant.settings`
- `agents/content/brand_voice.py` — brand voice extraction from local settings
- `agents/coordinator/nodes.py` — `_content_specialist_payload()` store_context from local data
- `backend/tenants/management/commands/seed_prestia.py` — demo tenant/store defaults

## Open questions

1. Whether Botkonak should pre-fill tenant settings from Prestia OAuth metadata (store name only) during onboarding — optional UX, not a Prestia API requirement.
2. Canonical timezone default for Iranian stores (`Asia/Tehran`).
