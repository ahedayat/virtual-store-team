# Step 8.2 — Content Agent Draft Limit Per Run

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Enforce a deterministic maximum number of content draft suggestions per Content Agent run. The MVP default is **3** drafts per run, configurable per request, per store settings, or via environment variable, with safe validation and **code-level trimming** after LLM/mock output is parsed.

Prompt guidance includes the resolved limit, but the final guarantee comes from code enforcement — not prompt wording alone.

---

## Scope of this step

- Draft limit helper: `agents/content/draft_limit.py`
- Result normalization hook: `agents/content/analysis.py`
- Prompt updates: `agents/content/prompts.py`
- Focused unit tests: `agents/content/tests/test_draft_limit.py`
- Cursor scope rule: `.cursor/rules/phase-8-2-content-agent-draft-limit.mdc`
- Environment documentation: `.env.example` (`CONTENT_AGENT_MAX_DRAFTS_PER_RUN`)
- This documentation file

**Not in scope:** Step 8.3 full schema-validation expansion, FastAPI `/run` endpoint, Django product fetch, real LLM provider wiring, coordinator integration, Instagram publish/send, competitor scraping, or website article generation.

---

## Files changed

| File | Change |
|------|--------|
| `agents/content/draft_limit.py` | Created — `resolve_max_drafts_per_run`, `limit_content_suggestions` |
| `agents/content/analysis.py` | Created — parse mock/LLM JSON and apply draft limit before return |
| `agents/content/prompts.py` | Updated — draft limit section and resolved max in output contract |
| `agents/content/tests/test_draft_limit.py` | Created — resolution, trimming, and prompt tests |
| `.cursor/rules/phase-8-2-content-agent-draft-limit.mdc` | Updated — code enforcement requirement |
| `.env.example` | Updated — `CONTENT_AGENT_MAX_DRAFTS_PER_RUN` |
| `docs/phases/step-8.2.md` | Created — this document |

---

## How the max draft limit is resolved

Module: `agents/content/draft_limit.py`

| Constant | Value | Purpose |
|----------|-------|---------|
| `DEFAULT_MAX_DRAFTS_PER_RUN` | `3` | MVP default when no valid configuration exists |
| `HARD_MAX_DRAFTS_PER_RUN` | `5` | Upper clamp for excessively high configured values |

### Resolution order

1. **Request-level override** — `max_drafts_per_run` on `build_content_draft_messages()` / `build_content_draft_system_prompt()`, or `request_max_drafts` on `apply_content_draft_limit()` / `normalize_content_agent_output()`
2. **Store settings** — `store.settings.content_agent.max_drafts_per_run`
3. **Environment** — `CONTENT_AGENT_MAX_DRAFTS_PER_RUN`
4. **Fallback** — `3`

### Validation rules

| Input | Result |
|-------|--------|
| Missing / `None` | Try next source; final fallback `3` |
| Non-integer (e.g. `"bad"`, `true`) | Skip that source; try next; final fallback `3` |
| Integer `< 1` | Clamp to `1` |
| Integer `> 5` | Clamp to `5` |
| Valid integer in `[1, 5]` | Use as-is |

Resolution is deterministic and never raises on malformed store settings.

---

## Global vs per-category limit

The MVP output envelope uses a single combined **`drafts`** array for all suggestion types (`content.instagram_draft` and `content.product_description`). The limit applies **globally across all drafts** in that array, in list order (first N kept).

There is no separate per-category cap in this step because the Step 8.1 prompt contract does not define separate draft arrays.

---

## Prompt guidance and code enforcement

### Prompt (guidance only)

`build_content_draft_system_prompt()` resolves the limit and injects:

- A **Draft count limit** section (`at most N draft suggestion(s)`)
- An updated **Draft output contract** (`no more than N draft object(s) in the drafts array`)

### Code (guarantee)

After LLM or mock output is parsed:

```python
from agents.content.analysis import normalize_content_agent_output

limited = normalize_content_agent_output(
    raw_llm_json,
    request_max_drafts=request_max,
    store_settings=store_context.get("settings"),
)
```

`limit_content_suggestions()` trims `result["drafts"]` to the resolved maximum. Excess drafts are dropped silently in MVP; Step 8.3 may add warnings when trimming occurs.

Draft objects retain `content.instagram_draft` / `content.product_description` action types and remain reviewable, approval-required suggestions — no auto-publishing.

---

## API summary

| Symbol | Description |
|--------|-------------|
| `resolve_max_drafts_per_run(...)` | Resolve validated max drafts for a run |
| `limit_content_suggestions(result, max_drafts)` | Trim `drafts` list in a parsed result dict |
| `apply_content_draft_limit(result, ...)` | Resolve limit and trim in one call |
| `normalize_content_agent_output(raw_output, ...)` | Parse JSON + enforce limit (pipeline hook) |

---

## Tests added

`agents/content/tests/test_draft_limit.py`:

- Default limit is 3 when no setting exists
- Store setting can change the limit
- Request override takes precedence over store and env
- Invalid store/request settings fall back safely
- Value below 1 clamps to 1
- Value above hard maximum clamps to 5
- Environment variable used when store setting missing
- Content Agent output trimmed to resolved max
- Prompt includes resolved max draft count
- Draft action types remain approval-compatible
- No LLM API key required

---

## Validation commands

Run focused Step 8.2 tests:

```bash
PYTHONPATH=. python -m unittest agents.content.tests.test_draft_limit -v
```

Run all Content Agent tests (8.1 + 8.2):

```bash
PYTHONPATH=. python -m unittest agents.content.tests -v
```

Run all agent unit tests:

```bash
PYTHONPATH=. python -m unittest discover -s agents -p 'test_*.py' -v
```

---

## Multi-tenancy notes

- Limits come from per-store `settings.content_agent.max_drafts_per_run` when provided in context.
- Missing or malformed `settings` never crash the agent; defaults apply.
- No Prestia-specific values, categories, handles, or brand voice are hardcoded.
- Request-level overrides support future coordinator/report-run specific limits without code changes.

---

## Known limitations

| Limitation | Notes |
|------------|-------|
| No `ContentSuggestions` Pydantic schema yet | Deferred to Step 8.3; trimming operates on parsed dicts |
| No `/run` endpoint on content-agent | Normalization hook exists; HTTP wiring is later Phase 8 work |
| No trim warning in output | Excess drafts dropped silently; may add `warnings[]` in 8.3 |
| Single `drafts` array only | Separate category arrays not supported until schema defines them |
| No Django `Store.settings` field yet | Settings passed via structured context as in Step 8.1 |

---

## Intentionally deferred to Step 8.3

| Item | Deferred to |
|------|-------------|
| Full `ContentSuggestions` schema validation | Step 8.3 |
| Expanded invalid-output and trim-warning tests | Step 8.3 |
| FastAPI `/run` endpoint with validated response | Full Phase 8 pipeline |
| Django product fetch and action persistence | Full Phase 8 pipeline |
| Coordinator integration | Phase 10 |

---

## Acceptance checklist

- [x] Deterministic max-drafts-per-run mechanism
- [x] Default limit is 3
- [x] Malformed or missing configuration cannot crash the agent
- [x] Excessive draft output trimmed in code
- [x] Prompt guidance includes resolved max count
- [x] Generated suggestions remain reviewable and approval-required
- [x] No external publishing behavior introduced
- [x] No Prestia-specific business logic hardcoded
- [x] Focused tests pass
- [x] `docs/phases/step-8.2.md` documents the implementation
