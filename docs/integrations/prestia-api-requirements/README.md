# Prestia ↔ Botkonak API Requirements

## Purpose of this documentation

This directory documents the **external APIs that Prestia (prestia.ir) must expose** so Botkonak can operate as an intelligent store management layer for a connected Prestia store. Requirements are derived from the existing Botkonak codebase — models, internal AI services, agents, coordinator workflow, and dashboard — not from generic e-commerce assumptions.

**Prestia is the first demo tenant** in Botkonak (`seed_prestia`), but the platform is multi-tenant. These contracts describe what any Prestia store integration must supply; they are not Prestia-only runtime code paths inside Botkonak today.

## Integration summary

| Aspect | Current Botkonak state | Target Prestia integration |
|--------|------------------------|----------------------------|
| Data source | PostgreSQL via Django models; demo data from `seed_prestia` | Prestia APIs as system of record (or sync source) |
| Auth to external store | Not implemented | OAuth 2.0 access token; `Authorization: Bearer <token>` |
| Agent data path | Coordinator → Django `GET /internal/ai/context/{report_run_id}/` | Botkonak connector fetches from Prestia, normalizes into Django (or calls Prestia at runtime) |
| Writes back to store | Not implemented (actions are internal approval stubs) | Future / optional |

Botkonak today **does not call prestia.ir**. It mirrors Prestia-shaped data locally. This documentation defines the Prestia-side contract needed for a real connector.

## Directory map

| File | Contents |
|------|----------|
| [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) | OAuth 2.0, Bearer headers, scopes, token lifecycle |
| [01-shared-data-contracts.md](./01-shared-data-contracts.md) | Common types, pagination, errors, field mappings |
| [02-store-profile-apis.md](./02-store-profile-apis.md) | Botkonak tenant settings (not a Prestia API) |
| [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) | Products, categories, variant inventories |
| [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) | Orders (sales summary computed by Botkonak) |
| [05-customer-apis.md](./05-customer-apis.md) | Customer records and order history (limited current need) |
| [06-content-agent-apis.md](./06-content-agent-apis.md) | APIs consumed (directly or via sync) by the Content Agent |
| [07-sales-agent-apis.md](./07-sales-agent-apis.md) | APIs consumed by the Sales Agent |
| [08-support-agent-apis.md](./08-support-agent-apis.md) | APIs consumed by the Support Agent |
| [09-coordinator-agent-and-dashboard-apis.md](./09-coordinator-agent-and-dashboard-apis.md) | Coordinator context needs and dashboard implications |
| [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md) | On-demand API fetch + webhook message ingestion |
| [11-api-priority-and-mvp-scope.md](./11-api-priority-and-mvp-scope.md) | P0–Future classification and open questions |
| [12-full-api-index.md](./12-full-api-index.md) | Complete API index table |

## How Botkonak authenticates with Prestia

1. A store manager authorizes Botkonak via **OAuth 2.0** on Prestia (authorization code flow recommended).
2. Botkonak stores the **access token** (and refresh token if issued) securely server-side.
3. Every Prestia API call from Botkonak includes:

```http
Authorization: Bearer <access_token>
Accept: application/json
Content-Type: application/json
```

4. **Tenant/store scope** must be resolved **server-side from the token** on Prestia. Botkonak must not send store secrets in query strings.

See [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) for full details.

## High-level data flow

```
┌─────────────┐     OAuth 2.0      ┌──────────────┐
│   Manager   │ ─────────────────► │   Prestia    │
│  (browser)  │                    │  (prestia.ir)│
└─────────────┘                    └──────┬───────┘
                                          │
                              Bearer token API calls
                                          │
┌─────────────┐     sync / fetch   ┌──────▼───────┐
│  Dashboard  │ ◄───────────────── │   Botkonak   │
│  (Next.js)  │   Django REST API  │   Django     │
└─────────────┘                    └──────┬───────┘
                                          │
                              Celery daily report task
                                          │
                                   ┌──────▼───────┐
                                   │ Coordinator  │
                                   │    Agent     │
                                   └──────┬───────┘
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                    Sales Agent    Content Agent    Support Agent
```

**Daily report path (implemented today):**

1. Manager triggers `POST /api/reports/generate/` → Celery `reports.generate_daily`.
2. Coordinator `POST /workflows/daily-report` → Django `GET /internal/ai/context/{report_run_id}/`.
3. Context bundle feeds sales, content, and support agents in parallel.
4. Coordinator merges outputs → Django `POST /internal/ai/report-runs/{id}/complete/`.
5. Dashboard reads reports and actions from Django (not from Prestia directly).

A Prestia connector must ensure Django's catalog tables (or runtime fetches) reflect Prestia data **before** step 2.

## MVP API groups

| Group | Prestia endpoints (summary) | Why |
|-------|----------------------------|-----|
| **Auth** | OAuth token (+ refresh) | Secure connection |
| **Catalog** | `GET /products` | Content + sales agents |
| **Orders** | `GET /orders` | Sales agent computes summary locally |
| **Support** | `GET /faqs` + website message webhook | FAQ answers + real-time inbox |
| **Settings** | *(Botkonak UI)* | Brand voice, timezone, currency |

Full P0 list: [11-api-priority-and-mvp-scope.md](./11-api-priority-and-mvp-scope.md).

## Non-goals

This documentation explicitly does **not**:

- Implement Prestia APIs or any Botkonak connector code
- Modify Prestia's production systems
- Modify Botkonak runtime application code
- Create an OAuth authorization server inside Botkonak
- Define Botkonak's internal Django `/internal/ai/*` APIs (those are Botkonak-private; Prestia equivalents are documented here as the external contract)
- Require Prestia to accept agent-generated drafts, discounts, or support replies (no write path exists in current Botkonak code)

## Evidence from codebase

| Area | Key files |
|------|-----------|
| Domain models | `backend/catalog/models.py`, `backend/stores/models.py`, `backend/tenants/models.py` |
| Aggregation services | `backend/catalog/services.py`, `backend/catalog/context.py` |
| Internal AI read APIs | `backend/catalog/internal_views.py`, `backend/accounts/internal_urls.py` |
| Prestia demo seed | `backend/tenants/management/commands/seed_prestia.py` |
| Agents | `agents/sales/`, `agents/content/`, `agents/support/`, `agents/coordinator/` |
| Daily report orchestration | `backend/operations/tasks.py`, `agents/coordinator/nodes.py` |
| Agent documentation | `docs/agents/*.md` |
| Phase 3 data contracts | `docs/phases/step-3.2.md` – `step-3.5.md` |

## Open questions

1. **Prestia API base URL and versioning** — not defined in this repository (assumed `https://api.prestia.ir/v1` in examples).
2. **Connector placement** — sync into Django vs runtime proxy to Prestia is undecided in code.
3. **Persian vs English catalog fields** — seed uses English product names; production Prestia may use Persian (`fa`) with different slug conventions.
4. **Instagram / Telegram / website message ingestion** — Support Agent uses webhook-based delivery; Prestia website chat must forward messages to Botkonak.
