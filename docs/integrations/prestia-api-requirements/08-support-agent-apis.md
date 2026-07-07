# Support Agent APIs

APIs and integration patterns required by the **Support Agent** for message analysis, reply drafts, and customer context.

## Agent summary

The Support Agent (`agents/support/`) analyzes sanitized message threads and produces `SupportInsights` (exposed as `SupportRunResponse` over HTTP). It:

- Refuses out-of-scope requests (pricing changes, other agents, credentials)
- Classifies themes (`generic_faq`, `product_question`, `refund_request`, etc.)
- Generates `reply_drafts` with approval metadata
- Uses FAQ content from Prestia and CRM context from Botkonak
- Does **not** send messages to customers

Coordinator passes `context.messages` and derives `customer_message` + `channel` from threads (`agents/coordinator/nodes.py`).

---

## Message sources

The Support Agent receives messages from separate channels. Planned sources:

| Source | Platform value | Channel (Botkonak) |
|--------|--------------|-------------------|
| Website | `website` | `web_chat` |
| Instagram | `instagram` | `instagram_dm` |
| Telegram | `telegram` | `telegram_dm` |

Each source is a distinct message ingestion path. Botkonak unifies them in a single tenant support inbox.

---

## Message ingestion model (webhook-based)

Support Agent message ingestion is **event-driven through webhooks**, not by repeatedly polling a Prestia messages API.

### Instagram and Telegram

- Use the **standard webhook mechanisms** provided by Instagram and Telegram.
- When a user sends a message through Instagram or Telegram, the platform webhook delivers that message to **Botkonak**.
- Botkonak stores the message, links it to the tenant CRM customer record, and surfaces it in the support inbox.

### Website

- Message ingestion is also **webhook-based**.
- When a user sends a message on the Prestia website chat widget, **Prestia must send that message to Botkonak immediately** via webhook.
- The message becomes visible inside the Botkonak message box / support inbox.

### Flow diagram

```
┌─────────────┐   platform webhook    ┌──────────────┐
│  Instagram  │ ────────────────────► │              │
└─────────────┘                       │   Botkonak   │
┌─────────────┐   platform webhook    │  (support    │
│  Telegram   │ ────────────────────► │   inbox +    │
└─────────────┘                       │   tenant     │
┌─────────────┐   Prestia → Botkonak  │   CRM)       │
│   Website   │ ────────────────────► │              │
└─────────────┘   webhook             └──────┬───────┘
                                             │
                                    Support Agent POST /run
                                    (local message threads)
```

**Prestia does not need to expose `GET /v1/messages/recent` for Support Agent MVP.** Messages arrive via webhooks; agents read from Botkonak's local database.

---

## Tenant CRM (Botkonak responsibility)

Botkonak maintains a **small tenant-level CRM**:

| Aspect | Behavior |
|--------|----------|
| Storage | Tenant-specific customer database in Botkonak |
| Sources | Website, Instagram, Telegram, and future channels |
| Unification | Same customer may be linked across platforms via `platform` + `platform_user_id` |
| Agent usage | Support Agent uses CRM context (display name, platform, order history refs) when generating replies |
| PII handling | Email/phone redacted before agents see message text (`catalog/pii.py`) |

Prestia customer data from [GET /v1/customers](./05-customer-apis.md) supplements CRM during sync; webhook ingestion creates/updates CRM records in real time.

---

## Required Prestia data API: List FAQs

| Property | Value |
|----------|-------|
| **API name** | List FAQs |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/faqs` |
| **Botkonak consumer** | Support Agent |
| **Why Botkonak needs this** | Support Agent uses Prestia FAQ content to answer common user questions accurately. |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Required request headers

`Authorization: Bearer <access_token>`, `Accept: application/json`

### Query parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Pagination (default 50) |
| `offset` | integer | No | Pagination offset |

### Successful response shape

```json
{
  "count": 12,
  "results": [
    {
      "question": "زمان ارسال سفارش چقدر است؟",
      "answer": "سفارش‌های تهران ۱ تا ۳ روز کاری و سایر شهرها ۳ تا ۷ روز کاری ارسال می‌شوند."
    },
    {
      "question": "آیا امکان مرجوعی وجود دارد؟",
      "answer": "بله، تا ۷ روز پس از تحویل در صورت سالم بودن بسته."
    }
  ]
}
```

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| `question` | string | FAQ question text |
| `answer` | string | FAQ answer text |

FAQs are fetched on demand when the Support Agent needs fresh content (see [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md)).

### Example request

```http
GET /v1/faqs?limit=100&offset=0 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

---

## Optional Prestia read APIs

| API | Priority | Notes |
|-----|----------|-------|
| [GET /v1/orders/{order_id}](./04-order-and-sales-apis.md) | P2 | Order-status questions in threads |
| [GET /v1/customers](./05-customer-apis.md) | P1 | CRM sync and reconciliation |
| [GET /v1/products](./03-product-and-inventory-apis.md) | P1 | Product availability answers |

---

## APIs NOT required

| Data | Reason |
|------|--------|
| `GET /v1/store` | Brand tone and store identity are Botkonak tenant settings |
| `GET /v1/messages/recent` | Replaced by webhook-based message ingestion |
| Suggested replies from Prestia | Generated by Support Agent LLM |
| Risk flags from Prestia | Computed by `approval_policy.py` and `refusal.py` |
| Customer PII in agent APIs | `customer_ref` opaque ID only in AI path |

---

## Write API: Post Support Reply (Future)

| Property | Value |
|----------|-------|
| **API name** | Send Support Reply |
| **HTTP method** | `POST` |
| **Suggested path** | Outbound via platform APIs (Instagram, Telegram) or Prestia website chat API |
| **Requirement type** | Optional (Future) |
| **Priority** | Future |

Botkonak `actions.execute` uses a stub handler with no external side effects (`backend/operations/tasks.py`). Future execution would need outbound messaging APIs and scope `write:support_replies`.

---

## Field mapping (webhook → Support Agent)

When messages arrive via webhook, Botkonak normalizes to Support Agent input:

| Ingested field | Support agent normalized field |
|----------------|-------------------------------|
| `thread_id` | `thread_ref` |
| `message_id` | `message_ref` |
| `sender_type` | `sender_role` |
| `body` | `text` |
| `sent_at` | `created_at` |
| `platform` + `channel` | `channel` |

Support agent normalizes `body` → `text`, `sent_at` → `created_at` (`agents/support/support_context.py`).

---

## Evidence from codebase

| File | Relevance |
|------|-----------|
| `agents/support/analysis.py` | Runtime pipeline |
| `agents/support/approval_policy.py` | FAQ theme classification |
| `agents/support/refusal.py` | Scope guardrails |
| `agents/support/injection_guard.py` | Prompt injection defense |
| `agents/coordinator/nodes.py` | `_derive_support_message_from_context` |
| `docs/agents/support.md` | Agent documentation |
| `docs/examples/support_output.json` | Output contract |

## Open questions

1. Prestia website chat webhook payload schema and authentication (HMAC, shared secret).
2. Whether Instagram/Telegram webhooks route through Prestia or connect directly to Botkonak.
3. Message import format for `import_messages_json` vs live webhook shape alignment.
