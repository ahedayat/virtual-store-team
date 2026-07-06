<div dir="rtl" align="right">

# نیازمندی‌های API برای Prestia ↔ Botkonak

## هدف این مستندات

این directory، **APIهای خارجی‌ای را مستند می‌کند که Prestia، یعنی prestia.ir، باید expose کند** تا Botkonak بتواند به‌عنوان یک لایه هوشمند مدیریت فروشگاه برای یک فروشگاه Prestia متصل‌شده عمل کند. این نیازمندی‌ها از codebase موجود Botkonak استخراج شده‌اند؛ یعنی از modelها، internal AI serviceها، agentها، workflow مربوط به coordinator و dashboard — نه از فرضیات عمومی درباره e-commerce.

**Prestia اولین demo tenant** در Botkonak است؛ یعنی `seed_prestia`. با این حال، platform به‌صورت multi-tenant طراحی شده است. این contractها توضیح می‌دهند که هر integration مربوط به فروشگاه Prestia باید چه داده‌ها و APIهایی فراهم کند؛ اما این‌ها در حال حاضر code pathهای runtime مخصوص Prestia داخل Botkonak نیستند.

## خلاصه Integration

| Aspect | وضعیت فعلی Botkonak | integration هدف با Prestia |
|--------|----------------------|-----------------------------|
| Data source | PostgreSQL از طریق Django modelها؛ demo data از `seed_prestia` | APIهای Prestia به‌عنوان system of record یا sync source |
| Auth به external store | پیاده‌سازی نشده است | OAuth 2.0 access token؛ با `Authorization: Bearer <token>` |
| مسیر داده برای Agentها | Coordinator → Django `GET /internal/ai/context/{report_run_id}/` | Botkonak connector داده‌ها را از Prestia fetch می‌کند و داخل Django normalize می‌کند؛ یا در runtime مستقیماً Prestia را فراخوانی می‌کند |
| Write back به store | پیاده‌سازی نشده است؛ actionها internal approval stub هستند | Future / optional |

Botkonak در وضعیت فعلی **prestia.ir را فراخوانی نمی‌کند**. این سیستم فقط داده‌هایی با شکل داده‌های Prestia را به‌صورت local mirror می‌کند. این مستندات contract سمت Prestia را برای ساخت یک connector واقعی تعریف می‌کند.

## نقشه Directory

| File | Contents |
|------|----------|
| [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) | OAuth 2.0، Bearer headerها، scopeها و چرخه عمر token |
| [01-shared-data-contracts.md](./01-shared-data-contracts.md) | typeهای مشترک، pagination، errorها و field mappingها |
| [02-store-profile-apis.md](./02-store-profile-apis.md) | هویت store، timezone، currency و brand settings |
| [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) | products، categories، inventory و low-stock |
| [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) | orders، sales summary و revenue metrics |
| [05-customer-apis.md](./05-customer-apis.md) | customer recordها و order history؛ با نیاز فعلی محدود |
| [06-content-agent-apis.md](./06-content-agent-apis.md) | APIهایی که مستقیم یا از طریق sync توسط Content Agent مصرف می‌شوند |
| [07-sales-agent-apis.md](./07-sales-agent-apis.md) | APIهایی که Sales Agent مصرف می‌کند |
| [08-support-agent-apis.md](./08-support-agent-apis.md) | APIهایی که Support Agent مصرف می‌کند |
| [09-coordinator-agent-and-dashboard-apis.md](./09-coordinator-agent-and-dashboard-apis.md) | نیازهای context برای Coordinator و پیامدهای آن برای dashboard |
| [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md) | مقایسه polling و webhook بر اساس معماری فعلی |
| [11-api-priority-and-mvp-scope.md](./11-api-priority-and-mvp-scope.md) | دسته‌بندی P0 تا Future و سؤال‌های باز |
| [12-full-api-index.md](./12-full-api-index.md) | جدول کامل index مربوط به APIها |

## Botkonak چگونه با Prestia احراز هویت می‌کند؟

1. manager فروشگاه، Botkonak را از طریق **OAuth 2.0** در Prestia authorize می‌کند؛ authorization code flow پیشنهاد می‌شود.
2. Botkonak مقدار **access token** و در صورت صدور، refresh token را به‌شکل امن و سمت server ذخیره می‌کند.
3. هر API call از Botkonak به Prestia شامل موارد زیر است:

</div>

```http
Authorization: Bearer <access_token>
Accept: application/json
Content-Type: application/json
```

<div dir="rtl" align="right">

4. **Tenant/store scope** باید در سمت Prestia و **server-side از روی token** resolve شود. Botkonak نباید store secretها را در query string ارسال کند.

برای جزئیات کامل، به [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) مراجعه کنید.

## جریان داده در سطح بالا

</div>

```text
┌─────────────┐     OAuth 2.0      ┌──────────────┐
│   Manager   │ ─────────────────► │   Prestia    │
│  (browser)  │                    │  (prestia.ir)│
└─────────────┘                    └──────┬───────┘
                                          │
                              Bearer token API calls
                                          │
┌─────────────┐     sync / fetch   ┌──────▼───────┐
│  Dashboard  │ ◄───────────────── │   Botkonak   │
│  (Next.js)  │   Django REST API  │   Django     │
└─────────────┘                    └──────┬───────┘
                                          │
                              Celery daily report task
                                          │
                                   ┌──────▼───────┐
                                   │ Coordinator  │
                                   │    Agent     │
                                   └──────┬───────┘
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                    Sales Agent    Content Agent    Support Agent
```

<div dir="rtl" align="right">

**مسیر Daily Report که امروز پیاده‌سازی شده است:**

1. manager درخواست `POST /api/reports/generate/` را trigger می‌کند → اجرای Celery task به نام `reports.generate_daily`.
2. Coordinator درخواست `POST /workflows/daily-report` را اجرا می‌کند → سپس Django endpoint به شکل `GET /internal/ai/context/{report_run_id}/` فراخوانی می‌شود.
3. context bundle به Sales Agent، Content Agent و Support Agent به‌صورت parallel داده می‌شود.
4. Coordinator خروجی‌ها را merge می‌کند → سپس `POST /internal/ai/report-runs/{id}/complete/` در Django فراخوانی می‌شود.
5. Dashboard گزارش‌ها و actionها را از Django می‌خواند، نه مستقیماً از Prestia.

Prestia connector باید مطمئن شود که جدول‌های catalog در Django، یا fetchهای runtime، **قبل از مرحله 2** وضعیت داده‌های Prestia را منعکس می‌کنند.

## گروه‌های API برای MVP

| Group | خلاصه endpointهای Prestia | Why |
|-------|----------------------------|-----|
| **Auth** | OAuth token و refresh | اتصال امن |
| **Store** | `GET /store` | timezone، currency و brand voice |
| **Catalog** | `GET /products` و `GET /inventory/low-stock` | Content Agent و Sales Agent |
| **Sales** | `GET /sales/summary` | metrics مربوط به Sales Agent |
| **Support** | `GET /messages/recent` | threadهای مربوط به Support Agent |

فهرست کامل P0 در [11-api-priority-and-mvp-scope.md](./11-api-priority-and-mvp-scope.md) آمده است.

## Non-goals

این مستندات صراحتاً موارد زیر را **انجام نمی‌دهد**:

- پیاده‌سازی APIهای Prestia یا هرگونه connector code برای Botkonak
- تغییر دادن production systemهای Prestia
- تغییر دادن runtime application code در Botkonak
- ساخت OAuth authorization server داخل Botkonak
- تعریف APIهای داخلی Django در Botkonak با مسیر `/internal/ai/*`؛ این‌ها private برای Botkonak هستند و معادل‌های Prestia آن‌ها در اینجا به‌عنوان external contract مستند شده‌اند
- الزام Prestia به پذیرش draftها، discountها یا support replyهای تولیدشده توسط agentها؛ چون در کد فعلی Botkonak هیچ write pathی وجود ندارد

## شواهد از codebase

| Area | Key files |
|------|-----------|
| Domain models | `backend/catalog/models.py`، `backend/stores/models.py`، `backend/tenants/models.py` |
| Aggregation services | `backend/catalog/services.py`، `backend/catalog/context.py` |
| Internal AI read APIs | `backend/catalog/internal_views.py`، `backend/accounts/internal_urls.py` |
| Prestia demo seed | `backend/tenants/management/commands/seed_prestia.py` |
| Agents | `agents/sales/`، `agents/content/`، `agents/support/`، `agents/coordinator/` |
| Daily report orchestration | `backend/operations/tasks.py`، `agents/coordinator/nodes.py` |
| Agent documentation | `docs/agents/*.md` |
| Phase 3 data contracts | `docs/phases/step-3.2.md` تا `step-3.5.md` |

## سؤال‌های باز

1. **Prestia API base URL و versioning** — در این repository تعریف نشده است؛ در exampleها مقدار `https://api.prestia.ir/v1` فرض شده است.
2. **جایگاه Connector** — در کد هنوز مشخص نشده که sync داخل Django انجام شود یا runtime proxy به Prestia استفاده شود.
3. **fieldهای catalog به فارسی یا انگلیسی** — seed از نام‌های انگلیسی product استفاده می‌کند؛ Prestia در production ممکن است از فارسی، یعنی `fa`، با conventionهای متفاوت برای slug استفاده کند.
4. **Instagram DM ingestion** — Botkonak انتظار threadهایی با `platform: "instagram"` را دارد؛ اما مشخص نیست Prestia integration بومی Instagram دارد یا یک unified inbox API expose می‌کند.

</div>
