<div dir="rtl" align="right">

# APIهای Customer

APIها برای اطلاعات customer و order history.

## ارزیابی نیاز فعلی Botkonak

داده customer در Botkonak وجود دارد (`backend/catalog/models.py` — `Customer`) و برای demoهای support Prestia seed شده است. Support Agent یک **CRM سطح tenant** در Botkonak نگه می‌دارد که customerها را از website، Instagram، Telegram و کانال‌های آینده یکپارچه می‌کند.

- **APIهای AI-facing هرگز PII خام expose نمی‌کنند** — messageها از `customer_ref` مبهم استفاده می‌کنند (`catalog/pii.py`)
- **Sales Agent** صراحتاً از PII customer در promptها اجتناب می‌کند (`agents/sales/prompts.py`)
- customer recordهای sync‌شده از Prestia context CRM Botkonak را تکمیل می‌کنند

---

## API: List Customers

| Property | Value |
|----------|-------|
| **API name** | List Customers |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/customers` |
| **Botkonak consumer** | Support Agent CRM، on-demand fetch |
| **Why Botkonak needs this** | پر کردن و reconcile ردیف‌های `Customer` در دیتابیس tenant Botkonak. `platform` + `platform_user_id` را به threadهای support وصل می‌کند. |
| **Requirement type** | Direct |
| **Priority** | P1 |

### Headerهای لازم برای request

`Authorization: Bearer <access_token>`، `Accept: application/json`

### Query parameterها — pagination

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | Yes | اندازه صفحه (پیش‌فرض 50، حداکثر 100) |
| `offset` | integer | Yes | offset pagination (پیش‌فرض 0) |

### Query parameterها — filter و search

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `platform` | string | No | filter بر اساس platform منبع (مثلاً `website`، `instagram`، `telegram`) |
| `search` | string | No | جستجو بر اساس `phone`، `email` یا `display_name` |

### شکل successful response

<div dir="ltr" align="left">

```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "botkonak_customer_id": "bk-cust-001",
      "tenant_user_id": "prestia-cust-001",
      "display_name": "Sara Jamali",
      "email": "sara.jamali@example.com",
      "phone": "09121234567",
      "platform": "instagram",
      "platform_user_id": "ig-prestia-001",
      "metadata": {},
      "created_at": "2025-06-01T10:00:00+00:00",
      "updated_at": "2026-06-20T12:00:00+00:00"
    }
  ]
}
```

</div>

### تعریف fieldها

| Field | Type | Description |
|-------|------|-------------|
| `botkonak_customer_id` | string | شناسه customer اختصاص‌داده‌شده Botkonak هنگام link |
| `tenant_user_id` | string | شناسه customer در scope tenant Prestia |
| `display_name` | string | نام نمایشی customer |
| `email` | string \| null | آدرس email |
| `phone` | string \| null | شماره تلفن |
| `platform` | string | platform منبع — `website`، `instagram`، `telegram` و غیره |
| `platform_user_id` | string \| null | شناسه customer در platform خارجی در صورت وجود |
| `metadata` | object | اطلاعات اضافی سطح customer |
| `created_at` | datetime | زمان ایجاد record |
| `updated_at` | datetime | زمان آخرین به‌روزرسانی |

### fieldهای مهم — mapping Botkonak

| Field | Botkonak model field | AI exposure |
|-------|---------------------|-------------|
| `platform` | `Customer.platform` | فقط metadata thread |
| `platform_user_id` | `Customer.platform_user_id` | در AI APIها نیست |
| `display_name`، `email`، `phone` | همان | **فقط Admin** — در مسیر agent redact می‌شود |

### نکات امنیتی

- Botkonak **نباید** email/phone را به agentها forward کند.
- PII در Django/Postgres ذخیره می‌شود؛ AI APIها فقط body message را sanitize می‌کنند.

### نمونه request

<div dir="ltr" align="left">

```http
GET /v1/customers?limit=50&offset=0&platform=instagram&search=sara HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

</div>

### فایل‌های مرتبط

- `backend/catalog/models.py` — `Customer`
- `seed_prestia.py` — `PRESTIA_CUSTOMERS`
- `backend/catalog/management/commands/import_messages_json.py` — import customer

---

## API: Get Customer Order History

| Property | Value |
|----------|-------|
| **API name** | Get Customer Order History |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/customer/{tenant_customer_id}/orders` |
| **Botkonak consumer** | Support Agent، Sales Agent، Admin Dashboard |
| **Why Botkonak needs this** | order history برای customer مشخص. پاسخ support و sales follow-up ممکن است به خریدهای گذشته ارجاع دهد. |
| **Requirement type** | Inferred |
| **Priority** | P1 |

### Path parameterها

| Name | Type | Description |
|------|------|-------------|
| `tenant_customer_id` | string | شناسه customer در scope tenant Prestia (`tenant_user_id`) |

### Query parameterها

همان pagination و filterهای [List Orders](./04-order-and-sales-apis.md):

- `limit`، `offset`
- `created_at_from`، `created_at_to`
- `customer_id` (وقتی با path scope شده redundant است — اختیاری)
- `product_slug`
- `total_min`، `total_max`
- `status`

### Successful response

لیست paginated از objectهای order — **همان schema `GET /v1/orders`**.

### فایل‌های مرتبط

- `frontend/types/mock-data.ts` — payload follow-up در `mockRecommendations`
- `agents/shared/schemas/sales.py` — نوع action `sales.follow_up`

---

## segmentation / analytics مشتری

**در کد موجود لازم نیست.** هیچ model یا API segmentation در Botkonak وجود ندارد.

**Requirement type:** Optional (Future)

---

## شواهد از codebase

- `backend/catalog/models.py` — `Customer` با constraint یکتا per platform
- `backend/catalog/pii.py` — PII به AI export نمی‌شود
- `docs/phases/step-3.4.md` — منطق model customer
- `frontend/hooks/use-customers.ts` — فقط mock data

## سؤال‌های باز

1. آیا Prestia `platform_user_id` Instagram را برای customerهای DM expose می‌کند.
2. GDPR/consent برای ذخیره PII customer در Botkonak پس از sync.
3. mapping بین `tenant_user_id` و `botkonak_customer_id` در onboarding.

</div>
