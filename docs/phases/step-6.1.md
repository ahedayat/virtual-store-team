# Step 6.1 — `AI_OUTPUT_LANGUAGE` Prompt Prefix Helper

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Introduce a small, deterministic shared helper under `agents/shared/` that reads `AI_OUTPUT_LANGUAGE`, defaults to Persian (`fa`), and produces reusable system-prompt language instructions for future specialist and coordinator agents.

This step establishes the language contract before LLM providers, Django HTTP clients, schemas, or real agent workflows are wired.

---

## Scope of this step

- Shared package scaffold: `agents/shared/__init__.py`, `agents/shared/language.py`
- Environment documentation in `.env.example`
- Focused unit tests in `agents/shared/tests/test_language.py`
- Cursor scope rule at `.cursor/rules/step-6.1-ai-output-language-helper.mdc`
- This documentation file

**Not in scope:** `DjangoClient`, LLM provider abstraction, JSON schema validation, coordinator stub endpoint, LangGraph, real agent business logic, or real LLM calls.

---

## Why `AI_OUTPUT_LANGUAGE` exists

The MVP targets Persian-speaking store managers (Prestia demo) while keeping the platform generic. Agent prompts must consistently tell the model which language to use for **user-facing** text (report sections, action descriptions, drafts) without hardcoding locale inside each agent.

A single environment variable lets compose, CI, and future per-tenant settings converge on one helper. Structured JSON fields that require a fixed language (for example machine-readable codes) can still override via schema field semantics — the instruction text makes that explicit.

---

## Default language behavior

| Input | `normalize_output_language()` | `get_output_language()` |
|-------|------------------------------|-------------------------|
| Missing / `None` | `fa` | `fa` |
| Empty / whitespace | `fa` | `fa` |
| Supported code or alias | Canonical `fa` or `en` | Canonical `fa` or `en` |
| Unsupported value | Raises `ValueError` | Falls back to `fa` |

**Rationale:** Pure normalization functions fail fast for invalid explicit values (tests, API validation). Environment reads are forgiving so a typo in `.env` does not prevent agent containers from starting.

---

## Supported languages

| Canonical | Aliases (case-insensitive) |
|-----------|----------------------------|
| `fa` (default) | `fa`, `fa-IR`, `persian`, `farsi` |
| `en` | `en`, `en-US`, `english` |

---

## Helper API

Module: `agents/shared/language.py`

| Symbol | Description |
|--------|-------------|
| `DEFAULT_OUTPUT_LANGUAGE` | `"fa"` |
| `SUPPORTED_OUTPUT_LANGUAGES` | `frozenset({"fa", "en"})` |
| `normalize_output_language(value)` | Normalize alias/code; default blank → `fa`; unsupported → `ValueError` |
| `get_output_language()` | Read `AI_OUTPUT_LANGUAGE` from environment |
| `get_language_instruction(language=None)` | Stable prompt instruction string for Persian or English |
| `build_language_prompt_prefix(language=None)` | Alias of `get_language_instruction()` for prepend use cases |

The helper uses only the Python standard library (`os`, `re`). It does not import OpenAI, Anthropic, LangChain, LangGraph, FastAPI, Django, or any network client.

### Instruction semantics

**Persian (`fa`):**

> Generate all user-facing AI output in Persian (fa). Use clear, natural Persian unless a schema field explicitly requires another language.

**English (`en`):**

> Generate all user-facing AI output in English (en). Use clear, natural English unless a schema field explicitly requires another language.

---

## Environment variable

```env
AI_OUTPUT_LANGUAGE=fa
```

Documented in `.env.example`. All agent containers receive this via compose `env_file` when agents start importing the helper in later steps.

---

## Example usage for future agents

```python
from agents.shared.language import get_language_instruction

system_prompt = "\n".join([
    "You are the sales analyst agent.",
    get_language_instruction(),
])
```

To force a language without reading the environment:

```python
from agents.shared.language import build_language_prompt_prefix

prefix = build_language_prompt_prefix("en")
```

---

## Files changed

| File | Change |
|------|--------|
| `agents/__init__.py` | Created — minimal package marker |
| `agents/shared/__init__.py` | Created — re-exports language helpers |
| `agents/shared/language.py` | Created — language helper implementation |
| `agents/shared/tests/test_language.py` | Created — unit tests |
| `.env.example` | Updated — `AI_OUTPUT_LANGUAGE=fa` with Step 6.1 comment |
| `.cursor/rules/step-6.1-ai-output-language-helper.mdc` | Scoped globs to `agents/shared/**` |

---

## Tests added

`agents/shared/tests/test_language.py` (stdlib `unittest`):

- Missing / empty values default to `fa`
- `fa` and `en` canonical codes
- Alias normalization (`fa-IR`, `persian`, `en-US`, `english`, …)
- Unsupported values raise `ValueError` in `normalize_output_language`
- Unsupported env value falls back to `fa` in `get_output_language`
- `get_language_instruction()` returns stable Persian/English directive text
- `build_language_prompt_prefix()` matches `get_language_instruction()`

No real LLM or network behavior is tested.

---

## Validation commands

Start the stack (optional — not required for language helper tests):

```bash
docker compose up --build
```

Run Django backend tests (unchanged by this step):

```bash
docker compose exec backend python manage.py test
```

Run focused language helper tests from the repository root:

```bash
PYTHONPATH=. python -m unittest discover -s agents/shared/tests -p 'test_*.py' -v
```

Inside a Python 3.12+ environment at the repo root:

```bash
PYTHONPATH=. python -m unittest agents.shared.tests.test_language -v
```

---

## What is intentionally not implemented in this step

- Step 6.2 — `DjangoClient` with retry and correlation ID header
- Step 6.3 — JSON schema validation on agent responses
- Step 6.4 — Coordinator stub endpoint accepting report jobs
- `LLMProvider`, `OpenAIProvider`, `AnthropicProvider`, `MockProvider`
- LangGraph workflows
- Sales, content, or support agent business logic
- Wiring the helper into existing FastAPI `/health` stubs
- Real LLM provider calls

---

## Next steps

| Step | Focus |
|------|-------|
| **6.2** | `DjangoClient` with retry and `X-Request-ID` / correlation ID header |
| **6.3** | JSON schema validation on agent responses |
| **6.4** | Coordinator stub endpoint accepting report job payload from Celery |
