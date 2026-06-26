# Step 8.5 — Content Agent FastAPI `/run` Endpoint

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Expose the Step 8.4 Content Agent runtime pipeline (`run_content_analysis()`) through a runnable FastAPI `POST /run` endpoint on `content-agent`, aligned with the Sales Agent `/run` pattern.

The endpoint returns only schema-validated `ContentSuggestions` output. No action persistence, external publishing, or coordinator orchestration is introduced in this step.

---

## Scope and non-goals

### In scope

- `POST /run` on `content-agent`
- Request schema compatible with the runtime pipeline
- Response schema: validated `ContentSuggestions`
- Correlation via `X-Request-ID` header and optional `request_id` body field
- HTTP 422 mapping for schema/LLM output validation failures
- Deterministic endpoint tests with `MockProvider` (no real LLM API keys)
- Preserve existing `GET /health`

### Out of scope (deferred)

| Step | Deferred work |
|------|----------------|
| 8.6 | Content action mapping and Django `POST /internal/ai/actions/` persistence |
| 8.7 | `docs/examples/content_output.json` and final acceptance proof |
| — | Coordinator/LangGraph orchestration, Support Agent, frontend, real Instagram publishing, competitor scraping, website article generation |

---

## Files changed

| File | Change |
|------|--------|
| `agents/content/app/schemas.py` | Created — `ContentRunRequest` |
| `agents/content/app/main.py` | Updated — `POST /run` endpoint, error mapping, safe logging |
| `agents/content/tests/test_run_endpoint.py` | Created — Step 8.5 endpoint tests |
| `agents/content/requirements.txt` | Updated — added `pydantic` |
| `agents/content/Dockerfile` | Updated — copy `agents/shared` + full content package; `PYTHONPATH=/app` |
| `docker-compose.yml` | Updated — content-agent build context `./agents` |
| `.cursor/rules/phase-8-5-content-agent-run-endpoint.mdc` | Present — scope rule for this step |
| `docs/phases/step-8.5.md` | Created — this document |

---

## Endpoint

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check (unchanged) |
| `POST` | `/run` | Run Content Agent pipeline and return `ContentSuggestions` |

---

## Request schema

`ContentRunRequest` (`agents/content/app/schemas.py`) — all fields optional; strict `extra="forbid"`.

| Field | Type | Description |
|-------|------|-------------|
| `context` | `object \| null` | Coordinator-style bundle (`store`, `products`, `campaign_angle`) |
| `products` | `array \| null` | Explicit product list |
| `store_context` | `object \| null` | Store mapping (`display_name`, `settings`, etc.) |
| `campaign_angle` | `string \| null` | Optional campaign focus |
| `report_run_id` | `string \| null` | Trace id propagated to response metadata |
| `output_language` | `string \| null` | `fa` or `en`; defaults to `AI_OUTPUT_LANGUAGE` |
| `max_drafts_per_run` | `integer \| null` | Request-level draft limit override (Step 8.2) |
| `request_id` | `string \| null` | Correlation id; overridden by `X-Request-ID` header when present |

### Example request (coordinator bundle)

```json
{
  "context": {
    "store": {
      "id": "store-uuid",
      "display_name": "Demo Store",
      "settings": {
        "brand_voice": {
          "tone": "luxury, warm, concise",
          "audience": "modern shoppers"
        },
        "content_agent": {
          "max_drafts_per_run": 3
        }
      }
    },
    "products": [
      {
        "product_id": "00000000-0000-4000-8000-000000000001",
        "title": "Everyday Leather Tote",
        "category": "Bags",
        "price": "89.00",
        "currency": "USD"
      }
    ],
    "campaign_angle": "New arrivals"
  },
  "report_run_id": "run-valid-1",
  "output_language": "en"
}
```

### Example request (explicit fields)

```json
{
  "products": [
    {
      "product_id": "00000000-0000-4000-8000-000000000001",
      "title": "Everyday Leather Tote",
      "category": "Bags"
    }
  ],
  "store_context": {
    "display_name": "Demo Store",
    "settings": {
      "brand_voice": { "tone": "warm, concise" }
    }
  },
  "max_drafts_per_run": 1,
  "output_language": "en"
}
```

---

## Response schema

Validated `ContentSuggestions` (`agents/shared/schemas/content.py`):

| Field | Type | Notes |
|-------|------|-------|
| `metadata` | object | `agent_name` = `content-agent`; optional `report_run_id` |
| `summary` | string | Manager-facing summary |
| `drafts` | array | `ContentDraft` items only |
| `warnings` | array | Optional agent warnings |
| `output_language` | string \| null | Resolved output language |

Each `ContentDraft` must:

- use `content.instagram_draft` or `content.product_description`
- set `requires_approval` to `true`
- pass strict schema validation (Step 8.3)
- respect draft limit (Step 8.2)

---

## Pipeline integration

`POST /run` calls `run_content_analysis()` from `agents/content/analysis.py` with request fields mapped directly:

```
POST /run
  → ContentRunRequest validation (FastAPI/Pydantic)
  → run_content_analysis(
        context, products, store_context, campaign_angle,
        report_run_id, output_language, max_drafts_per_run,
        request_id
    )
  → Step 8.4 pipeline (context resolve → empty check → LLM → limit → validate)
  → ContentSuggestions response
```

Default LLM path uses `get_llm_provider()` (`LLM_PROVIDER=mock` in `.env.example`).

---

## Validation behavior

- Request body validated by `ContentRunRequest` (invalid types/extra fields → HTTP **422** FastAPI validation error).
- Pipeline output always passes `ensure_valid_content_suggestions()` before return.
- Invalid provider output is never returned as-is.
- Empty product context returns deterministic empty `ContentSuggestions` (Step 8.4) without an LLM call.

---

## Error handling

| Condition | HTTP status | `detail.code` |
|-----------|-------------|---------------|
| Invalid request body | 422 | FastAPI validation error list |
| Schema validation failure | 422 | `schema_validation_failed` |
| Malformed/unparseable LLM JSON | 422 | `llm_output_invalid` |

Error responses include safe messages only — no prompt bodies, full product payloads, or raw provider responses.

INFO-level logging records `service`, `report_run_id`, and `request_id` only.

---

## Test coverage

`agents/content/tests/test_run_endpoint.py`:

- `GET /health` returns success
- `POST /run` returns valid `ContentSuggestions` for product fixtures
- Response includes at least one `content.instagram_draft`
- `max_drafts_per_run` request override is enforced
- All drafts have `requires_approval=true`
- English mode via `AI_OUTPUT_LANGUAGE=en`
- Empty product context returns Step 8.4 empty result
- Invalid request body returns validation error
- No real LLM API key required (`LLM_PROVIDER=mock`)
- Validation/LLM errors map to HTTP 422 without stack traces

---

## Validation commands

From repository root:

```bash
PYTHONPATH=. python -m unittest agents.content.tests.test_run_endpoint -v
```

Content Agent full suite:

```bash
PYTHONPATH=. python -m unittest \
  agents.content.tests.test_prompts \
  agents.content.tests.test_draft_limit \
  agents.content.tests.test_schema_validation \
  agents.content.tests.test_runtime_pipeline \
  agents.content.tests.test_run_endpoint \
  -v
```

Regression (Sales Agent):

```bash
PYTHONPATH=. python -m unittest discover -s agents/sales/tests -p 'test_*.py' -v
```

Docker (optional):

```bash
docker compose build content-agent
docker compose up -d content-agent
curl -s http://localhost:8102/health
```

---

## Known limitations

- Only `MockProvider` is wired in `get_llm_provider()`; real OpenAI/Anthropic providers are deferred.
- No service JWT validation on `/run` yet (aligned with Sales Agent MVP).
- No Django product fetch — callers must supply context in the request body.
- No action persistence (Step 8.6).
- Coordinator must call this endpoint explicitly (Step 10).

---

## Deferred work

| Step | Work |
|------|------|
| **8.6** | Map validated drafts to Django action payloads and persist via internal APIs |
| **8.7** | Prestia-style acceptance proof and `docs/examples/content_output.json` |
| **10** | Coordinator LangGraph node calling `content-agent` `/run` |

---

## Acceptance criteria (Step 8.5)

- [x] Content Agent exposes runnable `POST /run`
- [x] `GET /health` still works
- [x] `/run` calls Step 8.4 `run_content_analysis()`
- [x] `/run` returns schema-validated `ContentSuggestions`
- [x] Endpoint tests pass with MockProvider/fixtures, no real LLM API key
- [x] Response respects draft limit and `requires_approval=true`
- [x] Invalid requests handled deterministically
- [x] No action persistence or external side effects
- [x] No Prestia-specific business logic hardcoded
- [x] `docs/phases/step-8.5.md` documents the implementation
