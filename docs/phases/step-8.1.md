# Step 8.1 — Content Agent Prompt Template with Brand Voice

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Build a reusable Content Agent prompt template that injects brand voice from tenant/store settings, supports `AI_OUTPUT_LANGUAGE`, and instructs the model to produce reviewable Instagram and product-description drafts without external publishing side effects.

This step establishes the prompt contract and brand voice helper only. It does not implement the full Phase 8 pipeline (Django product fetch, LLM invocation, schema validation, or action persistence).

---

## Scope of this step

- Brand voice helper: `agents/content/brand_voice.py`
- Content Agent prompt module: `agents/content/prompts.py`
- Package marker: `agents/content/__init__.py`
- Focused unit tests: `agents/content/tests/test_prompts.py`
- Cursor scope rule: `.cursor/rules/phase-8-1-content-agent-brand-voice.mdc`
- This documentation file

**Not in scope:** Step 8.2 (draft count limiting), Step 8.3 (schema-validation test expansion beyond minimal prompt tests), FastAPI `/run` endpoints, Django API integration, LangGraph, real LLM provider calls, coordinator changes, or Instagram publish/send behavior.

---

## Files added/changed

| File | Change |
|------|--------|
| `agents/content/__init__.py` | Created — package marker |
| `agents/content/brand_voice.py` | Created — defensive brand voice extraction from `store.settings` |
| `agents/content/prompts.py` | Created — system prompt, draft contract, safety guardrails |
| `agents/content/tests/__init__.py` | Created — test package marker |
| `agents/content/tests/test_prompts.py` | Created — brand voice and prompt unit tests |
| `.cursor/rules/phase-8-1-content-agent-brand-voice.mdc` | Present — Phase 8.1 scope rule |
| `docs/phases/step-8.1.md` | Created — this document |

---

## Brand voice extraction strategy

Module: `agents/content/brand_voice.py`

The helper reads `settings["brand_voice"]` when `settings` is a mapping. Supported fields:

| Field | Purpose |
|-------|---------|
| `tone` | Voice and personality (e.g. `luxury, warm, concise`) |
| `audience` | Target reader profile |
| `style_notes` | Additional writing constraints |
| `language` | Optional brand-language hint (separate from `AI_OUTPUT_LANGUAGE`) |

### Defensive behavior

- Missing `settings` or `brand_voice` → deterministic generic fallback (`is_fallback=True`)
- Malformed `settings` (non-dict, wrong types) → fallback without raising
- Partial `brand_voice` → configured fields used; missing fields filled from defaults
- Empty `brand_voice` object → fallback
- Never hardcodes Prestia or tenant-specific brand rules in code

### Default fallback values

| Field | Fallback |
|-------|----------|
| `tone` | `friendly, clear, professional` |
| `audience` | `online shoppers` |
| `style_notes` | `keep claims factual and concise; avoid exaggerated marketing language` |
| `language` | `None` (output language comes from `AI_OUTPUT_LANGUAGE`) |

### Settings source note

The Django `Store` model does not yet expose a `settings` JSON field. The prompt API accepts `store_settings` from structured input (as future context bundles or store APIs will provide). Today, callers pass `store_context["settings"]` when available; otherwise the fallback applies.

---

## Prompt template behavior

Module: `agents/content/prompts.py`

| Symbol | Description |
|--------|-------------|
| `ALLOWED_CONTENT_ACTION_TYPES` | `content.instagram_draft`, `content.product_description` |
| `DRAFT_REQUIRED_FIELDS` | `action_type`, `title`, `description`, `draft_text`, `product_id`, `rationale` |
| `build_content_draft_system_prompt(...)` | Full system prompt with brand voice and guardrails |
| `build_content_draft_messages(...)` | Chat message list for the shared LLM abstraction |

### Prompt sections

1. **Role and scope** — Content Agent drafts only; no publish/send/execute
2. **Output language** — from Step 6.1 `build_language_prompt_prefix`
3. **Store context** — display name and currency when provided in input
4. **Brand voice** — extracted from `store_settings`
5. **Data access** — sanitized Django API data only; no invented attributes
6. **Campaign angle** — optional angle-aware copy when `campaign_angle` is set
7. **Draft output contract** — maps to `content.instagram_draft` and `content.product_description`
8. **Safety guardrails** — PII, discounts, scarcity, policies, publishing

### Example usage

```python
from agents.content.prompts import build_content_draft_messages

messages = build_content_draft_messages(
    store_context={
        "id": "uuid",
        "name": "Demo Store",
        "currency": "USD",
        "settings": {
            "brand_voice": {
                "tone": "luxury, warm, concise",
                "audience": "modern customers",
                "style_notes": "avoid exaggerated claims",
                "language": "fa",
            }
        },
    },
    products=[{"product_id": "uuid", "name": "Leather Tote", "price": "120.00"}],
    campaign_angle="New season collection",
    output_language="fa",
)
# Pass `messages` to the shared LLM provider in a later step.
```

Store display names (including demo tenants such as Prestia) appear in prompts only when passed in `store_context`; they are never hardcoded in agent code.

---

## Language handling

Uses `agents/shared/language.py` (Step 6.1):

- `build_language_prompt_prefix(output_language)` injects the output-language directive
- Default is Persian (`fa`) when `AI_OUTPUT_LANGUAGE` is unset
- English (`en`) supported when configured
- Brand voice `language` hint is separate and optional; manager-facing `draft_text` follows `AI_OUTPUT_LANGUAGE`

---

## Safety / PII / content guardrails

The prompt explicitly forbids:

- Publishing, posting, sending, or scheduling content externally
- Phone numbers, emails, addresses, customer names, payment details
- Customer-specific or thread-specific content
- Discount or promotion claims without supporting data
- Scarcity or urgency without inventory evidence
- Refunds, warranties, delivery promises, or policies not in context
- Invented product attributes

Drafts are framed as **reviewable** and **approval-required** before any external use.

---

## Tests added

`agents/content/tests/test_prompts.py` (stdlib `unittest`):

- Configured brand voice values appear in the prompt
- Safe fallback when brand voice is missing or malformed
- `AI_OUTPUT_LANGUAGE=en` produces English instruction
- Default Persian when env unset
- No Prestia hardcoding in prompt code
- Store display name only when provided in input
- Guardrails for publishing, discounts, scarcity, PII, and approval
- Allowed content action types and required draft fields documented
- Campaign angle section when provided
- `build_content_draft_messages()` returns system/user messages
- No LLM API key required to build prompts

No real LLM providers or Django APIs are called in tests.

---

## Validation commands

Run focused Content Agent prompt tests from the repository root:

```bash
PYTHONPATH=. python -m unittest agents.content.tests.test_prompts -v
```

Run all agent unit tests (shared + coordinator + sales + content):

```bash
PYTHONPATH=. python -m unittest discover -s agents -p 'test_*.py' -v
```

---

## Known limitations

| Limitation | Notes |
|------------|-------|
| No `Store.settings` Django field yet | Prompt accepts `settings` from structured input; context bundle does not include settings today |
| No LLM pipeline | Prompt/messages only; no `/run` endpoint or schema validation on agent output |
| No draft count cap | Deferred to Step 8.2 |
| No `ContentSuggestions` schema | Deferred to Step 8.3 and full Phase 8 pipeline |
| Brand voice `language` vs `AI_OUTPUT_LANGUAGE` | Both may appear; output language for drafts follows `AI_OUTPUT_LANGUAGE` |

---

## Intentionally deferred

| Item | Deferred to |
|------|-------------|
| Limit drafts to N per run | Step 8.2 |
| Full schema validation and expanded tests | Step 8.3 |
| Fetch products from Django internal APIs | Full Phase 8 pipeline |
| LLM invocation and structured output parsing | Full Phase 8 pipeline |
| Action persistence (`content.instagram_draft`, etc.) | Full Phase 8 pipeline |
| FastAPI `/run` on `content-agent` | Later Phase 8 work |
| Instagram publish/send integration | Post-MVP |

---

## Acceptance checklist

- [x] Reusable Content Agent prompt template injects brand voice from `store.settings` input
- [x] Brand voice fallback works without crashing on missing or malformed settings
- [x] Implementation is generic and multi-tenant (no Prestia hardcoding)
- [x] Persian and English output instructions supported via `AI_OUTPUT_LANGUAGE`
- [x] Drafts are reviewable and approval-required in intent
- [x] No external publishing/sending behavior added
- [x] `.cursor/rules/phase-8-1-content-agent-brand-voice.mdc` exists
- [x] `docs/phases/step-8.1.md` documents the implementation
- [x] Focused unit tests cover prompt and brand voice behavior

---

## Next steps

| Step | Focus |
|------|-------|
| **8.2** | Limit content drafts to N per run |
| **8.3** | Schema validation tests for Content Agent output |
| **Phase 8 pipeline** | Django fetch, LLM call, action mapping, `/run` endpoint |
