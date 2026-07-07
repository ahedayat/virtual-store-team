# API Priority and MVP Scope

Classification of all Prestia APIs documented for Botkonak integration.

## Priority legend

| Priority | Meaning |
|----------|---------|
| **P0** | Required for MVP — daily report workflow cannot function without this data |
| **P1** | Important — needed for reliable integration or operational quality |
| **P2** | Nice to have — enhances specific flows but not blocking |
| **Future** | Not needed for initial Botkonak + Prestia integration |

## Requirement type legend

| Type | Meaning |
|------|---------|
| **Direct** | Explicitly required by the revised integration contract |
| **Inferred** | Logically required for integration but connector not yet built |
| **Optional** | Useful enhancement; no current code dependency |

---

## P0 — MVP required

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| OAuth Authorization | `GET` | `/oauth/authorize` | Onboarding | Inferred |
| OAuth Token | `POST` | `/v1/oauth/token` | On-demand fetch | Inferred |
| List Products | `GET` | `/v1/products` | Content, Sales, Coordinator | Direct |
| List Orders | `GET` | `/v1/orders` | Sales, Coordinator | Direct |
| List FAQs | `GET` | `/v1/faqs` | Support | Direct |
| Website message webhook | `POST` | Botkonak receiver | Support | Direct |

**MVP outcome:** Manager connects Prestia store → configures Botkonak tenant settings → on-demand Prestia fetch + webhook messages → daily report produces sales, content, and support agent outputs.

**Not P0 on Prestia side:** store profile API, sales summary API, message polling API.

---

## P1 — Important but not blocking

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| OAuth Token Revocation | `POST` | `/v1/oauth/revoke` | Dashboard disconnect | Inferred |
| OAuth Token Refresh | `POST` | `/v1/oauth/token` (refresh grant) | On-demand fetch | Inferred |
| List Categories | `GET` | `/v1/categories` | Connector | Inferred |
| List Customers | `GET` | `/v1/customers` | Support CRM | Inferred |
| Customer Order History | `GET` | `/v1/customer/{tenant_customer_id}/orders` | Support, Sales | Inferred |
| Aggregated Context | `GET` | `/v1/context` | Connector optimization | Inferred |

---

## P2 — Nice to have

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| Get Product Detail | `GET` | `/v1/products/{slug}` | Content Agent | Inferred |
| Get Order Detail | `GET` | `/v1/orders/{order_id}` | Support Agent | Inferred |

---

## Future / optional

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| List Draft/Pending Orders | `GET` | `/v1/orders?status=draft,pending` | Sales follow-up | Optional |
| Send Support Reply | Outbound | Platform APIs | Action execution | Optional |
| Update Product Description | `PATCH` | `/v1/products/{slug}` | Content action execution | Optional |
| Apply Discount | `POST` | `/v1/promotions` | Sales action execution | Optional |
| Data webhooks (products, orders) | `POST` | Botkonak receiver | Latency optimization | Optional |

---

## OAuth scopes MVP set

Minimum scopes for P0 APIs:

```
read:products read:orders read:customers read:faqs
```

`read:store` and `read:analytics` are **not required** — store settings are Botkonak-local; sales analytics are computed from orders.

Instagram/Telegram webhooks use platform credentials, not Prestia OAuth scopes.

**Do not require for MVP:** `write:*` scopes (no write path in Botkonak).

---

## Open questions

| # | Question | Impact |
|---|----------|--------|
| 1 | Prestia API base URL and versioning | Documentation examples |
| 2 | On-demand fetch vs sync-into-Django | Connector architecture |
| 3 | Aggregated `/v1/context` vs discrete endpoints | API design on Prestia side |
| 4 | Website chat webhook payload schema | Support P0 feasibility |
| 5 | Order status mapping | Sales revenue accuracy |
| 6 | Product `inventories[]` variant modeling | Inventory signal accuracy |
| 7 | Persian (`fa`) as primary catalog language | Content agent output language |
| 8 | Stale data policy on fetch failure | Report reliability |
| 9 | OAuth flow type (auth code vs client credentials) | Onboarding UX |
| 10 | Rate limits for on-demand bulk fetch | Connector performance |

---

## Evidence from codebase

Priority assignments based on:

- `backend/catalog/context.py` — context bundle sections (P0 data)
- `agents/coordinator/nodes.py` — daily report workflow
- `backend/operations/tasks.py` — report generation trigger
- `frontend/hooks/*.ts` — mock-only dashboard (Future for live Prestia reads)
- `backend/operations/tasks.py` — `execute_action` stub (Future for writes)

## Non-goals (recap)

See [README.md](./README.md#non-goals).
