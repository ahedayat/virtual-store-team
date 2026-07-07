<div dir="rtl" align="right">

# APIهای Order و Sales

APIها برای orders و داده خام sales. **خلاصه sales، پرفروش‌ها، insightهای low-stock، کاندیدهای discount و sales recommendation توسط Sales Agent Botkonak** از orders و داده product/inventory محاسبه می‌شوند — Prestia API خلاصه sales expose نمی‌کند.

---

## API: List Orders

| Property | Value |
|----------|-------|
| **API name** | List Orders |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/orders` |
| **Botkonak consumer** | Sales Agent، Coordinator Agent، on-demand fetch |
| **Why Botkonak needs this** | Botkonak sales summary، پرفروش‌ها و سیگنال recommendation را از `Order` + line itemها به‌صورت local محاسبه می‌کند (`backend/catalog/services.py`). داده خام order منبع حقیقت Prestia برای تحلیل sales است. |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Headerهای لازم برای request

`Authorization: Bearer <access_token>`، `Accept: application/json`

### Query parameterها — pagination

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | Yes | اندازه صفحه (پیش‌فرض 50، حداکثر 100) |
| `offset` | integer | Yes | offset pagination (پیش‌فرض 0) |

### Query parameterها — filter

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `created_at_from` | datetime | No | شروع بازه تاریخ order (شامل) |
| `created_at_to` | datetime | No | پایان بازه تاریخ order (شامل) |
| `customer_id` | string | No | filter بر اساس customer |
| `product_slug` | string | No | orderهای حاوی این product |
| `total_min` | number | No | حداقل `total` order (شامل) |
| `total_max` | number | No | حداکثر `total` order (شامل) |
| `status` | string | No | filter بر اساس وضعیت order |

### Path parameterها

هیچ.

### Request body

قابل اعمال نیست.

### شکل successful response

<div dir="ltr" align="left">

```json
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "order_id": "PRS-ORD-001",
      "status": "paid",
      "currency": "USD",
      "subtotal": 247.00,
      "discount_amount": 0.00,
      "tax": 0.00,
      "shipping_price": 0.00,
      "total": 247.00,
      "customer_id": "66666666-6666-6666-6666-666666666666",
      "items": [
        {
          "product_slug": "milano-leather-tote",
          "product_name": "Milano Leather Tote",
          "quantity": 1,
          "unit_price": 189.00,
          "line_total": 189.00
        }
      ],
      "metadata": {},
      "created_at": "2026-06-25T14:00:00+00:00",
      "updated_at": "2026-06-25T14:05:00+00:00"
    }
  ]
}
```

</div>

### تعریف fieldها

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | string | شناسه پایدار order |
| `status` | string | وضعیت order (map به Botkonak `OrderStatus` — [01-shared-data-contracts.md](./01-shared-data-contracts.md)) |
| `currency` | string | کد ISO 4217 |
| `subtotal` | number | subtotal قبل از discount |
| `discount_amount` | number | مجموع discountهای اعمال‌شده |
| `tax` | number | مبلغ tax |
| `shipping_price` | number | هزینه shipping |
| `total` | number | total نهایی order |
| `customer_id` | string | map به customer record متناظر |
| `items` | array | line itemها (لیست object) |
| `items[].product_slug` | string | product slug |
| `items[].product_name` | string | نام product در زمان order |
| `items[].quantity` | integer | تعداد سفارش‌داده‌شده |
| `items[].unit_price` | number | قیمت واحد |
| `items[].line_total` | number | total خط |
| `metadata` | object | اطلاعات اضافی سطح order |
| `created_at` | datetime | زمان ایجاد order |
| `updated_at` | datetime | زمان آخرین به‌روزرسانی |

### وضعیت‌های order قابل‌شمارش در revenue

فقط orderهای با وضعیت `paid`، `completed` یا `fulfilled` در sales summary Botkonak شمارش می‌شوند (`REVENUE_COUNTABLE_ORDER_STATUSES` در `catalog/models.py`).

### Pagination

الزامی: `limit` و `offset`.

### Error caseها

`401`، `403`، `429`، `500`

### نمونه request

<div dir="ltr" align="left">

```http
GET /v1/orders?limit=50&offset=0&created_at_from=2026-06-01T00:00:00+00:00&created_at_to=2026-06-30T23:59:59+00:00&status=paid HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

</div>

### فایل‌های مرتبط

- `backend/catalog/models.py` — `Order`، `OrderItem`، `OrderStatus`
- `backend/catalog/services.py` — `build_sales_summary`
- `agents/sales/django_fetch.py` — `get_sales_summary`
- `seed_prestia.py` — `PRESTIA_ORDERS`

---

## API: Get Order Detail

| Property | Value |
|----------|-------|
| **API name** | Get Order Detail |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/orders/{order_id}` |
| **Botkonak consumer** | Support Agent |
| **Why Botkonak needs this** | threadهای support به شماره order ارجاع می‌دهند (مثلاً `PRS-ORD-001` در messageهای seed). agent ممکن است برای پاسخ وضعیت order به جزئیات نیاز داشته باشد. |
| **Requirement type** | Inferred |
| **Priority** | P2 |

### Path parameterها

| Name | Type | Description |
|------|------|-------------|
| `order_id` | string | شناسه order در Prestia |

### Successful response

یک object order — **همان schema یک آیتم از `GET /v1/orders`**.

### فایل‌های مرتبط

- `seed_prestia.py` — message در `prestia-thread-order-followup` به `PRS-ORD-001` ارجاع می‌دهد
- `agents/support/refusal.py` — درخواست mutation order رد می‌شود (read-only همچنان مفید است)

---

## تحلیل sales (مسئولیت Botkonak)

Prestia **`GET /v1/sales/summary` یا endpointهای sales از پیش aggregate‌شده** expose نمی‌کند.

Sales Agent Botkonak موارد زیر را از `GET /v1/orders` و `GET /v1/products` استخراج می‌کند:

| Insight | Source |
|---------|--------|
| Sales summary (امروز، ۷ روز گذشته) | aggregate از orders در timezone فروشگاه |
| پرفروش‌ترین productها | line itemهای order گروه‌بندی‌شده بر اساس `product_slug` |
| insightهای low-stock | `inventories[].num` product با sales velocity |
| کاندیدهای discount | تفسیر LLM از روند sales + inventory (`agents/sales/inventory_signals.py`) |
| slow moverها | تفسیر LLM از sales velocity ضعیف |

---

## orderهای رها‌شده / pending

| Property | Value |
|----------|-------|
| **API name** | List Draft or Pending Orders |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/orders?status=draft,pending` |
| **Botkonak consumer** | Sales Agent |
| **Why Botkonak needs this** | UI mock پیگیری «سبد رها‌شده» را نشان می‌دهد (`frontend/types/mock-data.ts`). **هیچ پیاده‌سازی backend** امروز از داده abandoned-cart استفاده نمی‌کند. |
| **Requirement type** | Optional (Future) |
| **Priority** | Future |

---

## شواهد از codebase

به بخش per-API مراجعه کنید.

## سؤال‌های باز

1. در دسترس بودن داده abandoned cart در Prestia.
2. mapping وضعیت order از وضعیت‌های native Prestia به enum Botkonak.
3. آیا `order_id` human-readable است (`PRS-ORD-001`) یا UUID — connector باید به `external_id` map کند.

</div>
