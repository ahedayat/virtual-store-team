<div dir="rtl" align="right">

# APIهای Content Agent

APIهایی که **Content Agent** برای تولید draftهای caption و product-description به آن‌ها نیاز دارد.

## خلاصه Agent

Content Agent، یعنی `agents/content/`، مقدارهای قابل‌بازبینی از نوع `ContentSuggestions` تولید می‌کند؛ از جمله Instagram captionها با نوع `content.instagram_draft` و product descriptionها با نوع `content.product_description`. این Agent **مستقیماً API خارجی را فراخوانی نمی‌کند** — بلکه context را از Coordinator دریافت می‌کند؛ فایل `docs/agents/content.md`.

برای integration با Prestia، این APIهای Prestia باید داده‌هایی را فراهم کنند که Botkonak بتواند آن‌ها را به context bundle و content specialist payload نگاشت کند.

## جریان داده

</div>

```text
Prestia APIs → Botkonak connector/sync → Django catalog
       ↓
Coordinator GET context bundle (or Prestia aggregated context)
       ↓
Content Agent POST /run { products, store_context }
```

<div dir="rtl" align="right">

## APIهای لازم از Prestia

| Prestia API                                            | ورودی Content Agent                                                    | Priority |
| ------------------------------------------------------ | ---------------------------------------------------------------------- | -------- |
| [GET /v1/store](./02-store-profile-apis.md)            | مقدارهای `store_context.settings.brand_voice`، display name و currency | P0       |
| [GET /v1/products](./03-product-and-inventory-apis.md) | مقدار `products[]` برای promptها                                       | P0       |

## فیلدهای Context که مصرف می‌شوند

### Products؛ فایل `agents/content/product_context.py`

این داده‌ها از مقدار `products.items` در context bundle نرمال‌سازی می‌شوند:

| Field                        | Source                         | Required for drafts                                                    |
| ---------------------------- | ------------------------------ | ---------------------------------------------------------------------- |
| `product_id` / `id`          | مقدار `id` محصول در Prestia    | بله، برای `content.product_description`                                |
| `title` / `name`             | مقدار `name` در Prestia        | بله                                                                    |
| `category` / `category.name` | category به‌صورت nested        | پیشنهاد می‌شود                                                         |
| `price`, `currency`          | product و store                | پیشنهاد می‌شود                                                         |
| `image_url` / `images[0]`    | تصاویر product                 | برای captionهای rich پیشنهاد می‌شود                                    |
| `sku`                        | SKU محصول                      | اختیاری                                                                |
| `metadata`                   | برای مثال `material` و `color` | پیشنهاد می‌شود — guardrailها اجازه invent کردن attributeها را نمی‌دهند |

**در context bundle فعلی وجود ندارد، اما دریافت آن از Prestia ارزشمند است:**

| Field                                  | Requirement type | Notes                                                                                            |
| -------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------ |
| `description`                          | Inferred         | product description موجود به بازنویسی draftها کمک می‌کند؛ روی `Product.description` ذخیره می‌شود |
| `compare_at_price`, `discount_percent` | Optional         | Agent نباید بدون داده، ادعای discount کند؛ guardrailهای فایل `agents/content/prompts.py`         |

### Store context؛ فایل‌های `agents/content/brand_voice.py` و `agents/content/prompts.py`

| Field                              | Source                                              |
| ---------------------------------- | --------------------------------------------------- |
| `display_name`                     | مقدار `store.name` یا `settings.store_display_name` |
| `settings.brand_voice.tone`        | settings فروشگاه در Prestia                         |
| `settings.brand_voice.audience`    | settings فروشگاه در Prestia                         |
| `settings.brand_voice.style_notes` | settings فروشگاه در Prestia                         |
| `settings.brand_voice.language`    | settings فروشگاه در Prestia                         |
| `currency`                         | Store profile                                       |

وقتی settings وجود نداشته باشد، Coordinator از fallback زیر استفاده می‌کند: `{"brand_voice": {"tone": "warm"}}`؛ فایل `agents/coordinator/nodes.py`.

### Campaign angle

مقدار `campaign_angle` در request اجرای content اختیاری است — این مقدار فعلاً از API مربوط به Prestia نمی‌آید.

## رفتار در صورت خالی بودن Products

اگر بعد از sync هیچ productی وجود نداشته باشد، Content Agent بدون فراخوانی LLM یک نتیجه deterministic empty برمی‌گرداند؛ فایل `agents/content/empty_products.py`. برای تولید draftهای معنادار، Prestia باید حداقل یک product فعال expose کند.

## محدودیت تعداد Draftها

مقدار `CONTENT_AGENT_MAX_DRAFTS_PER_RUN` از env خوانده می‌شود و مقدار پیش‌فرض آن 3 است؛ یا می‌تواند از `store.settings.content_agent_max_drafts_per_run` بیاید؛ فایل `agents/content/draft_limit.py`. Prestia می‌تواند این مقدار را در store settings expose کند؛ Priority برابر P2.

## APIهایی که Content Agent به آن‌ها نیاز ندارد

| Data                    | Reason                                                       |
| ----------------------- | ------------------------------------------------------------ |
| Orders و sales summary  | حوزه کاری Sales Agent                                        |
| Support messages        | حوزه کاری Support Agent                                      |
| Customer PII            | به‌صورت صریح در promptها ممنوع است                           |
| FAQ content             | مدل FAQ وجود ندارد؛ Content Agent FAQها را نمی‌خواند         |
| Instagram publish/write | draftها نیازمند approval مدیر هستند؛ مسیر publish وجود ندارد |

## Write APIها در آینده

| API                                       | Status                                                                                                             |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| POST برای update کردن product description | **لازم نیست** — فایل `action_mapping.py` وجود دارد، اما Coordinator مقدار `persist_actions: False` را تنظیم می‌کند |
| POST برای publish در Instagram            | **لازم نیست** — خارج از scope است                                                                                  |

## شواهد از codebase

| File                                | Relevance                            |
| ----------------------------------- | ------------------------------------ |
| `agents/content/analysis.py`        | orchestration مربوط به pipeline      |
| `agents/content/product_context.py` | استخراج product/store                |
| `agents/content/brand_voice.py`     | استخراج brand voice از settings      |
| `agents/content/prompts.py`         | guardrailهای prompt                  |
| `agents/coordinator/nodes.py`       | تابع `_content_specialist_payload()` |
| `backend/catalog/context.py`        | تابع `build_product_summary`         |
| `docs/agents/content.md`            | مستندات Agent                        |
| `docs/examples/content_output.json` | output contract                      |

## سؤال‌های باز

1. آیا Prestia برای `output_language: fa`، متن فارسی product copy را به‌صورت native ارائه می‌کند؟ در حال حاضر Coordinator مقدار `output_language: "en"` را ارسال می‌کند.
2. وضعیت URLهای Image CDN چگونه است؟ آیا برای agent fetch نیاز به authentication یا signed URL وجود دارد؟ البته agentها فقط URLها را در prompt استفاده می‌کنند و image download انجام نمی‌دهند.

</div>
