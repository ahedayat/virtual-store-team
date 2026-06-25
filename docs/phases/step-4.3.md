# Step 4.3 — Internal AI Write APIs

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Add internal Django REST API endpoints that allow authenticated AI services to persist suggested actions and structured agent outputs. These endpoints will later be used by coordinator and specialist agents.

---

## Scope of implementation

- `POST /internal/ai/actions/` — create suggested actions via `ActionService.create_from_agent_payload()`
- `POST /internal/ai/agent-outputs/` — persist structured agent outputs via `AgentOutputService.create_from_agent_payload()`
- Request/response serializers with shape validation and tenant-scoped reference resolution
- Service JWT authentication using existing `InternalAIAuthentication`
- Focused API tests for auth, scoping, validation, and service delegation

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/internal_utils.py` | Created — tenant/store/report_run/agent_output resolution helpers |
| `backend/operations/internal_serializers.py` | Created — request/response serializers for both endpoints |
| `backend/operations/internal_views.py` | Created — thin API views for action and agent output creation |
| `backend/operations/services.py` | Updated — added `AgentOutputService.create_from_agent_payload()` |
| `backend/operations/exceptions.py` | Updated — added agent output service exceptions |
| `backend/accounts/internal_urls.py` | Updated — registered new internal AI write routes |
| `backend/operations/tests/test_internal_ai_write_api.py` | Created — Step 4.3 API tests |
| `.cursor/rules/step-4.3-internal-ai-write-apis.mdc` | Already present — Step 4.3 scope rule |
| `docs/phases/step-4.3.md` | Created — this document |

---

## Endpoints implemented

### `POST /internal/ai/actions/`

Creates a suggested action from an AI service payload.

**Request example:**

```json
{
  "action_type": "sales.restock",
  "title": "Restock: Leather Tote Model A",
  "description": "Only 2 units left; sold 14 in the last 7 days.",
  "priority": 1,
  "requires_approval": true,
  "payload": {
    "product_id": "uuid",
    "sku": "BAG-001",
    "current_stock": 2,
    "suggested_order_qty": 20,
    "rationale": "High velocity relative to stock"
  },
  "report_run_id": "optional-uuid",
  "agent_output_id": "optional-uuid"
}
```

**Response example (201 Created):**

```json
{
  "id": "action-uuid",
  "action_type": "sales.restock",
  "title": "Restock: Leather Tote Model A",
  "priority": 1,
  "requires_approval": true,
  "status": "pending_approval",
  "agent_name": "sales-agent",
  "report_run_id": "optional-uuid",
  "created_at": "2026-06-26T12:00:00Z"
}
```

### `POST /internal/ai/agent-outputs/`

Persists raw structured output from an AI service.

**Request example:**

```json
{
  "output_type": "sales_analysis",
  "payload": {
    "summary": "Sales increased for top products.",
    "recommendations": []
  },
  "metadata": {
    "model": "mock",
    "duration_ms": 1200
  },
  "report_run_id": "optional-uuid"
}
```

**Response example (201 Created):**

```json
{
  "id": "agent-output-uuid",
  "agent_name": "sales-agent",
  "output_type": "sales_analysis",
  "report_run_id": "optional-uuid",
  "created_at": "2026-06-26T12:00:00Z"
}
```

---

## Authentication requirements

- Both endpoints require `Authorization: Bearer <service_jwt>`.
- Uses existing `InternalAIAuthentication` (same as Phase 2/3 internal routes).
- Missing, expired, malformed, wrong-audience, or unknown-service tokens return **401 Unauthorized**.
- Human session authentication is **not** accepted on `/internal/ai/*`.
- `tenant_id`, `store_id`, and `service_name` (`sub` claim) are resolved from the JWT — never from the request body.

---

## Tenant/store scoping behavior

- Created records always use `tenant` and `store` from the authenticated service context.
- Body fields `tenant_id` and `store_id` are ignored and do not override JWT context.
- Optional `report_run_id` and `agent_output_id` are resolved with `(tenant, store)` filters.
- Cross-tenant or cross-store references return **404 Not Found** (no information leakage).
- `agent_name` is always set from the authenticated service name (`request.service_name`).

---

## Serializer validation behavior

Serializers validate request shape only; lifecycle policy stays in the service layer.

| Endpoint | Validated fields |
|----------|------------------|
| Actions | `action_type` (supported types), `title`, `description`, `priority` (1–5), optional `requires_approval`, optional `low_risk`, JSON `payload`, optional UUID refs |
| Agent outputs | non-empty `output_type`, JSON object `payload`, optional JSON object `metadata`, optional `report_run_id` |

Validation failures return **400 Bad Request**. Unsupported action types are rejected at the serializer layer; deeper payload rules (e.g. empty title) are enforced by `ActionService`.

---

## Service-layer delegation behavior

### Actions

- View resolves tenant/store and optional FK references, then calls `ActionService.create_from_agent_payload()`.
- Initial status (`pending_approval` or `queued`) is determined solely by Step 4.1 policy logic.
- View does **not** call `approve()`, `reject()`, or `queue_execution()`.

### Agent outputs

- View calls `AgentOutputService.create_from_agent_payload()`.
- Structured data is stored in `AgentOutput.output` as:

```json
{
  "output_type": "...",
  "payload": { },
  "metadata": { }
}
```

- No report completion or action lifecycle side effects.

---

## Tests added

`backend/operations/tests/test_internal_ai_write_api.py` covers:

1. Valid service JWT can create an action
2. Missing token is rejected
3. Invalid token is rejected
4. Human-authenticated user cannot call internal AI action endpoint
5. Action endpoint uses tenant/store from service JWT, not request body
6. Cross-tenant `report_run_id` is rejected (404)
7. Cross-store `report_run_id` is rejected (404)
8. Invalid action payload is rejected (400)
9. Action endpoint delegates to `ActionService.create_from_agent_payload()`
10. Created action receives correct initial status from the service
11. Valid service JWT can create an `AgentOutput`
12. Invalid agent output payload is rejected (400)
13. Agent output uses authenticated service name as `agent_name`
14. Cross-tenant `report_run_id` is rejected for agent output (404)
15. Endpoints do not approve, reject, execute, or complete reports

---

## Validation commands

```bash
cd backend

# Run Step 4.3 tests
python manage.py test operations.tests.test_internal_ai_write_api -v 2

# Run all operations tests
python manage.py test operations -v 2

# Full backend suite
python manage.py test -v 1

# Migration check (no new migrations in this step)
python manage.py makemigrations --check
```

---

## Intentionally not implemented

- `POST /internal/ai/report-runs/{id}/complete/`
- `GET /api/history/`
- `POST /api/actions/{id}/approve/`
- `POST /api/actions/{id}/reject/`
- Dashboard-facing action read APIs
- Celery `actions.execute`
- Real Instagram send/publish integration
- Any external API write
- Frontend UI

---

## Notes for Step 4.4

- Report completion endpoint should accept final report payloads and mark `ReportRun` as `completed`.
- Step 4.4 may create or update `DailyReport` content and link existing `AgentOutput` / `Action` records from the same report run.
- Reuse the same internal auth pattern and `resolve_tenant_and_store()` helpers.
- Continue returning **404** for cross-tenant report run access.
- Do not auto-approve actions during report completion.
