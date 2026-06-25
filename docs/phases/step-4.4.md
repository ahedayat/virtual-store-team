# Step 4.4 — Internal Report Run Completion API

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Add an internal Django REST API endpoint that allows the authenticated coordinator service to complete a report run and persist the final daily report payload after agent outputs and actions have been collected.

---

## Scope of implementation

- `POST /internal/ai/report-runs/{id}/complete/` — complete a running report run and persist `DailyReport`
- `ReportRunService.complete_from_ai_payload()` — transactional completion business logic
- Request/response serializers with validation and tenant-scoped reference checks
- Service JWT authentication using existing `InternalAIAuthentication`
- Coordinator-only authorization (`coordinator-agent`)
- Focused API tests for auth, scoping, validation, lifecycle, and non-mutation guarantees

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/exceptions.py` | Updated — added report run service exceptions |
| `backend/operations/services.py` | Updated — added `ReportRunService.complete_from_ai_payload()` |
| `backend/operations/internal_utils.py` | Updated — added `get_scoped_report_run()` |
| `backend/operations/internal_serializers.py` | Updated — completion request/response serializers |
| `backend/operations/internal_views.py` | Updated — added `InternalReportRunCompleteView` |
| `backend/accounts/internal_urls.py` | Updated — registered completion route |
| `backend/operations/tests/test_internal_report_run_complete_api.py` | Created — Step 4.4 API tests |
| `.cursor/rules/step-4.4-report-run-completion.mdc` | Already present — Step 4.4 scope rule |
| `docs/phases/step-4.4.md` | Created — this document |

---

## Endpoint implemented

### `POST /internal/ai/report-runs/{id}/complete/`

Completes a running report run and persists the final daily report document.

**Request example:**

```json
{
  "report": {
    "generated_at": "2026-06-26T10:30:00Z",
    "period": {
      "from": "2026-06-25T00:00:00Z",
      "to": "2026-06-26T00:00:00Z"
    },
    "sales_summary": {
      "total_revenue": 12500000,
      "order_count": 18,
      "top_products": [],
      "low_performers": []
    },
    "operational_insights": [
      "Inventory is low for two fast-moving products."
    ],
    "prioritized_actions": [
      {
        "action_id": "action-uuid",
        "priority": 1,
        "summary": "Restock the best-selling leather tote."
      }
    ],
    "content_suggestions": [
      {
        "type": "instagram_caption",
        "draft_preview": "..."
      }
    ],
    "support_insights": [
      {
        "theme": "shipping questions",
        "message_count": 4,
        "summary": "Customers asked about delivery timing."
      }
    ],
    "next_steps": [
      "Review pending approval actions."
    ],
    "warnings": []
  },
  "agent_output_ids": [
    "agent-output-uuid"
  ],
  "action_ids": [
    "action-uuid"
  ],
  "metadata": {
    "coordinator_version": "mock",
    "duration_ms": 3500
  }
}
```

**Response example (200 OK):**

```json
{
  "report_run_id": "report-run-uuid",
  "daily_report_id": "daily-report-uuid",
  "status": "completed",
  "completed_at": "2026-06-26T10:30:05Z"
}
```

---

## Authentication requirements

- Requires `Authorization: Bearer <service_jwt>` via `InternalAIAuthentication`.
- Missing, expired, malformed, wrong-audience, or unknown-service tokens return **401 Unauthorized**.
- Human session authentication is **not** accepted on `/internal/ai/*`.
- `tenant_id`, `store_id`, and `service_name` are resolved from JWT claims — never from the request body.

---

## Coordinator-only behavior

Only `coordinator-agent` may complete report runs. Other allowed AI services (`sales-agent`, `content-agent`, `support-agent`) receive **403 Forbidden**.

This is enforced in `ReportRunService.complete_from_ai_payload()` and surfaced by the view as a permission error.

---

## Tenant/store scoping behavior

- The report run is resolved by path `id` filtered by authenticated `tenant` and `store`.
- Cross-tenant or cross-store report runs return **404 Not Found** (no information leakage).
- Body fields `tenant_id` and `store_id` are ignored.
- Optional `agent_output_ids` and `action_ids` must belong to the same tenant/store.
- When `AgentOutput.report_run` or `Action.report_run` is set, it must match the report run being completed.

---

## ReportRun lifecycle behavior

| Transition | Allowed |
|------------|---------|
| `running` → `completed` | Yes |

| Transition | Result |
|------------|--------|
| `failed` → `completed` | **400 Bad Request** |
| `completed` → `completed` | **400 Bad Request** (not idempotent) |
| `queued` → `completed` | **400 Bad Request** |

On successful completion:

- `ReportRun.status` is set to `completed`
- `ReportRun.error_message` is cleared
- `ReportRun.updated_at` reflects completion time (used as `completed_at` in the API response)

The `running` state is available in the current model constants and is enforced strictly.

---

## DailyReport persistence behavior

- One `DailyReport` per `ReportRun` (OneToOne enforced by model).
- Created inside the same database transaction as the report run status update.
- `DailyReport.content` stores the original report JSON payload (string datetimes preserved) plus optional top-level `metadata` from the request.
- `DailyReport.generated_at` is parsed from `report.generated_at`.
- `tenant`, `store`, and `report_run` are set from trusted service context.

---

## Validation behavior

| Field | Rule |
|-------|------|
| `report` | Required JSON object with required `generated_at` (ISO 8601) |
| `report.period` | Optional; must be a JSON object when provided |
| `metadata` | Optional JSON object |
| `agent_output_ids` | Optional list of UUIDs; all must exist in tenant/store |
| `action_ids` | Optional list of UUIDs; all must exist in tenant/store |

Reference validation failures return **400 Bad Request**. Invalid lifecycle state returns **400 Bad Request**.

The endpoint does **not** create, approve, reject, queue, or execute actions.

---

## Service layer

```python
ReportRunService.complete_from_ai_payload(
    *,
    report_run,
    tenant,
    store,
    service_name: str,
    report_payload: dict,
    agent_output_ids: list | None = None,
    action_ids: list | None = None,
    metadata: dict | None = None,
) -> DailyReport
```

- Uses `select_for_update()` on the report run row.
- Validates coordinator service, scope, lifecycle, payload, and references.
- Creates `DailyReport` and updates `ReportRun` in one `transaction.atomic()` block.

---

## Tests added

`backend/operations/tests/test_internal_report_run_complete_api.py` covers:

1. Valid coordinator service JWT can complete a running report run
2. Missing token is rejected
3. Invalid token is rejected
4. Human-authenticated user cannot call the endpoint
5. Non-coordinator service cannot complete report runs
6. Cross-tenant report run is rejected
7. Cross-store report run is rejected
8. Valid completion creates a `DailyReport`
9. Valid completion changes `ReportRun.status` to `completed`
10. Completion stores the final structured report payload
11. Completion validates `agent_output_ids`
12. Cross-tenant `agent_output_ids` are rejected
13. Completion validates `action_ids`
14. Cross-tenant `action_ids` are rejected
15. A failed report run cannot be completed
16. A completed report run cannot be completed again
17. Invalid report payload is rejected
18. The endpoint does not create actions
19. The endpoint does not approve, reject, queue, or mutate actions
20. The endpoint delegates to `ReportRunService`
21. Expired service JWT is rejected

---

## Validation commands

```bash
cd backend

# Run Step 4.4 tests
python manage.py test operations.tests.test_internal_report_run_complete_api -v 2

# Run all operations tests
python manage.py test operations -v 2

# Full backend suite
python manage.py test -v 1

# Migration check (no new migrations in this step)
python manage.py makemigrations operations --check
```

---

## Intentionally not implemented

- `GET /api/history/`
- Dashboard report list/detail APIs
- `POST /api/actions/{id}/approve/`
- `POST /api/actions/{id}/reject/`
- Celery `reports.generate_daily`
- Celery `actions.execute`
- Coordinator service implementation
- Agent service implementation
- Real Instagram send/publish integration
- Any external API write
- Frontend UI

---

## Assumptions

- Only `coordinator-agent` may complete report runs (enforced in service layer).
- Report completion is not idempotent; a second completion attempt on an already `completed` run returns **400**.
- `DailyReport.content` stores the request `report` object as JSON-safe strings (no parsed datetime objects in JSON).
- Optional completion `metadata` is stored under `content.metadata`.
- `completed_at` in the API response is `ReportRun.updated_at` after completion (no separate `completed_at` column on `ReportRun` yet).

---

## Notes for Step 4.5

- The unified history endpoint can read from `ReportRun`, `DailyReport`, `AgentOutput`, `Action`, and `ActionEvent` records created in Steps 4.1–4.4.
- `DailyReport.content` contains the merged final report sections for dashboard display.
- History should include report completion events keyed by `report_run_id` and `daily_report_id`.
- Continue tenant-scoped reads from authenticated manager context (not service JWT).
- Do not re-implement report completion logic in the history feed; treat persisted records as source of truth.
