# Step 6.8 — Agent Scaffold Verification Across All Four Agents

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Scope

Add lightweight cross-agent verification tests proving the Phase 6 scaffold contract across coordinator, sales, content, and support agents. Tests use FastAPI `TestClient` only — no Docker smoke tests.

---

## Verification matrix

| Agent | Health | Structured workflow | `LLM_PROVIDER=mock` | No real LLM API |
|-------|--------|---------------------|---------------------|-----------------|
| `coordinator-agent` | `GET /health` | `POST /workflows/daily-report` stub | N/A (no LLM) | Yes |
| `sales-agent` | `GET /health` | `POST /run` | Mock recommendations | Yes |
| `content-agent` | `GET /health` | `POST /run` | Mock drafts | Yes |
| `support-agent` | `GET /health` | `POST /run` | Mock support reply | Yes |

**Also verified (existing suites, re-run in Step 6.9):**

- Shared `DjangoClient` unit tests
- Shared schema validation tests
- Shared language helper tests
- Coordinator daily-report stub tests

---

## Files changed

| Path | Change |
|------|--------|
| `agents/shared/tests/test_phase6_scaffold.py` | Cross-agent verification tests |
| `docs/phases/step-6.8.md` | This document |

---

## Commands run

```bash
PYTHONPATH=. python -m unittest agents.shared.tests.test_phase6_scaffold -v
PYTHONPATH=. python -m unittest agents.shared.tests.test_django_client -v
PYTHONPATH=. python -m unittest agents.shared.tests.test_schemas_validation -v
PYTHONPATH=. python -m unittest agents.shared.tests.test_language -v
PYTHONPATH=. python -m unittest agents.coordinator.tests.test_daily_report_stub -v
```

**Results:**

| Suite | Tests | Result |
|-------|-------|--------|
| `test_phase6_scaffold` | 6 | Passed |
| `test_django_client` | (existing) | Passed |
| `test_schemas_validation` | (existing) | Passed |
| `test_language` | (existing) | Passed |
| `test_daily_report_stub` | (existing) | Passed |

---

## Remaining risks

- Container startup and Docker healthchecks are not re-verified in this step (covered by Phase 0.8/0.11).
- Real LLM provider integration remains deferred.
- Full LangGraph orchestration and Django context fetch remain Phase 10 work.

---

## Acceptance criteria

- [x] All four agents verified for health endpoints
- [x] Structured output paths verified where scaffold workflows exist
- [x] `LLM_PROVIDER=mock` produces structured output without external API keys
- [x] No test depends on real LLM APIs
- [x] Shared Django client and schema validation tests still pass
- [x] Coordinator daily-report stub tests still pass
