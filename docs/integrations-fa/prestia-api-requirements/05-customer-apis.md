<div dir="rtl" align="right">

# APIهای Customer

APIهایی برای customer information، order history و segmentation.

## ارزیابی نیاز فعلی Botkonak

Customer data در Botkonak وجود دارد؛ فایل `backend/catalog/models.py` و مدل `Customer`. همچنین برای demoهای support مربوط به Prestia، داده customer به‌صورت seed اضافه شده است. با این حال:

- **APIهایی که در مسیر AI استفاده می‌شوند، هرگز raw PII را expose نمی‌کنند** — messageها از `customer_ref` مبهم استفاده می‌کنند؛ فایل `catalog/pii.py`.
- **Sales Agent** به‌صورت صریح از قرار دادن customer PII در promptها پرهیز می‌کند؛ فایل `agents/sales/prompts.py`.
- **Frontend** فقط از mock customerها استفاده می‌کند؛ فایل `frontend/hooks/use-customers.ts`.
- **هیچ کد customer analytics یا segmentation** وجود ندارد.

بنابراین Customer APIها در درجه اول برای **background sync** لازم هستند؛ یعنی برای پر کردن rowهای مربوط به `Customer` که به message threadها وصل می‌شوند، نه برای مصرف مستقیم توسط agentها.

---

## API: دریافت فهرست Customers

| Property                               | Value                                                                                                                                                          |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | List Customers                                                                                                                                                 |
| **HTTP method**                        | `GET`                                                                                                                                                          |
| **مسیر endpoint پیشنهادی**             | `/v1/customers`                                                                                                                                                |
| **مصرف‌کننده در Botkonak**             | Background sync                                                                                                                                                |
| **چرا Botkonak به این API نیاز دارد؟** | هنگام import کردن support threadها، برای populate کردن `Customer` استفاده می‌شود. این API مقدارهای `platform` و `platform_user_id` را به threadها link می‌کند. |
| **نوع نیازمندی**                       | Inferred                                                                                                                                                       |
| **Priority**                           | P2                                                                                                                                                             |

### Headerهای لازم برای request

`Authorization: Bearer <access_token>`، `Accept: application/json`

### Query parameterها

| Parameter         | Description           |
| ----------------- | --------------------- |
| `platform`        | برای مثال `instagram` |
| `updated_since`   | برای incremental sync |
| `limit`, `offset` | برای pagination       |

### ساختار response موفق

</div>

```json
{
  "count": 5,
  "results": [
    {
      "id": "66666666-6666-6666-6666-666666666666",
      "external_id": "ig-prestia-001",
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

<div dir="rtl" align="right">

### Fieldهای مهم

| Field                            | فیلد متناظر در مدل Botkonak | نمایش در مسیر AI                                   |
| -------------------------------- | --------------------------- | -------------------------------------------------- |
| `platform`                       | `Customer.platform`         | فقط thread metadata                                |
| `platform_user_id`               | `Customer.platform_user_id` | در AI APIها نمی‌آید                                |
| `display_name`, `email`, `phone` | همان fieldها                | **فقط Admin** — در مسیرهای agentها redacted می‌شود |

### نکات امنیتی

- Botkonak **نباید** email یا phone را به agentها forward کند.
- عملیات sync مقدارهای PII را در Django/Postgres ذخیره می‌کند؛ اما AI APIها فقط message bodyها را sanitize می‌کنند.

### فایل‌های مرتبط

- `backend/catalog/models.py` — مدل `Customer`
- `seed_prestia.py` — مقدار `PRESTIA_CUSTOMERS`
- `backend/catalog/management/commands/import_messages_json.py` — import کردن customer

---

## API: دریافت Order History مربوط به Customer

| Property                               | Value                                                                                                                                                                                    |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | Get Customer Order History                                                                                                                                                               |
| **HTTP method**                        | `GET`                                                                                                                                                                                    |
| **مسیر endpoint پیشنهادی**             | `/v1/customers/{customer_id}/orders`                                                                                                                                                     |
| **مصرف‌کننده در Botkonak**             | Sales Agent در آینده، Admin Dashboard                                                                                                                                                    |
| **چرا Botkonak به این API نیاز دارد؟** | Mock UI مربوط به `sales.follow_up` به purchase history مشتری VIP اشاره می‌کند؛ فایل `frontend/types/mock-data.ts`. این قابلیت در backend logic فعلی Sales Agent **پیاده‌سازی نشده است**. |
| **نوع نیازمندی**                       | Optional (Future)                                                                                                                                                                        |
| **Priority**                           | Future                                                                                                                                                                                   |

### Response موفق

یک paginated list از objectهای خلاصه order؛ بدون PII فراتر از opaque customer ref.

### فایل‌های مرتبط

- `frontend/types/mock-data.ts` — مقدار `mockRecommendations` برای follow-up payload
- `agents/shared/schemas/sales.py` — action type به نام `sales.follow_up`

---

## Customer segmentation / analytics

در کد موجود **لازم نیست**. هیچ segmentation model یا API مربوط به segmentation در Botkonak وجود ندارد.

**نوع نیازمندی:** Optional (Future)

---

## شواهد از codebase

- `backend/catalog/models.py` — مدل `Customer` همراه با platform-scoped unique constraint
- `backend/catalog/pii.py` — PII به AI export نمی‌شود
- `docs/phases/step-3.4.md` — rationale مربوط به customer model
- `frontend/hooks/use-customers.ts` — فقط mock data

## سؤال‌های باز

1. آیا Prestia برای customerهای DM در Instagram مقدار `platform_user_id` را expose می‌کند؟
2. وضعیت GDPR/consent برای ذخیره customer PII در Botkonak بعد از sync چگونه است؟
3. آیا flagهای VIP یا repeat-buyer در سمت Prestia وجود دارد تا در آینده برای `sales.follow_up` استفاده شود؟

</div>
