<div dir="rtl" align="right">

# APIهای Product و Inventory

APIهایی برای products، categories، variants، prices، images، inventory، stock status و product metadata.

---

## API: دریافت فهرست Products

| Property                               | Value                                                                                                                                                                                                                                   |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | List Products                                                                                                                                                                                                                           |
| **HTTP method**                        | `GET`                                                                                                                                                                                                                                   |
| **مسیر endpoint پیشنهادی**             | `/v1/products`                                                                                                                                                                                                                          |
| **مصرف‌کننده در Botkonak**             | Content Agent، Coordinator Agent، Background sync                                                                                                                                                                                       |
| **چرا Botkonak به این API نیاز دارد؟** | بخش `products.items` در context bundle مبنای تولید content draftهاست. اگر products خالی باشند، خروجی Content Agent به‌صورت deterministic و بدون فراخوانی LLM، نتیجه empty content برمی‌گرداند؛ فایل `agents/content/empty_products.py`. |
| **نوع نیازمندی**                       | Direct                                                                                                                                                                                                                                  |
| **Priority**                           | P0                                                                                                                                                                                                                                      |

### Headerهای لازم برای request

`Authorization: Bearer <access_token>`، `Accept: application/json`

### Query parameterها

| Parameter       | Type         | Required | Description                                                                      |
| --------------- | ------------ | -------- | -------------------------------------------------------------------------------- |
| `is_active`     | boolean      | No       | مقدار پیش‌فرض `true` است — با filter موجود در `build_product_summary` هماهنگ است |
| `limit`         | integer      | No       | برای pagination؛ مقدار پیش‌فرض 50 و حداکثر 100                                   |
| `offset`        | integer      | No       | offset مربوط به pagination                                                       |
| `updated_since` | ISO datetime | No       | برای incremental sync                                                            |
| `category_slug` | string       | No       | filter بر اساس category                                                          |

### Path parameterها

ندارد.

### Request body

قابل اعمال نیست.

### ساختار response موفق

</div>

```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "33333333-3333-3333-3333-333333333333",
      "external_id": "prestia-prod-milano-tote",
      "name": "کیف چرم میلانو",
      "title": "کیف چرم میلانو",
      "slug": "milano-leather-tote",
      "sku": "PRS-TOTE-001",
      "description": "کیف چرم تمام‌گرین با جیب زیپ داخلی.",
      "price": "189.00",
      "compare_at_price": "219.00",
      "discount_percent": null,
      "currency": "USD",
      "image_url": "https://cdn.prestia.ir/products/milano-tote.jpg",
      "images": ["https://cdn.prestia.ir/products/milano-tote.jpg"],
      "is_active": true,
      "category": {
        "id": "44444444-4444-4444-4444-444444444444",
        "name": "Handbags",
        "slug": "handbags"
      },
      "metadata": {
        "material": "leather",
        "color": "cognac"
      },
      "created_at": "2025-03-01T10:00:00+00:00",
      "updated_at": "2026-06-18T09:00:00+00:00"
    }
  ]
}
```

<div dir="rtl" align="right">

### Fieldهای مهم

| Field                  | نگاشت در Botkonak                    | کاربرد در Agent                                                                              |
| ---------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------- |
| `id`                   | مقدار `product_id` در context bundle | مقدار `product_id` در content draftها                                                        |
| `name` / `title`       | مقدار `name`                         | promptها و captionها                                                                         |
| `sku`                  | مقدار `sku`                          | payload مربوط به sales recommendationها                                                      |
| `description`          | مقدار `Product.description`          | draftهای product description؛ Inferred — در context bundle فعلی وجود ندارد، اما در model هست |
| `price`, `currency`    | fieldهای context item                | اشاره به قیمت در caption                                                                     |
| `image_url` / `images` | مقدار `image_url`                    | تابع `normalize_product` در Content Agent                                                    |
| `category`             | nested object                        | context مربوط به category در promptها                                                        |
| `metadata`             | مقدار JSON به نام `metadata`         | guardrail برای ادعاهای مربوط به material/color                                               |
| `is_active`            | filter                               | فقط productهای active وارد AI bundle می‌شوند                                                 |

### Pagination

می‌تواند به‌صورت offset/limit یا cursor باشد. Connector باید برای داشتن context کامل، همه productهای active را fetch کند.

### Filtering و sorting

- مقدار پیش‌فرض: `is_active=true`، مرتب‌سازی بر اساس `name` به‌صورت ascending.

### Error caseها

`401`، `403`، `429`، `500`

### نکات امنیتی

- داده‌های public catalog هستند؛ customer PII در این API وجود ندارد.

### نمونه request

</div>

```http
GET /v1/products?is_active=true&limit=100 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

<div dir="rtl" align="right">

### فایل‌های مرتبط

- `backend/catalog/models.py` — مدل‌های `Product` و `Category`
- `backend/catalog/context.py` — توابع `_serialize_product_summary` و `build_product_summary`
- `agents/content/product_context.py` — توابع `normalize_product` و `extract_products`
- `backend/tenants/management/commands/seed_prestia.py` — مقدار `PRESTIA_PRODUCTS`

---

## API: دریافت جزئیات Product

| Property                               | Value                                                                                                                                         |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | Get Product Detail                                                                                                                            |
| **HTTP method**                        | `GET`                                                                                                                                         |
| **مسیر endpoint پیشنهادی**             | `/v1/products/{product_id}`                                                                                                                   |
| **مصرف‌کننده در Botkonak**             | Content Agent، Admin Dashboard                                                                                                                |
| **چرا Botkonak به این API نیاز دارد؟** | برای workflowهای content تک‌محصولی، به `description` کامل و مجموعه images نیاز است. endpoint فهرست ممکن است descriptionهای طولانی را حذف کند. |
| **نوع نیازمندی**                       | Inferred                                                                                                                                      |
| **Priority**                           | P2                                                                                                                                            |

### Path parameterها

| Name         | Type          | Description              |
| ------------ | ------------- | ------------------------ |
| `product_id` | string (UUID) | شناسه product در Prestia |

### Response موفق

یک object مربوط به product، با همان ساختاری که itemهای list دارند.

### فایل‌های مرتبط

- `backend/catalog/models.py` — فیلدهای `Product.description` و `Product.image_url`
- `frontend/hooks/use-products.ts` — product picker به‌صورت mock، برای real API آینده

---

## API: دریافت فهرست Categories

| Property                               | Value                                                                                                                                                                  |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | List Categories                                                                                                                                                        |
| **HTTP method**                        | `GET`                                                                                                                                                                  |
| **مسیر endpoint پیشنهادی**             | `/v1/categories`                                                                                                                                                       |
| **مصرف‌کننده در Botkonak**             | Background sync، Content Agent                                                                                                                                         |
| **چرا Botkonak به این API نیاز دارد؟** | در حال حاضر categories داخل product list به‌صورت embedded آمده‌اند. داشتن endpoint جداگانه کمک می‌کند قبل از sync کردن products، rowهای مربوط به `Category` sync شوند. |
| **نوع نیازمندی**                       | Inferred                                                                                                                                                               |
| **Priority**                           | P1                                                                                                                                                                     |

### Query parameterها

`is_active`، `limit`، `offset`

### ساختار response موفق

</div>

```json
{
  "count": 5,
  "results": [
    {
      "id": "44444444-4444-4444-4444-444444444444",
      "name": "Handbags",
      "slug": "handbags",
      "description": "Structured handbags for everyday use.",
      "is_active": true,
      "metadata": {}
    }
  ]
}
```

<div dir="rtl" align="right">

### فایل‌های مرتبط

- `backend/catalog/models.py` — مدل `Category`
- `seed_prestia.py` — مقدار `PRESTIA_CATEGORIES`

---

## API: دریافت فهرست Inventory Levels

| Property                               | Value                                                                                                                                                |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | List Inventory Levels                                                                                                                                |
| **HTTP method**                        | `GET`                                                                                                                                                |
| **مسیر endpoint پیشنهادی**             | `/v1/inventory`                                                                                                                                      |
| **مصرف‌کننده در Botkonak**             | Background sync، Sales Agent                                                                                                                         |
| **چرا Botkonak به این API نیاز دارد؟** | برای پر کردن `InventoryLevel` و محاسبه low-stock استفاده می‌شود. اگر endpoint مربوط به low-stock تنها source نباشد، این API برای sync دقیق لازم است. |
| **نوع نیازمندی**                       | Inferred                                                                                                                                             |
| **Priority**                           | P1                                                                                                                                                   |

### Query parameterها

| Parameter         | Description           |
| ----------------- | --------------------- |
| `updated_since`   | برای incremental sync |
| `is_active`       | مقدار پیش‌فرض `true`  |
| `limit`, `offset` | برای pagination       |

### ساختار response موفق

</div>

```json
{
  "count": 10,
  "results": [
    {
      "product_id": "33333333-3333-3333-3333-333333333333",
      "sku": "PRS-TOTE-001",
      "quantity_on_hand": 5,
      "reserved_quantity": 2,
      "available_quantity": 3,
      "low_stock_threshold": 10,
      "reorder_target": 25,
      "location_name": "Main Floor",
      "is_active": true,
      "updated_at": "2026-06-25T12:00:00+00:00",
      "metadata": {}
    }
  ]
}
```

<div dir="rtl" align="right">

### فایل‌های مرتبط

- `backend/catalog/models.py` — مدل `InventoryLevel`
- `seed_prestia.py` — مقدار `PRESTIA_INVENTORY`

---

## API: دریافت Inventory با وضعیت Low Stock

| Property                               | Value                                                                                                                                                                                                               |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **نام API**                            | Get Low Stock Inventory                                                                                                                                                                                             |
| **HTTP method**                        | `GET`                                                                                                                                                                                                               |
| **مسیر endpoint پیشنهادی**             | `/v1/inventory/low-stock`                                                                                                                                                                                           |
| **مصرف‌کننده در Botkonak**             | Sales Agent، Coordinator Agent، Background sync                                                                                                                                                                     |
| **چرا Botkonak به این API نیاز دارد؟** | برای restock recommendationهای Sales Agent استفاده می‌شود. همچنین بخش `inventory` در context bundle را تغذیه می‌کند. این API productهایی را برمی‌گرداند که در آن‌ها `available_quantity < low_stock_threshold` است. |
| **نوع نیازمندی**                       | Direct                                                                                                                                                                                                              |
| **Priority**                           | P0                                                                                                                                                                                                                  |

### Headerهای لازم برای request

`Authorization: Bearer <access_token>`، `Accept: application/json`

### Query parameterها

هیچ موردی الزامی نیست. به‌صورت اختیاری می‌توان از `limit` برای محدود کردن تعداد itemها استفاده کرد؛ البته Botkonak همه matchها را برمی‌گرداند.

### ساختار response موفق

</div>

```json
{
  "generated_at": "2026-06-25T14:30:00+00:00",
  "store_id": "22222222-2222-2222-2222-222222222222",
  "low_stock_count": 4,
  "items": [
    {
      "product_id": "33333333-3333-3333-3333-333333333333",
      "product_name": "Milano Leather Tote",
      "sku": "PRS-TOTE-001",
      "category": "Handbags",
      "quantity_on_hand": 5,
      "reserved_quantity": 2,
      "available_quantity": 3,
      "low_stock_threshold": 10,
      "shortage_units": 7,
      "reorder_target": 25,
      "suggested_reorder_quantity": 22,
      "last_updated": "2026-06-25T12:00:00+00:00"
    }
  ]
}
```

<div dir="rtl" align="right">

### Fieldهای مهم

| Field                        | Usage                                                                                       |
| ---------------------------- | ------------------------------------------------------------------------------------------- |
| `available_quantity`         | برابر با `quantity_on_hand - reserved_quantity`                                             |
| `shortage_units`             | برابر با `max(0, low_stock_threshold - available_quantity)`                                 |
| `suggested_reorder_quantity` | اگر `reorder_target` تنظیم شده باشد، برابر با `max(0, reorder_target - available_quantity)` |
| `sku`, `product_id`          | مقدارهای موردنیاز در `payload` مربوط به Sales recommendation                                |

### Pagination

اگر تعداد itemها محدود و قابل‌کنترل باشد، لازم نیست. استفاده از `limit` اختیاری است.

### Error caseها

`401`، `403`، `500`

### نمونه request

</div>

```http
GET /v1/inventory/low-stock HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

<div dir="rtl" align="right">

### فایل‌های مرتبط

- `backend/catalog/services.py` — توابع `build_low_stock_summary` و `_serialize_low_stock_item`
- `backend/catalog/internal_views.py` — کلاس `InternalLowStockInventoryView`
- `agents/sales/django_fetch.py` — تابع `get_low_stock_inventory`
- `agents/sales/inventory_signals.py` — ساخت low stock signal
- `docs/phases/step-3.3.md`

---

## نکته مربوط به Variants

مدل `Product` در Botkonak **هیچ variant table ندارد** — مقدار SKU روی همان row مربوط به product قرار دارد. اگر Prestia از variants استفاده می‌کند:

- **سؤال باز:** آیا هر variant باید به یک row از `Product` در Botkonak map شود، یا schema مربوط به Botkonak باید توسعه پیدا کند؟ این موضوع خارج از scope این سند است.
- Prestia باید `sku`، `color` و inventory سطح variant را در payloadهای product یا inventory expose کند. در seed از `metadata.color` استفاده شده است.

## شواهد از codebase

به بخش مربوط به هر API مراجعه کنید.

## سؤال‌های باز

1. آیا Prestia به‌صورت native از `compare_at_price` و `discount_percent` پشتیبانی می‌کند؟
2. آیا gallery چندتصویری وجود دارد یا فقط یک `image_url`؟
3. strategy مربوط به variant modeling برای connector چیست؟

</div>
