<div dir="rtl" align="right">

# احراز هویت و استفاده از Token

نحوه احراز هویت Botkonak هنگام فراخوانی APIهای Prestia.

## نمای کلی

Botkonak با **OAuth 2.0** به Prestia متصل می‌شود. پس از authorization، Botkonak APIهای REST Prestia را با **Bearer access token** در header `Authorization` فراخوانی می‌کند. این الگو با فراخوانی APIهای داخلی Django توسط agentهای Botkonak هم‌راستاست (`agents/shared/django_client/client.py`).

**نوع نیازمندی:** استنباط‌شده — هیچ کد OAuth یا connector مربوط به Prestia در repository وجود ندارد. این الگو برای هدف integration لازم است و با استفاده فعلی از `Authorization: Bearer` هماهنگ است.

## Headerهای لازم برای request

هر request از Botkonak به APIهای Prestia **باید** شامل موارد زیر باشد:

<div dir="ltr" align="left">

```http
Authorization: Bearer <access_token>
Accept: application/json
Content-Type: application/json
```

</div>

Header اختیاری correlation (Botkonak همین حالا هم برای Django ارسال می‌کند):

<div dir="ltr" align="left">

```http
X-Request-ID: <uuid-or-trace-id>
```

</div>

## شناسایی Tenant

در integration صحیح OAuth 2.0:

- **access token نماینده فروشگاه/tenant مجاز Prestia** است.
- Prestia **tenant و store scope را server-side از روی token** resolve می‌کند.
- Botkonak **نباید** store ID یا tenant secret را در query parameter برای authentication ارسال کند.
- path parameterهایی مثل `/products` به فروشگاهی که token نشان می‌دهد اعمال می‌شوند، مگر Prestia multi-store token را مستند کرده باشد.

این با model داخلی Botkonak هم‌خوان است: Django `InternalAIAuthentication` مقدار `tenant_id` و `store_id` را از service JWT می‌گیرد، نه از fieldهای request body (`backend/catalog/internal_views.py`).

## مفاهیم OAuth

### Access token

- credential کوتاه‌عمر برای هر API call به Prestia.
- فقط در header `Authorization` با scheme Bearer ارسال می‌شود.
- نباید در URL، query string یا logهای قابل‌مشاهده browser ظاهر شود.

### Refresh token

- **پیشنهاد می‌شود (P1)** برای اتصال بلندمدت Botkonak بدون consent مکرر manager.
- Botkonak آن را در token endpoint Prestia با access token جدید عوض می‌کند.
- در کد فعلی Botkonak ارجاعی ندارد (service JWTها per report run صادر می‌شوند).

### انقضای token

- Prestia باید `expires_in` (ثانیه) هنگام صدور token برگرداند.
- Botkonak باید قبل از انقضا refresh یا re-authorize کند.
- token منقضی → Prestia `401 Unauthorized` با error body قابل‌خواندن برای ماشین برمی‌گرداند.

### Token scopeها

scopeها باید **از read APIهایی که Botkonak واقعاً نیاز دارد** استخراج شوند. لیست پیشنهادی:

| Scope | نگاشت به گروه API Prestia | موردنیاز در codebase |
|-------|---------------------------|----------------------|
| `read:products` | Products، categories | بله — Content Agent، Sales Agent، context bundle |
| `read:orders` | Orders | بله — sales aggregation (محاسبه local) |
| `read:customers` | Customer list | بله — Support CRM sync |
| `read:faqs` | FAQ list | بله — Support Agent |
| `write:support_replies` | ارسال support reply | **لازم نیست** — write به Prestia در کد وجود ندارد |
| `write:content_drafts` | انتشار content | **لازم نیست** — draftها در Botkonak می‌مانند |
| `write:recommendations` | اعمال discount/restock | **لازم نیست** — actionها approval stub هستند |

**لازم نیست:** `read:store` (Botkonak tenant settings)، `read:analytics` (بدون sales summary Prestia)، `read:inventory` (inventory روی products)، `read:support_messages` (webhook ingestion).

### لغو token

- Prestia باید هنگام disconnect کردن Botkonak توسط manager، revocation را پشتیبانی کند.
- پس از revocation، access و refresh tokenهای قبلی باید رد شوند (`401`).

### نحوه اعتبارسنجی token توسط Prestia

1. تأیید signature (JWT) یا lookup (opaque token) در هر request.
2. بررسی expiration و وضعیت revocation.
3. اعمال scope per endpoint.
4. bind کردن token به دقیقاً یک store (و tenant) برای use case Botkonak.
5. برگرداندن `403 Forbidden` وقتی token معتبر است اما scope کافی ندارد.

### چرا Botkonak نباید token را در query parameter ارسال کند

- query string در logهای proxy، history browser و referrer header ظاهر می‌شود.
- OAuth 2.0 Bearer Token Usage (RFC 6750) header `Authorization` را مشخص می‌کند.
- `DjangoClient` در Botkonak فقط از auth مبتنی بر header استفاده می‌کند (`agents/shared/django_client/client.py`).

### چرا HTTPS لازم است

- Bearer token معادل password برای دسترسی API است.
- همه endpointهای OAuth و API Prestia باید TLS (`https://`) داشته باشند.

## endpointهای OAuth (Prestia باید expose کند)

### 1. Authorization endpoint

| Property | Value |
|----------|-------|
| **API name** | OAuth 2.0 Authorization |
| **HTTP method** | `GET` (browser redirect) |
| **Suggested path** | `https://prestia.ir/oauth/authorize` |
| **Botkonak consumer** | Admin onboarding / Background sync (token acquisition) |
| **Requirement type** | Inferred |
| **Priority** | P0 |

**Query parameterها:** `client_id`، `redirect_uri`، `response_type=code`، `scope`، `state`

**نتیجه موفق:** redirect به Botkonak با `code` و `state`.

### 2. Token endpoint

| Property | Value |
|----------|-------|
| **API name** | OAuth 2.0 Token Exchange |
| **HTTP method** | `POST` |
| **Suggested path** | `https://api.prestia.ir/v1/oauth/token` |
| **Botkonak consumer** | Background sync، Coordinator (از طریق credential ذخیره‌شده) |
| **Requirement type** | Inferred |
| **Priority** | P0 |

**Request body (authorization code grant):**

<div dir="ltr" align="left">

```json
{
  "grant_type": "authorization_code",
  "code": "<authorization_code>",
  "redirect_uri": "https://botkonak.example/oauth/callback",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>"
}
```

</div>

**Request body (refresh grant):**

<div dir="ltr" align="left">

```json
{
  "grant_type": "refresh_token",
  "refresh_token": "<refresh_token>",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>"
}
```

</div>

**Successful response:**

<div dir="ltr" align="left">

```json
{
  "access_token": "prestia_at_abc123",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "prestia_rt_xyz789",
  "scope": "read:products read:orders read:customers read:faqs"
}
```

</div>

**Error caseها:** `400` invalid_grant، `401` invalid_client

### 3. Token revocation endpoint

| Property | Value |
|----------|-------|
| **API name** | OAuth 2.0 Token Revocation |
| **HTTP method** | `POST` |
| **Suggested path** | `https://api.prestia.ir/v1/oauth/revoke` |
| **Botkonak consumer** | Admin Dashboard (disconnect store) |
| **Requirement type** | Inferred |
| **Priority** | P1 |

## نمونه request احراز هویت‌شده

<div dir="ltr" align="left">

```http
GET /v1/products?is_active=true&limit=100 HTTP/1.1
Host: api.prestia.ir
Authorization: Bearer prestia_at_abc123
Accept: application/json
X-Request-ID: 7c9e6679-7425-40de-944b-e07fc1f90ae7
```

</div>

## نکات امنیتی

- `client_secret`، access token و refresh token فقط در backend Botkonak ذخیره شوند؛ هرگز در bundleهای Next.js client.
- tokenها هنگام تغییر scope یا انتقال مالکیت store rotate شوند.
- `X-Request-ID` برای debug بین سرویس‌ها log شود؛ هرگز token کامل log نشود (Coordinator همین حالا از log کردن JWT خودداری می‌کند — `docs/agents/coordinator.md`).

## شواهد از codebase

- `agents/shared/django_client/client.py` — `_build_headers()` مقدار `Authorization: Bearer`، `Accept`، `Content-Type` را تنظیم می‌کند
- `backend/accounts/authentication.py`، `backend/accounts/service_jwt.py` — الگوی internal JWT برای AI serviceها
- `docs/phases/step-2.2.md` — طراحی internal AI auth
- `backend/catalog/internal_views.py` — store scope از identity token، نه فقط URL

## سؤال‌های باز

1. OAuth flow دقیق Prestia (authorization code در مقابل client credentials برای server-to-server).
2. Prestia JWT یا opaque access token صادر می‌کند.
3. آیا یک حساب Prestia می‌تواند چند store را authorize کند (Botkonak `Store` per-tenant scoped است).

</div>
