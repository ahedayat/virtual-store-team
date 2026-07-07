# Product and Inventory APIs

APIs for products, categories, variants, prices, images, inventory, stock status, and product metadata.

---

## API: List Products

| Property | Value |
|----------|-------|
| **API name** | List Products |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/products` |
| **Botkonak consumer** | Content Agent, Sales Agent, Coordinator Agent, on-demand fetch |
| **Why Botkonak needs this** | Primary catalog source. Context bundle `products.items` drives content draft generation. Sales Agent uses product and `inventories` data for stock and recommendation signals. Empty products → deterministic empty content result without LLM (`agents/content/empty_products.py`). |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Required request headers

`Authorization: Bearer <access_token>`, `Accept: application/json`

### Query parameters — pagination

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | Yes | Page size (default 50, max 100) |
| `offset` | integer | Yes | Pagination offset (default 0) |

### Query parameters — search

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search` | string | No | Search by product `title` or `slug` |

### Query parameters — filters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter by category slug |
| `price_min` | number | No | Minimum product price (inclusive) |
| `price_max` | number | No | Maximum product price (inclusive) |
| `currency` | string | No | Filter by ISO 4217 currency code |
| `has_discount` | boolean | No | `true` when `discount` is non-null |
| `inventory_lte` | integer | No | At least one inventory variant has `num` ≤ value |
| `inventory_gte` | integer | No | At least one inventory variant has `num` ≥ value |
| `is_active` | boolean | No | Default `true` — matches `build_product_summary` filter |

**Inventory filter semantics:**

- `inventory_lte` — match products where **at least one** `inventories[]` entry has `num` less than or equal to the given value.
- `inventory_gte` — match products where **at least one** `inventories[]` entry has `num` greater than or equal to the given value.

### Path parameters

None.

### Request body

Not applicable.

### Successful response shape

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

### Field definitions

| Field | Type | Description |
|-------|------|-------------|
| `slug` | string | Stable product identifier |
| `title` | string | Product display name |
| `category.slug` | string | Category slug |
| `category.title` | string | Category display title |
| `description` | string | Full product description |
| `price` | number | Base or default variant price |
| `currency` | string | ISO 4217 code |
| `discount` | number \| null | Discount amount or percentage (Prestia to document unit); `null` when no discount |
| `images` | string[] | Image URLs |
| `inventories` | array | Variant-level inventory list |
| `inventories[].metadata` | object | Variant attributes (color, size, material, etc.) |
| `inventories[].num` | integer | Available quantity for that variant |
| `metadata` | object | Product-level metadata — colors, materials, feature lists, technical attributes, or any additional product information useful for agents |
| `created_at` | datetime | ISO 8601 with timezone |
| `updated_at` | datetime | ISO 8601 with timezone |
| `is_active` | boolean | Whether product is sellable / visible |

### Important fields — Botkonak mapping

| Prestia field | Botkonak / agent usage |
|---------------|------------------------|
| `slug` | Product identifier in context bundle and order line items |
| `title` | Prompts, captions, sales recommendations |
| `category.slug`, `category.title` | Category context in prompts |
| `price`, `currency`, `discount` | Pricing references; agent must not claim discounts without data |
| `images` | Content agent image URLs |
| `inventories` | Stock levels per variant; Sales Agent low-stock signals |
| `inventories[].metadata` | Variant attributes for support and content replies |
| `metadata` | Material/color/feature guardrails |
| `is_active` | Only active products in AI bundle |

### Pagination

Required: `limit` and `offset`. Connector fetches all active products when building full context.

### Filtering and sorting

- Default: `is_active=true`, order by `title` ascending.
- All search and filter parameters above are supported on this endpoint.

### Error cases

`401`, `403`, `429`, `500`

### Security notes

- Public catalog data; no customer PII.

### Example request

```http
GET /v1/products?is_active=true&limit=100&offset=0&search=milano&category=handbags&inventory_lte=5 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

### Related files

- `backend/catalog/models.py` — `Product`, `Category`
- `backend/catalog/context.py` — `_serialize_product_summary`, `build_product_summary`
- `agents/content/product_context.py` — `normalize_product`, `extract_products`
- `backend/tenants/management/commands/seed_prestia.py` — `PRESTIA_PRODUCTS`

---

## API: Get Product Detail

| Property | Value |
|----------|-------|
| **API name** | Get Product Detail |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/products/{slug}` |
| **Botkonak consumer** | Content Agent, Admin Dashboard |
| **Why Botkonak needs this** | Full `description` and image set for single-product content workflows. List endpoint may omit long descriptions. |
| **Requirement type** | Inferred |
| **Priority** | P2 |

### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `slug` | string | Prestia product slug |

### Successful response

Single product object (same shape as list item).

### Related files

- `backend/catalog/models.py` — `Product.description`, `Product.image_url`
- `frontend/hooks/use-products.ts` — mock product picker (future real API)

---

## API: List Categories

| Property | Value |
|----------|-------|
| **API name** | List Categories |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/categories` |
| **Botkonak consumer** | On-demand fetch, Content Agent |
| **Why Botkonak needs this** | Categories are embedded in product list today. Separate endpoint helps sync `Category` rows before products. |
| **Requirement type** | Inferred |
| **Priority** | P1 |

### Query parameters

`is_active`, `limit`, `offset`

### Successful response shape

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

### Related files

- `backend/catalog/models.py` — `Category`
- `seed_prestia.py` — `PRESTIA_CATEGORIES`

---

## Variants and inventory note

Variant-level stock is modeled in the `inventories` array on each product:

- Each inventory item represents inventory for a **specific product variant or attribute combination**.
- `inventories[].metadata` stores variant attributes (color, size, material, etc.).
- `inventories[].num` stores the available quantity for that variant.

Botkonak connector maps `inventories` into local `InventoryLevel` rows or aggregates for agent context. Product-level `metadata` holds non-variant attributes useful for agents.

## Evidence from codebase

See per-API sections.

## Open questions

1. Whether `discount` is an absolute amount or percentage — Prestia must document the unit.
2. Multi-image gallery ordering semantics.
3. Whether list endpoint omits `description` for performance (detail endpoint required for full text).
