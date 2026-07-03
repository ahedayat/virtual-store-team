# Product and Inventory APIs

APIs for products, categories, variants, prices, images, inventory, stock status, and product metadata.

---

## API: List Products

| Property | Value |
|----------|-------|
| **API name** | List Products |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/products` |
| **Botkonak consumer** | Content Agent, Coordinator Agent, Background sync |
| **Why Botkonak needs this** | Context bundle `products.items` drives content draft generation. Empty products → deterministic empty content result without LLM (`agents/content/empty_products.py`). |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Required request headers

`Authorization: Bearer <access_token>`, `Accept: application/json`

### Query parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `is_active` | boolean | No | Default `true` — matches `build_product_summary` filter |
| `limit` | integer | No | Pagination (default 50, max 100) |
| `offset` | integer | No | Pagination offset |
| `updated_since` | ISO datetime | No | Incremental sync |
| `category_slug` | string | No | Filter by category |

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
      "images": [
        "https://cdn.prestia.ir/products/milano-tote.jpg"
      ],
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

### Important fields

| Field | Botkonak mapping | Agent usage |
|-------|------------------|-------------|
| `id` | `product_id` in context bundle | Content drafts `product_id` |
| `name` / `title` | `name` | Prompts, captions |
| `sku` | `sku` | Sales recommendations payload |
| `description` | `Product.description` | Product description drafts (Inferred — not in context bundle today but in model) |
| `price`, `currency` | context item fields | Caption pricing references |
| `image_url` / `images` | `image_url` | Content agent `normalize_product` |
| `category` | nested object | Category context in prompts |
| `metadata` | `metadata` JSON | Material/color claims guardrail |
| `is_active` | filter | Only active in AI bundle |

### Pagination

Offset/limit or cursor. Connector must fetch all active products for full context.

### Filtering and sorting

- Default: `is_active=true`, order by `name` ascending.

### Error cases

`401`, `403`, `429`, `500`

### Security notes

- Public catalog data; no customer PII.

### Example request

```http
GET /v1/products?is_active=true&limit=100 HTTP/1.1
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
| **Suggested endpoint path** | `/v1/products/{product_id}` |
| **Botkonak consumer** | Content Agent, Admin Dashboard |
| **Why Botkonak needs this** | Full `description` and image set for single-product content workflows. List endpoint may omit long descriptions. |
| **Requirement type** | Inferred |
| **Priority** | P2 |

### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `product_id` | string (UUID) | Prestia product id |

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
| **Botkonak consumer** | Background sync, Content Agent |
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

### Related files

- `backend/catalog/models.py` — `Category`
- `seed_prestia.py` — `PRESTIA_CATEGORIES`

---

## API: List Inventory Levels

| Property | Value |
|----------|-------|
| **API name** | List Inventory Levels |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/inventory` |
| **Botkonak consumer** | Background sync, Sales Agent |
| **Why Botkonak needs this** | Populates `InventoryLevel` for low-stock computation. Required for accurate sync if low-stock endpoint is not sole source. |
| **Requirement type** | Inferred |
| **Priority** | P1 |

### Query parameters

| Parameter | Description |
|-----------|-------------|
| `updated_since` | Incremental sync |
| `is_active` | Default `true` |
| `limit`, `offset` | Pagination |

### Successful response shape

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

### Related files

- `backend/catalog/models.py` — `InventoryLevel`
- `seed_prestia.py` — `PRESTIA_INVENTORY`

---

## API: Get Low Stock Inventory

| Property | Value |
|----------|-------|
| **API name** | Get Low Stock Inventory |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/inventory/low-stock` |
| **Botkonak consumer** | Sales Agent, Coordinator Agent, Background sync |
| **Why Botkonak needs this** | Sales agent restock recommendations. Context bundle `inventory` section. Products where `available_quantity < low_stock_threshold`. |
| **Requirement type** | Direct |
| **Priority** | P0 |

### Required request headers

`Authorization: Bearer <access_token>`, `Accept: application/json`

### Query parameters

None required. Optional: `limit` to cap items (Botkonak returns all matches).

### Successful response shape

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

### Important fields

| Field | Usage |
|-------|-------|
| `available_quantity` | `quantity_on_hand - reserved_quantity` |
| `shortage_units` | `max(0, low_stock_threshold - available_quantity)` |
| `suggested_reorder_quantity` | `max(0, reorder_target - available_quantity)` when reorder_target set |
| `sku`, `product_id` | Sales recommendation `payload` |

### Pagination

Not required if item count is bounded; optional `limit`.

### Error cases

`401`, `403`, `500`

### Example request

```http
GET /v1/inventory/low-stock HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
```

### Related files

- `backend/catalog/services.py` — `build_low_stock_summary`, `_serialize_low_stock_item`
- `backend/catalog/internal_views.py` — `InternalLowStockInventoryView`
- `agents/sales/django_fetch.py` — `get_low_stock_inventory`
- `agents/sales/inventory_signals.py` — low stock signal building
- `docs/phases/step-3.3.md`

---

## Variants note

Botkonak `Product` model has **no variant table** — SKU is on the product row. If Prestia uses variants:

- **Open question:** Map each variant to a Botkonak `Product` row, or extend Botkonak schema (out of scope for this doc).
- Prestia should expose `sku`, `color`, and variant-level inventory in product or inventory payloads (`metadata.color` used in seed).

## Evidence from codebase

See per-API sections.

## Open questions

1. Does Prestia support `compare_at_price` / `discount_percent` natively?
2. Multi-image gallery vs single `image_url`.
3. Variant modeling strategy for connector.
