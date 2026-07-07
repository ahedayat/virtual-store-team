<div dir="rtl" align="right">

# APIهای Product و Inventory

APIها برای products، categories، variants، قیمت‌ها، تصاویر، inventory، وضعیت stock و metadata محصول.

---

## API: List Products

| Property | Value |
|----------|-------|
| **API name** | List Products |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/products` |
| **Botkonak consumer** | Content Agent، Sales Agent، Coordinator Agent، on-demand fetch |
| **Why Botkonak needs this** | منبع اصلی catalog. `products.items` در context bundle تولید draft محتوا را هدایت می‌کند. Sales Agent از product و داده `inventories` برای سیگنال stock و recommendation استفاده می‌کند. product خالی → نتیجه deterministic خالی بدون LLM (`agents/content/empty_products.py`). |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Headerهای لازم برای request

`Authorization: Bearer <access_token>`، `Accept: application/json`

### Query parameterها — pagination

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | Yes | اندازه صفحه (پیش‌فرض 50، حداکثر 100) |
| `offset` | integer | Yes | offset pagination (پیش‌فرض 0) |

### Query parameterها — search

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search` | string | No | جستجو بر اساس `title` یا `slug` محصول |

### Query parameterها — filter

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | filter بر اساس category slug |
| `price_min` | number | No | حداقل قیمت محصول (شامل) |
| `price_max` | number | No | حداکثر قیمت محصول (شامل) |
| `currency` | string | No | filter بر اساس کد ISO 4217 |
| `has_discount` | boolean | No | `true` وقتی `discount` غیر null است |
| `inventory_lte` | integer | No | حداقل یک variant در `inventories[]` مقدار `num` ≤ value دارد |
| `inventory_gte` | integer | No | حداقل یک variant در `inventories[]` مقدار `num` ≥ value دارد |
| `is_active` | boolean | No | پیش‌فرض `true` — با filter `build_product_summary` هم‌خوان است |

**معنای filter inventory:**

- `inventory_lte` — productهایی که **حداقل یک** ورودی `inventories[]` مقدار `num` کمتر یا مساوی value دارد.
- `inventory_gte` — productهایی که **حداقل یک** ورودی `inventories[]` مقدار `num` بیشتر یا مساوی value دارد.

### Path parameterها

هیچ.

### Request body

قابل اعمال نیست.

### شکل successful response

<div dir="ltr" align="left">

```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "slug": "milano-leather-tote",
      "title": "کیف چرم میلانو",
      "category": {
        "slug": "handbags",
        "title": "Handbags"
      },
      "description": "کیف چرم تمام‌گرین با جیب زیپ داخلی.",
      "price": 189.00,
      "currency": "USD",
      "discount": null,
      "images": [
        "https://cdn.prestia.ir/products/milano-tote.jpg"
      ],
      "inventories": [
        {
          "metadata": {
            "color": "cognac",
            "size": "one-size"
          },
          "num": 3
        }
      ],
      "metadata": {
        "material": "leather",
        "colors": ["cognac", "black"],
        "features": ["zip pocket", "adjustable strap"]
      },
      "created_at": "2025-03-01T10:00:00+00:00",
      "updated_at": "2026-06-18T09:00:00+00:00",
      "is_active": true
    }
  ]
}
```

</div>

### تعریف fieldها

| Field | Type | Description |
|-------|------|-------------|
| `slug` | string | شناسه پایدار product |
| `title` | string | نام نمایشی product |
| `category.slug` | string | category slug |
| `category.title` | string | عنوان نمایشی category |
| `description` | string | توضیح کامل product |
| `price` | number | قیمت پایه یا variant پیش‌فرض |
| `currency` | string | کد ISO 4217 |
| `discount` | number \| null | مقدار یا درصد discount (واحد را Prestia مستند کند)؛ `null` بدون discount |
| `images` | string[] | URL تصاویر |
| `inventories` | array | لیست inventory سطح variant |
| `inventories[].metadata` | object | attributeهای variant (color، size، material و غیره) |
| `inventories[].num` | integer | تعداد موجود برای آن variant |
| `metadata` | object | metadata سطح product — رنگ‌ها، مواد، لیست featureها، attributeهای فنی یا هر اطلاعات اضافی مفید برای agentها |
| `created_at` | datetime | ISO 8601 با timezone |
| `updated_at` | datetime | ISO 8601 با timezone |
| `is_active` | boolean | آیا product قابل فروش / قابل نمایش است |

### fieldهای مهم — mapping Botkonak

| Prestia field | استفاده Botkonak / agent |
|---------------|--------------------------|
| `slug` | شناسه product در context bundle و line itemهای order |
| `title` | promptها، captionها، sales recommendationها |
| `category.slug`، `category.title` | context category در promptها |
| `price`، `currency`، `discount` | مرجع قیمت؛ agent نباید بدون داده discount ادعا کند |
| `images` | URL تصویر برای Content Agent |
| `inventories` | سطح stock per variant؛ سیگنال low-stock Sales Agent |
| `inventories[].metadata` | attributeهای variant برای پاسخ support و content |
| `metadata` | guardrail مواد/رنگ/feature |
| `is_active` | فقط productهای active در AI bundle |

### Pagination

الزامی: `limit` و `offset`. connector هنگام ساخت context کامل همه productهای active را fetch می‌کند.

### Filter و sort

- پیش‌فرض: `is_active=true`، مرتب‌سازی بر اساس `title` صعودی.
- همه parameterهای search و filter بالا در این endpoint پشتیبانی می‌شوند.

### Error caseها

`401`، `403`، `429`، `500`

### نکات امنیتی

- داده catalog عمومی؛ بدون PII customer.

### نمونه request

<div dir="ltr" align="left">

```http
GET /v1/products?is_active=true&limit=100&offset=0&search=milano&category=handbags&inventory_lte=5 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

</div>

### فایل‌های مرتبط

- `backend/catalog/models.py` — `Product`، `Category`
- `backend/catalog/context.py` — `_serialize_product_summary`، `build_product_summary`
- `agents/content/product_context.py` — `normalize_product`، `extract_products`
- `backend/tenants/management/commands/seed_prestia.py` — `PRESTIA_PRODUCTS`

---

## API: Get Product Detail

| Property | Value |
|----------|-------|
| **API name** | Get Product Detail |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/products/{slug}` |
| **Botkonak consumer** | Content Agent، Admin Dashboard |
| **Why Botkonak needs this** | `description` کامل و مجموعه تصاویر برای workflow محتوای تک‌محصول. list endpoint ممکن است description بلند را حذف کند. |
| **Requirement type** | Inferred |
| **Priority** | P2 |

### Path parameterها

| Name | Type | Description |
|------|------|-------------|
| `slug` | string | product slug در Prestia |

### Successful response

یک object product (همان شکل آیتم list).

### فایل‌های مرتبط

- `backend/catalog/models.py` — `Product.description`، `Product.image_url`
- `frontend/hooks/use-products.ts` — mock product picker (API واقعی در آینده)

---

## API: List Categories

| Property | Value |
|----------|-------|
| **API name** | List Categories |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/categories` |
| **Botkonak consumer** | On-demand fetch، Content Agent |
| **Why Botkonak needs this** | categoryها امروز در product list embed شده‌اند. endpoint جداگانه قبل از products به sync ردیف‌های `Category` کمک می‌کند. |
| **Requirement type** | Inferred |
| **Priority** | P1 |

### Query parameterها

`is_active`، `limit`، `offset`

### شکل successful response

<div dir="ltr" align="left">

```json
{
  "count": 5,
  "results": [
    {
      "slug": "handbags",
      "title": "Handbags",
      "description": "Structured handbags for everyday use.",
      "is_active": true,
      "metadata": {}
    }
  ]
}
```

</div>

### فایل‌های مرتبط

- `backend/catalog/models.py` — `Category`
- `seed_prestia.py` — `PRESTIA_CATEGORIES`

---

## یادداشت variants و inventory

stock سطح variant در آرایه `inventories` روی هر product مدل‌سازی شده:

- هر آیتم inventory نماینده inventory برای **ترکیب variant یا attribute مشخص** است.
- `inventories[].metadata` attributeهای variant (color، size، material و غیره) را نگه می‌دارد.
- `inventories[].num` تعداد موجود آن variant را نگه می‌دارد.

Botkonak connector مقدار `inventories` را به ردیف‌های محلی `InventoryLevel` map می‌کند یا برای context agent aggregate می‌کند. `metadata` سطح product attributeهای غیر-variant مفید برای agentها را نگه می‌دارد.

## شواهد از codebase

به بخش per-API مراجعه کنید.

## سؤال‌های باز

1. آیا `discount` مبلغ مطلق است یا درصد — Prestia باید واحد را مستند کند.
2. معنای ترتیب gallery چند تصویری.
3. آیا list endpoint برای performance مقدار `description` را حذف می‌کند (endpoint detail برای متن کامل لازم است).

</div>
