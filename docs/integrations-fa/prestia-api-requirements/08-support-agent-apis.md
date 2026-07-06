<div dir="rtl" align="right">

# APIهای Support Agent

APIهایی که **Support Agent** برای تحلیل Instagram DM، تولید draftهای پاسخ و customer context به آن‌ها نیاز دارد.

## خلاصه Agent

Support Agent، یعنی `agents/support/`، message threadهای sanitize‌شده را تحلیل می‌کند و خروجی‌ای از نوع `SupportInsights` تولید می‌کند؛ این خروجی از طریق HTTP به شکل `SupportRunResponse` expose می‌شود. این Agent:

- requestهای خارج از scope را رد می‌کند؛ مثل تغییر قیمت، درخواست‌های مربوط به agentهای دیگر، یا credentialها.
- themeها را classify می‌کند؛ مثل `generic_faq`، `product_question`، `refund_request` و موارد مشابه.
- مقدارهای `reply_drafts` را همراه با approval metadata تولید می‌کند.
- به customerها پیام ارسال نمی‌کند.

Coordinator مقدار `context.messages` را ارسال می‌کند و مقدارهای `customer_message` و `channel` را از threadها استخراج می‌کند؛ فایل `agents/coordinator/nodes.py`. در مسیر Coordinator مقدار `fetch_recent_messages: False` تنظیم شده است.

## جریان داده

</div>

```text
Prestia GET /messages/recent
       ↓
Botkonak sync (PII stored admin-side; bodies sanitized for AI)
       ↓
Context bundle messages → Support Agent POST /run
```

<div dir="rtl" align="right">

## API لازم از Prestia

### دریافت Recent Message Threads

قرارداد کامل این API در قالب consolidated در ادامه آمده است.

| Property                               | Value                                                                                                                                                                                           |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | Get Recent Message Threads                                                                                                                                                                      |
| **HTTP method**                        | `GET`                                                                                                                                                                                           |
| **مسیر endpoint پیشنهادی**             | `/v1/messages/recent`                                                                                                                                                                           |
| **مصرف‌کننده در Botkonak**             | Support Agent، Coordinator Agent، Background sync                                                                                                                                               |
| **چرا Botkonak به این API نیاز دارد؟** | ورودی support analysis است. Coordinator آخرین پیام inbound مربوط به customer را برای مقدار `customer_message` استخراج می‌کند. history مربوط به thread هم context لازم را برای LLM فراهم می‌کند. |
| **نوع نیازمندی**                       | Direct                                                                                                                                                                                          |
| **Priority**                           | P0                                                                                                                                                                                              |

#### Headerهای لازم برای request

`Authorization: Bearer <access_token>`، `Accept: application/json`

#### Query parameterها

| Parameter             | Type    | Default | Max | Description                                   |
| --------------------- | ------- | ------- | --- | --------------------------------------------- |
| `thread_limit`        | integer | 10      | 50  | با `build_recent_messages_summary` هماهنگ است |
| `messages_per_thread` | integer | 5       | 50  | پیام‌های اخیر در هر thread                    |
| `platform`            | string  | —       | —   | filter، برای مثال `instagram`                 |
| `status`              | string  | —       | —   | مقدارهایی مثل `open`، `pending`، `closed`     |

#### ساختار response موفق

</div>

```json
{
  "generated_at": "2026-06-25T14:30:00+00:00",
  "store_id": "22222222-2222-2222-2222-222222222222",
  "thread_count": 2,
  "threads": [
    {
      "thread_id": "55555555-5555-5555-5555-555555555555",
      "external_thread_id": "prestia-thread-availability",
      "customer_ref": "customer-66666666-6666-6666-6666-666666666666",
      "platform": "instagram",
      "channel": "instagram_dm",
      "status": "open",
      "subject": "Milano Leather Tote availability",
      "last_message_at": "2026-06-25T12:00:00+00:00",
      "messages": [
        {
          "message_id": "77777777-7777-7777-7777-777777777777",
          "external_message_id": "prestia-msg-avail-001",
          "direction": "inbound",
          "sender_type": "customer",
          "body": "سلام! کیف میلانو رنگ cognac موجوده؟",
          "sent_at": "2026-06-25T11:48:00+00:00"
        },
        {
          "message_id": "77777777-7777-7777-7777-777777777888",
          "direction": "outbound",
          "sender_type": "staff",
          "body": "بله، موجودی محدود است.",
          "sent_at": "2026-06-25T12:00:00+00:00"
        }
      ]
    }
  ]
}
```

<div dir="rtl" align="right">

**نکته:** Botkonak قبل از اینکه agentها متن را ببینند، emailها و phoneها را در `body` با `[EMAIL_REDACTED]` و `[PHONE_REDACTED]` جایگزین می‌کند؛ فایل `catalog/pii.py`. Prestia ممکن است body خام را برگرداند؛ در این حالت Botkonak connector هنگام ingest یا در مرز API آن را sanitize می‌کند.

#### نگاشت Fieldها به Support Agent

| Prestia / Django field | فیلد normalize‌شده در Support Agent                     |
| ---------------------- | ------------------------------------------------------- |
| `thread_id`            | `thread_ref`                                            |
| `message_id`           | `message_ref`                                           |
| `sender_type`          | `sender_role`                                           |
| `body`                 | `text`                                                  |
| `sent_at`              | `created_at`                                            |
| `platform` + `channel` | `channel`؛ Coordinator از `instagram_dm` استفاده می‌کند |

#### Pagination

با `thread_limit` و `messages_per_thread` محدود می‌شود؛ این API برای sync کردن history کامل نیست.

#### Error caseها

`401`، `403`، `500`

#### نمونه request

</div>

```http
GET /v1/messages/recent?thread_limit=10&messages_per_thread=5&platform=instagram HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

<div dir="rtl" align="right">

#### فایل‌های مرتبط

- `backend/catalog/services.py` — تابع `build_recent_messages_summary`
- `backend/catalog/internal_views.py` — کلاس `InternalRecentMessagesView`
- `agents/support/django_fetch.py` — تابع `fetch_message_threads_from_django`
- `agents/support/support_context.py` — normalization
- `agents/coordinator/nodes.py` — تابع `_derive_support_message_from_context`
- `seed_prestia.py` — مقدارهای `PRESTIA_THREADS` و `PRESTIA_MESSAGES`
- `docs/phases/step-3.4.md`

## APIهایی که لازم نیستند؛ تأییدشده از codebase

| Data                                    | Reason                                                                                                                                      |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **FAQ database API**                    | FAQ یک **policy classification** است؛ یعنی `generic_faq` که توسط `agents/support/approval_policy.py` اعمال می‌شود و از Prestia load نمی‌شود |
| **Suggested replies from Prestia**      | توسط LLM مربوط به Support Agent تولید می‌شود                                                                                                |
| **Message status updates / send reply** | write outbound به Prestia وجود ندارد؛ در Coordinator مقدار `persist_actions: False` تنظیم شده است                                           |
| **Risk flags from Prestia**             | توسط `approval_policy.py` و `refusal.py` محاسبه می‌شود                                                                                      |
| **Customer PII in API**                 | در مسیر AI فقط opaque ID یعنی `customer_ref` وجود دارد                                                                                      |

## APIهای اختیاری از Prestia

| API                        | Priority | Notes                                           |
| -------------------------- | -------- | ----------------------------------------------- |
| `GET /v1/orders/{id}`      | P2       | برای سؤال‌های مربوط به order-status در threadها |
| `GET /v1/customers`        | P2       | فقط برای sync؛ نه برای agent                    |
| Webhook `message.received` | Future   | برای real-time support؛ به سند sync مراجعه شود  |

## Write API: ارسال Support Reply در آینده

| Property          | Value                                      |
| ----------------- | ------------------------------------------ |
| **نام API**       | Send Support Reply                         |
| **HTTP method**   | `POST`                                     |
| **مسیر پیشنهادی** | `/v1/messages/threads/{thread_id}/replies` |
| **نوع نیازمندی**  | Optional (Future)                          |
| **Priority**      | Future                                     |

در Botkonak، مسیر `actions.execute` از یک stub handler بدون external side effect استفاده می‌کند؛ فایل `backend/operations/tasks.py`. اجرای واقعی در آینده به این API و scope به نام `write:support_replies` نیاز خواهد داشت.

## شواهد از codebase

| File                                | Relevance                                   |
| ----------------------------------- | ------------------------------------------- |
| `agents/support/analysis.py`        | runtime pipeline                            |
| `agents/support/approval_policy.py` | policy مربوط به FAQ؛ نه FAQ data از Prestia |
| `agents/support/refusal.py`         | guardrailهای مربوط به scope                 |
| `agents/support/injection_guard.py` | دفاع در برابر prompt injection              |
| `docs/agents/support.md`            | مستندات Agent                               |
| `docs/examples/support_output.json` | output contract                             |

## سؤال‌های باز

1. آیا Prestia خودش مالک integration مربوط به Instagram DM است یا به third-party inbox نیاز دارد؟
2. آیا مقدار `channel` برای messageهای Instagram در Prestia همیشه باید `instagram_dm` باشد؟
3. فرمت import messageها برای `import_messages_json` با live API shape چقدر هم‌راستا است؟

</div>
