<div dir="rtl" align="right">

# APIهای Store Profile

APIهایی که برای دریافت هویت store، brand profile، settings و business metadata لازم هستند.

## API: دریافت Store Profile

| Property                               | Value                                                                                                                                                                                                                                                                                                                           |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | Get Store Profile                                                                                                                                                                                                                                                                                                               |
| **HTTP method**                        | `GET`                                                                                                                                                                                                                                                                                                                           |
| **مسیر endpoint پیشنهادی**             | `/v1/store`                                                                                                                                                                                                                                                                                                                     |
| **مصرف‌کننده در Botkonak**             | Coordinator Agent، Content Agent، Admin Dashboard، Background sync                                                                                                                                                                                                                                                              |
| **چرا Botkonak به این API نیاز دارد؟** | context bundle مربوط به daily report شامل metadataهای `tenant` و `store` است؛ مثل name، slug، timezone و currency. Content Agent از display name فروشگاه و `settings.brand_voice` برای تعیین tone در draft استفاده می‌کند. Sales summary هم از timezone فروشگاه برای تعیین مرزهای زمانی «today» و «last 7 days» استفاده می‌کند. |
| **نوع نیازمندی**                       | Direct                                                                                                                                                                                                                                                                                                                          |
| **Priority**                           | P0                                                                                                                                                                                                                                                                                                                              |

### Headerهای لازم برای request

</div>

```http
Authorization: Bearer <access_token>
Accept: application/json
```

<div dir="rtl" align="right">

### Query parameterها

ندارد. store scope از روی token برداشت می‌شود.

### Path parameterها

ندارد.

### Request body

قابل اعمال نیست.

### ساختار response موفق

</div>

```json
{
  "id": "22222222-2222-2222-2222-222222222222",
  "external_id": "prestia-store-main",
  "name": "Prestia Online Store",
  "slug": "main",
  "timezone": "Asia/Tehran",
  "currency": "IRR",
  "tenant": {
    "id": "11111111-1111-1111-1111-111111111111",
    "slug": "prestia",
    "name": "Prestia"
  },
  "settings": {
    "store_display_name": "پرستیا",
    "brand_voice": {
      "tone": "گرم و صمیمی",
      "audience": "خریداران آنلاین کیف و اکسسوری",
      "style_notes": "جملات کوتاه؛ ادعاهای واقعی درباره محصول",
      "language": "fa"
    },
    "content_agent_max_drafts_per_run": 3
  },
  "created_at": "2025-01-15T08:00:00+00:00",
  "updated_at": "2026-06-20T14:30:00+00:00"
}
```

<div dir="rtl" align="right">

### Fieldهای مهم

| Field                         | استفاده‌شده توسط                                                         |
| ----------------------------- | ------------------------------------------------------------------------ |
| `id`                          | Connector mapping به `Store.id` در Botkonak                              |
| `name`                        | Context bundle و content promptها                                        |
| `slug`                        | شناسایی store در scope مربوط به tenant                                   |
| `timezone`                    | مرزبندی periodهای فروش؛ مثل `get_period_bounds` در `catalog/services.py` |
| `currency`                    | قیمت productها و sales summary                                           |
| `tenant`                      | Multi-tenant scoping                                                     |
| `settings.brand_voice`        | Content Agent؛ فایل `agents/content/brand_voice.py`                      |
| `settings.store_display_name` | tenant seed از این key استفاده می‌کند؛ فایل `seed_prestia.py`            |

### Pagination

قابل اعمال نیست؛ این API یک single resource برمی‌گرداند.

### Filtering و sorting

قابل اعمال نیست.

### Error caseها

| Status | Condition                      |
| ------ | ------------------------------ |
| `401`  | token نامعتبر یا منقضی‌شده است |
| `403`  | token برای این store مجاز نیست |

### نکات امنیتی

- Settings ممکن است شامل marketing preferences باشد؛ اما نباید هیچ secret در این response قرار بگیرد.
- Store باید سمت server و از روی token تشخیص داده شود.

### نمونه request

</div>

```http
GET /v1/store HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

<div dir="rtl" align="right">

### نمونه response

به ساختار response موفق در بالا مراجعه کنید.

### فایل‌های مرتبط

- `backend/stores/models.py` — fieldهای مدل `Store`
- `backend/tenants/models.py` — مقدار `Tenant.settings`
- `backend/catalog/context.py` — وجود `tenant` و `store` در context bundle
- `backend/stores/serializers.py` — serializer به نام `StoreReadSerializer`
- `backend/stores/views.py` — endpoint مربوط به dashboard یعنی `GET /api/stores/{store_id}/`
- `agents/content/brand_voice.py` — استخراج brand voice
- `agents/coordinator/nodes.py` — مقدار `store_context` در تابع `_content_specialist_payload()`
- `backend/tenants/management/commands/seed_prestia.py` — مقدارهای پیش‌فرض tenant/store برای Prestia

---

## API: دریافت Tenant Settings، در صورت جداسازی اختیاری

| Property                               | Value                                                                                                                                                    |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | Get Tenant Settings                                                                                                                                      |
| **HTTP method**                        | `GET`                                                                                                                                                    |
| **مسیر endpoint پیشنهادی**             | `/v1/tenant`                                                                                                                                             |
| **مصرف‌کننده در Botkonak**             | Content Agent، Background sync                                                                                                                           |
| **چرا Botkonak به این API نیاز دارد؟** | مقدار `Tenant.settings` در seed data شامل `store_display_name` است. البته این اطلاعات می‌تواند به‌جای یک endpoint جداگانه، داخل store profile ادغام شود. |
| **نوع نیازمندی**                       | Inferred                                                                                                                                                 |
| **Priority**                           | P2                                                                                                                                                       |

اگر Prestia اطلاعات tenant و store را در `GET /v1/store` ترکیب کند، این endpoint لازم نیست.

### شواهد از codebase

- `backend/tenants/models.py` — فیلد JSONField به نام `Tenant.settings`
- `seed_prestia.py` — مقدار `settings: {"store_display_name": "Prestia"}`

### سؤال‌های باز

- آیا Prestia در data model خودش بین settings سطح tenant و settings سطح store تفاوت قائل می‌شود یا نه؟

## شواهد از codebase

در بخش مربوط به هر API در بالا آمده است.

## سؤال‌های باز

1. آیا Prestia مقدار `content_agent_max_drafts_per_run` را expose می‌کند یا Botkonak باید فقط از env default یعنی `CONTENT_AGENT_MAX_DRAFTS_PER_RUN` استفاده کند؟
2. timezone رسمی برای فروشگاه‌های ایرانی چیست؟ `Asia/Tehran` یا مقدار `America/New_York` که در seed آمده است؟

</div>
