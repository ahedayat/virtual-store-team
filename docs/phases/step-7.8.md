# Step 7.8 — Persist `sales.*` Actions to Django

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Integrate mapped Sales Agent recommendations with the existing Django internal action workflow via the shared `DjangoClient`, with safe dry-run support for tests and local runs.

---

## Persistence flow

1. `run_sales_analysis()` returns a validated `SalesAnalysisResult`.
2. When `persist_actions=True` on `POST /run`, mapped action bodies are built via `map_sales_analysis_to_actions()`.
3. Each action is submitted with `DjangoClient.create_action()` → `POST /internal/ai/actions/`.
4. When `dry_run=True`, actions are mapped but not POSTed; a warning with code `dry_run` is appended to the result.
5. Tenant/store scope comes from the service JWT on the Django client — not from action payload bodies.

---

## Django integration point

- Client helper: `agents/shared/django_client/client.py` → `create_action()`
- Backend endpoint: `POST /internal/ai/actions/` (Phase 4.3 `ActionService.create_from_agent_payload()`)

---

## Error handling

| Condition | Behavior |
|-----------|----------|
| Invalid recommendation mapping | HTTP 422 with `action_mapping_failed` |
| Django HTTP/client error during persistence | Non-fatal warning `action_persistence_failed` on the result; analysis output still returned |
| Persistence requested without Django client | Warning `action_persistence_skipped` |
| `dry_run=True` | No POST; warning `dry_run` with mapped action count |

This follows the Content Agent pattern of keeping analysis output primary while surfacing persistence failures explicitly in warnings.

---

## Files changed

| File | Change |
|------|--------|
| `agents/sales/action_mapping.py` | `persist_sales_actions()` with `dry_run` support |
| `agents/sales/app/main.py` | `/run` persistence orchestration and warning handling |
| `agents/sales/app/schemas.py` | `persist_actions`, `dry_run`, `service_token` request fields |
| `agents/sales/tests/test_action_mapping.py` | Persistence, dry-run, and `/run` behavior tests |

---

## Test coverage

- Successful action persistence via mocked Django endpoint
- Dry-run maps without POST
- Django failure response surfaced as warning on `/run`
- `/run` dry-run path with `persist_actions=True`

---

## Verification commands

```bash
PYTHONPATH=. python -m unittest agents.sales.tests.test_action_mapping -v
PYTHONPATH=. python -m unittest discover -s agents/sales/tests -p 'test_*.py' -v
```
