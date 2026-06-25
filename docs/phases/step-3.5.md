# Step 3.5 — Internal AI Context Bundle Endpoint (Sanitized Stub)

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Add a read-only internal AI context bundle endpoint that aggregates existing Phase 3 store data (products, sales, inventory, messages) into a single sanitized JSON payload for future coordinator-agent consumption. The endpoint accepts a `report_run_id` path parameter as a stub for Phase 4 report orchestration without persisting a `ReportRun` model.

---

## Summary of implemented changes

- Added `catalog/context.py` with `build_product_summary()` and `build_context_bundle()` orchestration
- Added `GET /internal/ai/context/<report_run_id>/` protected by `InternalAIAuthentication`
- Tenant and store scope are derived from the service JWT (not from URL path parameters)
- Optional `report_run_id` JWT claim is validated against the path parameter when present
- Composes existing Phase 3 services without duplicating aggregation or sanitization logic
- Missing optional sections return empty values plus a `warnings` entry instead of HTTP 500
- Added focused API and security tests
- Cursor scope rule at `.cursor/rules/step-3.5-ai-context-bundle.mdc`

---

## Files created/modified

| Path | Action |
|------|--------|
| `.cursor/rules/step-3.5-ai-context-bundle.mdc` | Present — Step 3.5 scope rule |
| `backend/catalog/context.py` | Created — product summary + context bundle builder |
| `backend/catalog/internal_views.py` | Updated — `InternalAIContextView` |
| `backend/accounts/internal_urls.py` | Updated — context bundle route |
| `backend/catalog/tests/test_internal_context_bundle.py` | Created — security, shape, PII, stub tests |
| `docs/phases/step-3.5.md` | Created — this document |

---

## Context bundle builder design

`build_context_bundle()` in `catalog/context.py` is the orchestration entry point. It:

1. Loads tenant and store metadata from the resolved ORM objects
2. Calls existing Phase 3 service functions:
   - `build_product_summary()` (new, local to context module)
   - `build_sales_summary()` from Step 3.2
   - `build_low_stock_summary()` from Step 3.3
   - `build_recent_messages_summary()` from Step 3.4
3. Maps each service output into the stable bundle shape
4. Wraps each section in `_safe_section()` so failures produce empty sections and a warning string

Product summaries include only AI-safe fields: `product_id`, `name`, `slug`, `sku`, `category`, `price`, `currency`, `is_active`, and non-empty `metadata` when present.

---

## Internal AI context endpoint contract

| Property | Value |
|----------|-------|
| Method | `GET` |
| Path | `/internal/ai/context/<uuid:report_run_id>/` |
| Auth | `Authorization: Bearer <service_jwt>` |
| Scope | `tenant_id` and `store_id` from JWT claims |
| Writes | None (read-only stub) |

### HTTP status codes

| Condition | Status |
|-----------|--------|
| Missing/invalid JWT | `401 Unauthorized` |
| JWT `report_run_id` claim ≠ path parameter | `403 Forbidden` |
| Tenant or store not found for JWT scope | `404 Not Found` |
| Success | `200 OK` |

---

## Example request

```http
GET /internal/ai/context/550e8400-e29b-41d4-a716-446655440000/ HTTP/1.1
Host: localhost:8000
Authorization: Bearer <coordinator-agent-service-jwt>
```

The service JWT must include at minimum: `sub`, `tenant_id`, `store_id`, `iat`, `exp`, `aud`.

Optional claim: `report_run_id` — when present, must equal the path UUID.

---

## Example sanitized response shape

```json
{
  "report_run_id": "550e8400-e29b-41d4-a716-446655440000",
  "generated_at": "2026-06-25T14:30:00+00:00",
  "tenant": {
    "id": "11111111-1111-1111-1111-111111111111",
    "slug": "prestia",
    "name": "Prestia"
  },
  "store": {
    "id": "22222222-2222-2222-2222-222222222222",
    "slug": "main",
    "name": "Prestia Main Store",
    "timezone": "Asia/Tehran",
    "currency": "IRR"
  },
  "products": {
    "count": 2,
    "items": [
      {
        "product_id": "33333333-3333-3333-3333-333333333333",
        "name": "Classic Leather Tote",
        "slug": "classic-leather-tote",
        "sku": "BAG-001",
        "category": {
          "id": "44444444-4444-4444-4444-444444444444",
          "name": "Handbags",
          "slug": "handbags"
        },
        "price": "4500000.00",
        "currency": "IRR",
        "is_active": true
      }
    ]
  },
  "sales_summary": {
    "currency": "IRR",
    "today": {
      "from": "2026-06-24T20:30:00+00:00",
      "to": "2026-06-25T20:30:00+00:00",
      "total_revenue": "9000000.00",
      "order_count": 2,
      "units_sold": 2,
      "average_order_value": "4500000.00",
      "top_products": []
    },
    "last_7_days": {
      "from": "2026-06-18T20:30:00+00:00",
      "to": "2026-06-25T20:30:00+00:00",
      "total_revenue": "9000000.00",
      "order_count": 2,
      "units_sold": 2,
      "average_order_value": "4500000.00",
      "top_products": []
    }
  },
  "inventory": {
    "low_stock_count": 1,
    "items": [
      {
        "product_id": "33333333-3333-3333-3333-333333333333",
        "product_name": "Classic Leather Tote",
        "sku": "BAG-001",
        "category": "Handbags",
        "quantity_on_hand": 3,
        "reserved_quantity": 1,
        "available_quantity": 2,
        "low_stock_threshold": 10,
        "shortage_units": 8,
        "reorder_target": 25,
        "suggested_reorder_quantity": 23,
        "last_updated": "2026-06-25T12:00:00+00:00"
      }
    ]
  },
  "messages": {
    "thread_count": 1,
    "threads": [
      {
        "thread_id": "55555555-5555-5555-5555-555555555555",
        "customer_ref": "customer-66666666-6666-6666-6666-666666666666",
        "platform": "instagram",
        "status": "open",
        "subject": "Availability question",
        "last_message_at": "2026-06-25T12:00:00+00:00",
        "messages": [
          {
            "message_id": "77777777-7777-7777-7777-777777777777",
            "direction": "inbound",
            "sender_type": "customer",
            "body": "Please email [EMAIL_REDACTED] or call [PHONE_REDACTED] about the tote.",
            "sent_at": "2026-06-25T12:00:00+00:00"
          }
        ]
      }
    ]
  },
  "warnings": []
}
```

---

## Report run stub behavior

- `report_run_id` is a UUID path parameter validated by Django URL routing.
- No `ReportRun` database record is created or queried.
- If the JWT includes a `report_run_id` claim, it must match the path value or the request is rejected with `403`.
- If the JWT omits `report_run_id`, the path value is echoed in the response for traceability.
- Phase 4 will introduce real `ReportRun` persistence and Celery orchestration.

---

## Tenant/store scoping decisions

Unlike store-scoped endpoints (`/internal/ai/stores/<store_id>/...`), the context endpoint has no store ID in the URL. Scope authority comes entirely from JWT claims:

1. Load `Tenant` by `identity.tenant_id`
2. Load `Store` via `Store.objects.get_for_tenant(tenant, pk=identity.store_id)`
3. All bundled data is filtered to that tenant/store pair

Cross-tenant access (JWT `tenant_id` with a store belonging to another tenant) returns `404`. A JWT scoped to a different store under the same tenant returns that store's data only — it cannot access another store's records.

---

## PII sanitization guarantees

- Message bodies and thread subjects pass through `PiiSanitizer.sanitize_text()` via `build_recent_messages_summary()`.
- Customer references use opaque `customer_ref` values (`customer-{uuid}`).
- Raw email, phone, display name, platform user ID, and address fields are never included.
- Product and sales sections contain no customer PII by design.
- Context bundle contents are not logged at INFO level; section failures log only section name metadata at ERROR.

---

## How existing Phase 3 services are reused

| Section | Source | Duplicated? |
|---------|--------|-------------|
| Products | `build_product_summary()` in `catalog/context.py` | New minimal summary only |
| Sales | `build_sales_summary()` in `catalog/services.py` | No |
| Inventory | `build_low_stock_summary()` in `catalog/services.py` | No |
| Messages | `build_recent_messages_summary()` in `catalog/services.py` | No |
| PII redaction | `PiiSanitizer` in `catalog/pii.py` (via messages service) | No |

---

## Tests added

`backend/catalog/tests/test_internal_context_bundle.py` covers:

- Service JWT required (`401`)
- Valid service JWT accepted (`200`)
- Cross-tenant access rejected (`404`)
- Cross-store JWT returns only that store's data (no leakage from sibling store)
- Expected top-level response keys
- Product summary fields present
- Sales summary data from existing service
- Low-stock inventory data from existing service
- Sanitized recent message threads
- No raw seeded email or phone values in response
- No raw PII field names in response
- `report_run_id` echoed when JWT claim absent
- `report_run_id` validated when JWT claim present
- Mismatched `report_run_id` claim rejected (`403`)
- Empty sections for stores with no optional data
- Simulated section failure returns warning, not `500`
- No catalog database writes on GET

---

## How to run relevant tests

From the repository root:

```bash
cd backend
python manage.py test catalog.tests.test_internal_context_bundle
```

Run all catalog internal API tests:

```bash
python manage.py test catalog.tests.test_internal_context_bundle catalog.tests.test_internal_sales_summary catalog.tests.test_internal_low_stock catalog.tests.test_internal_recent_messages
```

---

## Explicit out-of-scope items (deferred to later phases)

- `ReportRun` model
- `DailyReport` model
- `AgentOutput` model
- `Action` and `ActionEvent` models
- Celery report generation
- coordinator-agent workflow
- LangGraph
- specialist agent execution
- frontend dashboard integration
