# Full API Index

Complete index of Prestia APIs documented for Botkonak integration.

| Category | API name | Method | Endpoint | Used by | Priority | Requirement type | Documentation file |
|----------|----------|--------|----------|---------|----------|------------------|-------------------|
| Authentication | OAuth 2.0 Authorization | `GET` | `/oauth/authorize` | Onboarding, Background sync | P0 | Inferred | [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) |
| Authentication | OAuth 2.0 Token Exchange | `POST` | `/v1/oauth/token` | Background sync, Coordinator | P0 | Inferred | [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) |
| Authentication | OAuth 2.0 Token Refresh | `POST` | `/v1/oauth/token` | Background sync | P1 | Inferred | [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) |
| Authentication | OAuth 2.0 Token Revocation | `POST` | `/v1/oauth/revoke` | Admin Dashboard | P1 | Inferred | [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) |
| Store | Get Store Profile | `GET` | `/v1/store` | Coordinator Agent, Content Agent, Admin Dashboard, Background sync | P0 | Direct | [02-store-profile-apis.md](./02-store-profile-apis.md) |
| Store | Get Tenant Settings | `GET` | `/v1/tenant` | Content Agent, Background sync | P2 | Inferred | [02-store-profile-apis.md](./02-store-profile-apis.md) |
| Products | List Products | `GET` | `/v1/products` | Content Agent, Coordinator Agent, Background sync | P0 | Direct | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| Products | Get Product Detail | `GET` | `/v1/products/{product_id}` | Content Agent, Admin Dashboard | P2 | Inferred | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| Products | List Categories | `GET` | `/v1/categories` | Content Agent, Background sync | P1 | Inferred | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| Inventory | List Inventory Levels | `GET` | `/v1/inventory` | Sales Agent, Background sync | P1 | Inferred | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| Inventory | Get Low Stock Inventory | `GET` | `/v1/inventory/low-stock` | Sales Agent, Coordinator Agent, Background sync | P0 | Direct | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| Orders & Sales | Get Sales Summary | `GET` | `/v1/sales/summary` | Sales Agent, Coordinator Agent, Background sync | P0 | Direct | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| Orders & Sales | List Orders | `GET` | `/v1/orders` | Background sync | P1 | Inferred | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| Orders & Sales | Get Order Detail | `GET` | `/v1/orders/{order_id}` | Support Agent | P2 | Inferred | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| Orders & Sales | List Draft/Pending Orders | `GET` | `/v1/orders?status=draft,pending` | Sales Agent | Future | Optional | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| Customers | List Customers | `GET` | `/v1/customers` | Background sync | P2 | Inferred | [05-customer-apis.md](./05-customer-apis.md) |
| Customers | Get Customer Order History | `GET` | `/v1/customers/{customer_id}/orders` | Sales Agent, Admin Dashboard | Future | Optional | [05-customer-apis.md](./05-customer-apis.md) |
| Support | Get Recent Message Threads | `GET` | `/v1/messages/recent` | Support Agent, Coordinator Agent, Background sync | P0 | Direct | [08-support-agent-apis.md](./08-support-agent-apis.md) |
| Support | Send Support Reply | `POST` | `/v1/messages/threads/{thread_id}/replies` | Action execution (future) | Future | Optional | [08-support-agent-apis.md](./08-support-agent-apis.md) |
| Coordinator | Get Aggregated Store Context | `GET` | `/v1/context` | Coordinator Agent, Background sync | P1 | Inferred | [09-coordinator-agent-and-dashboard-apis.md](./09-coordinator-agent-and-dashboard-apis.md) |
| Content (write) | Update Product Description | `PATCH` | `/v1/products/{product_id}` | Content action execution (future) | Future | Optional | [06-content-agent-apis.md](./06-content-agent-apis.md) |
| Sales (write) | Apply Discount / Promotion | `POST` | `/v1/promotions` | Sales action execution (future) | Future | Optional | [07-sales-agent-apis.md](./07-sales-agent-apis.md) |
| Analytics | Pre-computed Slow Movers / Discount Candidates | `GET` | `/v1/analytics/product-performance` | Sales Agent | Future | Optional | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| Support | FAQ Content List | `GET` | `/v1/faqs` | Support Agent | Future | Optional | [08-support-agent-apis.md](./08-support-agent-apis.md) |
| Webhooks | Product Updated | `POST` | (Botkonak receiver) | Background sync | Future | Optional | [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md) |
| Webhooks | Inventory Updated | `POST` | (Botkonak receiver) | Background sync | Future | Optional | [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md) |
| Webhooks | Order Created/Updated | `POST` | (Botkonak receiver) | Background sync | Future | Optional | [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md) |
| Webhooks | Message Received | `POST` | (Botkonak receiver) | Background sync | Future | Optional | [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md) |

## Summary counts

| Priority | Count |
|----------|-------|
| P0 | 7 |
| P1 | 6 |
| P2 | 4 |
| Future | 11 |
| **Total documented** | **28** |

| Requirement type | Count |
|------------------|-------|
| Direct | 6 |
| Inferred | 15 |
| Optional | 7 |
| Open question | 0 (see [11-api-priority-and-mvp-scope.md](./11-api-priority-and-mvp-scope.md) for open questions list) |

## P0 endpoints (quick reference)

1. `GET /oauth/authorize`
2. `POST /v1/oauth/token`
3. `GET /v1/store`
4. `GET /v1/products`
5. `GET /v1/sales/summary`
6. `GET /v1/inventory/low-stock`
7. `GET /v1/messages/recent`

## Evidence from codebase

This index aggregates APIs derived from:

- `backend/catalog/internal_views.py` and `backend/accounts/internal_urls.py`
- `backend/catalog/services.py`, `backend/catalog/context.py`
- `agents/sales/django_fetch.py`, `agents/support/django_fetch.py`
- `agents/coordinator/nodes.py`
- `docs/agents/*.md`, `docs/phases/step-3.*.md`

## Open questions

See [11-api-priority-and-mvp-scope.md](./11-api-priority-and-mvp-scope.md).
