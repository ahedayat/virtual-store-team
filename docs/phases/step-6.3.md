# Step 6.3 — JSON Schema Validation on Agent Responses

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Provide a reusable validation layer under `agents/shared/` that future FastAPI agent services can use to validate structured JSON outputs from LLM calls before returning them to the coordinator or persisting them through Django.

This step establishes the schema validation foundation before coordinator stubs, LLM provider abstraction, or specialist agent business logic are wired.

---

## Scope of this step

- Shared schemas package: `agents/shared/schemas/`
- Validation utilities and custom errors
- Minimal generic base schemas for shared metadata and warnings
- Focused unit tests in `agents/shared/tests/test_schemas_validation.py`
- Cursor scope rule at `.cursor/rules/step-6.3-agent-response-validation.mdc`
- `pydantic` added to `agents/requirements.txt`
- This documentation file

**Not in scope:** Coordinator stub endpoint, `LLMProvider`, LangGraph, FastAPI `/run` or workflow endpoints, sales/content/support business schemas, real LLM calls, or real Django API calls.

---

## Why JSON schema validation is required

Specialist and coordinator agents must return **structured JSON** that downstream systems can trust:

- The coordinator merges agent outputs into a daily report.
- Django persists `AgentOutput` records and creates `Action` rows from typed payloads.
- Invalid or partially formed JSON from an LLM must fail fast with clear, safe errors instead of corrupting report data.

A shared validator keeps schema rules, extra-field policy, and error formatting consistent across all agents. Future phases (7–9) add business-specific schemas; this step provides the generic machinery they will reuse.

---

## File / module layout

| Path | Purpose |
|------|---------|
| `agents/shared/schemas/__init__.py` | Public exports |
| `agents/shared/schemas/base.py` | Generic shared Pydantic models |
| `agents/shared/schemas/validation.py` | `validate_agent_response()`, `export_json_schema()` |
| `agents/shared/schemas/errors.py` | Custom validation exceptions |
| `agents/shared/tests/test_schemas_validation.py` | Unit tests |
| `agents/requirements.txt` | Adds `pydantic` runtime dependency |

The validation module imports only Pydantic and the standard library. It does **not** import Django, Celery, FastAPI app modules, LangGraph, or LLM provider SDKs.

---

## Validation API

Module: `agents.shared.schemas`

### `validate_agent_response(payload, schema_model)`

```python
from agents.shared.schemas.validation import validate_agent_response
from agents.shared.schemas.base import BaseAgentResponse

validated = validate_agent_response(payload, BaseAgentResponse)
```

| Behavior | Detail |
|----------|--------|
| Input | `payload` — Python `dict` parsed from JSON |
| Schema | `schema_model` — Pydantic `BaseModel` subclass |
| Success | Returns a typed, validated model instance |
| Failure | Raises `AgentSchemaValidationError` with field paths and safe messages |
| Non-dict input | Raises `AgentSchemaValidationError` without echoing the raw payload |

### `export_json_schema(schema_model)`

```python
from agents.shared.schemas.validation import export_json_schema

schema_document = export_json_schema(BaseAgentResponse)
```

Returns a JSON Schema dictionary suitable for prompts, tests, or documentation. Raises `AgentSchemaConfigurationError` when `schema_model` is not a valid Pydantic model.

---

## Base schemas added

Generic shared models in `agents.shared.schemas.base`:

| Model | Fields | Purpose |
|-------|--------|---------|
| `StrictAgentModel` | — | Base class with `extra="forbid"` |
| `AgentWarning` | `code`, `message` | Non-fatal issues in an agent response |
| `ScopeViolation` | `requested_scope`, `reason` | Structured out-of-scope refusal (coordinator contract) |
| `AgentResponseMetadata` | `agent_name`, `report_run_id` | Common response header metadata |
| `BaseAgentResponse` | `metadata`, `warnings` | Minimal envelope future agents can extend |

Business-specific schemas such as `SalesAnalysisResult`, `ContentSuggestions`, and `SupportInsights` belong to Phases 7, 8, and 9 — not this step.

---

## Error handling behavior

| Exception | When raised |
|-----------|-------------|
| `AgentSchemaError` | Base class for schema-related failures |
| `AgentSchemaValidationError` | Payload fails validation against the provided model |
| `AgentSchemaConfigurationError` | `schema_model` is not a Pydantic `BaseModel` subclass |

`AgentSchemaValidationError` exposes:

- `schema_name` — model class name
- `field_errors` — list of `{"field", "message", "type"}` entries with dotted paths (e.g. `metadata.agent_name`, `warnings[0].message`)
- A human-readable `str(exception)` summary

**Safety rules:**

- Exception messages do **not** include the raw full payload.
- Validation does **not** log payloads.
- Field error details omit unsafe `input` values from Pydantic internals.

---

## Extra-field policy

All shared agent response schemas inherit from `StrictAgentModel`, which sets Pydantic `model_config = ConfigDict(extra="forbid")`.

| Policy | Behavior |
|--------|----------|
| Unknown top-level fields | Rejected |
| Unknown nested fields | Rejected |
| Rationale | LLM outputs must match the contract exactly; silent acceptance of extra keys hides prompt or parsing bugs |

Future agent-specific schemas should inherit `StrictAgentModel` (or set the same `extra="forbid"` config) unless a documented exception is required.

---

## Example usage for future agents

```python
from enum import StrEnum

from agents.shared.schemas.base import AgentResponseMetadata, StrictAgentModel
from agents.shared.schemas.validation import export_json_schema, validate_agent_response


class SalesPriority(StrEnum):
    LOW = "low"
    HIGH = "high"


class SalesRecommendation(StrictAgentModel):
    sku: str
    priority: SalesPriority
    rationale: str


class SalesAnalysisResult(StrictAgentModel):
    metadata: AgentResponseMetadata
    recommendations: list[SalesRecommendation]


# After parsing LLM JSON into a dict:
validated = validate_agent_response(llm_payload, SalesAnalysisResult)

# Optional: embed schema in a prompt or test fixture
schema_doc = export_json_schema(SalesAnalysisResult)
```

Scope violation example:

```python
from agents.shared.schemas.base import ScopeViolation
from agents.shared.schemas.validation import validate_agent_response

violation = validate_agent_response(
    {
        "requested_scope": "publish_instagram",
        "reason": "Content agent cannot publish posts in MVP.",
    },
    ScopeViolation,
)
```

---

## Tests added

`agents/shared/tests/test_schemas_validation.py` (stdlib `unittest`):

- Valid payload passes validation and returns a typed object
- Missing required field fails validation with field path
- Wrong field type fails validation
- Invalid enum/literal value fails validation
- Extra fields are forbidden and fail validation
- Error message contains useful field-level details
- Error message does not include the raw full payload
- Non-dict payload fails without echoing payload contents
- Dummy future-agent schema (`DummyAgentResult`) uses `validate_agent_response()` successfully
- `export_json_schema()` returns a dictionary with expected structure
- Invalid model passed to `export_json_schema()` raises `AgentSchemaConfigurationError`
- Nested warning models validate correctly
- `StrictAgentModel` forbids extra fields on ad hoc test schemas

No real LLM providers or Django APIs are required.

---

## Validation commands

Install shared agent dependencies (once per local environment):

```bash
pip install -r agents/requirements.txt
```

Run all shared agent tests from the repository root:

```bash
PYTHONPATH=. python -m unittest discover -s agents/shared/tests -p 'test_*.py' -v
```

Run only schema validation tests:

```bash
PYTHONPATH=. python -m unittest agents.shared.tests.test_schemas_validation -v
```

Start the stack (optional — not required for schema unit tests):

```bash
docker compose up --build
```

Run Django backend tests (unchanged by this step):

```bash
docker compose exec backend python manage.py test
```

---

## What is intentionally not implemented in this step

- Step 6.4 — Coordinator stub endpoint accepting report job
- `LLMProvider`, `OpenAIProvider`, `AnthropicProvider`, `MockProvider`
- FastAPI `/run` or workflow endpoints
- LangGraph workflows
- Final `SalesAnalysisResult`, `ContentSuggestions`, or `SupportInsights` business schemas
- Wiring validation into existing agent `/health` stubs
- Real LLM calls or Django API integration tests

---

## Next step

| Step | Focus |
|------|-------|
| **6.4** | Coordinator stub endpoint accepting report job payload from Celery |
