# Step 8.4 — Content Agent Runtime Pipeline

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Connect Steps 8.1–8.3 into a runnable Content Agent pipeline that:

- consumes sanitized product/store context,
- builds prompts with brand voice and language instructions,
- calls the shared LLM abstraction (MockProvider by default),
- parses and normalizes provider output,
- enforces draft limits,
- validates against `ContentSuggestions` / `ContentDraft` schemas,
- returns a validated result without external publishing side effects.

This step implements the runtime pipeline only. It does **not** add FastAPI `/run`, Django action persistence, or example output documentation.

---

## Scope and non-goals

### In scope

- `run_content_analysis()` pipeline entry point
- Product context extraction/normalization
- Empty-product deterministic fallback
- Shared `MockProvider` / `get_llm_provider()` usage
- Runtime tests with fixtures and MockProvider

### Out of scope (deferred)

| Step | Deferred work |
|------|----------------|
| 8.5 | FastAPI `POST /run` endpoint on `content-agent` |
| 8.6 | Content action mapping and Django `POST /internal/ai/actions/` persistence |
| 8.7 | `docs/examples/content_output.json` and final acceptance proof |
| — | Coordinator/LangGraph orchestration, Support Agent, frontend, real Instagram publishing, competitor scraping, website article generation |

---

## Files changed

| File | Change |
|------|--------|
| `agents/shared/llm/__init__.py` | Created — shared LLM package exports |
| `agents/shared/llm/provider.py` | Created — `LLMProvider` protocol and `get_llm_provider()` factory |
| `agents/shared/llm/mock.py` | Created — deterministic `MockProvider` with content/sales inference |
| `agents/content/product_context.py` | Created — product/store context extraction and normalization |
| `agents/content/empty_products.py` | Created — empty-product deterministic fallback |
| `agents/content/analysis.py` | Extended — `run_content_analysis()` runtime pipeline |
| `agents/content/tests/test_runtime_pipeline.py` | Created — Step 8.4 pipeline tests |
| `.cursor/rules/phase-8-4-content-agent-runtime-pipeline.mdc` | Present — scope rule for this step |
| `docs/phases/step-8.4.md` | Created — this document |

---

## Pipeline entry point

```python
from agents.content.analysis import run_content_analysis

result = run_content_analysis(
    context={...},              # optional coordinator bundle
    products=[...],             # optional explicit product list
    store_context={...},        # optional explicit store mapping
    campaign_angle="...",       # optional
    report_run_id="...",        # optional trace id
    output_language="fa",       # optional; defaults to AI_OUTPUT_LANGUAGE
    max_drafts_per_run=3,       # optional request override
    llm_provider=None,          # optional; defaults to get_llm_provider()
    request_id="...",           # optional correlation id for safe logging
)
```

Returns: validated `ContentSuggestions` (Pydantic model).

---

## Pipeline order

1. **Resolve context** — `resolve_content_run_context()` merges explicit args and coordinator bundle fields.
2. **Empty-product short-circuit** — deterministic `ContentSuggestions` with `drafts=[]` when no products are available; no LLM call.
3. **Build prompts** — `build_content_draft_messages()` (Step 8.1) injects brand voice, language, campaign angle, and draft-limit instructions.
4. **Call LLM provider** — `get_llm_provider()` returns `MockProvider` when `LLM_PROVIDER=mock`.
5. **Parse output** — `parse_llm_json_output()` accepts JSON string or dict.
6. **Apply draft limit** — `apply_content_draft_limit()` (Step 8.2).
7. **Schema validate** — `ensure_valid_content_suggestions()` (Step 8.3).
8. **Return** — validated `ContentSuggestions`.

---

## Input / context shape

### Coordinator-style bundle

```json
{
  "store": {
    "id": "store-uuid",
    "display_name": "Demo Store",
    "currency": "USD",
    "settings": {
      "brand_voice": { "tone": "...", "audience": "...", "style_notes": "..." },
      "content_agent": { "max_drafts_per_run": 3 }
    }
  },
  "products": [
    {
      "product_id": "uuid",
      "title": "Everyday Leather Tote",
      "category": "Bags",
      "price": "89.00",
      "currency": "USD",
      "image_url": "https://cdn.example.test/products/tote.jpg"
    }
  ],
  "campaign_angle": "New arrivals"
}
```

### Product normalization

`normalize_product()` maps common API shapes:

| Input keys | Normalized field |
|------------|------------------|
| `product_id` or `id` | `product_id` |
| `title` or `name` | `title` |
| `category` or `category_name` | `category` |
| `price` | `price` |
| `currency` | `currency` |
| `image_url` or `image` | `image_url` |
| `sku` | `sku` |

The pipeline does **not** invent missing product facts.

---

## Product context handling

- Products may be passed explicitly (`products=`) or via `context["products"]`.
- Store context may be passed explicitly (`store_context=`) or via `context["store"]` / top-level store fields.
- Campaign angle may be passed explicitly or via `context["campaign_angle"]`.
- When products are empty or missing, the pipeline returns a valid empty `ContentSuggestions` result without calling the LLM.

### Empty-product messages

| Language | Summary |
|----------|---------|
| `fa` | محصولی برای تولید پیش‌نویس محتوا در دسترس نیست. |
| `en` | No products were available for content draft generation. |

---

## LLM / MockProvider usage

- Business logic imports `get_llm_provider()` from `agents/shared/llm/` — no direct OpenAI/Anthropic SDK imports.
- Default: `LLM_PROVIDER=mock` (documented in `.env.example`).
- `MockProvider.complete(messages)` inspects the system prompt and user JSON payload:
  - **Content Agent** prompts → `ContentSuggestions`-shaped dict with instagram + product description drafts per product (deterministic).
  - **Sales Agent** prompts → basic `SalesAnalysisResult`-shaped dict (for future shared mock use; Sales tests still use inline test doubles).

Tests and local development require no real API keys.

---

## Parsing and normalization

- Shared parser: `parse_llm_json_output()` in `agents/content/validation.py`.
- Accepts provider JSON string or dict (MockProvider returns dict).
- Normalization gate: `normalize_content_agent_output()` remains available for direct LLM output post-processing outside the full pipeline.

---

## Draft limit enforcement

Applied in `_run_llm_content_analysis()` **after** parsing and **before** schema validation via `apply_content_draft_limit()`.

Resolution order (Step 8.2):

1. `max_drafts_per_run` request argument
2. `store.settings.content_agent.max_drafts_per_run`
3. `CONTENT_AGENT_MAX_DRAFTS_PER_RUN` environment variable
4. Default `3` (hard cap `5`)

---

## Schema validation boundary

Final return path always passes through `ensure_valid_content_suggestions()`:

- allowed action types: `content.instagram_draft`, `content.product_description`
- `requires_approval` must be `true`
- strict `extra="forbid"` policy on schemas
- validation failures log a safe summary via `log_content_validation_failure()` and re-raise

---

## Tests and validation commands

### New tests

`agents/content/tests/test_runtime_pipeline.py` covers:

- validated `ContentSuggestions` for product fixtures
- instagram draft generation
- product description draft generation
- brand voice injection via prompt builder
- draft limit inside runtime pipeline
- over-limit mock output trimming
- invalid mock output rejection
- empty product context (no hallucinated products, no LLM call)
- `AI_OUTPUT_LANGUAGE=fa` and explicit `en` paths
- default `get_llm_provider()` / MockProvider without API keys

### Run tests

From the repository root:

```bash
python -m unittest discover -s agents/content/tests -p 'test_*.py' -v
```

Content Agent only:

```bash
python -m unittest agents.content.tests.test_runtime_pipeline -v
```

Full content test suite:

```bash
python -m unittest \
  agents.content.tests.test_prompts \
  agents.content.tests.test_draft_limit \
  agents.content.tests.test_schema_validation \
  agents.content.tests.test_runtime_pipeline \
  -v
```

Regression check (Sales Agent — inline mock providers unchanged):

```bash
python -m unittest discover -s agents/sales/tests -p 'test_*.py' -v
```

---

## Known limitations

- Only `MockProvider` is implemented in `get_llm_provider()`; OpenAI/Anthropic providers are deferred.
- Mock output is template-based and does not call a real LLM; copy quality is not representative of production.
- No Django product fetch in this step — callers must supply context or wait for Step 8.5/10 integration.
- `MockProvider` generates at most three products' worth of drafts (two per product: instagram + description).
- No FastAPI `/run` endpoint yet (Step 8.5).
- No action persistence or approval workflow integration yet (Step 8.6).

---

## Deferred to later steps

| Step | Work |
|------|------|
| **8.5** | Wire `run_content_analysis()` to `POST /run` on `content-agent` |
| **8.6** | Map validated drafts to Django action payloads (`content.instagram_draft`, `content.product_description`) |
| **8.7** | Prestia-style acceptance proof and `docs/examples/content_output.json` |

---

## Acceptance criteria (Step 8.4)

- [x] Runnable `run_content_analysis()` pipeline function
- [x] Consumes product context from bundle or explicit args
- [x] Uses Step 8.1 prompt/brand voice behavior
- [x] Uses shared LLM provider abstraction
- [x] Works with MockProvider without real API keys
- [x] Applies Step 8.2 draft limits
- [x] Validates output with Step 8.3 schemas
- [x] Handles empty product data safely
- [x] No FastAPI `/run` endpoint
- [x] No action persistence
- [x] No external publishing or side effects
- [x] No Prestia-specific hardcoded business logic
- [x] `docs/phases/step-8.4.md` documents the implementation
- [x] Relevant tests pass
