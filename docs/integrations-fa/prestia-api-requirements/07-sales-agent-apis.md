<div dir="rtl" align="right">

# APIهای Sales Agent

APIهای موردنیاز **Sales Agent** برای تحلیل عملکرد sales، هشدار inventory و recommendationها.

## خلاصه Agent

Sales Agent (`agents/sales/`) `SalesAnalysisResult` با recommendationهای زیر تولید می‌کند:

- `sales.restock` — stock کم / تقاضای بالا
- `sales.discount` — کاندیدهای discount
- `sales.follow_up` — فرصت‌های follow-up

rubric اولویت 1 (فوری) تا 5 (اطلاعاتی) (`agents/sales/prompts.py`). Coordinator `sales_summary` و `inventory` را از context bundle با `fetch_from_django: False` می‌فرستد (`agents/coordinator/nodes.py`).

**خلاصه sales، پرفروش‌ها، insightهای low-stock، کاندیدهای discount و recommendationها داخل Botkonak** از داده خام order و product Prestia محاسبه می‌شوند — Prestia API خلاصه sales expose نمی‌کند.

## جریان داده

<div dir="ltr" align="left">

```
GET /v1/orders + GET /v1/products (on demand)
       ↓
Botkonak aggregates sales summary + inventory signals locally
       ↓
Context bundle → Sales Agent POST /run
```

</div>

timezone و currency برای مرزهای دوره از **Botkonak tenant settings** می‌آیند، نه Prestia ([02-store-profile-apis.md](./02-store-profile-apis.md)).

## APIهای Prestia موردنیاز

| Prestia API | ورودی Sales Agent | Priority |
|-------------|-------------------|----------|
| [GET /v1/orders](./04-order-and-sales-apis.md) | orderهای خام برای sales aggregation | P0 |
| [GET /v1/products](./03-product-and-inventory-apis.md) | عنوان product، `inventories[]` برای سیگنال stock | P0 |

## Sales summary (محاسبه‌شده توسط Botkonak)

Botkonak `sales_summary.today` و `sales_summary.last_7_days` را از `GET /v1/orders` با timezone فروشگاه از tenant settings می‌سازد (`backend/catalog/services.py`).

| Period field | Source |
|--------------|--------|
| `total_revenue` | مجموع `total` orderهای revenue-countable |
| `order_count` | تعداد orderهای revenue-countable |
| `units_sold` | مجموع `items[].quantity` |
| `average_order_value` | `total_revenue / order_count` |
| `top_products[]` | گروه‌بندی بر اساس `items[].product_slug` |

هر آیتم `top_products` (محاسبه local):

| Field | Source |
|-------|--------|
| `product_slug` | line item order |
| `name` | `items[].product_name` |
| `quantity_sold` | quantity aggregate‌شده |
| `revenue` | `line_total` aggregate‌شده |
| `category` | از product متناظر در `/v1/products` |

## fieldهای inventory استفاده‌شده

از `inventories[]` product در [GET /v1/products](./03-product-and-inventory-apis.md):

| Field | Usage |
|-------|-------|
| `slug`، `title` | recommendationهای restock |
| `inventories[].num` | ریسک stockout |
| `inventories[].metadata` | context variant |
| `category.title` | گروه‌بندی در payload LLM |

## نوع سیگنال‌های ساخته‌شده داخلی

| Signal | Source | Prestia API |
|--------|--------|-------------|
| productهای low stock | `inventories[].num` زیر آستانه | `GET /v1/products` |
| پرفروش با stock کم | cross-reference پرفروش + inventories | Orders + products |
| slow moverها | LLM از پرفروش ضعیف | Orders (محاسبه‌شده) |
| کاندیدهای discount | LLM از روند sales + inventory | Orders + products |

## رفتار sales خالی

اگر هم `today` و هم `last_7_days` revenue و order صفر داشته باشند، agent از LLM رد می‌شود (`agents/sales/empty_sales.py`). aggregation Botkonak باید صفر عددی برگرداند، نه حذف دوره‌ها.

## APIهای اختیاری Prestia

| API | Why | Priority |
|-----|-----|----------|
| [GET /v1/customer/{id}/orders](./05-customer-apis.md) | order history customer برای follow-up | P1 |
| abandoned cart / orderهای `status=draft` | فقط follow-up UI mock | Future |

## APIهایی که لازم نیست

| API | Reason |
|-----|--------|
| `GET /v1/sales/summary` | توسط Botkonak از orders محاسبه می‌شود |
| `GET /v1/store` | timezone/currency در Botkonak tenant settings |
| `GET /v1/inventory/low-stock` | داده stock در `inventories[]` product |

## Write APIها (لازم نیست)

Sales agent می‌تواند وقتی فعال باشد `persist_actions` را به Django `POST /internal/ai/actions/` بفرستد. **هیچ write Prestia** برای discount یا restock وجود ندارد.

## شواهد از codebase

| File | Relevance |
|------|-----------|
| `agents/sales/analysis.py` | pipeline اصلی |
| `agents/sales/django_fetch.py` | الگوی fetch Django (معادل Prestia) |
| `agents/sales/inventory_signals.py` | ساخت سیگنال |
| `agents/sales/empty_sales.py` | مدیریت sales خالی |
| `agents/sales/prompts.py` | rubric اولویت |
| `backend/catalog/services.py` | منطق aggregation |
| `docs/agents/sales.md` | مستندات agent |

## سؤال‌های باز

1. آیا Prestia می‌تواند productهای «واجد شرایط discount» را به‌صورت native flag کند در مقابل استنتاج LLM.
2. دقت inventory بلادرنگ در دوره‌های ترافیک بالا.
3. آستانه low-stock — تنظیم tenant Botkonak در مقابل metadata Prestia.

</div>
