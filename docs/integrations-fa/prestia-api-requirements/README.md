<div dir="rtl" align="right">

# نیازمندی‌های API برای Prestia ↔ Botkonak

## هدف این مستندات

این directory، **APIهای خارجی‌ای را مستند می‌کند که Prestia (prestia.ir) باید expose کند** تا Botkonak بتواند به‌عنوان یک لایه هوشمند مدیریت فروشگاه برای یک فروشگاه Prestia متصل‌شده عمل کند. این نیازمندی‌ها از codebase موجود Botkonak استخراج شده‌اند — modelها، internal AI serviceها، agentها، workflow مربوط به Coordinator و dashboard — نه از فرضیات عمومی e-commerce.

**Prestia اولین demo tenant** در Botkonak است (`seed_prestia`)، اما platform به‌صورت multi-tenant طراحی شده است. این contractها توضیح می‌دهند هر integration فروشگاه Prestia چه داده‌ای باید فراهم کند؛ این‌ها code pathهای runtime مخصوص Prestia داخل Botkonak نیستند.

## خلاصه Integration

| Aspect | وضعیت فعلی Botkonak | integration هدف با Prestia |
|--------|----------------------|-----------------------------|
| Data source | PostgreSQL از طریق Django modelها؛ demo data از `seed_prestia` | APIهای Prestia به‌عنوان system of record (یا sync source) |
| Auth به external store | پیاده‌سازی نشده | OAuth 2.0 access token؛ `Authorization: Bearer <token>` |
| مسیر داده برای Agentها | Coordinator → Django `GET /internal/ai/context/{report_run_id}/` | Botkonak connector از Prestia fetch می‌کند، داخل Django normalize می‌کند (یا در runtime Prestia را فراخوانی می‌کند) |
| Write back به store | پیاده‌سازی نشده (actionها internal approval stub هستند) | Future / optional |

Botkonak امروز **prestia.ir را فراخوانی نمی‌کند**. داده‌های شکل‌گرفته Prestia را به‌صورت local mirror می‌کند. این مستندات contract سمت Prestia را برای connector واقعی تعریف می‌کند.

## نقشه Directory

| File | Contents |
|------|----------|
| [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) | OAuth 2.0، Bearer headerها، scopeها، چرخه عمر token |
| [01-shared-data-contracts.md](./01-shared-data-contracts.md) | typeهای مشترک، pagination، errorها، field mappingها |
| [02-store-profile-apis.md](./02-store-profile-apis.md) | Botkonak tenant settings (نه API مربوط به Prestia) |
| [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) | products، categories، variant inventories |
| [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) | orders (sales summary توسط Botkonak محاسبه می‌شود) |
| [05-customer-apis.md](./05-customer-apis.md) | customer recordها و order history (نیاز فعلی محدود) |
| [06-content-agent-apis.md](./06-content-agent-apis.md) | APIهایی که Content Agent مصرف می‌کند (مستقیم یا از طریق sync) |
| [07-sales-agent-apis.md](./07-sales-agent-apis.md) | APIهایی که Sales Agent مصرف می‌کند |
| [08-support-agent-apis.md](./08-support-agent-apis.md) | APIهایی که Support Agent مصرف می‌کند |
| [09-coordinator-agent-and-dashboard-apis.md](./09-coordinator-agent-and-dashboard-apis.md) | نیازهای context برای Coordinator و پیامدهای dashboard |
| [10-sync-webhooks-and-refresh-strategy.md](./10-sync-webhooks-and-refresh-strategy.md) | on-demand API fetch + webhook ingestion برای messageها |
| [11-api-priority-and-mvp-scope.md](./11-api-priority-and-mvp-scope.md) | دسته‌بندی P0 تا Future و سؤال‌های باز |
| [12-full-api-index.md](./12-full-api-index.md) | جدول کامل index مربوط به APIها |

## Botkonak چگونه با Prestia احراز هویت می‌کند؟

1. manager فروشگاه Botkonak را از طریق **OAuth 2.0** در Prestia authorize می‌کند (authorization code flow پیشنهاد می‌شود).
2. Botkonak **access token** (و refresh token در صورت صدور) را به‌صورت امن سمت server ذخیره می‌کند.
3. هر API call از Botkonak به Prestia شامل موارد زیر است:

<div dir="ltr" align="left">

```http
Authorization: Bearer <access_token>
Accept: application/json
Content-Type: application/json
```

</div>

4. **Tenant/store scope** باید در سمت Prestia و **server-side از روی token** resolve شود. Botkonak نباید store secretها را در query string ارسال کند.

برای جزئیات کامل به [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md) مراجعه کنید.

## جریان داده در سطح بالا

<div dir="ltr" align="left">

```
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

</div>

**مسیر Daily Report (امروز پیاده‌سازی شده):**

1. manager درخواست `POST /api/reports/generate/` را trigger می‌کند → Celery `reports.generate_daily`.
2. Coordinator `POST /workflows/daily-report` → Django `GET /internal/ai/context/{report_run_id}/`.
3. context bundle به Sales Agent، Content Agent و Support Agent به‌صورت parallel داده می‌شود.
4. Coordinator خروجی‌ها را merge می‌کند → Django `POST /internal/ai/report-runs/{id}/complete/`.
5. Dashboard گزارش‌ها و actionها را از Django می‌خواند (نه مستقیماً از Prestia).

Prestia connector باید مطمئن شود جدول‌های catalog در Django (یا fetchهای runtime) وضعیت Prestia را **قبل از مرحله 2** منعکس می‌کنند.

## گروه‌های API برای MVP

| Group | خلاصه endpointهای Prestia | Why |
|-------|----------------------------|-----|
| **Auth** | OAuth token (+ refresh) | اتصال امن |
| **Catalog** | `GET /products` | Content Agent + Sales Agent |
| **Orders** | `GET /orders` | Sales Agent summary را به‌صورت local محاسبه می‌کند |
| **Support** | `GET /faqs` + website message webhook | پاسخ FAQ + inbox بلادرنگ |
| **Settings** | *(Botkonak UI)* | brand voice، timezone، currency |

فهرست کامل P0: [11-api-priority-and-mvp-scope.md](./11-api-priority-and-mvp-scope.md).

## Non-goals

این مستندات صراحتاً موارد زیر را **انجام نمی‌دهد**:

- پیاده‌سازی APIهای Prestia یا connector code در Botkonak
- تغییر production systemهای Prestia
- تغییر runtime application code در Botkonak
- ساخت OAuth authorization server داخل Botkonak
- تعریف APIهای داخلی Django در Botkonak با مسیر `/internal/ai/*` (این‌ها private برای Botkonak هستند؛ معادل‌های Prestia به‌عنوان external contract مستند شده‌اند)
- الزام Prestia به پذیرش draftها، discountها یا support replyهای تولیدشده توسط agentها (write path در کد فعلی Botkonak وجود ندارد)

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
| Phase 3 data contracts | `docs/phases/step-3.2.md` – `step-3.5.md` |

## سؤال‌های باز

1. **Prestia API base URL و versioning** — در این repository تعریف نشده (در exampleها `https://api.prestia.ir/v1` فرض شده).
2. **جایگاه Connector** — sync داخل Django در مقابل runtime proxy به Prestia در کد مشخص نشده.
3. **fieldهای catalog به فارسی یا انگلیسی** — seed از نام‌های انگلیسی product استفاده می‌کند؛ Prestia در production ممکن است فارسی (`fa`) با conventionهای متفاوت slug داشته باشد.
4. **Instagram / Telegram / website message ingestion** — Support Agent از webhook استفاده می‌کند؛ website chat در Prestia باید messageها را به Botkonak forward کند.

</div>
