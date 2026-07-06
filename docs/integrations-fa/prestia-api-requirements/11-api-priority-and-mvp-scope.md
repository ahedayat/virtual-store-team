<div dir="rtl" align="right">

# Priority و Scope مربوط به APIها برای MVP

این سند، همه APIهای Prestia را که در این مجموعه مستندات شناسایی شده‌اند، دسته‌بندی می‌کند.

## راهنمای Priority

| Priority   | Meaning                                                                            |
| ---------- | ---------------------------------------------------------------------------------- |
| **P0**     | برای MVP لازم است — workflow مربوط به daily report بدون این داده نمی‌تواند کار کند |
| **P1**     | مهم است — برای sync قابل‌اعتماد، reconciliation یا کیفیت عملیاتی لازم است          |
| **P2**     | خوب است داشته باشیم — بعضی flowهای خاص را بهتر می‌کند، اما blocker نیست            |
| **Future** | برای integration اولیه Botkonak + Prestia لازم نیست                                |

## راهنمای Requirement Type

| Type              | Meaning                                                                        |
| ----------------- | ------------------------------------------------------------------------------ |
| **Direct**        | به‌صورت صریح توسط code pathهای موجود در Botkonak لازم است                      |
| **Inferred**      | از نظر منطقی برای integration لازم است، اما connector/sync هنوز ساخته نشده است |
| **Optional**      | enhancement مفید است؛ اما dependency فعلی در کد ندارد                          |
| **Open question** | از روی codebase قابل تأیید نیست                                                |

---

## P0 — لازم برای MVP

| API                     | Method | Endpoint                  | Used by                         | Type     |
| ----------------------- | ------ | ------------------------- | ------------------------------- | -------- |
| OAuth Authorization     | `GET`  | `/oauth/authorize`        | Onboarding                      | Inferred |
| OAuth Token             | `POST` | `/v1/oauth/token`         | Background sync                 | Inferred |
| Get Store Profile       | `GET`  | `/v1/store`               | Coordinator، Content، Dashboard | Direct   |
| List Products           | `GET`  | `/v1/products`            | Content، Coordinator            | Direct   |
| Get Sales Summary       | `GET`  | `/v1/sales/summary`       | Sales، Coordinator              | Direct   |
| Get Low Stock Inventory | `GET`  | `/v1/inventory/low-stock` | Sales، Coordinator              | Direct   |
| Get Recent Messages     | `GET`  | `/v1/messages/recent`     | Support، Coordinator            | Direct   |

**خروجی MVP:** manager فروشگاه Prestia را connect می‌کند → Botkonak داده‌های P0 را sync می‌کند → daily report خروجی‌های Sales Agent، Content Agent و Support Agent را تولید می‌کند.

---

## P1 — مهم، اما blocker نیست

| API                    | Method | Endpoint                            | Used by                               | Type     |
| ---------------------- | ------ | ----------------------------------- | ------------------------------------- | -------- |
| OAuth Token Revocation | `POST` | `/v1/oauth/revoke`                  | Dashboard disconnect                  | Inferred |
| OAuth Token Refresh    | `POST` | `/v1/oauth/token`، با refresh grant | Background sync                       | Inferred |
| List Categories        | `GET`  | `/v1/categories`                    | Background sync                       | Inferred |
| List Inventory         | `GET`  | `/v1/inventory`                     | Background sync                       | Inferred |
| List Orders            | `GET`  | `/v1/orders`                        | Background sync، sales reconciliation | Inferred |
| Aggregated Context     | `GET`  | `/v1/context`                       | connector optimization                | Inferred |

---

## P2 — خوب است داشته باشیم

| API                 | Method | Endpoint            | Used by         | Type     |
| ------------------- | ------ | ------------------- | --------------- | -------- |
| Get Product Detail  | `GET`  | `/v1/products/{id}` | Content Agent   | Inferred |
| Get Order Detail    | `GET`  | `/v1/orders/{id}`   | Support Agent   | Inferred |
| List Customers      | `GET`  | `/v1/customers`     | Background sync | Inferred |
| Get Tenant Settings | `GET`  | `/v1/tenant`        | Content Agent   | Inferred |

---

## Future / optional

| API                        | Method  | Endpoint                            | Used by                  | Type                                                        |
| -------------------------- | ------- | ----------------------------------- | ------------------------ | ----------------------------------------------------------- |
| List Draft/Pending Orders  | `GET`   | `/v1/orders?status=draft,pending`   | Sales follow-up          | Optional                                                    |
| Customer Order History     | `GET`   | `/v1/customers/{id}/orders`         | Sales follow-up          | Optional                                                    |
| Send Support Reply         | `POST`  | `/v1/messages/threads/{id}/replies` | action execution         | Optional                                                    |
| Update Product Description | `PATCH` | `/v1/products/{id}`                 | content action execution | Optional                                                    |
| Apply Discount             | `POST`  | `/v1/promotions`                    | sales action execution   | Optional                                                    |
| Analytics / slow-movers    | `GET`   | `/v1/analytics/...`                 | Sales Agent              | Optional                                                    |
| FAQ content API            | `GET`   | `/v1/faqs`                          | Support Agent            | Optional — agent از policy codeها استفاده می‌کند، نه FAQ DB |
| Webhooks، همه eventها      | `POST`  | Botkonak webhook receiver           | Background sync          | Optional                                                    |

---

## مجموعه OAuth Scopeهای MVP

حداقل scopeهای لازم برای APIهای P0:

</div>

```text
read:store read:products read:inventory read:orders read:support_messages read:analytics
```

<div dir="rtl" align="right">

`read:analytics` در صورتی استفاده می‌شود که sales summary اختصاصی به‌عنوان analytics endpoint پیاده‌سازی شود.

**برای MVP لازم نیست:** scopeهای `write:*`، چون در Botkonak هیچ write path فعالی وجود ندارد.

---

## سؤال‌های باز

| #   | Question                                                     | Impact                          |
| --- | ------------------------------------------------------------ | ------------------------------- |
| 1   | base URL و versioning مربوط به Prestia API                   | مثال‌های documentation          |
| 2   | sync کردن داده‌ها داخل Django در برابر runtime Prestia proxy | معماری connector                |
| 3   | endpoint تجمیعی `/v1/context` در برابر endpointهای جداگانه   | طراحی API در سمت Prestia        |
| 4   | منبع Instagram DM در Prestia                                 | امکان‌پذیری P0 برای Support     |
| 5   | نگاشت order statusها                                         | دقت revenue در Sales            |
| 6   | variant modeling                                             | sync مربوط به Product/Inventory |
| 7   | فارسی، یعنی `fa`، به‌عنوان زبان اصلی catalog                 | زبان خروجی Content Agent        |
| 8   | سیاست stale data هنگام sync failure                          | قابلیت اعتماد report            |
| 9   | نوع OAuth flow؛ auth code در برابر client credentials        | UX مربوط به Onboarding          |
| 10  | rate limitها برای initial bulk sync                          | performance مربوط به connector  |

---

## شواهد از codebase

تخصیص priorityها بر اساس موارد زیر انجام شده است:

- `backend/catalog/context.py` — sectionهای context bundle؛ داده‌های P0
- `agents/coordinator/nodes.py` — workflow مربوط به daily report
- `backend/operations/tasks.py` — trigger مربوط به report generation
- `frontend/hooks/*.ts` — dashboard فعلاً فقط mock است؛ live Prestia readها مربوط به آینده هستند
- `backend/operations/tasks.py` — stub مربوط به `execute_action`؛ writeها مربوط به آینده هستند

## Non-goals؛ مرور مجدد

به [README.md](./README.md#non-goals) مراجعه کنید.

</div>
