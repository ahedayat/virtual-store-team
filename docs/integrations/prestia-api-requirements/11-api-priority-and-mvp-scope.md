# API Priority and MVP Scope

Classification of all Prestia APIs discovered in this documentation set.

## Priority legend

| Priority | Meaning |
|----------|---------|
| **P0** | Required for MVP — daily report workflow cannot function without this data |
| **P1** | Important — needed for reliable sync, reconciliation, or operational quality |
| **P2** | Nice to have — enhances specific flows but not blocking |
| **Future** | Not needed for initial Botkonak + Prestia integration |

## Requirement type legend

| Type | Meaning |
|------|---------|
| **Direct** | Explicitly required by existing Botkonak code paths |
| **Inferred** | Logically required for integration but connector/sync not yet built |
| **Optional** | Useful enhancement; no current code dependency |
| **Open question** | Cannot confirm from codebase |

---

## P0 — MVP required

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| OAuth Authorization | `GET` | `/oauth/authorize` | Onboarding | Inferred |
| OAuth Token | `POST` | `/v1/oauth/token` | Background sync | Inferred |
| Get Store Profile | `GET` | `/v1/store` | Coordinator, Content, Dashboard | Direct |
| List Products | `GET` | `/v1/products` | Content, Coordinator | Direct |
| Get Sales Summary | `GET` | `/v1/sales/summary` | Sales, Coordinator | Direct |
| Get Low Stock Inventory | `GET` | `/v1/inventory/low-stock` | Sales, Coordinator | Direct |
| Get Recent Messages | `GET` | `/v1/messages/recent` | Support, Coordinator | Direct |

**MVP outcome:** Manager connects Prestia store → Botkonak syncs P0 data → daily report produces sales, content, and support agent outputs.

---

## P1 — Important but not blocking

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| OAuth Token Revocation | `POST` | `/v1/oauth/revoke` | Dashboard disconnect | Inferred |
| OAuth Token Refresh | `POST` | `/v1/oauth/token` (refresh grant) | Background sync | Inferred |
| List Categories | `GET` | `/v1/categories` | Background sync | Inferred |
| List Inventory | `GET` | `/v1/inventory` | Background sync | Inferred |
| List Orders | `GET` | `/v1/orders` | Background sync, sales reconciliation | Inferred |
| Aggregated Context | `GET` | `/v1/context` | Connector optimization | Inferred |

---

## P2 — Nice to have

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| Get Product Detail | `GET` | `/v1/products/{id}` | Content Agent | Inferred |
| Get Order Detail | `GET` | `/v1/orders/{id}` | Support Agent | Inferred |
| List Customers | `GET` | `/v1/customers` | Background sync | Inferred |
| Get Tenant Settings | `GET` | `/v1/tenant` | Content Agent | Inferred |

---

## Future / optional

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| List Draft/Pending Orders | `GET` | `/v1/orders?status=draft,pending` | Sales follow-up | Optional |
| Customer Order History | `GET` | `/v1/customers/{id}/orders` | Sales follow-up | Optional |
| Send Support Reply | `POST` | `/v1/messages/threads/{id}/replies` | Action execution | Optional |
| Update Product Description | `PATCH` | `/v1/products/{id}` | Content action execution | Optional |
| Apply Discount | `POST` | `/v1/promotions` | Sales action execution | Optional |
| Analytics / slow-movers | `GET` | `/v1/analytics/...` | Sales Agent | Optional |
| FAQ content API | `GET` | `/v1/faqs` | Support Agent | Optional — agent uses policy codes, not FAQ DB |
| Webhooks (all events) | `POST` | Botkonak webhook receiver | Background sync | Optional |

---

## OAuth scopes MVP set

Minimum scopes for P0 APIs:

```
read:store read:products read:inventory read:orders read:support_messages read:analytics
```

`read:analytics` covers dedicated sales summary if implemented as analytics endpoint.

**Do not require for MVP:** `write:*` scopes (no write path in Botkonak).

---

## Open questions

| # | Question | Impact |
|---|----------|--------|
| 1 | Prestia API base URL and versioning | Documentation examples |
| 2 | Sync-into-Django vs runtime Prestia proxy | Connector architecture |
| 3 | Aggregated `/v1/context` vs discrete endpoints | API design on Prestia side |
| 4 | Instagram DM source in Prestia | Support P0 feasibility |
| 5 | Order status mapping | Sales revenue accuracy |
| 6 | Variant modeling | Product/inventory sync |
| 7 | Persian (`fa`) as primary catalog language | Content agent output language |
| 8 | Stale data policy on sync failure | Report reliability |
| 9 | OAuth flow type (auth code vs client credentials) | Onboarding UX |
| 10 | Rate limits for initial bulk sync | Connector performance |

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
