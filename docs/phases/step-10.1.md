# Step 10.1 — Coordinator Star Topology

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-27  
**Status:** Implemented

---

## Objective

Establish and verify the coordinator-agent **star-topology contract**: the coordinator is the only orchestrator that calls specialist agents. Sales, content, and support agents must not call each other directly.

This step is topology foundation only — not full LangGraph orchestration, merge logic, or daily report completion.

---

## Scope

### In scope

- Explicit star-topology contract module (`agents/coordinator/topology.py`)
- Coordinator specialist HTTP client (`agents/coordinator/specialist_clients.py`)
- Lightweight daily report workflow node scaffold (`agents/coordinator/workflow.py`)
- Deterministic unit tests (`agents/coordinator/tests/test_star_topology.py`)
- Step documentation (this file)

### Out of scope (explicit non-goals)

| Area | Deferred work |
|------|----------------|
| Phase 10.2 | Node timeout behavior |
| Phase 10.3 | Intermediate `AgentOutput` persistence |
| Phase 10.4 | Full graph integration test |
| — | End-to-end daily report orchestration (merge, submit, Celery → Django `ReportRun=completed`) |
| — | LangGraph graph state and real node execution |
| — | Frontend changes |
| — | Specialist agent behavior changes |
| — | Real external side effects, LLM API calls, or API keys |
| — | Direct database access from agents |
| — | Prestia-specific hardcoding |

---

## Files created/updated

| File | Change |
|------|--------|
| `agents/coordinator/topology.py` | Created — star topology contract, URL resolution, `assert_star_topology()` |
| `agents/coordinator/specialist_clients.py` | Created — `SpecialistAgentClient` for coordinator `POST /run` calls |
| `agents/coordinator/workflow.py` | Created — daily report workflow node name scaffold |
| `agents/coordinator/tests/test_star_topology.py` | Created — topology contract and mocked HTTP client tests |
| `docs/phases/step-10.1.md` | Created — this document |

**Unchanged:** Specialist agent services (`sales-agent`, `content-agent`, `support-agent`), coordinator stub endpoint (`POST /workflows/daily-report`), `.env.example` (specialist URL variables already present).

---

## Star topology contract

```
                    coordinator-agent
                   /        |         \
                  /         |          \
          sales-agent   content-agent   support-agent
```

1. **Coordinator may call** `sales-agent`, `content-agent`, and `support-agent` via configured service URLs and `POST /run`.
2. **Specialist agents must not call each other directly.**
3. **No agent mesh** — peer-to-peer specialist HTTP calls are disallowed.
4. **Coordinator client imports** shared HTTP utilities and topology only — not specialist business modules (`agents.sales.analysis`, etc.).
5. **Service URLs** come from environment/settings, not hardcoded tenant values.

Enforcement helpers:

| Symbol | Purpose |
|--------|---------|
| `SpecialistAgentName` | Allowed callee enum: `sales`, `content`, `support` |
| `get_allowed_specialist_agents()` | Returns the allowed specialist set |
| `SPECIALIST_PEER_CALL_PATHS` | Must remain empty (no peer edges) |
| `build_specialist_run_url()` | Builds `{base_url}/run` for a specialist |
| `assert_star_topology()` | Runtime/test assertion of the contract |

---

## Allowed specialist agents

| Agent | Service URL env var | Default (Docker Compose) | Run endpoint |
|-------|---------------------|--------------------------|--------------|
| `sales` | `SALES_AGENT_URL` | `http://sales-agent:8101` | `POST /run` |
| `content` | `CONTENT_AGENT_URL` | `http://content-agent:8102` | `POST /run` |
| `support` | `SUPPORT_AGENT_URL` | `http://support-agent:8103` | `POST /run` |

Unknown specialist names raise `UnknownSpecialistAgentError`.

---

## Disallowed agent-to-agent communication

- Sales agent must not call content or support agents.
- Content agent must not call sales or support agents.
- Support agent must not call sales or content agents.
- No specialist-to-specialist URL env references in specialist agent source (verified by static test).
- `SPECIALIST_PEER_CALL_PATHS` must remain an empty set.

---

## Coordinator specialist-client behavior

`SpecialistAgentClient` (`agents/coordinator/specialist_clients.py`):

| Method | Behavior |
|--------|----------|
| `prepare_run_request(agent_name, payload)` | Returns `(url, headers, json_body)` without HTTP |
| `run_specialist(agent_name, payload)` | `POST` to specialist `/run` |
| `run_sales(payload)` | Delegates to `run_specialist(SALES, ...)` |
| `run_content(payload)` | Delegates to `run_specialist(CONTENT, ...)` |
| `run_support(payload)` | Delegates to `run_specialist(SUPPORT, ...)` |

Header forwarding (aligned with Step 6.2 Django client conventions):

| Header | When set |
|--------|----------|
| `Authorization: Bearer <token>` | When `service_token` is provided on the client |
| `X-Request-ID` | When `request_id` is provided on the client |
| `Content-Type: application/json` | Always for run requests |

The client does not auto-approve actions, execute specialist side effects, query the database, or call LLM providers.

---

## Settings/environment variables used

| Variable | Purpose |
|----------|---------|
| `SALES_AGENT_URL` | Base URL for sales-agent |
| `CONTENT_AGENT_URL` | Base URL for content-agent |
| `SUPPORT_AGENT_URL` | Base URL for support-agent |

These variables are already documented in `.env.example`. Compose-friendly defaults apply when a variable is unset (not tenant-specific).

---

## Workflow scaffold (Step 10.1 only)

`agents/coordinator/workflow.py` defines conceptual LangGraph node names for the future daily report workflow:

| Node | Step 10.1 status |
|------|------------------|
| `fetch_context` | Name only — behavior deferred |
| `run_sales` | Name only — will call `SpecialistAgentClient.run_sales` in Phase 10 |
| `run_content` | Name only — will call `SpecialistAgentClient.run_content` in Phase 10 |
| `run_support` | Name only — will call `SpecialistAgentClient.run_support` in Phase 10 |
| `merge` | Name only — deferred |
| `submit` | Name only — deferred |

No LangGraph graph, timeouts, persistence, or merge logic is implemented in this step.

---

## Relationship to Phase 10 future steps

| Step | Focus |
|------|-------|
| **10.1** (this step) | Star topology contract and coordinator specialist client |
| **10.2** | Timeout per workflow node |
| **10.3** | Persist intermediate `AgentOutput` records via Django client |
| **10.4** | Full graph integration test with mock LLM across services |
| **10+** | LangGraph workflow, context fetch, parallel specialist runs, merge/prioritize, Django report completion |

---

## Verification commands run

```bash
PYTHONPATH=. python -m unittest agents.coordinator.tests.test_star_topology -v
PYTHONPATH=. python -m unittest discover agents/coordinator/tests -v
PYTHONPATH=. python -m unittest agents.coordinator.tests.test_daily_report_stub -v
```

**Results:**

| Suite | Tests | Result |
|-------|-------|--------|
| `test_star_topology` | 20 | Passed |
| `discover agents/coordinator/tests` | 34 | Passed |
| `test_daily_report_stub` | 14 | Passed |

---

## Acceptance criteria checklist

- [x] Coordinator star-topology contract is explicit in code and documentation
- [x] Allowed specialist agents are `sales`, `content`, and `support`
- [x] Specialist service URLs are configurable through settings/environment
- [x] Coordinator can build and prepare calls to specialist `/run` endpoints
- [x] Unknown specialist names are rejected
- [x] No specialist-to-specialist communication is introduced
- [x] No agent mesh behavior is introduced
- [x] No Phase 10.2, 10.3, or 10.4 work is implemented
- [x] No real HTTP/LLM/external-service calls are required by tests
- [x] `docs/phases/step-10.1.md` exists and documents the step

---

## Completion decision

**Phase 10.1 is complete.** The coordinator star-topology contract is explicit, tested, and ready for Phase 10.2 (node timeouts) and subsequent LangGraph orchestration work.

---

## Known limitations

- Coordinator stub endpoint (`POST /workflows/daily-report`) still returns stub acceptance only — it does not invoke specialist agents yet.
- No LangGraph dependency or graph execution is wired in this step.
- Full daily report merge, prioritization, and Django completion remain deferred.
