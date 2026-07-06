<div dir="rtl" align="right">

# استراتژی Sync، Webhook و Refresh

این سند توضیح می‌دهد که Botkonak بر اساس معماری **موجود**، چگونه باید داده‌های Prestia را تازه و به‌روز نگه دارد.

## وضعیت فعلی؛ بدون Prestia Connector

| Mechanism         | چیزی که وجود دارد                                                             | نقش Prestia                               |
| ----------------- | ----------------------------------------------------------------------------- | ----------------------------------------- |
| Demo seed         | `python manage.py seed_prestia`                                               | fixture data ثابت با شکل داده‌های Prestia |
| Message import    | دستور `import_messages_json`                                                  | import از فایل JSON، نه live API          |
| Daily report      | اجرای زمان‌بندی‌شده یا triggerشده Celery task به نام `reports.generate_daily` | فقط **local Django DB** را می‌خواند       |
| Real-time updates | ندارد                                                                         | ندارد                                     |

در حال حاضر **هیچ کد polling، webhook یا OAuth connector** در repository وجود ندارد.

---

## استراتژی پیشنهادی برای MVP: scheduled pull sync

**نوع نیازمندی:** Inferred — برای integration واقعی با Prestia لازم است، اما هنوز پیاده‌سازی نشده است.

### چه زمانی Sync انجام شود؟

| Trigger                     | Rationale                                                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **قبل از daily report**     | context مربوط به Coordinator باید وضعیت فعلی Prestia را منعکس کند؛ مسیر `backend/operations/tasks.py` → coordinator → context bundle |
| **Periodic background job** | برای مثال هر 15 تا 60 دقیقه برای catalog/inventory/messages بین reportها                                                             |
| **هنگام OAuth connect**     | initial full sync بعد از authorization                                                                                               |

### چه چیزهایی Sync شوند؟ Pull endpoints

| Prestia endpoint          | Botkonak target             | Sync mode                                         |
| ------------------------- | --------------------------- | ------------------------------------------------- |
| `GET /v1/store`           | `Store` و `Tenant.settings` | Full                                              |
| `GET /v1/categories`      | `Category`                  | Full + incremental با `updated_since`             |
| `GET /v1/products`        | `Product`                   | Incremental                                       |
| `GET /v1/inventory`       | `InventoryLevel`            | Incremental                                       |
| `GET /v1/orders`          | `Order` و `OrderItem`       | Incremental بر اساس `placed_at` / `updated_since` |
| `GET /v1/customers`       | `Customer`                  | Incremental                                       |
| `GET /v1/messages/recent` | `MessageThread` و `Message` | Incremental یا window بزرگ‌تر از AI default       |

**Alternative:** هنگام report time، فقط `GET /v1/sales/summary` و `GET /v1/inventory/low-stock` فراخوانی شوند و raw orderها ذخیره نشوند. این روش storage را کاهش می‌دهد، اما امکان drill-down در dashboard را محدود می‌کند.

### پارامترهای Incremental Sync

در list endpointهایی که پشتیبانی می‌کنند، از `updated_since` با فرمت ISO datetime استفاده کنید؛ فایل [01-shared-data-contracts.md](./01-shared-data-contracts.md).

آخرین timestamp مربوط به sync موفق برای هر store باید در Botkonak ذخیره شود؛ به‌عنوان connector metadata، که در schema فعلی وجود ندارد.

### Idempotency

برای جلوگیری از duplicate شدن داده‌ها، مقدارهای `external_id` در Prestia باید با constraintهای unique مربوط به `external_id` / `external_thread_id` / `external_message_id` در Botkonak match شوند؛ فایل `catalog/models.py`.

---

## زمان‌بندی Daily Report

</div>

```text
Manager POST /api/reports/generate/
    → Celery generate_daily
        → (Future) Prestia sync job OR verify sync freshness
        → Coordinator POST /workflows/daily-report
            → Django GET context (local DB)
            → Specialist agents
            → Django POST complete
```

<div dir="rtl" align="right">

Botkonak همین حالا هم با constraint به نام `unique_active_report_run_per_store` در `operations/models.py`، از اجرای هم‌زمان report runهای concurrent برای یک store جلوگیری می‌کند.

---

## Webhookها؛ اختیاری / آینده

در کد فعلی **لازم نیستند**. هیچ webhook handlerی در Botkonak وجود ندارد.

اگر Prestia webhook اضافه کند، این webhookها می‌توانند latency مربوط به polling را کاهش دهند:

| Webhook event                         | Priority | اقدام Botkonak در آینده                    |
| ------------------------------------- | -------- | ------------------------------------------ |
| `product.created` / `product.updated` | P2       | Upsert کردن `Product`                      |
| `inventory.updated`                   | P1       | Upsert کردن `InventoryLevel`               |
| `order.created` / `order.updated`     | P1       | Upsert کردن `Order`                        |
| `message.received`                    | P1       | Insert کردن `Message` و update کردن thread |
| `store.settings.updated`              | P2       | update کردن brand voice settings           |

### امنیت Webhook؛ در صورت پیاده‌سازی

- verify کردن HMAC signature
- فقط HTTPS
- پردازش idempotent eventها بر اساس `event_id`

**علامت‌گذاری:** Optional (Future) — یک improvement مفید است، اما برای MVP blocker نیست.

---

## On-demand Refresh

| Scenario                                       | Strategy                                                            |
| ---------------------------------------------- | ------------------------------------------------------------------- |
| manager وارد support UI می‌شود                 | فراخوانی `GET /v1/messages/recent`؛ در آینده وقتی frontend وصل شود  |
| manager report را trigger می‌کند               | full sync یا incremental sync بلافاصله قبل از Coordinator           |
| Sales Agent با `fetch_from_django` اجرا می‌شود | بعد از sync، local DB را می‌خواند؛ Prestia را live فراخوانی نمی‌کند |

Sales Agent و Support Agent از flagهای `fetch_from_django` و `fetch_recent_messages` پشتیبانی می‌کنند، اما Coordinator هر دو را `False` تنظیم می‌کند؛ یعنی context از قبل از طریق bundle preload شده است.

---

## Refresh کردن Token هنگام Sync

Sync jobهای طولانی باید قبل از انقضای OAuth token، از طریق `POST /v1/oauth/token` و refresh grant، token را refresh کنند؛ فایل [00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md).

---

## مدیریت Failure

این بخش باید با patternهای موجود در Botkonak هم‌راستا باشد:

| Failure                          | Behavior                                                                                                                                       |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Prestia API هنگام sync down باشد | error را log کند؛ به‌صورت اختیاری با stale data ادامه دهد و در context bundle مقدار `warnings` اضافه کند؛ تابع `_safe_section` در `context.py` |
| failure در یک section جزئی       | section خالی + warning string؛ مشابه context bundle                                                                                            |
| sync failure قبل از report       | report run fail شود یا با stale data ادامه دهد — **سؤال باز** برای تصمیم محصول                                                                 |

`DjangoClient` برای transient GET failureها retry انجام می‌دهد؛ فایل `agents/shared/django_client/client.py`. Prestia connector هم باید retry policy مشابهی داشته باشد.

---

## شواهد از codebase

| File                                                          | Relevance                                              |
| ------------------------------------------------------------- | ------------------------------------------------------ |
| `backend/tenants/management/commands/seed_prestia.py`         | pattern فعلی برای data ingestion                       |
| `backend/catalog/management/commands/import_messages_json.py` | precedent مربوط به import از JSON                      |
| `backend/operations/tasks.py`                                 | Celery task مربوط به daily report                      |
| `backend/catalog/context.py`                                  | pattern مربوط به partial failure با `_safe_section`    |
| `agents/coordinator/nodes.py`                                 | مقدار `fetch_from_django: False` — رویکرد bundle-first |
| `docs/phases/step-3.5.md`                                     | طراحی context bundle                                   |

## سؤال‌های باز

1. حداکثر stale بودن قابل‌قبول برای inventory هنگام daily report چقدر است؟
2. آیا Botkonak باید full order history را ذخیره کند یا فقط rolling 7-day window کافی است؟
3. آیا webhook در Prestia در دسترس است و event catalog آن چیست؟
4. rate limitها برای bulk sync در مقایسه با incremental sync چقدر هستند؟

</div>
