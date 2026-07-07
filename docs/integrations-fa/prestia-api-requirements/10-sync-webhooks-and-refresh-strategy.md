<div dir="rtl" align="right">

# Sync، Webhook و Refresh Strategy

نحوه تازه نگه‌داشتن داده Prestia در Botkonak بر اساس **مدل integration بازنگری‌شده**.

## وضعیت فعلی (بدون Prestia connector)

| Mechanism | آنچه وجود دارد | نقش Prestia |
|-----------|----------------|-------------|
| Demo seed | `python manage.py seed_prestia` | fixture data با شکل Prestia |
| Message import | command `import_messages_json` | import فایل JSON، نه API زنده |
| Daily report | Celery `reports.generate_daily` زمان‌بندی/trigger | فقط **دیتابیس محلی Django** را می‌خواند |
| به‌روزرسانی بلادرنگ | هیچ | هیچ |

**هیچ polling، webhook یا کد connector OAuth در repository امروز وجود ندارد.**

---

## اصل پایه: on-demand data API + webhook ingestion برای message

| Pattern | Applies to | Behavior |
|---------|------------|----------|
| **On-demand API calls** | Products، orders، customers، FAQها و APIهای داده مشابه | Botkonak Prestia را **هر وقت agent مربوطه به داده تازه نیاز دارد** فراخوانی می‌کند — نه با poll loop دائمی یا webhook sync گسترده |
| **Webhook ingestion** | فقط messageهای Support Agent | تحویل بلادرنگ وقتی کاربران از website، Instagram یا Telegram message می‌فرستند |

**سیستم webhook sync گسترده برای همه داده Prestia را توصیف نکنید** مگر صریحاً به‌عنوان enhancement آینده علامت بخورد.

---

## On-demand API fetch (پیش‌فرض برای همه data API)

### چه موقع Prestia را فراخوانی کنیم

| Trigger | endpointهای Prestia | Rationale |
|---------|---------------------|-----------|
| **قبل از daily report** | `GET /v1/products`، `GET /v1/orders`، `GET /v1/faqs` | context Coordinator باید وضعیت فعلی Prestia را منعکس کند |
| **نیاز agent مشخص** | endpoint مربوط به آن agent | Sales Agent orders + products؛ Content Agent products؛ Support Agent FAQها |
| **در OAuth connect** | fetch اولیه کامل catalog و orderهای تاریخی | bootstrap cache محلی |

### Data APIها (on-demand، نه مبتنی بر webhook)

| Prestia endpoint | Botkonak consumer | Fetch mode |
|------------------|-------------------|------------|
| `GET /v1/products` | Content Agent، Sales Agent، Coordinator | On demand |
| `GET /v1/orders` | Sales Agent، Coordinator | On demand |
| `GET /v1/customers` | Support Agent CRM sync | On demand |
| `GET /v1/faqs` | Support Agent | On demand |
| `GET /v1/categories` | Connector (اختیاری) | On demand |

تنظیمات store profile (`brand_voice`، timezone، currency) **از Prestia fetch نمی‌شوند** — در Botkonak tenant settings پیکربندی می‌شوند ([02-store-profile-apis.md](./02-store-profile-apis.md)).

خلاصه sales **توسط Botkonak** از orders و products محاسبه می‌شود — Prestia `GET /v1/sales/summary` expose نمی‌کند.

### Pagination

از `limit` و `offset` در list endpointها استفاده کنید. connector هنگام ساخت context کامل برای report run همه صفحات را fetch می‌کند.

### Idempotency

شناسه‌های پایدار Prestia (`slug`، `order_id`، `tenant_user_id`) را به fieldهای `external_id` Botkonak map کنید (`catalog/models.py`).

---

## Webhook-based message ingestion (فقط Support Agent)

**تنها integration مبتنی بر webhook که امروز لازم است** ingestion message برای Support Agent است.

| Source | مسیر Webhook | نقش Prestia |
|--------|--------------|-------------|
| Instagram | Platform → Botkonak | relay اختیاری؛ ممکن است مستقیم وصل شود |
| Telegram | Platform → Botkonak | relay اختیاری؛ ممکن است مستقیم وصل شود |
| Website | Prestia → Botkonak | **Prestia باید** messageهای chat وب‌سایت را فوراً به Botkonak بفرستد |

وقتی message می‌رسد:

1. webhook receiver Botkonak signature / secret را validate می‌کند.
2. message در inbox support tenant ذخیره می‌شود.
3. customer record در CRM tenant ایجاد یا به‌روز می‌شود.
4. Support Agent از دیتابیس محلی می‌خواند (نه poll زنده Prestia).

جزئیات کانال: [08-support-agent-apis.md](./08-support-agent-apis.md).

### امنیت Webhook

- تأیید signature HMAC یا shared secret
- فقط HTTPS
- پردازش idempotent بر اساس `message_id` / `external_message_id`

---

## زمان‌بندی daily report

<div dir="ltr" align="left">

```
Manager POST /api/reports/generate/
    → Celery generate_daily
        → On-demand Prestia fetch (products, orders, FAQs)
        → Coordinator POST /workflows/daily-report
            → Django GET context (local DB + fresh fetch results)
            → Specialist agents
            → Django POST complete
```

</div>

Botkonak همین حالا report run همزمان per store را جلوگیری می‌کند (constraint `unique_active_report_run_per_store` در `operations/models.py`).

---

## Enhancementهای آینده (اختیاری — نه MVP)

این‌ها **برای integration اولیه لازم نیستند**:

| Enhancement | Priority | Notes |
|-------------|----------|-------|
| webhook `product.updated` | Future | latency fetch catalog on-demand را کم می‌کند |
| webhook `order.created` | Future | latency fetch order on-demand را کم می‌کند |
| webhook `inventory.updated` | Future | هشدار stock بلادرنگ |
| job sync پس‌زمینه زمان‌بندی‌شده | Future | جایگزین purely on-demand اگر latency مشکل شود |

همه webhookهای داده گسترده را **Future / optional** علامت بزنید — on-demand API callها contract MVP هستند.

---

## سناریوهای refresh on-demand

| Scenario | Strategy |
|----------|----------|
| manager daily report را trigger می‌کند | فوراً قبل از coordinator products، orders، FAQها را از Prestia fetch کنید |
| Support Agent run | messageها از inbox محلی (webhook-ingested)؛ FAQها on-demand |
| Sales Agent run | orders + products on-demand؛ summary محلی محاسبه شود |
| Content Agent run | products on-demand |

---

## Token refresh هنگام fetch

jobهای fetch طولانی باید قبل از انقضا OAuth token را از طریق `POST /v1/oauth/token` (refresh grant) تازه کنند ([00-authentication-and-token-usage.md](./00-authentication-and-token-usage.md)).

---

## مدیریت خطا

هم‌راستا با الگوهای موجود Botkonak:

| Failure | Behavior |
|---------|----------|
| API Prestia هنگام fetch down است | log خطا؛ اختیاری ادامه با داده stale + `warnings` در context bundle (`_safe_section` در `context.py`) |
| خطای جزئی بخش | بخش خالی + رشته warning (مثل context bundle) |
| خطای fetch قبل از report | fail report run یا ادامه با داده stale — **سؤال باز** برای تصمیم محصول |
| خطای تحویل webhook | Prestia/website باید retry کند؛ Botkonak log و alert |

`DjangoClient` روی خطای موقت GET retry می‌کند (`agents/shared/django_client/client.py`). Prestia connector باید policy retry مشابه داشته باشد.

---

## شواهد از codebase

| File | Relevance |
|------|-----------|
| `backend/tenants/management/commands/seed_prestia.py` | الگوی ingestion داده فعلی |
| `backend/catalog/management/commands/import_messages_json.py` | سابقه import JSON |
| `backend/operations/tasks.py` | Celery task daily report |
| `backend/catalog/context.py` | الگوی خطای جزئی `_safe_section` |
| `agents/coordinator/nodes.py` | `fetch_from_django: False` — bundle-first |
| `docs/phases/step-3.5.md` | طراحی context bundle |

## سؤال‌های باز

1. حداکثر staleness قابل‌قبول catalog در daily report وقتی on-demand fetch شکست می‌خورد.
2. آیا Botkonak کل order history را نگه می‌دارد یا فقط پنجره rolling.
3. schema payload webhook chat وب‌سایت Prestia.
4. rate limit برای on-demand bulk fetch در مقابل درخواست صفحه incremental.

</div>
