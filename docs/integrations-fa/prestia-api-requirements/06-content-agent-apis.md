<div dir="rtl" align="right">

# APIهای Content Agent

APIهای موردنیاز **Content Agent** برای تولید draft caption و توضیح product.

## خلاصه Agent

Content Agent (`agents/content/`) `ContentSuggestions` قابل بررسی با caption اینستاگرام (`content.instagram_draft`) و توضیح product (`content.product_description`) تولید می‌کند. این agent **مستقیماً API خارجی فراخوانی نمی‌کند** — context را از Coordinator دریافت می‌کند (`docs/agents/content.md`).

برای integration Prestia، داده product از Prestia می‌آید؛ پیکربندی brand و store از Botkonak tenant settings.

## جریان داده

<div dir="ltr" align="left">

```
GET /v1/products (on demand) → Botkonak connector
       ↓
Botkonak tenant settings (brand voice, display name, currency)
       ↓
Coordinator GET context bundle
       ↓
Content Agent POST /run { products, store_context }
```

</div>

## APIهای Prestia موردنیاز

| Prestia API | ورودی Content Agent | Priority |
|-------------|---------------------|----------|
| [GET /v1/products](./03-product-and-inventory-apis.md) | `products[]` برای promptها | P0 |

## پیکربندی Botkonak موردنیاز (نه Prestia)

تنظیمات store profile **از Prestia fetch نمی‌شوند**. در UI تنظیمات tenant/store Botkonak پیکربندی کنید:

| Setting | استفاده Content Agent |
|---------|----------------------|
| `settings.brand_voice.tone` | tone draft |
| `settings.brand_voice.audience` | مخاطب هدف |
| `settings.brand_voice.style_notes` | قوانین نگارش |
| `settings.brand_voice.language` | ترجیح زبان خروجی |
| Store display name | context prompt |
| `currency` پیش‌فرض | مرجع قیمت در captionها |

fallback Coordinator وقتی settings گم باشد: `{"brand_voice": {"tone": "warm"}}` (`agents/coordinator/nodes.py`).

## fieldهای context مصرف‌شده

### Products (`agents/content/product_context.py`)

از context bundle `products.items` normalize شده، منبع [GET /v1/products](./03-product-and-inventory-apis.md):

| Field | منبع Prestia | لازم برای draft |
|-------|--------------|-----------------|
| `slug` | `slug` | بله — شناسه product |
| `title` | `title` | بله |
| `category.slug`، `category.title` | `category` nested | توصیه می‌شود |
| `price`، `currency`، `discount` | fieldهای product | توصیه می‌شود |
| `images` | `images[]` | توصیه می‌شود برای caption غنی |
| `inventories[].metadata` | attributeهای variant | اختیاری — color/size در caption |
| `metadata` | metadata سطح product | توصیه می‌شود — guardrail از اختراع attribute جلوگیری می‌کند |
| `description` | `description` | توصیه می‌شود برای draft توضیح product |

**Guardrail agent:** نباید بدون داده `discount` ادعای discount کند (`agents/content/prompts.py`).

### Store context (`agents/content/brand_voice.py`، `agents/content/prompts.py`)

| Field | Source |
|-------|--------|
| `display_name` | Botkonak tenant/store settings |
| `settings.brand_voice.*` | Botkonak tenant/store settings |
| `currency` | Botkonak tenant/store settings (یا `currency` product) |

### Campaign angle

`campaign_angle` اختیاری در content run request — **امروز از API Prestia نیست**.

## رفتار product خالی

اگر پس از fetch هیچ productی نباشد، Content Agent نتیجه deterministic خالی بدون LLM برمی‌گرداند (`agents/content/empty_products.py`). Prestia باید حداقل یک product فعال برای draft معنادار expose کند.

## محدودیت draft

`CONTENT_AGENT_MAX_DRAFTS_PER_RUN` env (پیش‌فرض 3) یا `store.settings.content_agent_max_drafts_per_run` در Botkonak (`agents/content/draft_limit.py`).

## APIهایی که Content Agent نیاز ندارد

| Data | Reason |
|------|--------|
| `GET /v1/store` | store profile همان Botkonak tenant settings است |
| Orders، sales summary | حوزه Sales Agent |
| Support messageها | حوزه Support Agent |
| PII customer | صراحتاً در promptها ممنوع |
| محتوای FAQ | حوزه Support Agent |
| publish/write اینستاگرام | draftها نیاز به تأیید manager دارند؛ مسیر publish نیست |

## Write APIها (Future)

| API | Status |
|-----|--------|
| POST به‌روزرسانی توضیح product | **لازم نیست** — `action_mapping.py` وجود دارد اما coordinator `persist_actions: False` می‌گذارد |
| POST publish اینستاگرام | **لازم نیست** — خارج از scope |

## شواهد از codebase

| File | Relevance |
|------|-----------|
| `agents/content/analysis.py` | orchestration pipeline |
| `agents/content/product_context.py` | استخراج product/store |
| `agents/content/brand_voice.py` | brand voice از تنظیمات محلی |
| `agents/content/prompts.py` | guardrailهای prompt |
| `agents/coordinator/nodes.py` | `_content_specialist_payload()` |
| `backend/catalog/context.py` | `build_product_summary` |
| `docs/agents/content.md` | مستندات agent |
| `docs/examples/content_output.json` | contract خروجی |

## سؤال‌های باز

1. آیا Prestia متن فارسی product را به‌صورت native برای `output_language: fa` فراهم می‌کند (coordinator امروز `output_language: "en"` می‌فرستد).
2. URL CDN تصویر — authentication یا signed URL برای fetch agent (agentها فقط URL در prompt استفاده می‌کنند، تصویر download نمی‌کنند).

</div>
