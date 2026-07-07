# Full API Index

Complete index of Prestia APIs documented for Botkonak integration.

| Category | API name | Method | Endpoint | Used by | Priority | Requirement type | Documentation file |
|----------|----------|--------|----------|---------|----------|------------------|-------------------|
| Authentication | OAuth 2.0 Authorization | `GET` | `/oauth/authorize` | Onboarding | P0 | Inferred | [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) |
| Authentication | OAuth 2.0 Token Exchange | `POST` | `/v1/oauth/token` | On-demand fetch, Coordinator | P0 | Inferred | [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) |
| Authentication | OAuth 2.0 Token Refresh | `POST` | `/v1/oauth/token` | On-demand fetch | P1 | Inferred | [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) |
| Authentication | OAuth 2.0 Token Revocation | `POST` | `/v1/oauth/revoke` | Admin Dashboard | P1 | Inferred | [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) |
| Products | List Products | `GET` | `/v1/products` | Content Agent, Sales Agent, Coordinator | P0 | Direct | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| Products | Get Product Detail | `GET` | `/v1/products/{slug}` | Content Agent, Admin Dashboard | P2 | Inferred | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| Products | List Categories | `GET` | `/v1/categories` | On-demand fetch | P1 | Inferred | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| Orders | List Orders | `GET` | `/v1/orders` | Sales Agent, Coordinator | P0 | Direct | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| Orders | Get Order Detail | `GET` | `/v1/orders/{order_id}` | Support Agent | P2 | Inferred | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| Orders | List Draft/Pending Orders | `GET` | `/v1/orders?status=draft,pending` | Sales Agent | Future | Optional | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| Customers | List Customers | `GET` | `/v1/customers` | Support Agent CRM | P1 | Inferred | [05-customer-apis.md](./05-customer-apis.md) |
| Customers | Get Customer Order History | `GET` | `/v1/customer/{tenant_customer_id}/orders` | Support Agent, Sales Agent | P1 | Inferred | [05-customer-apis.md](./05-customer-apis.md) |
| Support | List FAQs | `GET` | `/v1/faqs` | Support Agent | P0 | Direct | [08-support-agent-apis.md](./08-support-agent-apis.md) |
| Support | Website message webhook | `POST` | (Botkonak receiver) | Support Agent | P0 | Direct | [08-support-agent-apis.md](./08-support-agent-apis.md) |
| Coordinator | Get Aggregated Store Context | `GET` | `/v1/context` | Connector optimization | P1 | Inferred | [09-coordinator-agent-and-dashboard-apis.md](./09-coordinator-agent-and-dashboard-apis.md) |
| Content (write) | Update Product Description | `PATCH` | `/v1/products/{slug}` | Content action execution (future) | Future | Optional | [06-content-agent-apis.md](./06-content-agent-apis.md) |
| Sales (write) | Apply Discount / Promotion | `POST` | `/v1/promotions` | Sales action execution (future) | Future | Optional | [07-sales-agent-apis.md](./07-sales-agent-apis.md) |
| Support (write) | Send Support Reply | `POST` | Platform-specific outbound | Action execution (future) | Future | Optional | [08-support-agent-apis.md](./08-support-agent-apis.md) |
| Webhooks (future) | Product Updated | `POST` | (Botkonak receiver) | On-demand fetch alternative | Future | Optional | [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md) |
| Webhooks (future) | Order Created/Updated | `POST` | (Botkonak receiver) | On-demand fetch alternative | Future | Optional | [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md) |

### Not part of Prestia API contract

| Former endpoint | Replacement |
|-----------------|-------------|
| `GET /v1/store` | Botkonak tenant/store settings UI |
| `GET /v1/tenant` | Botkonak tenant/store settings UI |
| `GET /v1/sales/summary` | Botkonak Sales Agent computes from orders |
| `GET /v1/inventory` | Product `inventories[]` on `/v1/products` |
| `GET /v1/inventory/low-stock` | Botkonak derives from product inventories |
| `GET /v1/messages/recent` | Webhook-based message ingestion |

## Summary counts

| Priority | Count |
|----------|-------|
| P0 | 6 |
| P1 | 5 |
| P2 | 2 |
| Future | 6 |
| **Total documented** | **19** |

| Requirement type | Count |
|------------------|-------|
| Direct | 5 |
| Inferred | 10 |
| Optional | 4 |

## P0 endpoints (quick reference)

1. `GET /oauth/authorize`
2. `POST /v1/oauth/token`
3. `GET /v1/products`
4. `GET /v1/orders`
5. `GET /v1/faqs`
6. Website message webhook → Botkonak

Store profile, sales summary, and message polling are **not** P0 Prestia APIs.

## Evidence from codebase

This index aggregates APIs derived from:

- `backend/catalog/internal_views.py` and `backend/accounts/internal_urls.py`
- `backend/catalog/services.py`, `backend/catalog/context.py`
- `agents/sales/django_fetch.py`, `agents/support/django_fetch.py`
- `agents/coordinator/nodes.py`
- `docs/agents/*.md`, `docs/phases/step-3.*.md`

## Open questions

See [11-api-priority-and-mvp-scope.md](./11-api-priority-and-mvp-scope.md).
