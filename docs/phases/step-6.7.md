# Step 6.7 — Sales Agent Mock Provider Default Wiring

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Scope

Fix the sales-agent scaffold so non-empty `/run` requests use `get_llm_provider()` by default when `LLM_PROVIDER=mock`, instead of returning HTTP 501 when no provider is injected.

Existing Phase 7 sales functionality (empty-sales handling, schema validation, prompts, example output) is preserved.

---

## Files changed

| Path | Change |
|------|--------|
| `agents/sales/analysis.py` | Default to `get_llm_provider()`; normalize context bundle via `extract_sales_summary()` |
| `agents/sales/tests/test_schema_validation.py` | Updated endpoint tests for mock default path |
| `docs/phases/step-6.7.md` | This document |

---

## Behavior change

**Before:** Non-empty `/run` without injected `llm_provider` raised `NotImplementedError` → HTTP 501.

**After:** Non-empty `/run` calls `get_llm_provider()` when no provider is injected. With `LLM_PROVIDER=mock`, returns schema-validated `SalesAnalysisResult` without external API keys.

Unimplemented providers (e.g. `LLM_PROVIDER=openai`) still return HTTP 501.

---

## Tests added/updated

`agents/sales/tests/test_schema_validation.py`:

- `test_run_sales_analysis_uses_default_mock_provider` — pipeline uses shared mock without injection
- `test_run_endpoint_returns_mock_output_for_non_empty_sales` — `/run` returns 200 with recommendations
- `test_run_endpoint_returns_501_for_unimplemented_provider` — non-mock provider still 501
- Existing injected-provider and empty-sales tests unchanged

---

## Commands run

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_schema_validation -v
```

**Result:** All sales schema/endpoint tests passed.

---

## Acceptance criteria

- [x] Non-empty sales `/run` does not return 501 when `LLM_PROVIDER=mock`
- [x] Uses `get_llm_provider()` as default provider path
- [x] No external API key required for mock output
- [x] Existing empty-input deterministic path still passes
- [x] Existing injected-provider tests still pass
- [x] Later-phase sales functionality preserved

---

## Known limitations

- Real OpenAI/Anthropic providers remain unimplemented.
- Context bundles must include extractable `sales_summary` (or flat period keys) for mock recommendations.
