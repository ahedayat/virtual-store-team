<div dir="rtl" align="right">

# اولویت API و Scope MVP

دسته‌بندی همه APIهای Prestia مستندشده برای integration Botkonak.

## راهنمای اولویت

| Priority | Meaning |
|----------|---------|
| **P0** | لازم برای MVP — workflow daily report بدون این داده کار نمی‌کند |
| **P1** | مهم — برای integration قابل‌اعتماد یا کیفیت عملیاتی لازم است |
| **P2** | خوب است داشته باشیم — جریان‌های خاص را بهتر می‌کند اما blocking نیست |
| **Future** | برای integration اولیه Botkonak + Prestia لازم نیست |

## راهنمای نوع نیازمندی

| Type | Meaning |
|------|---------|
| **Direct** | صریحاً در contract integration بازنگری‌شده لازم است |
| **Inferred** | از نظر منطقی برای integration لازم است اما connector هنوز ساخته نشده |
| **Optional** | enhancement مفید؛ وابستگی کد فعلی ندارد |

---

## P0 — لازم برای MVP

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| OAuth Authorization | `GET` | `/oauth/authorize` | Onboarding | Inferred |
| OAuth Token | `POST` | `/v1/oauth/token` | On-demand fetch | Inferred |
| List Products | `GET` | `/v1/products` | Content، Sales، Coordinator | Direct |
| List Orders | `GET` | `/v1/orders` | Sales، Coordinator | Direct |
| List FAQs | `GET` | `/v1/faqs` | Support | Direct |
| Website message webhook | `POST` | Botkonak receiver | Support | Direct |

**نتیجه MVP:** manager فروشگاه Prestia را وصل می‌کند → Botkonak tenant settings را پیکربندی می‌کند → on-demand fetch Prestia + messageهای webhook → daily report خروجی Sales، Content و Support Agent تولید می‌کند.

**P0 سمت Prestia نیست:** store profile API، sales summary API، message polling API.

---

## P1 — مهم اما blocking نیست

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| OAuth Token Revocation | `POST` | `/v1/oauth/revoke` | Dashboard disconnect | Inferred |
| OAuth Token Refresh | `POST` | `/v1/oauth/token` (refresh grant) | On-demand fetch | Inferred |
| List Categories | `GET` | `/v1/categories` | Connector | Inferred |
| List Customers | `GET` | `/v1/customers` | Support CRM | Inferred |
| Customer Order History | `GET` | `/v1/customer/{tenant_customer_id}/orders` | Support، Sales | Inferred |
| Aggregated Context | `GET` | `/v1/context` | بهینه‌سازی connector | Inferred |

---

## P2 — خوب است داشته باشیم

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| Get Product Detail | `GET` | `/v1/products/{slug}` | Content Agent | Inferred |
| Get Order Detail | `GET` | `/v1/orders/{order_id}` | Support Agent | Inferred |

---

## Future / optional

| API | Method | Endpoint | Used by | Type |
|-----|--------|----------|---------|------|
| List Draft/Pending Orders | `GET` | `/v1/orders?status=draft,pending` | Sales follow-up | Optional |
| Send Support Reply | Outbound | Platform APIها | Action execution | Optional |
| Update Product Description | `PATCH` | `/v1/products/{slug}` | Content action execution | Optional |
| Apply Discount | `POST` | `/v1/promotions` | Sales action execution | Optional |
| Data webhookها (products، orders) | `POST` | Botkonak receiver | بهینه‌سازی latency | Optional |

---

## مجموعه scope OAuth برای MVP

حداقل scopeها برای APIهای P0:

<div dir="ltr" align="left">

```
read:products read:orders read:customers read:faqs
```

</div>

`read:store` و `read:analytics` **لازم نیستند** — تنظیمات store محلی Botkonak است؛ analytics sales از orders محاسبه می‌شود.

webhookهای Instagram/Telegram از credentialهای platform استفاده می‌کنند، نه scope OAuth Prestia.

**برای MVP لازم نیست:** scopeهای `write:*` (write path در Botkonak نیست).

---

## سؤال‌های باز

| # | Question | Impact |
|---|----------|--------|
| 1 | Prestia API base URL و versioning | exampleهای مستندات |
| 2 | On-demand fetch در مقابل sync-into-Django | معماری connector |
| 3 | `/v1/context` aggregate در مقابل endpointهای مجزا | طراحی API سمت Prestia |
| 4 | schema payload webhook chat وب‌سایت | امکان‌پذیری Support P0 |
| 5 | mapping وضعیت order | دقت revenue sales |
| 6 | مدل‌سازی variant `inventories[]` product | دقت سیگنال inventory |
| 7 | فارسی (`fa`) به‌عنوان زبان اصلی catalog | زبان خروجی Content Agent |
| 8 | سیاست داده stale هنگام شکست fetch | قابلیت اطمینان report |
| 9 | نوع OAuth flow (auth code در مقابل client credentials) | UX onboarding |
| 10 | rate limit برای on-demand bulk fetch | عملکرد connector |

---

## شواهد از codebase

تخصیص اولویت بر اساس:

- `backend/catalog/context.py` — بخش‌های context bundle (داده P0)
- `agents/coordinator/nodes.py` — workflow daily report
- `backend/operations/tasks.py` — trigger تولید گزارش
- `frontend/hooks/*.ts` — dashboard فقط mock (Future برای read زنده Prestia)
- `backend/operations/tasks.py` — stub `execute_action` (Future برای write)

## Non-goals (خلاصه)

به [README.md](./README.md#non-goals) مراجعه کنید.

</div>
