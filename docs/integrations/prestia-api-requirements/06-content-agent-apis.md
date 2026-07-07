# Content Agent APIs

APIs required by the **Content Agent** for caption and product-description draft generation.

## Agent summary

The Content Agent (`agents/content/`) generates reviewable `ContentSuggestions` with Instagram captions (`content.instagram_draft`) and product descriptions (`content.product_description`). It does **not** call external APIs directly — it receives context from the Coordinator (`docs/agents/content.md`).

For Prestia integration, product data comes from Prestia; brand and store configuration comes from Botkonak tenant settings.

## Data flow

```
GET /v1/products (on demand) → Botkonak connector
       ↓
Botkonak tenant settings (brand voice, display name, currency)
       ↓
Coordinator GET context bundle
       ↓
Content Agent POST /run { products, store_context }
```

## Required Prestia APIs

| Prestia API | Content Agent input | Priority |
|-------------|---------------------|----------|
| [GET /v1/products](./03-product-and-inventory-apis.md) | `products[]` for prompts | P0 |

## Required Botkonak configuration (not Prestia)

Store profile settings are **not** fetched from Prestia. Configure in Botkonak tenant/store settings UI:

| Setting | Content Agent usage |
|---------|---------------------|
| `settings.brand_voice.tone` | Draft tone |
| `settings.brand_voice.audience` | Target audience |
| `settings.brand_voice.style_notes` | Writing rules |
| `settings.brand_voice.language` | Output language preference |
| Store display name | Prompt context |
| Default `currency` | Pricing references in captions |

Coordinator fallback when settings missing: `{"brand_voice": {"tone": "warm"}}` (`agents/coordinator/nodes.py`).

## Context fields consumed

### Products (`agents/content/product_context.py`)

Normalized from context bundle `products.items`, sourced from [GET /v1/products](./03-product-and-inventory-apis.md):

| Field | Prestia source | Required for drafts |
|-------|----------------|---------------------|
| `slug` | `slug` | Yes — product identifier |
| `title` | `title` | Yes |
| `category.slug`, `category.title` | Nested `category` | Recommended |
| `price`, `currency`, `discount` | Product fields | Recommended |
| `images` | `images[]` | Recommended for rich captions |
| `inventories[].metadata` | Variant attributes | Optional — color/size in captions |
| `metadata` | Product-level metadata | Recommended — guardrails forbid inventing attributes |
| `description` | `description` | Recommended for product description drafts |

**Agent guardrail:** must not claim discounts without `discount` data (`agents/content/prompts.py`).

### Store context (`agents/content/brand_voice.py`, `agents/content/prompts.py`)

| Field | Source |
|-------|--------|
| `display_name` | Botkonak tenant/store settings |
| `settings.brand_voice.*` | Botkonak tenant/store settings |
| `currency` | Botkonak tenant/store settings (or product `currency`) |

### Campaign angle

Optional `campaign_angle` in content run request — **not from Prestia API** today.

## Empty products behavior

If no products after fetch, Content Agent returns deterministic empty result without LLM (`agents/content/empty_products.py`). Prestia must expose at least one active product for meaningful drafts.

## Draft limits

`CONTENT_AGENT_MAX_DRAFTS_PER_RUN` env (default 3) or Botkonak `store.settings.content_agent_max_drafts_per_run` (`agents/content/draft_limit.py`).

## APIs NOT required by Content Agent

| Data | Reason |
|------|--------|
| `GET /v1/store` | Store profile is Botkonak tenant settings |
| Orders, sales summary | Sales agent domain |
| Support messages | Support agent domain |
| Customer PII | Explicitly forbidden in prompts |
| FAQ content | Support agent domain |
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
| `agents/content/brand_voice.py` | Brand voice from local settings |
| `agents/content/prompts.py` | Prompt guardrails |
| `agents/coordinator/nodes.py` | `_content_specialist_payload()` |
| `backend/catalog/context.py` | `build_product_summary` |
| `docs/agents/content.md` | Agent documentation |
| `docs/examples/content_output.json` | Output contract |

## Open questions

1. Whether Prestia provides Persian product copy natively for `output_language: fa` (coordinator currently passes `output_language: "en"`).
2. Image CDN URLs — authentication or signed URLs for agent fetch (agents use URLs in prompts only, not image download).
