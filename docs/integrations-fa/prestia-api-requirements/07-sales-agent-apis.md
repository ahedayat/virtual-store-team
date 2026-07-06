<div dir="rtl" align="right">

# APIهای Sales Agent

APIهایی که **Sales Agent** برای تحلیل performance فروش، inventory alertها و recommendationها به آن‌ها نیاز دارد.

## خلاصه Agent

Sales Agent، یعنی `agents/sales/`، خروجی‌ای از نوع `SalesAnalysisResult` تولید می‌کند که شامل recommendationهای زیر است:

- `sales.restock` — موجودی کم / تقاضای بالا
- `sales.discount` — گزینه‌های مناسب برای discount
- `sales.follow_up` — فرصت‌های follow-up

rubric مربوط به priority از 1، یعنی urgent، تا 5، یعنی informational، تعریف شده است؛ فایل `agents/sales/prompts.py`. Coordinator مقدارهای `sales_summary` و `inventory` را از context bundle به Sales Agent ارسال می‌کند و مقدار `fetch_from_django: False` را تنظیم می‌کند؛ فایل `agents/coordinator/nodes.py`.

## جریان داده

</div>

```text
Prestia GET /sales/summary + GET /inventory/low-stock
       ↓
Botkonak sync / connector
       ↓
Context bundle → Sales Agent POST /run
```

<div dir="rtl" align="right">

مسیر direct اختیاری هم وجود دارد؛ پیاده‌سازی شده اما توسط Coordinator غیرفعال است: وقتی مقدار `fetch_from_django=True` باشد، Sales Agent endpointهای داخلی Django را فراخوانی می‌کند؛ فایل `agents/sales/django_fetch.py`.

## APIهای لازم از Prestia

| Prestia API                                                       | ورودی Sales Agent                                            | Priority         |
| ----------------------------------------------------------------- | ------------------------------------------------------------ | ---------------- |
| [GET /v1/sales/summary](./04-order-and-sales-apis.md)             | مقدارهای `sales_summary.today` و `sales_summary.last_7_days` | P0               |
| [GET /v1/inventory/low-stock](./03-product-and-inventory-apis.md) | مقدار `inventory.items`                                      | P0               |
| [GET /v1/products](./03-product-and-inventory-apis.md)            | نام productها و SKUها برای cross-reference                   | P0، از طریق sync |
| [GET /v1/store](./02-store-profile-apis.md)                       | مقدارهای `currency` و `timezone` برای period boundaryها      | P0               |

## فیلدهای Sales summary که استفاده می‌شوند

بر اساس فایل‌های `agents/sales/empty_sales.py` و `agents/sales/inventory_signals.py`:

| Period field          | Usage                                                             |
| --------------------- | ----------------------------------------------------------------- |
| `total_revenue`       | تشخیص empty sales                                                 |
| `order_count`         | تشخیص empty sales                                                 |
| `units_sold`          | demand signalها                                                   |
| `average_order_value` | insightها                                                         |
| `top_products[]`      | best sellerها؛ cross-reference با inventory برای restock/discount |

هر item داخل `top_products`:

| Field           | Usage                               |
| --------------- | ----------------------------------- |
| `product_id`    | مقدار داخل recommendation `payload` |
| `sku`           | مقدار داخل recommendation `payload` |
| `name`          | عنوان‌ها و descriptionها            |
| `quantity_sold` | velocity                            |
| `revenue`       | prioritization                      |
| `category`      | context                             |

## فیلدهای Inventory که استفاده می‌شوند

بر اساس `build_low_stock_summary` و فایل `agents/sales/inventory_signals.py`:

| Field                               | Usage                               |
| ----------------------------------- | ----------------------------------- |
| `product_id`, `sku`, `product_name` | restock recommendationها            |
| `available_quantity`                | ریسک stockout                       |
| `low_stock_threshold`               | مرز alert                           |
| `shortage_units`                    | اندازه‌گیری urgency                 |
| `suggested_reorder_quantity`        | مقدار `payload.suggested_order_qty` |
| `category`                          | grouping در LLM payload             |

## انواع Signalهایی که به‌صورت داخلی ساخته می‌شوند

| Signal                       | Source                                         | Prestia API                |
| ---------------------------- | ---------------------------------------------- | -------------------------- |
| Productهای low stock         | `inventory.items`                              | `GET /inventory/low-stock` |
| فروشنده‌های قوی با موجودی کم | cross-reference بین `top_products` و inventory | Summary + low-stock        |
| Slow movers                  | LLM از روی `top_products` / sales ضعیف         | Summary؛ API اختصاصی ندارد |
| Discount candidates          | LLM از روی sales trendها + inventory           | Summary؛ API اختصاصی ندارد |

## رفتار در صورت Empty بودن Sales

اگر هم `today` و هم `last_7_days` revenue صفر و order صفر داشته باشند، Agent فراخوانی LLM را skip می‌کند؛ فایل `agents/sales/empty_sales.py`. Prestia باید مقدارهای عددی صفر را برگرداند و periodها را حذف نکند.

## APIهای اختیاری از Prestia

| API                                         | Why                                                                        | Priority |
| ------------------------------------------- | -------------------------------------------------------------------------- | -------- |
| `GET /v1/orders`                            | محاسبه دوباره summary به‌صورت local؛ reconciliation بین Prestia و Botkonak | P1       |
| `GET /v1/inventory`                         | سطح کامل stock فراتر از low-stock                                          | P1       |
| Abandoned cart / orderهای با `status=draft` | فقط برای mock UI مربوط به follow-up                                        | Future   |

## Write APIها، لازم نیستند

Sales Agent وقتی فعال باشد می‌تواند actionها را در Django با `POST /internal/ai/actions/` persist کند. **هیچ write به Prestia** برای discount یا restock وجود ندارد.

فایل `agents/sales/action_mapping.py` فقط به actionهای داخلی map می‌کند.

## شواهد از codebase

| File                                | Relevance                                               |
| ----------------------------------- | ------------------------------------------------------- |
| `agents/sales/analysis.py`          | pipeline اصلی                                           |
| `agents/sales/django_fetch.py`      | الگوی fetch از Django؛ قابل نگاشت به معادل‌های Prestia  |
| `agents/sales/inventory_signals.py` | ساخت signalها                                           |
| `agents/sales/empty_sales.py`       | مدیریت empty sales                                      |
| `agents/sales/prompts.py`           | rubric مربوط به priority                                |
| `backend/catalog/services.py`       | منطق aggregation که Prestia باید مشابه آن را mirror کند |
| `docs/agents/sales.md`              | مستندات Agent                                           |
| `docs/examples/sales_output.json`   | output contract                                         |

## سؤال‌های باز

1. آیا Prestia می‌تواند productهای «discount-eligible» را به‌صورت native مشخص کند یا این مورد باید از طریق LLM inference انجام شود؟
2. دقت real-time مربوط به inventory reservation در دوره‌های high-traffic چقدر است؟

</div>
