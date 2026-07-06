<div dir="rtl" align="right">

# قراردادهای مشترک Data Contracts

قراردادها و conventionهای مشترک برای APIهای Prestia که توسط Botkonak مصرف می‌شوند.

## اصول طراحی

1. **هماهنگی با normalized shapes در Botkonak**؛ در جاهایی که این ساختارها از قبل در `backend/catalog/services.py` و `backend/catalog/context.py` وجود دارند، Prestia باید تا حد امکان با همان شکل‌های استاندارد Botkonak هماهنگ باشد.
2. **نام‌گذاری پایدار fieldها**؛ در responseهای Prestia از نام‌های بومی خود Prestia استفاده شود، اما mapping آن‌ها به نام‌های internal در Botkonak مستند شود.
3. **کاهش PII در مسیرهای AI**؛ بدنه‌ی پیام‌های Support ممکن است شامل متن مشتری باشد. Prestia می‌تواند متن خام را برگرداند، اما Botkonak قبل از اینکه agentها داده را مصرف کنند، emailها و شماره‌تلفن‌ها را با استفاده از `backend/catalog/pii.py` حذف یا redact می‌کند.
4. **فقط JSON**؛ برای requestها و responseها باید از `Content-Type: application/json` استفاده شود.

## شناسه‌ها

| مفهوم | field پیشنهادی در Prestia | field داخلی در Botkonak | نکات |
|---------|---------------------------|-------------------------|-------|
| Store | `id`، به‌صورت UUID یا stable string | `store.id` | هنگام connector onboarding مپ می‌شود. |
| Tenant | `tenant_id` یا به‌صورت implicit از روی token | `tenant.id` | Botkonak یک tenant محلی ایجاد می‌کند. |
| Product | `id` | `product_id` در AI bundle | در Content Agent، alias با نام `product_id` هم پذیرفته می‌شود. |
| Category | `id` | `category.id` | داخل context bundle، زیرمجموعه‌ی product قرار می‌گیرد. |
| Order | `id`، `order_number` | `order_number`، `external_id` | مقدار `external_id` شناسه‌ی order در Prestia را نگه می‌دارد. |
| Customer | `id` | مقدار opaque مانند `customer-{uuid}` در AI APIs | PII خام به agentها پاس داده نمی‌شود. |
| Message thread | `id`، `external_thread_id` | `thread_id` |  |
| Message | `id`، `external_message_id` | `message_id` |  |

## Timestampها

- از ISO 8601 همراه با timezone offset استفاده شود؛ برای مثال: `"2026-06-25T12:00:00+00:00"`.
- fieldهای Botkonak عبارت‌اند از: `created_at`، `updated_at`، `placed_at`، `sent_at`، `last_message_at`، `generated_at`.

## پول و currency

- مبلغ‌ها باید به‌صورت **decimal string** با دو رقم اعشار ارسال شوند؛ برای مثال: `"189.00"`. این روش با serialization مربوط به `DecimalField` در Django سازگار است.
- مقدار `currency` باید به‌صورت کد ISO 4217 باشد؛ برای مثال: `"USD"` یا `"IRR"`.
- currency پیش‌فرض در سطح Store داخل store profile مشخص می‌شود.

## enum مربوط به وضعیت Order

مقادیر `OrderStatus` در Botkonak در فایل `backend/catalog/models.py` تعریف شده‌اند:

| Status | آیا در sales summary به‌عنوان revenue حساب می‌شود؟ |
|--------|-----------------------------------|
| `paid` | بله |
| `completed` | بله |
| `fulfilled` | بله |
| `pending` | خیر |
| `draft` | خیر |
| `cancelled` | خیر |
| `refunded` | خیر |
| `failed` | خیر |

Prestia باید وضعیت‌های order خودش را به این مقدارها map کند. راه دیگر این است که یک mapping table داخل connector مستند شود.

## enum مربوط به Platform در Support

گزینه‌های `Platform` در Botkonak عبارت‌اند از: `instagram`، `whatsapp`، `email`، `web`، `manual`.

وقتی Support Agent Coordinator پیام‌ها را از context استخراج می‌کند، مقدار پیش‌فرض channel را `instagram_dm` در نظر می‌گیرد. این رفتار در `agents/coordinator/nodes.py` پیاده‌سازی شده است. بنابراین Prestia برای Instagram DMها باید از `platform: "instagram"` استفاده کند.

## جهت پیام و فرستنده

| مقدار پیشنهادی در Prestia | مقدار در Botkonak | alias در Support Agent |
|-----------------------|----------|---------------------|
| `direction: "inbound"` | `MessageDirection.INBOUND` | — |
| `direction: "outbound"` | `MessageDirection.OUTBOUND` | — |
| `sender_type: "customer"` | `SenderType.CUSTOMER` | `sender_role: "customer"` |
| `sender_type: "staff"` | `SenderType.STAFF` | `sender_role: "staff"` |
| `sender_type: "system"` | `SenderType.SYSTEM` | `sender_role: "system"` |

Support Agent مقدارهای `body` → `text` و `sent_at` → `created_at` را normalize می‌کند. این منطق در `agents/support/support_context.py` قرار دارد.

## Pagination

**نوع requirement:** برای list endpointها inferred است. در حال حاضر endpointهای internal AI در Botkonak فهرست‌های کامل اما bounded برمی‌گردانند؛ برای مثال همه‌ی productهای active یا ۱۰ thread برتر.

Convention پیشنهادی برای Prestia:

| Parameter | Type | Default | Max |
|-----------|------|---------|-----|
| `limit` | integer | 50 | 100 |
| `offset` | integer | 0 | — |
| `cursor` | string | — | جایگزین اختیاری مبتنی بر cursor |

**Response wrapper:**

</div>

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

<div dir="rtl" align="right">

برای endpointهای حساس به AI که window ثابت دارند، مثل پیام‌های اخیر، cursor pagination اختیاری است؛ البته به شرطی که defaultها با limitهای Botkonak هماهنگ باشند، مانند `thread_limit=10` و `messages_per_thread=5`.

## Filtering و Sorting

query parameterهای مشترکی که Botkonak ممکن است نیاز داشته باشد:

| Parameter | کاربرد برای | هدف |
|-----------|------------|---------|
| `is_active=true` | products، categories | Content Agent فقط از productهای active استفاده می‌کند. |
| `updated_since` | products، orders، inventory، messages | برای incremental sync استفاده می‌شود. |
| `status` | orders، threads | برای filter کردن open orders یا open threads استفاده می‌شود. |
| `placed_at_gte`، `placed_at_lt` | orders | برای aggregation فروش در یک بازه‌ی زمانی استفاده می‌شود؛ یا می‌توان از summary endpoint اختصاصی استفاده کرد. |

sort پیش‌فرض:

- Products: مرتب‌سازی صعودی بر اساس `name`، مطابق با `build_product_summary`
- Orders: مرتب‌سازی بر اساس `-placed_at`
- Threads: مرتب‌سازی بر اساس `-last_message_at`

## شکل response خطا

این ساختار باید با style مربوط به Django REST Framework که در Botkonak استفاده شده هماهنگ باشد:

</div>

<div dir="ltr" align="left">

```json
{
  "detail": "Human-readable error message."
}
```

</div>

<div dir="rtl" align="right">

| HTTP status | زمان استفاده |
|-------------|------|
| `400` | query parameterها نامعتبر هستند. |
| `401` | Bearer token وجود ندارد یا نامعتبر است. |
| `403` | token معتبر است، اما scope کافی ندارد یا مربوط به Store اشتباه است. |
| `404` | resource پیدا نشد. |
| `429` | rate limit رد شده است. |
| `500` | server error رخ داده است. |

`DjangoClient` در Botkonak، خطاهای transient با statusهای `502`، `503` و `504` را برای requestهای GET دوباره retry می‌کند. این رفتار در `agents/shared/django_client/client.py` قرار دارد. Prestia نباید از این statusها برای auth failure استفاده کند.

## الگوی Warningها در responseهای aggregated

context bundle در Botkonak برای partial failureها شامل `warnings: []` است. این ساختار در `backend/catalog/context.py` تعریف شده است. اگر Prestia یک aggregated context endpoint ارائه کند، می‌تواند از همین الگو استفاده کند.

## شکل تنظیمات Brand Voice

Content Agent مقدار `store_context.settings.brand_voice` را از `agents/content/brand_voice.py` می‌خواند:

</div>

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

<div dir="rtl" align="right">

store profile در Prestia باید تنظیمات معادل را expose کند. برای جزئیات بیشتر به [02-store-profile-apis.md](./02-store-profile-apis.md) مراجعه شود.

## شواهد از codebase

- `backend/catalog/models.py` — enumها و نام fieldها
- `backend/catalog/context.py` — کلیدهای سطح بالای context bundle
- `backend/catalog/pii.py` — قوانین PII redaction
- `agents/content/product_context.py` — aliasهای fieldها مانند `name`/`title` و `image`/`image_url`
- `agents/support/support_context.py` — aliasهای مربوط به message/thread fieldها
- `docs/phases/step-3.5.md` — نمونه‌ی JSON برای context bundle

## سؤال‌های باز

1. آیا Prestia از UUID استفاده می‌کند یا integer ID؟ Botkonak به‌صورت local از UUID استفاده می‌کند و connector باید mapping را انجام دهد.
2. rate limitهای استاندارد برای sync callها در مقایسه با interactive callها چیست؟
3. آیا Prestia قیمت‌ها را با رقم فارسی برمی‌گرداند؟ اگر بله، آیا قبل از import در Django به normalization نیاز داریم؟

</div>
