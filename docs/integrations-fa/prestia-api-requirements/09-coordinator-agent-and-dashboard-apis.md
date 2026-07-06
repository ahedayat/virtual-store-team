<div dir="rtl" align="right">

# APIهای Coordinator Agent و Dashboard

APIهایی که **Coordinator Agent** و **admin dashboard** برای daily reportها، orchestration و workflowهای manager به آن‌ها نیاز دارند.

## نکته معماری

در codebase فعلی، Coordinator و dashboard **مستقیماً Prestia را فراخوانی نمی‌کنند**. آن‌ها از **داده‌های Django در Botkonak** استفاده می‌کنند؛ داده‌هایی که در آینده از طریق connector از Prestia populate می‌شوند. این سند دو مورد را map می‌کند:

1. Prestia باید چه چیزهایی را expose کند تا Botkonak بتواند معادل **context bundle** را بسازد.
2. Dashboard به‌صورت غیرمستقیم و از طریق داده‌های sync‌شده به چه چیزهایی نیاز دارد.

---

## Coordinator Agent: معادل Context Bundle

node مربوط به `fetch_context` در Coordinator، endpoint زیر را در Django فراخوانی می‌کند:

</div>

```text
GET /internal/ai/context/{report_run_id}/
```

<div dir="rtl" align="right">

این endpoint همه read APIهای لازم از Prestia را برای یک daily report در قالب یک bundle جمع می‌کند:

| Context bundle section | منبع API در Prestia                  | Doc                                                                    |
| ---------------------- | ------------------------------------ | ---------------------------------------------------------------------- |
| `tenant`, `store`      | `GET /v1/store`                      | [02-store-profile-apis.md](./02-store-profile-apis.md)                 |
| `products`             | `GET /v1/products`                   | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| `sales_summary`        | `GET /v1/sales/summary`              | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md)             |
| `inventory`            | `GET /v1/inventory/low-stock`        | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| `messages`             | `GET /v1/messages/recent`            | [08-support-agent-apis.md](./08-support-agent-apis.md)                 |
| `warnings`             | failureهای partial هنگام aggregation | توسط Botkonak connector ساخته می‌شود                                   |

### API: Aggregated Store Context؛ shortcut اختیاری در Prestia

| Property                               | Value                                                                                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **نام API**                            | Get Aggregated Store Context                                                                                                               |
| **HTTP method**                        | `GET`                                                                                                                                      |
| **مسیر endpoint پیشنهادی**             | `/v1/context`                                                                                                                              |
| **مصرف‌کننده در Botkonak**             | Background sync، Coordinator از طریق connector                                                                                             |
| **چرا Botkonak به این API نیاز دارد؟** | جایگزینی با یک round-trip برای پنج endpoint قبل از daily report. اگر Botkonak context را به‌صورت local compose کند، این API **لازم نیست**. |
| **نوع نیازمندی**                       | Inferred                                                                                                                                   |
| **Priority**                           | P1                                                                                                                                         |

#### Query parameterها

| Parameter      | Description                                                      |
| -------------- | ---------------------------------------------------------------- |
| `include`      | مقدارهای comma-separated مثل `products,sales,inventory,messages` |
| `reference_at` | برای محاسبه sales periodها                                       |

#### ساختار response موفق

همان keyهای top-level در context bundle مربوط به Botkonak؛ مطابق example در `docs/phases/step-3.5.md`، با این تفاوت که `report_run_id` وجود ندارد، چون Botkonak آن را اضافه می‌کند.

#### فایل‌های مرتبط

- `backend/catalog/context.py` — تابع `build_context_bundle`
- `docs/phases/step-3.5.md`

---

## Workflow مربوط به Coordinator؛ داخلی Botkonak، نه Prestia

برای کامل بودن تصویر، موارد زیر آورده شده‌اند؛ اما این‌ها APIهای Prestia **نیستند**:

| Method | مسیر داخلی Botkonak                       | Purpose                                               |
| ------ | ----------------------------------------- | ----------------------------------------------------- |
| `GET`  | `/internal/ai/context/{report_run_id}/`   | دریافت context؛ داده از طریق sync از Prestia آمده است |
| `POST` | `/internal/ai/agent-outputs/`             | persist کردن خروجی‌های specialistها                   |
| `POST` | `/internal/ai/report-runs/{id}/complete/` | ارسال merged daily report                             |

Coordinator با استفاده از context مشتق‌شده از داده‌های Prestia، specialist agentها را trigger می‌کند؛ فایل `agents/coordinator/graph.py`.

### فیلدهای Merged Daily Report؛ مبتنی بر داده‌های Prestia

تابع `build_merged_daily_report` در فایل `agents/coordinator/merge.py` شامل موارد زیر است:

| Field                                     | وابستگی به داده Prestia                               |
| ----------------------------------------- | ----------------------------------------------------- |
| `sales_summary`                           | Sales summary API                                     |
| `prioritized_actions`                     | از Sales Agent؛ وابسته به sales + inventory           |
| `content_suggestions`                     | از Content Agent؛ وابسته به products + store settings |
| `support_insights`                        | از Support Agent؛ وابسته به messages                  |
| `warnings`, `partial`, `missing_sections` | pipeline metadata                                     |

---

## APIهای Dashboard؛ در Botkonak، اما داده‌ها در اصل از Prestia آمده‌اند

Dashboard در Next.js، **APIهای REST مربوط به Botkonak** را می‌خواند، نه Prestia را. Prestia باید داده‌های زیربنایی را از طریق sync فراهم کند.

| Dashboard feature    | Botkonak API                                  | داده لازم از Prestia                         |
| -------------------- | --------------------------------------------- | -------------------------------------------- |
| Trigger daily report | `POST /api/reports/generate/`                 | catalog، orders و messages تازه              |
| Report list/detail   | `GET /api/reports/`، `GET /api/reports/{id}/` | merged report از agent run                   |
| Actions list/approve | `GET /api/actions/`، `POST .../approve/`      | recommendationهای agent؛ نه write به Prestia |
| History feed         | `GET /api/history/`                           | actions، reports و events                    |
| Store profile        | `GET /api/stores/{store_id}/`                 | Store profile API                            |

### Store detail برای Dashboard

| Property                   | Value                                  |
| -------------------------- | -------------------------------------- |
| **Prestia API**            | `GET /v1/store`                        |
| **مصرف‌کننده در Botkonak** | Admin Dashboard                        |
| **نوع نیازمندی**           | Direct؛ به‌صورت غیرمستقیم از طریق sync |
| **Priority**               | P0                                     |

Frontend hookهایی مثل `use-products`، `use-customers`، `use-recommendations` و `use-content-items` هنوز از **mock data** استفاده می‌کنند و به Django APIها وصل نشده‌اند. integration مربوط به Prestia برای فهرست product/customer در dashboard مربوط به آینده است؛ یعنی زمانی که hookها پیاده‌سازی شوند.

---

## Agent Activity و Task Status

| Need                | Source in Botkonak                 | Prestia API? |
| ------------------- | ---------------------------------- | ------------ |
| Report run status   | مدل `ReportRun` و Celery task      | No           |
| Agent outputs       | مدل `AgentOutput`                  | No           |
| Task progress       | HTTP response مربوط به Coordinator | No           |
| Specialist timeouts | warningهای Coordinator             | No           |

برای orchestration metadata، **هیچ API از Prestia لازم نیست**.

---

## Recommendationها در Dashboard

Actionها و recommendationها **داخل Botkonak و توسط agentها** ساخته می‌شوند؛ مدل `operations.models.Action`. این موارد از Prestia fetch نمی‌شوند. Prestia فقط **inputها** را فراهم می‌کند؛ یعنی sales، inventory، products و messages.

---

## شواهد از codebase

| File                              | Relevance                                |
| --------------------------------- | ---------------------------------------- |
| `agents/coordinator/nodes.py`     | nodeهای workflow و payloadهای specialist |
| `agents/coordinator/merge.py`     | شکل merged report                        |
| `backend/operations/tasks.py`     | Celery task به نام `generate_daily`      |
| `backend/operations/views.py`     | APIهای dashboard برای report/action      |
| `backend/operations/urls.py`      | routeهای dashboard                       |
| `frontend/app/dashboard/page.tsx` | UI مربوط به Dashboard                    |
| `docs/agents/coordinator.md`      | مستندات Coordinator                      |

## سؤال‌های باز

1. timeline مربوط به live wiring داشبورد به Django در برابر mock data چیست؟
2. آیا managerها قبل از report generation باید بتوانند از dashboard به‌صورت manual، re-sync از Prestia را trigger کنند؟

</div>
