<div dir="rtl" align="right">

# APIهای Order و Sales

APIهایی برای orders، sales metrics، revenue، best sellers و تحلیل فروش مبتنی بر زمان.

---

## API: دریافت Sales Summary

| Property                               | Value                                                                                                                                                                                                                                                                                                                          |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **نام API**                            | Get Sales Summary                                                                                                                                                                                                                                                                                                              |
| **HTTP method**                        | `GET`                                                                                                                                                                                                                                                                                                                          |
| **مسیر endpoint پیشنهادی**             | `/v1/sales/summary`                                                                                                                                                                                                                                                                                                            |
| **مصرف‌کننده در Botkonak**             | Sales Agent، Coordinator Agent، Background sync                                                                                                                                                                                                                                                                                |
| **چرا Botkonak به این API نیاز دارد؟** | این API ورودی اصلی برای sales analysis است. مقدارهای revenue، تعداد orderها، units sold، AOV و top products را برای **today** و **last 7 days** در timezone فروشگاه aggregate می‌کند. اگر sales خالی باشد، Sales Agent به‌صورت deterministic و بدون فراخوانی LLM، نتیجه empty برمی‌گرداند؛ فایل `agents/sales/empty_sales.py`. |
| **نوع نیازمندی**                       | Direct                                                                                                                                                                                                                                                                                                                         |
| **Priority**                           | P0                                                                                                                                                                                                                                                                                                                             |

### Headerهای لازم برای request

`Authorization: Bearer <access_token>`، `Accept: application/json`

### Query parameterها

| Parameter            | Type         | Required | Description                                                                                                                                      |
| -------------------- | ------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `reference_at`       | ISO datetime | No       | periodها را نسبت به این لحظه محاسبه می‌کند؛ مقدار پیش‌فرض: now. Botkonak در `build_sales_summary` از `timezone.now()` سمت server استفاده می‌کند. |
| `top_products_limit` | integer      | No       | مقدار پیش‌فرض `5` است — با `_serialize_period` هماهنگ است                                                                                        |

### Path parameterها

ندارد.

### Request body

قابل اعمال نیست.

### ساختار response موفق

</div>

```json
{
  "generated_at": "2026-06-25T14:30:00+00:00",
  "store_id": "22222222-2222-2222-2222-222222222222",
  "currency": "USD",
  "periods": {
    "today": {
      "from": "2026-06-25T04:00:00+00:00",
      "to": "2026-06-26T04:00:00+00:00",
      "total_revenue": "318.00",
      "order_count": 2,
      "units_sold": 4,
      "average_order_value": "159.00",
      "top_products": [
        {
          "product_id": "33333333-3333-3333-3333-333333333333",
          "name": "Milano Leather Tote",
          "sku": "PRS-TOTE-001",
          "quantity_sold": 1,
          "revenue": "189.00",
          "category": "Handbags"
        }
      ]
    },
    "last_7_days": {
      "from": "2026-06-19T04:00:00+00:00",
      "to": "2026-06-26T04:00:00+00:00",
      "total_revenue": "892.00",
      "order_count": 6,
      "units_sold": 12,
      "average_order_value": "148.67",
      "top_products": []
    }
  }
}
```

<div dir="rtl" align="right">

**نگاشت به context bundle:** در Botkonak مقدار `periods.today` به `sales_summary.today` و مقدار `periods.last_7_days` به `sales_summary.last_7_days` نگاشت می‌شود؛ فایل `backend/catalog/context.py`.

### Fieldهای مهم

| Field                 | Usage                                                                              |
| --------------------- | ---------------------------------------------------------------------------------- |
| `total_revenue`       | مجموع `total_amount` برای orderهایی که در محاسبه revenue حساب می‌شوند              |
| `order_count`         | تعداد orderهای قابل‌محاسبه در revenue در بازه زمانی موردنظر                        |
| `units_sold`          | مجموع `OrderItem.quantity`                                                         |
| `average_order_value` | برابر با `total_revenue / order_count`؛ اگر order وجود نداشته باشد، مقدار 0        |
| `top_products`        | best sellers بر اساس revenue و سپس quantity — برای signalهای discount و slow-mover |

### وضعیت‌های Order قابل‌محاسبه در Revenue

فقط orderهایی با statusهای `paid`، `completed` یا `fulfilled` در محاسبه revenue حساب می‌شوند؛ مقدار `REVENUE_COUNTABLE_ORDER_STATUSES` در `catalog/models.py`.

### Pagination

فهرست `top_products` محدود است؛ مقدار پیش‌فرض 5 محصول برای هر period.

### Error caseها

`401`، `403`، `500`

### نمونه request

</div>

```http
GET /v1/sales/summary?top_products_limit=5 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

<div dir="rtl" align="right">

### فایل‌های مرتبط

- `backend/catalog/services.py` — توابع `build_sales_summary`، `_serialize_period` و `get_period_bounds`
- `backend/catalog/internal_views.py` — کلاس `InternalSalesSummaryView`
- `agents/sales/django_fetch.py` — تابع `get_sales_summary`
- `agents/sales/empty_sales.py` — تشخیص empty بودن sales
- `agents/sales/inventory_signals.py` — cross-reference کردن top products با inventory
- `docs/phases/step-3.2.md`

---

## API: دریافت فهرست Orders

| Property                               | Value                                                                                                                                                                                                                                  |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | List Orders                                                                                                                                                                                                                            |
| **HTTP method**                        | `GET`                                                                                                                                                                                                                                  |
| **مسیر endpoint پیشنهادی**             | `/v1/orders`                                                                                                                                                                                                                           |
| **مصرف‌کننده در Botkonak**             | Background sync                                                                                                                                                                                                                        |
| **چرا Botkonak به این API نیاز دارد؟** | Botkonak می‌تواند sales summary را به‌صورت local از rowهای `Order` و `OrderItem` محاسبه کند. اگر Prestia summary از پیش aggregate‌شده ارائه نکند، یا برای reconciliation، connector به order data نیاز دارد تا Django را populate کند. |
| **نوع نیازمندی**                       | Inferred                                                                                                                                                                                                                               |
| **Priority**                           | P1                                                                                                                                                                                                                                     |

### Query parameterها

| Parameter                       | Description                          |
| ------------------------------- | ------------------------------------ |
| `status`                        | filter بر اساس order status          |
| `placed_at_gte`, `placed_at_lt` | بازه زمانی؛ آگاه از timezone فروشگاه |
| `updated_since`                 | برای incremental sync                |
| `limit`, `offset`               | برای pagination                      |

### ساختار response موفق

</div>

```json
{
  "count": 8,
  "results": [
    {
      "id": "88888888-8888-8888-8888-888888888888",
      "external_id": "prestia-ord-001",
      "order_number": "PRS-ORD-001",
      "status": "paid",
      "currency": "USD",
      "subtotal_amount": "247.00",
      "discount_amount": "0.00",
      "total_amount": "247.00",
      "placed_at": "2026-06-25T14:00:00+00:00",
      "external_customer_ref": "demo-cust-001",
      "items": [
        {
          "product_id": "33333333-3333-3333-3333-333333333333",
          "product_name_snapshot": "Milano Leather Tote",
          "sku_snapshot": "PRS-TOTE-001",
          "quantity": 1,
          "unit_price": "189.00",
          "line_total": "189.00"
        }
      ],
      "metadata": {},
      "created_at": "2026-06-25T14:00:00+00:00",
      "updated_at": "2026-06-25T14:05:00+00:00"
    }
  ]
}
```

<div dir="rtl" align="right">

### Fieldهای مهم

این fieldها به مدل‌های `Order` و `OrderItem` در `backend/catalog/models.py` نگاشت می‌شوند.

### فایل‌های مرتبط

- `backend/catalog/models.py` — مدل‌های `Order`، `OrderItem` و `OrderStatus`
- `seed_prestia.py` — مقدار `PRESTIA_ORDERS`

---

## API: دریافت جزئیات Order

| Property                               | Value                                                                                                                                                                                                                 |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | Get Order Detail                                                                                                                                                                                                      |
| **HTTP method**                        | `GET`                                                                                                                                                                                                                 |
| **مسیر endpoint پیشنهادی**             | `/v1/orders/{order_id}`                                                                                                                                                                                               |
| **مصرف‌کننده در Botkonak**             | Support Agent                                                                                                                                                                                                         |
| **چرا Botkonak به این API نیاز دارد؟** | support threadها به order numberها اشاره می‌کنند؛ برای مثال `PRS-ORD-001` در seed messageها. Agent در حال حاضر جزئیات order را fetch نمی‌کند، اما ممکن است برای پاسخ‌های مربوط به order status به آن نیاز داشته باشد. |
| **نوع نیازمندی**                       | Inferred                                                                                                                                                                                                              |
| **Priority**                           | P2                                                                                                                                                                                                                    |

### Path parameterها

`order_id` — مقدار UUID مربوط به order در Prestia یا lookup بر اساس `order_number`؛ تعریف دقیق آن با Prestia است.

### Response موفق

یک object مربوط به order، همراه با آرایه `items`.

### فایل‌های مرتبط

- `seed_prestia.py` — پیام `prestia-thread-order-followup` به `PRS-ORD-001` اشاره می‌کند
- `agents/support/refusal.py` — requestهای مربوط به mutation روی order رد می‌شوند؛ البته دسترسی read-only همچنان مفید است

---

## Abandoned / pending orders

| Property                               | Value                                                                                                                                                                                                                                                                                                                           |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | List Draft or Pending Orders                                                                                                                                                                                                                                                                                                    |
| **HTTP method**                        | `GET`                                                                                                                                                                                                                                                                                                                           |
| **مسیر endpoint پیشنهادی**             | `/v1/orders?status=draft,pending`                                                                                                                                                                                                                                                                                               |
| **مصرف‌کننده در Botkonak**             | Sales Agent                                                                                                                                                                                                                                                                                                                     |
| **چرا Botkonak به این API نیاز دارد؟** | Mock UI موردی با عنوان abandoned cart follow-up را نشان می‌دهد؛ فایل `frontend/types/mock-data.ts`. **هیچ backend implementation** فعلی از abandoned-cart data استفاده نمی‌کند. action type مربوط به `sales.follow_up` در Sales Agent وجود دارد، اما فقط از context مربوط به sales/inventory و به‌صورت LLM-driven تولید می‌شود. |
| **نوع نیازمندی**                       | Optional (Future)                                                                                                                                                                                                                                                                                                               |
| **Priority**                           | Future                                                                                                                                                                                                                                                                                                                          |

---

## Slow movers و discount candidates

در کد فعلی، هیچ API اختصاصی از Prestia برای این مورد لازم نیست. Sales Agent موارد زیر را infer می‌کند:

- **Discount candidates** — از روی sales velocity پایین در `top_products` به‌همراه inventory signals؛ فایل‌های `agents/sales/inventory_signals.py` و `agents/sales/prompts.py`
- **Slow movers** — تفسیر LLM از sales summary؛ نه یک API جداگانه

**نوع نیازمندی:** Optional — یک endpoint تحلیلی pre-computed می‌تواند در آینده یا با Priority برابر Future/P2 اضافه شود.

---

## شواهد از codebase

به بخش مربوط به هر API مراجعه کنید.

## سؤال‌های باز

1. آیا Prestia مقدار aggregate‌شده `GET /sales/summary` را ارائه می‌کند یا Botkonak باید آن را از raw orders محاسبه کند؟
2. آیا abandoned cart data در Prestia در دسترس است؟
3. نگاشت order statusهای native در Prestia به enum مربوط به Botkonak چگونه است؟

</div>
