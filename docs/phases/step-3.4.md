# Step 3.4 — Message Ingest Model (Admin Entry, JSON Import, Sanitized Recent Messages API)

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-25  
**Status:** Implemented

---

## Goal

Add generic tenant/store-scoped support conversation models for MVP message ingest (manual admin entry and optional JSON import), a minimal PII sanitizer for AI-facing output, and a protected internal AI recent-messages endpoint. Raw customer PII remains in Django/Postgres and admin only.

---

## Summary of implemented changes

- Added `Customer`, `MessageThread`, and `Message` models to the `catalog` app (migration `0004_support_messages`)
- Implemented `PiiSanitizer` in `catalog/pii.py` for email and phone redaction (Latin and Persian digits)
- Implemented `build_recent_messages_summary()` in `catalog/services.py`
- Added `GET /internal/ai/stores/<store_id>/messages/recent/` protected by `InternalAIAuthentication`
- Registered support models in Django admin with `MessageInline` on `MessageThreadAdmin`
- Added optional `import_messages_json` management command for idempotent JSON import
- Extended `seed_prestia` with realistic Prestia support conversations (including PII in message bodies for sanitizer validation)
- Added model, PII, service, API, and seed tests
- Cursor scope rule at `.cursor/rules/step-3.4-message-ingest.mdc`

---

## Files created/modified

| Path | Action |
|------|--------|
| `.cursor/rules/step-3.4-message-ingest.mdc` | Present — Step 3.4 scope rule |
| `backend/catalog/models.py` | Updated — `Customer`, `MessageThread`, `Message` |
| `backend/catalog/pii.py` | Created — `PiiSanitizer` |
| `backend/catalog/services.py` | Updated — `build_recent_messages_summary()` |
| `backend/catalog/internal_views.py` | Updated — `InternalRecentMessagesView` |
| `backend/catalog/admin.py` | Updated — support model admins + message inline |
| `backend/catalog/migrations/0004_support_messages.py` | Created — support message schema migration |
| `backend/catalog/management/commands/import_messages_json.py` | Created — optional JSON import command |
| `backend/catalog/tests/test_models.py` | Updated — customer/thread/message scoping tests |
| `backend/catalog/tests/test_pii.py` | Created — sanitizer unit tests |
| `backend/catalog/tests/test_services.py` | Updated — recent messages query tests |
| `backend/catalog/tests/test_internal_recent_messages.py` | Created — internal API security/sanitization tests |
| `backend/catalog/tests/test_seed_prestia.py` | Updated — message seed tests |
| `backend/accounts/internal_urls.py` | Updated — recent messages route |
| `backend/tenants/management/commands/seed_prestia.py` | Updated — demo customers, threads, messages |
| `docs/phases/step-3.4.md` | Created — this document |

---

## Customer, MessageThread, and Message model design

### Customer

| Field | Type | Rationale |
|-------|------|-----------|
| `id` | `UUIDField` (PK) | Matches existing model convention. |
| `tenant` / `store` | `ForeignKey` | Tenant/store scoped via `TenantScopedModel`. |
| `display_name` | `CharField` | Human-readable name (admin only; not exported to AI API). |
| `email` / `phone` | Contact fields | Source-of-truth PII stored in DB/admin only. |
| `platform_user_id` | `CharField` | External platform identifier for idempotent import/seed. |
| `platform` | `TextChoices` | `instagram`, `whatsapp`, `email`, `web`, `manual`. |
| `metadata` | `JSONField` | Flexible context. |
| `created_at` / `updated_at` | timestamps | Audit/ordering support for admin. |

Unique constraint (partial): `(tenant, store, platform, platform_user_id)` when `platform_user_id` is non-empty.

### MessageThread

| Field | Type | Rationale |
|-------|------|-----------|
| `customer` | `ForeignKey(Customer)` | Conversation owner. |
| `platform` | `TextChoices` | Channel for the thread. |
| `external_thread_id` | `CharField` | Idempotent import/seed key. |
| `subject` | `CharField` | Short thread summary. |
| `status` | `TextChoices` | `open`, `pending`, `closed`. |
| `last_message_at` | `DateTimeField` | Recent-thread ordering. |
| `metadata` | `JSONField` | Flexible context. |
| `created_at` / `updated_at` | timestamps | Admin/audit support. |

Unique constraint (partial): `(tenant, store, external_thread_id)` when non-empty.

Indexes: `(tenant, store, platform, status)`, `(tenant, store, last_message_at)`.

### Message

| Field | Type | Rationale |
|-------|------|-----------|
| `thread` | `ForeignKey(MessageThread)` | Parent conversation. |
| `direction` | `TextChoices` | `inbound` / `outbound`. |
| `sender_type` | `TextChoices` | `customer` / `staff` / `system`. |
| `body` | `TextField` | Message content (sanitized before AI export). |
| `external_message_id` | `CharField` | Idempotent import/seed key. |
| `sent_at` | `DateTimeField` | Message ordering within thread. |
| `metadata` | `JSONField` | Flexible context. |
| `created_at` / `updated_at` | timestamps | Admin/audit support. |

Unique constraint (partial): `(thread, external_message_id)` when non-empty.

`clean()` on all three models enforces tenant/store consistency and cross-FK alignment (customer/thread/message must share store and tenant). `Message.save()` updates `thread.last_message_at` when a newer `sent_at` is saved.

---

## Manual admin entry behavior

- `CustomerAdmin`, `MessageThreadAdmin`, and `MessageAdmin` registered in `catalog/admin.py`
- `MessageThreadAdmin` includes `MessageInline` for adding messages while editing a thread
- Admin list views expose tenant, store, platform, status, timestamps, and raw contact fields for internal operators
- No AI-facing export actions were added; admin is the internal management surface only

---

## Optional JSON import behavior

Command: `python manage.py import_messages_json <path-to-file.json> [--tenant prestia] [--store main]`

- Defaults to Prestia tenant/store for demo imports
- Expects top-level keys: `customers`, `threads`, `messages`
- Idempotent via `platform_user_id`, `external_thread_id`, and `external_message_id`
- Raises a clear error if referenced customers or threads are missing

Example JSON shape:

```json
{
  "customers": [
    {
      "platform_user_id": "ig-demo-001",
      "platform": "instagram",
      "display_name": "Demo Customer",
      "email": "demo@example.com",
      "phone": "09120000000"
    }
  ],
  "threads": [
    {
      "external_thread_id": "demo-thread-001",
      "customer_platform_user_id": "ig-demo-001",
      "platform": "instagram",
      "subject": "Demo question",
      "status": "open",
      "last_message_at": "2026-06-25T12:00:00+00:00"
    }
  ],
  "messages": [
    {
      "external_thread_id": "demo-thread-001",
      "external_message_id": "demo-msg-001",
      "direction": "inbound",
      "sender_type": "customer",
      "body": "Is this bag in stock?",
      "sent_at": "2026-06-25T12:00:00+00:00"
    }
  ]
}
```

---

## PII sanitizer behavior

Module: `backend/catalog/pii.py`

- `PiiSanitizer.sanitize_text(text)` redacts:
  - Email addresses → `[EMAIL_REDACTED]`
  - Iranian mobile numbers (Latin and Persian/Arabic digits, `09…`, `+98…`) → `[PHONE_REDACTED]`
  - International phone-like patterns (e.g. `+1 (415) 555-0199`) → `[PHONE_REDACTED]`
- Persian/Arabic digits are normalized to Latin before phone matching
- `PiiSanitizer.customer_ref(customer_id)` returns opaque `customer-<uuid>` references for AI output
- Applied to message `body` and thread `subject` in `build_recent_messages_summary()`

---

## Recent messages query design

Module: `backend/catalog/services.py`

- `build_recent_messages_summary(store, thread_limit=10, messages_per_thread=5, reference=None)`
- Loads threads for the store ordered by `last_message_at` descending
- Includes up to `messages_per_thread` most recent messages per thread (chronological within the slice)
- Returns sanitized DTOs only — no raw customer name, email, phone, or platform user ID

Thread fields: `thread_id`, `customer_ref`, `platform`, `status`, `subject`, `last_message_at`, `messages`

Message fields: `message_id`, `direction`, `sender_type`, `body`, `sent_at`

---

## Internal AI recent messages endpoint contract

| Property | Value |
|----------|-------|
| Method | `GET` |
| Path | `/internal/ai/stores/<store_id>/messages/recent/` |
| Auth | `Authorization: Bearer <service_jwt>` via `InternalAIAuthentication` |
| Query params | `thread_limit` (default 10, max 50), `messages_per_thread` (default 5, max 50) |
| Scope | JWT `tenant_id` and `store_id` must match the requested store |
| Errors | `401` missing/invalid JWT; `403` cross-store token mismatch; `404` store not found for token tenant |

### Example sanitized response shape

```json
{
  "generated_at": "2026-06-25T18:00:00+00:00",
  "store_id": "550e8400-e29b-41d4-a716-446655440000",
  "thread_count": 1,
  "threads": [
    {
      "thread_id": "660e8400-e29b-41d4-a716-446655440001",
      "customer_ref": "customer-770e8400-e29b-41d4-a716-446655440002",
      "platform": "instagram",
      "status": "open",
      "subject": "Milano Leather Tote availability",
      "last_message_at": "2026-06-25T09:12:00+00:00",
      "messages": [
        {
          "message_id": "880e8400-e29b-41d4-a716-446655440003",
          "direction": "inbound",
          "sender_type": "customer",
          "body": "Hi! Is the Milano Leather Tote still available in cognac? Please email me at [EMAIL_REDACTED] if it is back in stock.",
          "sent_at": "2026-06-25T09:00:00+00:00"
        },
        {
          "message_id": "990e8400-e29b-41d4-a716-446655440004",
          "direction": "outbound",
          "sender_type": "staff",
          "body": "Thanks for reaching out! The Milano Leather Tote in cognac is low stock but still available.",
          "sent_at": "2026-06-25T09:12:00+00:00"
        }
      ]
    }
  ]
}
```

No raw customer email, phone, display name, physical address, or platform user ID appear in the response.

---

## Tenant/store scoping decisions

- All support models extend `TenantScopedModel` with explicit `tenant` and `store` foreign keys, consistent with `Product`, `Order`, and `InventoryLevel`
- `clean()` validates store/tenant alignment and cross-FK consistency
- Internal API follows the same JWT + `Store.objects.get_for_tenant()` pattern as Steps 3.2 and 3.3
- Prestia-specific data exists only in `seed_prestia` constants — no Prestia branches in application logic

---

## Prestia message seed behavior

Command: `python manage.py seed_prestia` (from `backend/`)

- Creates 5 demo customers, 5 threads, and 10 messages via `get_or_create` on natural keys
- Idempotent: repeated runs do not duplicate customers, threads, or messages
- Conversations cover:
  - Product availability (`Milano Leather Tote`) — includes email in message body
  - Shipping time to California
  - Luna Quilted material question — includes Persian-digit Iranian phone in message body
  - Exchange/return for `Aria Mini Crossbody`
  - Order follow-up for `PRS-ORD-001` — includes `+98` phone in message body
- After seeding, thread `last_message_at` is reconciled from the latest message timestamp

---

## Tests added

| File | Coverage |
|------|----------|
| `catalog/tests/test_models.py` | Customer/thread/message creation, cross-store validation |
| `catalog/tests/test_pii.py` | Email, Iranian (Latin/Persian), and international phone redaction |
| `catalog/tests/test_services.py` | Recent thread ordering, sanitized body output |
| `catalog/tests/test_internal_recent_messages.py` | JWT required/accepted, cross-tenant/store rejection, no raw PII |
| `catalog/tests/test_seed_prestia.py` | Message seed creation and idempotency |

### How to run relevant tests

From `backend/`:

```bash
python manage.py test catalog.tests.test_models.CustomerModelTests
python manage.py test catalog.tests.test_models.MessageThreadModelTests
python manage.py test catalog.tests.test_models.MessageModelTests
python manage.py test catalog.tests.test_pii
python manage.py test catalog.tests.test_services.RecentMessagesSummaryTests
python manage.py test catalog.tests.test_internal_recent_messages
python manage.py test catalog.tests.test_seed_prestia
```

Or run the full catalog suite:

```bash
python manage.py test catalog
```

---

## How to run the seed/import commands

```bash
cd backend
python manage.py seed_prestia
python manage.py import_messages_json /path/to/messages.json
python manage.py import_messages_json /path/to/messages.json --tenant prestia --store main
```

---

## Explicit out-of-scope items (deferred to later steps)

- Full AI context endpoint (`/internal/ai/context/{report_run_id}/`) — Step 3.5
- Report and action models — Phase 4
- Celery orchestration
- Support-agent implementation and reply drafting
- Real Instagram webhook integration
- Real Instagram send/reply behavior
- Advanced CRM workflow (escalation, approvals, classifications)
