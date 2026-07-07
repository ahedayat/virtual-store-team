# Sync, Webhooks, and Refresh Strategy

How Botkonak keeps Prestia data fresh based on the **revised** integration model.

## Current state (no Prestia connector)

| Mechanism | What exists | Prestia involvement |
|-----------|-------------|---------------------|
| Demo seed | `python manage.py seed_prestia` | Static Prestia-shaped fixture data |
| Message import | `import_messages_json` command | JSON file import, not live API |
| Daily report | Celery `reports.generate_daily` on schedule/trigger | Reads **local Django DB** only |
| Real-time updates | None | None |

**There is no polling, webhook, or OAuth connector code in the repository today.**

---

## Core principle: on-demand data APIs + webhook message ingestion

| Pattern | Applies to | Behavior |
|---------|------------|----------|
| **On-demand API calls** | Products, orders, customers, FAQs, and similar data APIs | Botkonak calls Prestia **whenever the relevant agent needs fresh data** — not via a standing poll loop or broad webhook sync |
| **Webhook ingestion** | Support Agent messages only | Real-time delivery when users send messages on website, Instagram, or Telegram |

**Do not** describe a broad webhook-based sync system for all Prestia data unless clearly marked as a future enhancement.

---

## On-demand API fetch (default for all data APIs)

### When to call Prestia

| Trigger | Prestia endpoints | Rationale |
|---------|-------------------|-----------|
| **Before daily report** | `GET /v1/products`, `GET /v1/orders`, `GET /v1/faqs` | Coordinator context must reflect current Prestia state |
| **Agent-specific need** | Relevant endpoint for that agent | Sales Agent fetches orders + products; Content Agent fetches products; Support Agent fetches FAQs |
| **On OAuth connect** | Initial full fetch of catalog and historical orders | Bootstrap local cache |

### Data APIs (on-demand, not webhook-based)

| Prestia endpoint | Botkonak consumer | Fetch mode |
|------------------|-------------------|------------|
| `GET /v1/products` | Content Agent, Sales Agent, Coordinator | On demand |
| `GET /v1/orders` | Sales Agent, Coordinator | On demand |
| `GET /v1/customers` | Support Agent CRM sync | On demand |
| `GET /v1/faqs` | Support Agent | On demand |
| `GET /v1/categories` | Connector (optional) | On demand |

Store profile settings (`brand_voice`, timezone, currency) are **not** fetched from Prestia — configured in Botkonak tenant settings ([02-store-profile-apis.md](./02-store-profile-apis.md)).

Sales summaries are **computed by Botkonak** from orders and products — Prestia does not expose `GET /v1/sales/summary`.

### Pagination

Use `limit` and `offset` on list endpoints. Connector fetches all pages when building full context for a report run.

### Idempotency

Match Prestia stable identifiers (`slug`, `order_id`, `tenant_user_id`) to Botkonak `external_id` fields (`catalog/models.py`).

---

## Webhook-based message ingestion (Support Agent only)

The **only webhook-based integration currently required** is Support Agent message ingestion.

| Source | Webhook path | Prestia role |
|--------|--------------|--------------|
| Instagram | Platform → Botkonak | Optional relay; may connect directly |
| Telegram | Platform → Botkonak | Optional relay; may connect directly |
| Website | Prestia → Botkonak | **Prestia must send** website chat messages to Botkonak immediately |

When a message arrives:

1. Botkonak webhook receiver validates signature / secret.
2. Message stored in tenant support inbox.
3. Customer record created or updated in tenant CRM.
4. Support Agent reads from local DB (not live Prestia poll).

See [08-support-agent-apis.md](./08-support-agent-apis.md) for channel details.

### Webhook security

- HMAC signature verification or shared secret
- HTTPS only
- Idempotent processing by `message_id` / `external_message_id`

---

## Daily report timing

```
Manager POST /api/reports/generate/
    → Celery generate_daily
        → On-demand Prestia fetch (products, orders, FAQs)
        → Coordinator POST /workflows/daily-report
            → Django GET context (local DB + fresh fetch results)
            → Specialist agents
            → Django POST complete
```

Botkonak already prevents concurrent report runs per store (`unique_active_report_run_per_store` constraint in `operations/models.py`).

---

## Future enhancements (optional — not MVP)

These are **not required** for initial integration:

| Enhancement | Priority | Notes |
|-------------|----------|-------|
| `product.updated` webhook | Future | Would reduce on-demand catalog fetch latency |
| `order.created` webhook | Future | Would reduce on-demand order fetch latency |
| `inventory.updated` webhook | Future | Real-time stock alerts |
| Scheduled background sync job | Future | Alternative to purely on-demand if latency becomes an issue |

Mark all broad data webhooks as **Future / optional** — on-demand API calls are the MVP contract.

---

## On-demand refresh scenarios

| Scenario | Strategy |
|----------|----------|
| Manager triggers daily report | Fetch products, orders, FAQs from Prestia immediately before coordinator |
| Support Agent run | Read messages from local inbox (webhook-ingested); fetch FAQs on demand |
| Sales Agent run | Fetch orders + products on demand; compute summary locally |
| Content Agent run | Fetch products on demand |

---

## Token refresh during fetch

Long-running fetch jobs must refresh OAuth tokens via `POST /v1/oauth/token` (refresh grant) before expiry ([00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md)).

---

## Failure handling

Align with existing Botkonak patterns:

| Failure | Behavior |
|---------|----------|
| Prestia API down during fetch | Log error; optionally proceed with stale data + `warnings` in context bundle (`_safe_section` in `context.py`) |
| Partial section failure | Empty section + warning string (same as context bundle) |
| Fetch failure before report | Fail report run or proceed with stale data — **Open question** for product decision |
| Webhook delivery failure | Prestia/website should retry; Botkonak logs and alerts |

`DjangoClient` retries transient GET failures (`agents/shared/django_client/client.py`). Prestia connector should use similar retry policy.

---

## Evidence from codebase

| File | Relevance |
|------|-----------|
| `backend/tenants/management/commands/seed_prestia.py` | Current data ingestion pattern |
| `backend/catalog/management/commands/import_messages_json.py` | JSON import precedent |
| `backend/operations/tasks.py` | Daily report Celery task |
| `backend/catalog/context.py` | `_safe_section` partial failure pattern |
| `agents/coordinator/nodes.py` | `fetch_from_django: False` — bundle-first |
| `docs/phases/step-3.5.md` | Context bundle design |

## Open questions

1. Maximum acceptable staleness for catalog during daily report when on-demand fetch fails.
2. Whether Botkonak stores full order history or only a rolling window.
3. Prestia website chat webhook payload schema.
4. Rate limits for on-demand bulk fetch vs incremental page requests.
