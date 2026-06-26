# Step 6.2 — `DjangoClient` with Retry and Correlation ID Header

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Provide a small, reusable HTTP client under `agents/shared/` that FastAPI AI services will use to call Django internal APIs. The client forwards service JWTs and correlation IDs, applies configurable timeouts, and retries safe transient GET failures.

This step establishes the Django boundary client before JSON schema validation, coordinator stubs, or real agent workflows are wired.

---

## Scope of this step

- Shared Django HTTP client package: `agents/shared/django_client/`
- Environment documentation in `.env.example`
- Focused unit tests in `agents/shared/tests/test_django_client.py`
- Cursor scope rule at `.cursor/rules/step-6.2-django-client.mdc`
- `httpx` added to `agents/requirements.txt`
- This documentation file

**Not in scope:** JSON schema validation, Pydantic agent I/O schemas, coordinator stub endpoint, `LLMProvider`, LangGraph, real agent business logic, or real external service calls.

---

## Why a shared Django client exists

AI agent services must not access Postgres directly. Django is the source of truth and exposes tenant-scoped internal APIs under `/internal/ai/*`. Every agent needs the same HTTP behavior:

- Correct base URL joining for Docker DNS names
- `Authorization: Bearer <service_jwt>` forwarding
- `X-Request-ID` correlation for cross-service tracing
- Bounded retries for transient infrastructure failures on safe GET requests
- Clear, typed errors instead of ad hoc `requests` calls in each agent

A single shared client keeps auth, retry, and error semantics consistent across coordinator and specialist agents.

---

## File / module layout

| Path | Purpose |
|------|---------|
| `agents/shared/django_client/__init__.py` | Public exports |
| `agents/shared/django_client/client.py` | `DjangoClient` implementation |
| `agents/shared/django_client/errors.py` | Client exception types |
| `agents/shared/tests/test_django_client.py` | Unit tests |
| `agents/requirements.txt` | Adds `httpx` runtime dependency |

---

## Client API

Module: `agents/shared/django_client`

### `DjangoClient`

```python
from agents.shared.django_client import DjangoClient

client = DjangoClient(
    service_token=service_jwt,
    request_id=request_id,
)

context = client.get(f"/internal/ai/context/{report_run_id}/")
```

Constructor parameters (all optional except that a base URL must be available from `base_url` or `DJANGO_INTERNAL_BASE_URL`):

| Parameter | Description |
|-----------|-------------|
| `base_url` | Django internal base URL; defaults to `DJANGO_INTERNAL_BASE_URL` |
| `service_token` | Service JWT sent as `Authorization: Bearer ...` when provided |
| `request_id` | Correlation ID sent as `X-Request-ID` when provided |
| `timeout_seconds` | Per-request timeout; defaults to `DJANGO_CLIENT_TIMEOUT_SECONDS` or `30` |
| `max_retries` | Additional retry attempts after transient failures; defaults to `DJANGO_CLIENT_MAX_RETRIES` or `2` |
| `retry_backoff_seconds` | Base backoff delay; defaults to `DJANGO_CLIENT_RETRY_BACKOFF_SECONDS` or `0.25` |
| `http_client` | Optional injected `httpx.Client` (primarily for tests) |

### Methods

| Method | Behavior |
|--------|----------|
| `get(path, *, params=None) -> dict` | JSON GET with retries enabled |
| `post(path, *, json=None, retry=False) -> dict` | JSON POST; retries disabled unless `retry=True` |
| `close()` | Close the underlying HTTP client when owned by `DjangoClient` |

Helper functions `normalize_base_url()` and `join_url()` are exported for URL joining tests and reuse.

---

## Environment variables

```env
DJANGO_INTERNAL_BASE_URL=http://backend:8000
DJANGO_CLIENT_TIMEOUT_SECONDS=30
DJANGO_CLIENT_MAX_RETRIES=2
DJANGO_CLIENT_RETRY_BACKOFF_SECONDS=0.25
```

Documented in `.env.example`. Agent containers receive these through compose `env_file` when the client is imported in later steps.

Constructor arguments override environment values, which keeps unit tests deterministic.

---

## JWT forwarding behavior

When `service_token` is provided at construction time, every request includes:

```http
Authorization: Bearer <service_token>
```

The client does not mint tokens. Django Celery tasks or coordinator workflows mint short-lived service JWTs (Phase 2) and pass them into `DjangoClient`.

No token values are logged.

---

## `X-Request-ID` correlation behavior

When `request_id` is provided, every request includes:

```http
X-Request-ID: <request_id>
```

This ties agent logs to Django, Celery, and nginx request tracing. The client does not generate IDs; callers propagate an existing correlation ID from the workflow.

---

## Retry policy

Retries apply only when enabled for the request method:

| Condition | Retried on GET | Retried on POST (default) |
|-----------|----------------|---------------------------|
| Connection error | Yes | No |
| Timeout | Yes | No |
| HTTP 502 / 503 / 504 | Yes | No |

- `max_retries=2` means up to **three total attempts** (initial try plus two retries).
- Backoff is exponential: `retry_backoff_seconds * 2**attempt` (e.g. `0.25s`, `0.5s`, `1.0s`).
- POST retries are opt-in via `post(..., retry=True)` because POST endpoints may be non-idempotent.

---

## Timeout policy

Each request uses a single client-level timeout configured by `timeout_seconds` or `DJANGO_CLIENT_TIMEOUT_SECONDS` (default `30` seconds). Timeout failures raise `DjangoTimeoutError`.

---

## Error handling behavior

| Exception | When raised |
|-----------|-------------|
| `DjangoConnectionError` | Cannot reach Django (connection failure after retries exhausted) |
| `DjangoTimeoutError` | Request exceeded timeout (after retries exhausted) |
| `DjangoHTTPError` | Non-2xx HTTP response; exposes `status_code` and a safe `detail` message when available |
| `DjangoJSONError` | Response body is not valid JSON or is not a JSON object when JSON is expected |
| `DjangoClientError` | Base class for all client errors |

The client does not log raw request or response payloads.

---

## Tests added

`agents/shared/tests/test_django_client.py` (stdlib `unittest` + `httpx.MockTransport`):

- Base URL normalization and path joining with trailing/leading slashes
- `Authorization` header forwarding when `service_token` is set
- `X-Request-ID` header forwarding when `request_id` is set
- Successful GET returns parsed JSON
- Successful POST sends JSON body and returns parsed JSON
- Non-2xx response raises `DjangoHTTPError` with status code and safe message
- Timeout raises `DjangoTimeoutError`
- Connection error raises `DjangoConnectionError`
- GET retries transient HTTP 503 failures and eventually succeeds
- GET fails after retry exhaustion on persistent 502
- GET retries connection errors
- POST is not retried by default
- Invalid JSON raises `DjangoJSONError`
- Environment variable configuration is read correctly
- Missing base URL raises `ValueError`

No real Django backend or external network is required.

---

## Validation commands

Install shared agent dependencies (once per local environment):

```bash
pip install -r agents/requirements.txt
```

Run focused Django client tests from the repository root:

```bash
PYTHONPATH=. python -m unittest discover -s agents/shared/tests -p 'test_*.py' -v
```

Or run only the Django client tests:

```bash
PYTHONPATH=. python -m unittest agents.shared.tests.test_django_client -v
```

Start the stack (optional — not required for client unit tests):

```bash
docker compose up --build
```

Run Django backend tests (unchanged by this step):

```bash
docker compose exec backend python manage.py test
```

---

## What is intentionally not implemented in this step

- Step 6.3 — JSON schema validation on agent responses
- Step 6.4 — Coordinator stub endpoint accepting report job
- `LLMProvider`, `OpenAIProvider`, `AnthropicProvider`, `MockProvider`
- Pydantic agent I/O schemas
- LangGraph workflows
- Sales, content, or support agent business logic
- Wiring `DjangoClient` into existing FastAPI `/health` stubs
- Real Django API integration tests against the backend container

---

## Next steps

| Step | Focus |
|------|-------|
| **6.3** | JSON schema validation on agent responses |
| **6.4** | Coordinator stub endpoint accepting report job payload from Celery |
