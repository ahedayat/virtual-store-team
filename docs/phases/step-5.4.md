# Step 5.4 — Integration Test with Mock Coordinator HTTP Server

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Prove the Phase 5 async daily report generation flow end-to-end inside the Django/Celery boundary using a mock coordinator HTTP server. Tests must run without a real `coordinator-agent` container, LangGraph, specialist agents, or LLM providers.

---

## Scope of this step

- Mock coordinator HTTP server test helper
- Integration tests for success, failure, timeout/connection error, and duplicate-run regression
- Celery eager mode for deterministic in-test task execution
- Coordinator request contract verification (payload + service JWT `Authorization` header)
- Cursor scope rule at `.cursor/rules/step-5.4-mock-coordinator-integration.mdc`
- Phase 5 completion summary

**Not in scope:** Phase 6 agent scaffold, real coordinator service, LangGraph, LLM abstraction, real report content generation, or changes to duplicate-prevention logic beyond test coverage.

---

## Mock coordinator test strategy

The project uses Django’s built-in test runner (`manage.py test`), not pytest. Rather than adding `pytest-httpserver` as a new dev dependency, tests use a lightweight **stdlib** `ThreadingHTTPServer` bound to an ephemeral `127.0.0.1` port.

Helper: `backend/operations/tests/mock_coordinator_server.py`

| Component | Role |
|-----------|------|
| `MockCoordinatorServer` | Starts/stops threaded HTTP server, captures requests |
| `MockCoordinatorHTTPServer` | Configurable status, JSON body, and response delay |
| Request capture | Method, path, headers (including `Authorization`), raw body |

The Celery task calls the real `CoordinatorDailyReportClient` over HTTP (`urllib.request.urlopen`). The mock server is the HTTP boundary — the coordinator client is **not** patched away in integration tests.

---

## Coordinator request contract

The mock server asserts each coordinator `POST` receives:

```json
{
  "report_run_id": "<uuid>",
  "tenant_id": "<uuid>",
  "store_id": "<uuid>",
  "context_ref": {
    "type": "report_run",
    "id": "<uuid>"
  }
}
```

**Authentication:** Phase 2 service JWT minting is wired into `CoordinatorDailyReportClient.build_auth_headers()`. Integration tests verify:

```
Authorization: Bearer <token>
```

Decoded claims include `sub=coordinator-agent`, matching `tenant_id`, `store_id`, and `report_run_id`.

---

## Celery eager mode (deterministic task execution)

Integration tests enable Celery eager execution via Django `override_settings`:

```python
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

With eager mode, `generate_daily.delay(...)` from `POST /api/reports/generate/` runs the task synchronously in the test process. Production Celery settings are unchanged.

---

## Success-path behavior

**Test:** `test_success_path_completes_report_run_via_mock_coordinator`

1. Manager calls `POST /api/reports/generate/`.
2. API creates a `ReportRun` with status `queued` and enqueues the Celery task (runs immediately in eager mode).
3. Task transitions the run to `running`.
4. Task `POST`s to the mock coordinator at `COORDINATOR_DAILY_REPORT_URL`.
5. Mock returns HTTP `200` with minimal JSON `{"status":"accepted"}`.
6. Task marks the run `completed` via skeleton fallback (`mark_completed_if_still_running`) because the mock does not call the internal complete API.

**Note:** In Phase 10, the real coordinator will call `POST /internal/ai/report-runs/{id}/complete/`; the Celery task will observe `completed` after refresh and skip skeleton completion (see Step 5.2).

---

## Failure-path behavior

| Test | Mock behavior | Expected `ReportRun` |
|------|---------------|----------------------|
| `test_coordinator_http_500_marks_report_run_failed_with_safe_error` | HTTP `500` with JSON body containing fake PII | `failed`; `error_message` contains `500` but **not** email/phone from response body |
| `test_coordinator_connection_error_marks_report_run_failed` | URL points to closed port | `failed`; safe connection error message |
| `test_coordinator_timeout_marks_report_run_failed` | Server delays 2s; timeout set to 1s | `failed`; message mentions timeout |

Error messages store only safe summaries (HTTP status or transport error). Raw coordinator response bodies are never persisted on `ReportRun.error_message`.

---

## Duplicate-run regression coverage

Step 5.3 duplicate prevention is exercised at integration level without patching `generate_daily.delay`:

| Test | Setup | Expected |
|------|-------|----------|
| `test_duplicate_active_run_does_not_call_coordinator` | Existing `queued` run | HTTP `409`; mock receives **0** requests |
| `test_duplicate_running_run_does_not_call_coordinator` | Existing `running` run | HTTP `409`; mock receives **0** requests |

Unit/API duplicate tests in `test_report_generate_api.py` (with mocked `delay`) remain; integration tests add HTTP-boundary regression coverage.

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/tests/mock_coordinator_server.py` | Created — threaded mock coordinator HTTP server |
| `backend/operations/tests/test_coordinator_integration.py` | Created — integration tests |
| `backend/operations/coordinator_client.py` | Updated — map `TimeoutError` to `CoordinatorClientError` |
| `backend/operations/tests/test_internal_report_run_complete_api.py` | Updated — respect active-run unique constraint in test helper |
| `.cursor/rules/step-5.4-mock-coordinator-integration.mdc` | Scope rule for this step |
| `docs/phases/step-5.4.md` | Created — this document |

No new production or test pip dependencies were added. Stdlib `http.server` was chosen because the project uses Django `TestCase`/`APITestCase`, not pytest.

---

## Test commands

Start the stack:

```bash
docker compose up --build
```

Check services:

```bash
docker compose ps
```

Run all backend tests:

```bash
docker compose exec backend python manage.py test
```

Focused integration tests:

```bash
docker compose exec backend python manage.py test operations.tests.test_coordinator_integration
```

Other Phase 5 tests:

```bash
docker compose exec backend python manage.py test operations.tests.test_generate_daily_task operations.tests.test_report_generate_api
```

---

## What is intentionally not implemented in this step

- Phase 6 — agent scaffold, FastAPI services, `MockProvider`, shared LLM library
- Real `coordinator-agent` container or LangGraph workflow
- Specialist agent logic (sales, content, support)
- Real `DailyReport` content from coordinator
- Calls to real external LLM or AI services
- `pytest-httpserver` (not required; stdlib server used instead)

---

## Phase 5 completion summary

Phase 5 — **Celery & Async Wiring** is complete:

| Step | Deliverable | Status |
|------|-------------|--------|
| 5.1 | Celery + Redis wiring in compose | Done |
| 5.2 | `reports.generate_daily` task lifecycle + coordinator HTTP client | Done |
| 5.3 | Duplicate concurrent run prevention per store | Done |
| 5.4 | Mock coordinator integration tests | Done |

The platform can:

- Accept manager-triggered report generation via `POST /api/reports/generate/`
- Enqueue and run the Celery task with `ReportRun` status transitions
- Call the coordinator over HTTP with service JWT and structured payload
- Mark runs `completed` or `failed` with safe error messages
- Block duplicate active runs per store

---

## Next phase

**Phase 6: Agent Scaffold & LLM Abstraction**

- Shared `agents/shared/` library (`llm/`, `django_client/`, schemas)
- FastAPI containers for coordinator, sales, content, and support agents
- `MockProvider` for deterministic agent output without API keys
- Coordinator stub endpoint accepting report jobs (replacing the test-only mock in production compose)
