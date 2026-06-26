# Step 7.1 — Define Recommendation Priority Rubric in Prompt

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Define the Sales Agent recommendation priority rubric in the prompt layer so future LLM calls produce consistent, manager-facing structured recommendations with explicit urgency levels and allowed sales action types.

This step establishes the prompt contract only. It does not implement the full Phase 7 pipeline (Django data fetch, LLM invocation, response validation, or action persistence).

---

## Scope of this step

- Sales Agent prompt module: `agents/sales/prompts.py`
- Package marker: `agents/sales/__init__.py`
- Focused unit tests: `agents/sales/tests/test_prompts.py`
- Cursor scope rule: `.cursor/rules/step-7.1-sales-agent-priority-rubric.mdc`
- This documentation file

**Not in scope:** Step 7.2 (empty sales handling), Step 7.3 (JSON schema validation), Step 7.4 (example output doc), FastAPI `/run` endpoints, Django API integration, LangGraph, real LLM provider calls, or coordinator changes.

---

## Files changed

| File | Change |
|------|--------|
| `agents/sales/__init__.py` | Created — package marker |
| `agents/sales/prompts.py` | Created — system prompt, priority rubric, safety constraints |
| `agents/sales/tests/__init__.py` | Created — test package marker |
| `agents/sales/tests/test_prompts.py` | Created — prompt/rubric unit tests |
| `.cursor/rules/step-7.1-sales-agent-priority-rubric.mdc` | Created — Step 7.1 scope rule |
| `docs/phases/step-7.1.md` | Created — this document |

---

## Prompt API

Module: `agents/sales/prompts.py`

| Symbol | Description |
|--------|-------------|
| `ALLOWED_SALES_ACTION_TYPES` | `sales.restock`, `sales.discount`, `sales.follow_up` |
| `RECOMMENDATION_REQUIRED_FIELDS` | `priority`, `action_type`, `title`, `description`, `rationale`, `payload` |
| `MIN_PRIORITY` / `MAX_PRIORITY` | `1` / `5` |
| `build_sales_analysis_system_prompt(output_language=None)` | Full system prompt with rubric and constraints |
| `build_sales_analysis_messages(output_language=None, user_context=None)` | Chat message list for the shared LLM abstraction |

### Example usage

```python
from agents.sales.prompts import build_sales_analysis_messages

messages = build_sales_analysis_messages(
    output_language="fa",
    user_context=sanitized_context_json,
)
# Pass `messages` to the shared LLM provider in a later step.
```

---

## Priority rubric

Numeric scale: **1 = highest urgency**, **5 = informational / lowest urgency**.

| Priority | Label | Example business signals |
|----------|-------|--------------------------|
| **1** | Urgent / highest business impact | Critical stockout risk; high-velocity SKU nearly out of stock; severe revenue-at-risk; immediate restock need |
| **2** | High priority | Low stock with meaningful recent sales; strong demand trend; high-value product needing restock, discount, or follow-up |
| **3** | Medium priority | Moderate restock need; discount candidate with enough evidence but not urgent; routine warm-lead follow-up |
| **4** | Low priority / monitor | Weak or early signal; slow-moving inventory to watch; minor optimization; low-urgency follow-up |
| **5** | Informational / no immediate action | Trend or ranking insight only; observation without operational action; insufficient evidence for restock, discount, or follow-up |

### Mapping guidance

| Signal pattern | Typical priority |
|----------------|------------------|
| High velocity + stock at or near zero | 1 |
| Low stock + strong recent sales on high-value SKU | 2 |
| Moderate stock gap or promotional opportunity with evidence | 3 |
| Slow mover or minor tweak; monitor first | 4 |
| Insight only, no actionable evidence | 5 |

The rubric text in the prompt is tenant-agnostic and applies across restock, discount, follow-up, and SKU prioritization recommendations.

---

## Allowed sales action types

| `action_type` | Purpose |
|---------------|---------|
| `sales.restock` | Restock recommendation for a product/SKU |
| `sales.discount` | Discount or promotional pricing suggestion |
| `sales.follow_up` | Sales follow-up suggestion (no direct customer contact) |

No other `action_type` values are permitted in Sales Agent recommendations.

---

## Recommendation shape (prompt contract)

Each recommendation must include:

| Field | Description |
|-------|-------------|
| `priority` | Integer 1–5 (1 = highest urgency) |
| `action_type` | One of the allowed sales action types |
| `title` | Short manager-facing headline |
| `description` | Concise summary |
| `rationale` | Non-PII explanation of priority and action choice |
| `payload` | Structured action-specific data (e.g. `product_id`, `sku`, stock, quantities) |

---

## PII and safety constraints

The prompt instructs the model to:

- Use only sanitized data from Django internal APIs.
- Avoid phone numbers, emails, addresses, customer names, payment details, and raw message identifiers.
- Not invent customer or product details.
- Not execute actions, change prices, post to social media, or reply to customers directly.
- Not claim an action was already executed.
- Propose recommendations only within the Django action workflow.

---

## Integration with `AI_OUTPUT_LANGUAGE`

The prompt uses the Step 6.1 helper (`agents/shared/language.py`):

- `build_language_prompt_prefix(output_language)` injects the output-language directive.
- Default is Persian (`fa`) when `AI_OUTPUT_LANGUAGE` is unset.
- English (`en`) is supported when configured.
- The rubric definitions remain in English for consistency; manager-facing `title`, `description`, and `rationale` follow the configured output language.

---

## Tests added

`agents/sales/tests/test_prompts.py` (stdlib `unittest`):

- Full 1–5 priority scale present in the prompt
- Priority 1 defined as highest urgency
- Priority 5 defined as informational / lowest urgency
- Allowed sales action types present
- Required recommendation fields documented in the prompt
- PII and safety instructions present
- Prompt builds without any LLM API key
- `build_sales_analysis_messages()` returns system/user messages for the LLM scaffold
- Default Persian and explicit English language instructions
- No direct database access or execution instructions

No real LLM providers or Django APIs are called in tests.

---

## Validation commands

Run focused Sales Agent prompt tests from the repository root:

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_prompts -v
```

Run all agent unit tests (shared + coordinator + sales):

```bash
PYTHONPATH=. python -m unittest discover -s agents -p 'test_*.py' -v
```

---

## What is intentionally not implemented in this step

| Item | Deferred to |
|------|-------------|
| Fetch sales/inventory from Django | Phase 7 pipeline (post-7.1) |
| LLM analysis with structured output | Phase 7 pipeline |
| Empty / no-data graceful handling | Step 7.2 |
| JSON schema validation before return | Step 7.3 |
| Example output at `docs/examples/sales_output.json` | Step 7.4 |
| FastAPI `/run` on `sales-agent` | Later Phase 7 work |
| Real `OpenAIProvider` / `AnthropicProvider` wiring in Sales Agent | When LLM abstraction is connected |
| Action persistence to Django | Later Phase 7 work |

---

## Acceptance checklist

- [x] Dedicated Cursor rule exists at `.cursor/rules/step-7.1-sales-agent-priority-rubric.mdc`
- [x] Sales Agent prompt includes a clear 1–5 priority rubric
- [x] Priority 1 = highest urgency; priority 5 = informational / lowest urgency
- [x] Allowed action types `sales.restock`, `sales.discount`, `sales.follow_up` are in the prompt
- [x] Required fields `priority`, `action_type`, `title`, `description`, `rationale`, `payload` are specified
- [x] PII and no-side-effect constraints are present
- [x] `AI_OUTPUT_LANGUAGE` integration via Step 6.1 helper
- [x] Unit tests cover prompt/rubric behavior
- [x] `docs/phases/step-7.1.md` documents the implementation
- [x] Implementation is generic, tenant-scoped, and not Prestia-hardcoded

---

## Next steps

| Step | Focus |
|------|-------|
| **7.2** | Handle empty sales / no-data gracefully in prompts and pipeline |
| **7.3** | Validate Sales Agent JSON output against schema before return |
| **7.4** | Document example output in `docs/examples/sales_output.json` |
