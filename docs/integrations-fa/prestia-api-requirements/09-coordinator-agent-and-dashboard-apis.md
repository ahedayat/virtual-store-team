<div dir="rtl" align="right">

# APIهای Coordinator Agent و Dashboard

APIهای موردنیاز **Coordinator Agent** و **admin dashboard** برای گزارش روزانه، orchestration و workflowهای manager.

## یادداشت معماری

Coordinator و dashboard در codebase فعلی **مستقیماً Prestia را فراخوانی نمی‌کنند**. آن‌ها **داده Django Botkonak** را مصرف می‌کنند (از Prestia از طریق connector آینده پر می‌شود). این سند map می‌کند:

1. Prestia چه چیزی باید expose کند تا Botkonak **معادل context bundle** بسازد
2. dashboard چه چیزی را به‌صورت غیرمستقیم از داده sync‌شده نیاز دارد

---

## Coordinator Agent: معادل context bundle

node `fetch_context` در coordinator Django را فراخوانی می‌کند:

`GET /internal/ai/context/{report_run_id}/` (`agents/coordinator/nodes.py`)

این همه read APIهای Prestia لازم برای یک daily report را bundle می‌کند:

| بخش context bundle | منبع داده | Doc |
|--------------------|-----------|-----|
| `tenant`، `store` | Botkonak tenant/store settings | [02-store-profile-apis.md](./02-store-profile-apis.md) |
| `products` | `GET /v1/products` (on demand) | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| `sales_summary` | محاسبه Botkonak از `GET /v1/orders` | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| `inventory` | استخراج از `inventories[]` در `GET /v1/products` | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| `messages` | webhook-ingested به inbox Botkonak | [08-support-agent-apis.md](./08-support-agent-apis.md) |
| `warnings` | خطاهای جزئی هنگام fetch/aggregation | ساخته‌شده توسط Botkonak connector |

### API: Aggregated Store Context (میانبر اختیاری Prestia)

| Property | Value |
|----------|-------|
| **API name** | Get Aggregated Store Context |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/context` |
| **Botkonak consumer** | Background sync، Coordinator (از طریق connector) |
| **Why Botkonak needs this** | جایگزین single round-trip برای پنج endpoint قبل از daily report. **لازم نیست** اگر Botkonak به‌صورت local compose کند. |
| **Requirement type** | Inferred |
| **Priority** | P1 |

#### Query parameterها

| Parameter | Description |
|-----------|-------------|
| `include` | جدا شده با کاما: `products,orders,faqs` |
| `reference_at` | برای محاسبه دوره sales (سمت Botkonak) |

#### شکل successful response

همان کلیدهای سطح بالای context bundle Botkonak (نمونه `docs/phases/step-3.5.md`)، منهای `report_run_id` (Botkonak آن را اضافه می‌کند).

#### فایل‌های مرتبط

- `backend/catalog/context.py` — `build_context_bundle`
- `docs/phases/step-3.5.md`

---

## Workflow Coordinator (داخلی Botkonak، نه Prestia)

برای کامل بودن — این‌ها **API Prestia نیستند**:

| Method | مسیر داخلی Botkonak | Purpose |
|--------|---------------------|---------|
| `GET` | `/internal/ai/context/{report_run_id}/` | fetch context (داده از Prestia از طریق sync) |
| `POST` | `/internal/ai/agent-outputs/` | persist خروجی specialistها |
| `POST` | `/internal/ai/report-runs/{id}/complete/` | ارسال daily report merge‌شده |

Coordinator specialist agentها را با context مشتق‌شده از داده منبع Prestia trigger می‌کند (`agents/coordinator/graph.py`).

### fieldهای daily report merge‌شده (از داده منبع Prestia)

`build_merged_daily_report` (`agents/coordinator/merge.py`) شامل:

| Field | وابستگی داده |
|-------|--------------|
| `sales_summary` | aggregation Botkonak از orderهای Prestia |
| `prioritized_actions` | از Sales Agent (orders + product inventories) |
| `content_suggestions` | از Content Agent (products + Botkonak tenant settings) |
| `support_insights` | از Support Agent (messageهای webhook + FAQها) |
| `warnings`، `partial`، `missing_sections` | metadata pipeline |

---

## APIهای Dashboard (Botkonak — داده اصلی از Prestia)

dashboard Next.js **API REST Botkonak** را می‌خواند، نه Prestia. Prestia باید داده زیرین را از طریق sync تأمین کند.

| قابلیت Dashboard | API Botkonak | داده Prestia موردنیاز |
|------------------|--------------|----------------------|
| trigger daily report | `POST /api/reports/generate/` | catalog/orders/messageهای تازه |
| لیست/جزئیات گزارش | `GET /api/reports/`، `GET /api/reports/{id}/` | گزارش merge‌شده از agent run |
| لیست/تأیید action | `GET /api/actions/`، `POST .../approve/` | recommendation agent (نه write Prestia) |
| feed تاریخچه | `GET /api/history/` | actionها، گزارش‌ها، eventها |
| store profile | `GET /api/stores/{store_id}/` | Botkonak tenant/store settings (نه API Prestia) |

hookهای frontend (`use-products`، `use-customers`، `use-recommendations`، `use-content-items`) هنوز از **mock data** استفاده می‌کنند — به API Django وصل نیستند. integration Prestia برای لیست product/customer در dashboard وقتی hookها پیاده شوند Future است.

---

## فعالیت agent و وضعیت task

| نیاز | منبع در Botkonak | API Prestia؟ |
|------|------------------|--------------|
| وضعیت report run | model `ReportRun`، Celery task | خیر |
| خروجی agent | model `AgentOutput` | خیر |
| پیشرفت task | response HTTP Coordinator | خیر |
| timeout specialist | warningهای Coordinator | خیر |

**هیچ API Prestia** برای metadata orchestration لازم نیست.

---

## recommendationها در dashboard

action/recommendationها **داخل Botkonak توسط agentها ساخته می‌شوند** (`operations.models.Action`)، نه از Prestia fetch می‌شوند. Prestia **ورودی** (orders، products، FAQها) را تأمین می‌کند؛ messageها از webhook می‌آیند.

---

## شواهد از codebase

| File | Relevance |
|------|-----------|
| `agents/coordinator/nodes.py` | nodeهای workflow، payload specialist |
| `agents/coordinator/merge.py` | شکل گزارش merge‌شده |
| `backend/operations/tasks.py` | Celery task `generate_daily` |
| `backend/operations/views.py` | API گزارش/action dashboard |
| `backend/operations/urls.py` | routeهای dashboard |
| `frontend/app/dashboard/page.tsx` | UI dashboard |
| `docs/agents/coordinator.md` | مستندات Coordinator |

## سؤال‌های باز

1. timeline وصل کردن dashboard زنده به Django در مقابل mock data.
2. آیا manager قبل از تولید گزارش re-sync Prestia را از dashboard به‌صورت دستی trigger می‌کند.

</div>
