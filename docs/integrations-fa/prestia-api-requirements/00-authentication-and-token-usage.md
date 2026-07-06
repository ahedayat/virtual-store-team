<div dir="rtl" align="right">

# احراز هویت و استفاده از Token

این سند توضیح می‌دهد که Botkonak هنگام فراخوانی APIهای Prestia باید چگونه احراز هویت کند.

## نمای کلی

Botkonak با استفاده از **OAuth 2.0** به Prestia متصل می‌شود. بعد از انجام authorization، Botkonak APIهای REST مربوط به Prestia را با یک **Bearer access token** در header به نام `Authorization` فراخوانی می‌کند. این الگو با روشی که agentهای Botkonak در حال حاضر برای فراخوانی APIهای داخلی Django استفاده می‌کنند هم‌راستا است؛ یعنی همان فایل `agents/shared/django_client/client.py`.

**نوع نیازمندی:** استنباط‌شده — در حال حاضر هیچ کد OAuth یا connector مربوط به Prestia در repository وجود ندارد. این الگو برای هدف integration اعلام‌شده لازم است و با استفاده فعلی از `Authorization: Bearer` هماهنگ است.

## Headerهای لازم برای request

هر request از Botkonak به APIهای Prestia **باید** شامل headerهای زیر باشد:

</div>

```http
Authorization: Bearer <access_token>
Accept: application/json
Content-Type: application/json
```

<div dir="rtl" align="right">

Header اختیاری برای correlation، که Botkonak همین حالا هم آن را برای Django ارسال می‌کند:

</div>

```http
X-Request-ID: <uuid-or-trace-id>
```

<div dir="rtl" align="right">

## شناسایی Tenant

در یک integration درست مبتنی بر OAuth 2.0:

- **access token نماینده فروشگاه/tenant مجازشده در Prestia است**.
- Prestia باید **tenant و store scope را سمت server** و از روی token تشخیص دهد.
- Botkonak **نباید** برای authentication، شناسه store یا secret مربوط به tenant را در query parameterها ارسال کند.
- پارامترهای مسیر مثل `/products` باید برای همان فروشگاهی اعمال شوند که از token برداشت می‌شود؛ مگر اینکه Prestia به‌صورت رسمی multi-store tokenها را مستند کرده باشد.

این مدل مشابه مدل داخلی Botkonak است: در Django، کلاس `InternalAIAuthentication` مقدارهای `tenant_id` و `store_id` را از service JWT استخراج می‌کند، نه از fieldهای موجود در request body. این موضوع در فایل `backend/catalog/internal_views.py` دیده می‌شود.

## مفاهیم OAuth

### Access token

- credential کوتاه‌مدتی است که در هر فراخوانی APIهای Prestia استفاده می‌شود.
- فقط باید در header به نام `Authorization` و با Bearer scheme ارسال شود.
- نباید در URL، query string یا logهایی که در browser قابل مشاهده‌اند ظاهر شود.

### Refresh token

- برای اتصال‌های بلندمدت Botkonak، بدون نیاز به گرفتن consent تکراری از manager، **پیشنهاد می‌شود (P1)**.
- Botkonak آن را در token endpoint مربوط به Prestia با یک access token جدید exchange می‌کند.
- در کد فعلی Botkonak به آن اشاره‌ای نشده است، چون service JWTها برای هر report run جداگانه mint می‌شوند.

### انقضای Token

- Prestia باید هنگام صدور token مقدار `expires_in` را بر حسب ثانیه برگرداند.
- Botkonak باید قبل از انقضا token را refresh کند یا authorization را دوباره انجام دهد.
- اگر token منقضی شده باشد، Prestia باید پاسخ `401 Unauthorized` را همراه با یک error body قابل‌خواندن توسط ماشین برگرداند.

### Scopeهای Token

Scopeها باید از روی read APIهایی استخراج شوند که Botkonak واقعاً به آن‌ها نیاز دارد. فهرست پیشنهادی scopeها:

| Scope                   | نگاشت به گروه API در Prestia | موردنیاز در codebase                                                   |
| ----------------------- | ---------------------------- | ---------------------------------------------------------------------- |
| `read:store`            | Store profile                | بله — context bundle شامل `store` و `tenant`                           |
| `read:products`         | Products و categories        | بله — content agent و context bundle                                   |
| `read:inventory`        | Inventory و low-stock        | بله — sales agent                                                      |
| `read:orders`           | Orders و sales summary       | بله — sales aggregation                                                |
| `read:customers`        | Customer list                | محدود — فقط برای sync؛ AI APIها از `customer_ref` مبهم استفاده می‌کنند |
| `read:support_messages` | Recent message threads       | بله — support agent                                                    |
| `read:analytics`        | Pre-aggregated sales summary | بله — اگر sales summary یک endpoint اختصاصی باشد                       |
| `write:support_replies` | Post support replies         | **لازم نیست** — در کد فعلی هیچ write outbound به Prestia وجود ندارد    |
| `write:content_drafts`  | Publish content              | **لازم نیست** — draftها داخل Botkonak باقی می‌مانند                    |
| `write:recommendations` | Apply discounts/restock      | **لازم نیست** — actionها در حد approval stub هستند                     |

### لغو Token یا Token revocation

- Prestia باید از revocation پشتیبانی کند تا وقتی manager اتصال Botkonak را قطع می‌کند، tokenها باطل شوند.
- بعد از revocation، همه access tokenها و refresh tokenهای قبلاً صادرشده باید رد شوند و پاسخ `401` برگردد.

### Prestia چگونه باید Tokenها را validate کند؟

1. در هر request، signature مربوط به JWT را verify کند یا در صورت استفاده از opaque token، token را lookup کند.
2. وضعیت expiration و revocation را بررسی کند.
3. Scopeها را برای هر endpoint enforce کند.
4. برای use case مربوط به Botkonak، token را دقیقاً به یک store و tenant bind کند.
5. وقتی token معتبر است اما scope لازم را ندارد، پاسخ `403 Forbidden` برگرداند.

### چرا Botkonak نباید Tokenها را در query parameter ارسال کند؟

- Query stringها در proxy logها، browser history و referrer headerها ظاهر می‌شوند.
- استاندارد OAuth 2.0 Bearer Token Usage یعنی RFC 6750 استفاده از header به نام `Authorization` را مشخص می‌کند.
- `DjangoClient` در Botkonak همین حالا هم فقط از auth مبتنی بر header استفاده می‌کند؛ یعنی فایل `agents/shared/django_client/client.py`.

### چرا HTTPS لازم است؟

- Bearer tokenها برای دسترسی API عملاً معادل password هستند.
- همه endpointهای OAuth و API در Prestia باید از TLS و آدرس‌های `https://` استفاده کنند.

## Endpointهای OAuth که Prestia باید expose کند

### 1. Authorization endpoint

| Property                   | Value                                                     |
| -------------------------- | --------------------------------------------------------- |
| **نام API**                | OAuth 2.0 Authorization                                   |
| **HTTP method**            | `GET`، از طریق browser redirect                           |
| **مسیر پیشنهادی**          | `https://prestia.ir/oauth/authorize`                      |
| **مصرف‌کننده در Botkonak** | Admin onboarding / Background sync برای token acquisition |
| **نوع نیازمندی**           | استنباط‌شده                                               |
| **Priority**               | P0                                                        |

**Query parameterها:** `client_id`، `redirect_uri`، `response_type=code`، `scope`، `state`

**نتیجه موفق:** redirect به Botkonak همراه با `code` و `state`.

### 2. Token endpoint

| Property                   | Value                                                         |
| -------------------------- | ------------------------------------------------------------- |
| **نام API**                | OAuth 2.0 Token Exchange                                      |
| **HTTP method**            | `POST`                                                        |
| **مسیر پیشنهادی**          | `https://api.prestia.ir/v1/oauth/token`                       |
| **مصرف‌کننده در Botkonak** | Background sync و Coordinator از طریق credentialهای ذخیره‌شده |
| **نوع نیازمندی**           | استنباط‌شده                                                   |
| **Priority**               | P0                                                            |

**Request body برای authorization code grant:**

</div>

```json
{
  "grant_type": "authorization_code",
  "code": "<authorization_code>",
  "redirect_uri": "https://botkonak.example/oauth/callback",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>"
}
```

<div dir="rtl" align="right">

**Request body برای refresh grant:**

</div>

```json
{
  "grant_type": "refresh_token",
  "refresh_token": "<refresh_token>",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>"
}
```

<div dir="rtl" align="right">

**Response موفق:**

</div>

```json
{
  "access_token": "prestia_at_abc123",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "prestia_rt_xyz789",
  "scope": "read:store read:products read:inventory read:orders read:support_messages read:analytics"
}
```

<div dir="rtl" align="right">

**Error caseها:** `400` برای `invalid_grant`، و `401` برای `invalid_client`

### 3. Token revocation endpoint

| Property                   | Value                                      |
| -------------------------- | ------------------------------------------ |
| **نام API**                | OAuth 2.0 Token Revocation                 |
| **HTTP method**            | `POST`                                     |
| **مسیر پیشنهادی**          | `https://api.prestia.ir/v1/oauth/revoke`   |
| **مصرف‌کننده در Botkonak** | Admin Dashboard برای disconnect کردن store |
| **نوع نیازمندی**           | استنباط‌شده                                |
| **Priority**               | P1                                         |

## نمونه request احرازهویت‌شده به API

</div>

```http
GET /v1/products?is_active=true&limit=100 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
X-Request-ID: 7c9e6679-7425-40de-944b-e07fc1f90ae7
```

<div dir="rtl" align="right">

## نکات امنیتی

- مقدارهای `client_secret`، access tokenها و refresh tokenها را فقط در backend مربوط به Botkonak ذخیره کنید؛ هرگز آن‌ها را داخل bundleهای client مربوط به Next.js قرار ندهید.
- در صورت تغییر scopeها یا انتقال مالکیت store، tokenها را rotate کنید.
- برای debug بین سرویس‌ها، مقدار `X-Request-ID` را log کنید؛ اما هرگز token کامل را log نکنید. Coordinator در Botkonak همین حالا هم از log کردن JWTها پرهیز می‌کند؛ این موضوع در `docs/agents/coordinator.md` آمده است.

## شواهد از codebase

- `agents/shared/django_client/client.py` — تابع `_build_headers()` مقدارهای `Authorization: Bearer`، `Accept` و `Content-Type` را تنظیم می‌کند.
- `backend/accounts/authentication.py` و `backend/accounts/service_jwt.py` — الگوی JWT داخلی برای AI serviceها.
- `docs/phases/step-2.2.md` — طراحی internal AI auth.
- `backend/catalog/internal_views.py` — store scope از هویت token گرفته می‌شود، نه فقط از URL.

## سؤال‌های باز

1. Prestia دقیقاً از کدام OAuth flow پشتیبانی می‌کند: authorization code یا client credentials برای server-to-server؟
2. آیا Prestia access token را به شکل JWT صادر می‌کند یا opaque access token؟
3. آیا یک Prestia account می‌تواند چند store را authorize کند؟ چون در Botkonak، هر `Store` در scope یک tenant تعریف می‌شود.

</div>
