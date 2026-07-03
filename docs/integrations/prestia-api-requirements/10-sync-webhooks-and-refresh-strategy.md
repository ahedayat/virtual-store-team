# Sync, Webhooks, and Refresh Strategy

How Botkonak should keep Prestia data fresh based on the **existing** architecture.

## Current state (no Prestia connector)

| Mechanism | What exists | Prestia involvement |
|-----------|-------------|---------------------|
| Demo seed | `python manage.py seed_prestia` | Static Prestia-shaped fixture data |
| Message import | `import_messages_json` command | JSON file import, not live API |
| Daily report | Celery `reports.generate_daily` on schedule/trigger | Reads **local Django DB** only |
| Real-time updates | None | None |

**There is no polling, webhook, or OAuth connector code in the repository today.**

---

## Recommended MVP strategy: scheduled pull sync

**Requirement type:** Inferred — required for real Prestia integration but not implemented.

### When to sync

| Trigger | Rationale |
|---------|-----------|
| **Before daily report** | Coordinator context must reflect current Prestia state (`backend/operations/tasks.py` → coordinator → context bundle) |
| **Periodic background job** | e.g. every 15–60 minutes for catalog/inventory/messages between reports |
| **On OAuth connect** | Initial full sync after authorization |

### What to sync (pull endpoints)

| Prestia endpoint | Botkonak target | Sync mode |
|------------------|-----------------|-----------|
| `GET /v1/store` | `Store`, `Tenant.settings` | Full |
| `GET /v1/categories` | `Category` | Full + incremental `updated_since` |
| `GET /v1/products` | `Product` | Incremental |
| `GET /v1/inventory` | `InventoryLevel` | Incremental |
| `GET /v1/orders` | `Order`, `OrderItem` | Incremental by `placed_at` / `updated_since` |
| `GET /v1/customers` | `Customer` | Incremental |
| `GET /v1/messages/recent` | `MessageThread`, `Message` | Incremental (or larger window than AI default) |

**Alternative:** Call `GET /v1/sales/summary` and `GET /v1/inventory/low-stock` at report time without storing raw orders — reduces storage but limits dashboard drill-down.

### Incremental sync parameters

Use `updated_since` (ISO datetime) on list endpoints where supported ([01-shared-data-contracts.md](./01-shared-data-contracts.md)).

Store last successful sync timestamp per store in Botkonak (connector metadata — not in current schema).

### Idempotency

Match Prestia `external_id` fields to Botkonak `external_id` / `external_thread_id` / `external_message_id` unique constraints (`catalog/models.py`).

---

## Daily report timing

```
Manager POST /api/reports/generate/
    → Celery generate_daily
        → (Future) Prestia sync job OR verify sync freshness
        → Coordinator POST /workflows/daily-report
            → Django GET context (local DB)
            → Specialist agents
            → Django POST complete
```

Botkonak already prevents concurrent report runs per store (`unique_active_report_run_per_store` constraint in `operations/models.py`).

---

## Webhooks (optional / future)

**Not required by current code.** No webhook handlers exist in Botkonak.

If Prestia adds webhooks, these would reduce polling latency:

| Webhook event | Priority | Botkonak action (future) |
|---------------|----------|--------------------------|
| `product.created` / `product.updated` | P2 | Upsert `Product` |
| `inventory.updated` | P1 | Upsert `InventoryLevel` |
| `order.created` / `order.updated` | P1 | Upsert `Order` |
| `message.received` | P1 | Insert `Message`, update thread |
| `store.settings.updated` | P2 | Update brand voice settings |

### Webhook security (if implemented)

- HMAC signature verification
- HTTPS only
- Idempotent event processing by `event_id`

**Mark as:** Optional (Future) — useful improvement, not blocking MVP.

---

## On-demand refresh

| Scenario | Strategy |
|----------|----------|
| Manager opens support UI | Pull `GET /v1/messages/recent` (future wired frontend) |
| Manager triggers report | Full or incremental sync immediately before coordinator |
| Sales agent `fetch_from_django` | Reads local DB after sync (not live Prestia call) |

Sales/support agents support `fetch_from_django` / `fetch_recent_messages` flags but coordinator sets both to `False` — context is preloaded from bundle.

---

## Token refresh during sync

Long-running sync jobs must refresh OAuth tokens via `POST /v1/oauth/token` (refresh grant) before expiry ([00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md)).

---

## Failure handling

Align with existing Botkonak patterns:

| Failure | Behavior |
|---------|----------|
| Prestia API down during sync | Log error; optionally proceed with stale data + `warnings` in context bundle (`_safe_section` in `context.py`) |
| Partial section failure | Empty section + warning string (same as context bundle) |
| Sync failure before report | Fail report run or proceed with stale data — **Open question** for product decision |

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

1. Maximum acceptable staleness for inventory during daily report.
2. Whether Botkonak stores full order history or only rolling 7-day window.
3. Prestia webhook availability and event catalog.
4. Rate limits for bulk sync vs incremental sync.
