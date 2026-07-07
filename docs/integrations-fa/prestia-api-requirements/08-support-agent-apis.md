<div dir="rtl" align="right">

# APIهای Support Agent

APIها و الگوهای integration موردنیاز **Support Agent** برای تحلیل message، draft پاسخ و context customer.

## خلاصه Agent

Support Agent (`agents/support/`) threadهای message sanitize‌شده را تحلیل می‌کند و `SupportInsights` تولید می‌کند (روی HTTP به‌صورت `SupportRunResponse` expose می‌شود). این agent:

- درخواست‌های خارج از scope را رد می‌کند (تغییر قیمت، agentهای دیگر، credentialها)
- themeها را طبقه‌بندی می‌کند (`generic_faq`، `product_question`، `refund_request` و غیره)
- `reply_drafts` با metadata تأیید تولید می‌کند
- از محتوای FAQ Prestia و context CRM Botkonak استفاده می‌کند
- **message به customer ارسال نمی‌کند**

Coordinator `context.messages` را می‌فرستد و `customer_message` + `channel` را از threadها استخراج می‌کند (`agents/coordinator/nodes.py`).

---

## منابع Message

Support Agent messageها را از کانال‌های جداگانه دریافت می‌کند. منابع برنامه‌ریزی‌شده:

| Source | مقدار Platform | Channel (Botkonak) |
|--------|---------------|-------------------|
| Website | `website` | `web_chat` |
| Instagram | `instagram` | `instagram_dm` |
| Telegram | `telegram` | `telegram_dm` |

هر منبع مسیر ingestion message جداگانه‌ای است. Botkonak آن‌ها را در یک inbox support سطح tenant یکپارچه می‌کند.

---

## مدل ingestion message (مبتنی بر webhook)

ingestion message برای Support Agent **event-driven از طریق webhook** است، نه با polling مکرر API messageهای Prestia.

### Instagram و Telegram

- از **مکانیزم webhook استاندارد** Instagram و Telegram استفاده کنید.
- وقتی کاربر از Instagram یا Telegram message می‌فرستد، webhook platform آن message را به **Botkonak** تحویل می‌دهد.
- Botkonak message را ذخیره می‌کند، به customer record CRM tenant وصل می‌کند و در inbox support نمایش می‌دهد.

### Website

- ingestion message هم **مبتنی بر webhook** است.
- وقتی کاربر در widget chat وب‌سایت Prestia message می‌فرستد، **Prestia باید فوراً آن message را از طریق webhook به Botkonak بفرستد**.
- message در message box / inbox support Botkonak قابل مشاهده می‌شود.

### نمودار جریان

<div dir="ltr" align="left">

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

</div>

**Prestia برای MVP Support Agent نیازی به expose کردن `GET /v1/messages/recent` ندارد.** messageها از webhook می‌آیند؛ agentها از دیتابیس محلی Botkonak می‌خوانند.

---

## CRM سطح Tenant (مسئولیت Botkonak)

Botkonak یک **CRM کوچک سطح tenant** نگه می‌دارد:

| Aspect | Behavior |
|--------|----------|
| Storage | دیتابیس customer مخصوص tenant در Botkonak |
| Sources | Website، Instagram، Telegram و کانال‌های آینده |
| Unification | همان customer ممکن است از طریق `platform` + `platform_user_id` بین platformها link شود |
| Agent usage | Support Agent از context CRM (display name، platform، ارجاع order history) هنگام تولید پاسخ استفاده می‌کند |
| PII handling | email/phone قبل از دیدن agentها redact می‌شود (`catalog/pii.py`) |

داده customer Prestia از [GET /v1/customers](./05-customer-apis.md) CRM را در sync تکمیل می‌کند؛ ingestion webhook در بلادرنگ record CRM را ایجاد/به‌روز می‌کند.

---

## API داده Prestia موردنیاز: List FAQs

| Property | Value |
|----------|-------|
| **API name** | List FAQs |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/faqs` |
| **Botkonak consumer** | Support Agent |
| **Why Botkonak needs this** | Support Agent از محتوای FAQ Prestia برای پاسخ دقیق به سؤال‌های رایج استفاده می‌کند. |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Headerهای لازم برای request

`Authorization: Bearer <access_token>`، `Accept: application/json`

### Query parameterها

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | pagination (پیش‌فرض 50) |
| `offset` | integer | No | offset pagination |

### شکل successful response

<div dir="ltr" align="left">

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

</div>

### تعریف fieldها

| Field | Type | Description |
|-------|------|-------------|
| `question` | string | متن سؤال FAQ |
| `answer` | string | متن پاسخ FAQ |

FAQها on-demand وقتی Support Agent به محتوای تازه نیاز دارد fetch می‌شوند ([10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md)).

### نمونه request

<div dir="ltr" align="left">

```http
GET /v1/faqs?limit=100&offset=0 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

</div>

---

## Read APIهای اختیاری Prestia

| API | Priority | Notes |
|-----|----------|-------|
| [GET /v1/orders/{order_id}](./04-order-and-sales-apis.md) | P2 | سؤال‌های وضعیت order در threadها |
| [GET /v1/customers](./05-customer-apis.md) | P1 | sync و reconcile CRM |
| [GET /v1/products](./03-product-and-inventory-apis.md) | P1 | پاسخ‌های موجودی product |

---

## APIهایی که لازم نیست

| Data | Reason |
|------|--------|
| `GET /v1/store` | brand tone و هویت store همان Botkonak tenant settings است |
| `GET /v1/messages/recent` | با ingestion message مبتنی بر webhook جایگزین شده |
| suggested reply از Prestia | توسط LLM Support Agent تولید می‌شود |
| risk flag از Prestia | توسط `approval_policy.py` و `refusal.py` محاسبه می‌شود |
| PII customer در API agent | فقط ID مبهم `customer_ref` در مسیر AI |

---

## Write API: Post Support Reply (Future)

| Property | Value |
|----------|-------|
| **API name** | Send Support Reply |
| **HTTP method** | `POST` |
| **Suggested path** | outbound از طریق APIهای platform (Instagram، Telegram) یا API chat وب‌سایت Prestia |
| **Requirement type** | Optional (Future) |
| **Priority** | Future |

`actions.execute` در Botkonak از handler stub بدون اثر خارجی استفاده می‌کند (`backend/operations/tasks.py`). اجرای آینده به API messaging outbound و scope `write:support_replies` نیاز دارد.

---

## Field mapping (webhook → Support Agent)

وقتی messageها از webhook می‌آیند، Botkonak به ورودی Support Agent normalize می‌کند:

| Ingested field | Support agent normalized field |
|----------------|-------------------------------|
| `thread_id` | `thread_ref` |
| `message_id` | `message_ref` |
| `sender_type` | `sender_role` |
| `body` | `text` |
| `sent_at` | `created_at` |
| `platform` + `channel` | `channel` |

Support Agent مقدار `body` → `text` و `sent_at` → `created_at` normalize می‌کند (`agents/support/support_context.py`).

---

## شواهد از codebase

| File | Relevance |
|------|-----------|
| `agents/support/analysis.py` | pipeline runtime |
| `agents/support/approval_policy.py` | طبقه‌بندی theme FAQ |
| `agents/support/refusal.py` | guardrailهای scope |
| `agents/support/injection_guard.py` | دفاع prompt injection |
| `agents/coordinator/nodes.py` | `_derive_support_message_from_context` |
| `docs/agents/support.md` | مستندات agent |
| `docs/examples/support_output.json` | contract خروجی |

## سؤال‌های باز

1. schema payload و authentication webhook chat وب‌سایت Prestia (HMAC، shared secret).
2. آیا webhookهای Instagram/Telegram از Prestia عبور می‌کنند یا مستقیم به Botkonak وصل می‌شوند.
3. هم‌راستایی فرمت import `import_messages_json` با شکل webhook زنده.

</div>
