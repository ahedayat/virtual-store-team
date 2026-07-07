<div dir="rtl" align="right">

# Contractهای داده مشترک

قراردادهای مشترک برای APIهای Prestia که Botkonak مصرف می‌کند.

## اصول طراحی

1. **هم‌راستا با شکل‌های normalize‌شده Botkonak** جایی که در `backend/catalog/services.py` و `backend/catalog/context.py` وجود دارند.
2. **نام field پایدار** — در responseهای Prestia از نام‌های native Prestia استفاده شود؛ mapping به نام‌های داخلی Botkonak مستند شود.
3. **کاهش PII برای مسیرهای AI** — bodyهای message ممکن است متن customer داشته باشند؛ Prestia ممکن است متن خام برگرداند و Botkonak قبل از مصرف توسط agentها email/phone را redact می‌کند (`backend/catalog/pii.py`).
4. **فقط JSON** — `Content-Type: application/json` برای request و response.

## شناسه‌ها

| Concept | Prestia field (پیشنهادی) | Botkonak internal field | Notes |
|---------|---------------------------|-------------------------|-------|
| Store | `id` (UUID یا string پایدار) | `store.id` | در onboarding connector map می‌شود |
| Tenant | `tenant_id` یا implicit از token | `tenant.id` | Botkonak tenant محلی می‌سازد |
| Product | `slug` | `product_id` در AI bundle | شناسه اصلی؛ همچنین map به UUID محلی |
| Category | `slug` | `category.slug` | nested زیر product در context bundle |
| Order | `order_id` | `order_number`، `external_id` | `external_id` شناسه order Prestia را نگه می‌دارد |
| Customer | `tenant_user_id` | `customer-{uuid}` مبهم در AI APIها | PII خام به agentها داده نمی‌شود |
| Message thread | `id`، `external_thread_id` | `thread_id` | |
| Message | `id`، `external_message_id` | `message_id` | |

## Timestampها

- ISO 8601 با timezone offset، مثلاً `"2026-06-25T12:00:00+00:00"`.
- fieldهای Botkonak: `created_at`، `updated_at`، `placed_at`، `sent_at`، `last_message_at`، `generated_at`.

## پول و currency

- مبالغ پولی به‌صورت **number** (مثلاً `189.00`) یا decimal string — Prestia باید فرمت را مستند کند؛ Botkonak هنگام ingest normalize می‌کند.
- `currency` به‌صورت کد ISO 4217، مثلاً `"USD"`، `"IRR"`.
- currency پیش‌فرض در **Botkonak tenant settings** تنظیم می‌شود، نه از Prestia fetch می‌شود.

## enum وضعیت order

Botkonak `OrderStatus` (`backend/catalog/models.py`):

| Status | در sales summary revenue شمارش می‌شود؟ |
|--------|--------------------------------------|
| `paid` | بله |
| `completed` | بله |
| `fulfilled` | بله |
| `pending` | خیر |
| `draft` | خیر |
| `cancelled` | خیر |
| `refunded` | خیر |
| `failed` | خیر |

Prestia باید وضعیت‌های order خود را به این مقادیر map کند (یا جدول mapping را در connector مستند کند).

## enum platform (support)

گزینه‌های Botkonak `Platform`: `instagram`، `whatsapp`، `email`، `web`، `telegram`، `manual`.

Coordinator هنگام استخراج message از context، channel پیش‌فرض را `instagram_dm` می‌گذارد (`agents/coordinator/nodes.py`). Prestia باید برای Instagram DM از `platform: "instagram"`، برای Telegram از `platform: "telegram"` و برای website chat از `platform: "website"` استفاده کند.

## جهت message و sender

| Prestia (پیشنهادی) | Botkonak | alias Support Agent |
|--------------------|----------|---------------------|
| `direction: "inbound"` | `MessageDirection.INBOUND` | — |
| `direction: "outbound"` | `MessageDirection.OUTBOUND` | — |
| `sender_type: "customer"` | `SenderType.CUSTOMER` | `sender_role: "customer"` |
| `sender_type: "staff"` | `SenderType.STAFF` | `sender_role: "staff"` |
| `sender_type: "system"` | `SenderType.SYSTEM` | `sender_role: "system"` |

Support Agent مقدار `body` → `text` و `sent_at` → `created_at` normalize می‌کند (`agents/support/support_context.py`).

## Pagination

**نوع نیازمندی:** استنباط‌شده برای list endpointها — endpointهای AI داخلی Botkonak امروز لیست‌های bounded کامل برمی‌گردانند (مثلاً همه productهای active، 10 thread برتر).

قرارداد پیشنهادی Prestia:

| Parameter | Type | Default | Max |
|-----------|------|---------|-----|
| `limit` | integer | 50 | 100 |
| `offset` | integer | 0 | — |
| `cursor` | string | — | جایگزین اختیاری مبتنی بر cursor |

**Response wrapper:**

<div dir="ltr" align="left">

```json
{
  "count": 120,
  "next": "https://api.prestia.ir/v1/products?cursor=eyJpZCI6MTIzfQ",
  "previous": null,
  "results": []
}
```

</div>

برای endpointهای حیاتی AI با پنجره ثابت (messageهای اخیر)، cursor pagination اختیاری است اگر defaultها با limitهای Botkonak هم‌خوان باشند (`thread_limit=10`، `messages_per_thread=5`).

## Filter و sort

query parameterهای رایجی که Botkonak ممکن است نیاز داشته باشد:

| Parameter | Applies to | Purpose |
|-----------|------------|---------|
| `is_active` | products | Content Agent فقط productهای active |
| `search` | products، customers | جستجو بر اساس title/slug یا phone/email/name |
| `category` | products | filter بر اساس category slug |
| `price_min`، `price_max` | products | filter بازه قیمت |
| `currency` | products | filter currency |
| `has_discount` | products | filter discount |
| `inventory_lte`، `inventory_gte` | products | filter تعداد variant |
| `status` | orders | filter وضعیت order |
| `created_at_from`، `created_at_to` | orders | بازه تاریخ order |
| `customer_id` | orders | filter بر اساس customer |
| `product_slug` | orders | orderهای حاوی product |
| `total_min`، `total_max` | orders | بازه total order |
| `platform` | customers | filter منبع message |

sort پیش‌فرض:
- Products: `title` صعودی
- Orders: `-created_at`
- Customers: `-updated_at`

## شکل error response

هم‌راستا با سبک Django REST Framework در Botkonak:

<div dir="ltr" align="left">

```json
{
  "detail": "Human-readable error message."
}
```

</div>

| HTTP status | When |
|-------------|------|
| `400` | query parameter نامعتبر |
| `401` | Bearer token گم‌شده یا نامعتبر |
| `403` | token معتبر اما scope ناکافی یا store اشتباه |
| `404` | resource پیدا نشد |
| `429` | rate limit رد شد |
| `500` | خطای server |

`DjangoClient` در Botkonak برای GET روی `502`، `503`، `504` موقت retry می‌کند (`agents/shared/django_client/client.py`). Prestia نباید این کدها را برای خطای auth استفاده کند.

## الگوی warnings (responseهای aggregate)

context bundle Botkonak شامل `warnings: []` برای خطاهای جزئی است (`backend/catalog/context.py`). اگر Prestia endpoint context aggregate ارائه دهد، می‌تواند همان الگو را استفاده کند.

## شکل brand voice settings

Content Agent مقدار `store_context.settings.brand_voice` را از **Botkonak tenant settings** می‌خواند (`agents/content/brand_voice.py`):

<div dir="ltr" align="left">

```json
{
  "brand_voice": {
    "tone": "warm, approachable",
    "audience": "fashion-conscious online shoppers",
    "style_notes": "short sentences; factual product claims only",
    "language": "fa"
  }
}
```

</div>

در UI تنظیمات tenant/store Botkonak پیکربندی می‌شود — از Prestia fetch نمی‌شود (به [02-store-profile-apis.md](./02-store-profile-apis.md) مراجعه کنید).

## شواهد از codebase

- `backend/catalog/models.py` — enumها و نام fieldها
- `backend/catalog/context.py` — کلیدهای سطح بالای context bundle
- `backend/catalog/pii.py` — قوانین redaction PII
- `agents/content/product_context.py` — aliasهای field (`name`/`title`، `image`/`image_url`)
- `agents/support/support_context.py` — aliasهای field message/thread
- `docs/phases/step-3.5.md` — نمونه JSON context bundle

## سؤال‌های باز

1. Prestia از UUID یا integer ID استفاده می‌کند (Botkonak محلی UUID دارد؛ connector باید map کند).
2. rate limit استاندارد برای sync در مقابل call تعاملی.
3. آیا Prestia ارقام فارسی در قیمت برمی‌گرداند و آیا قبل از import به Django normalize لازم است.

</div>
