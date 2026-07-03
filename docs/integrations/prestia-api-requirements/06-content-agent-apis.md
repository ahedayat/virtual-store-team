# Content Agent APIs

APIs required by the **Content Agent** for caption and product-description draft generation.

## Agent summary

The Content Agent (`agents/content/`) generates reviewable `ContentSuggestions` with Instagram captions (`content.instagram_draft`) and product descriptions (`content.product_description`). It does **not** call external APIs directly — it receives context from the Coordinator (`docs/agents/content.md`).

For Prestia integration, these Prestia APIs must supply data that Botkonak maps into the context bundle and content specialist payload.

## Data flow

```
Prestia APIs → Botkonak connector/sync → Django catalog
       ↓
Coordinator GET context bundle (or Prestia aggregated context)
       ↓
Content Agent POST /run { products, store_context }
```

## Required Prestia APIs

| Prestia API | Content Agent input | Priority |
|-------------|---------------------|----------|
| [GET /v1/store](./02-store-profile-apis.md) | `store_context.settings.brand_voice`, display name, currency | P0 |
| [GET /v1/products](./03-product-and-inventory-apis.md) | `products[]` for prompts | P0 |

## Context fields consumed

### Products (`agents/content/product_context.py`)

Normalized from context bundle `products.items`:

| Field | Source | Required for drafts |
|-------|--------|---------------------|
| `product_id` / `id` | Prestia product `id` | Yes for `content.product_description` |
| `title` / `name` | Prestia `name` | Yes |
| `category` / `category.name` | Nested category | Recommended |
| `price`, `currency` | Product + store | Recommended |
| `image_url` / `images[0]` | Product images | Recommended for rich captions |
| `sku` | Product SKU | Optional |
| `metadata` | e.g. `material`, `color` | Recommended — guardrails forbid inventing attributes |

**Not in context bundle today but valuable from Prestia:**

| Field | Requirement type | Notes |
|-------|------------------|-------|
| `description` | Inferred | Existing product description helps rewrite drafts; stored on `Product.description` |
| `compare_at_price`, `discount_percent` | Optional | Agent must not claim discounts without data (`agents/content/prompts.py` guardrails) |

### Store context (`agents/content/brand_voice.py`, `agents/content/prompts.py`)

| Field | Source |
|-------|--------|
| `display_name` | `store.name` or `settings.store_display_name` |
| `settings.brand_voice.tone` | Prestia store settings |
| `settings.brand_voice.audience` | Prestia store settings |
| `settings.brand_voice.style_notes` | Prestia store settings |
| `settings.brand_voice.language` | Prestia store settings |
| `currency` | Store profile |

Coordinator fallback when settings missing: `{"brand_voice": {"tone": "warm"}}` (`agents/coordinator/nodes.py`).

### Campaign angle

Optional `campaign_angle` in content run request — **not from Prestia API** today.

## Empty products behavior

If no products after sync, Content Agent returns deterministic empty result without LLM (`agents/content/empty_products.py`). Prestia must expose at least one active product for meaningful drafts.

## Draft limits

`CONTENT_AGENT_MAX_DRAFTS_PER_RUN` env (default 3) or `store.settings.content_agent_max_drafts_per_run` (`agents/content/draft_limit.py`). Prestia may expose this in store settings (P2).

## APIs NOT required by Content Agent

| Data | Reason |
|------|--------|
| Orders, sales summary | Sales agent domain |
| Support messages | Support agent domain |
| Customer PII | Explicitly forbidden in prompts |
| FAQ content | No FAQ model; content agent does not read FAQs |
| Instagram publish/write | Drafts require manager approval; no publish path |

## Write APIs (Future)

| API | Status |
|-----|--------|
| POST product description update | **Not required** — `action_mapping.py` exists but coordinator sets `persist_actions: False` |
| POST Instagram publish | **Not required** — out of scope |

## Evidence from codebase

| File | Relevance |
|------|-----------|
| `agents/content/analysis.py` | Pipeline orchestration |
| `agents/content/product_context.py` | Product/store extraction |
| `agents/content/brand_voice.py` | Brand voice from settings |
| `agents/content/prompts.py` | Prompt guardrails |
| `agents/coordinator/nodes.py` | `_content_specialist_payload()` |
| `backend/catalog/context.py` | `build_product_summary` |
| `docs/agents/content.md` | Agent documentation |
| `docs/examples/content_output.json` | Output contract |

## Open questions

1. Whether Prestia provides Persian product copy natively for `output_language: fa` (coordinator currently passes `output_language: "en"`).
2. Image CDN URLs — authentication or signed URLs for agent fetch (agents use URLs in prompts only, not image download).
