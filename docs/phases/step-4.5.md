# Step 4.5 — Unified Dashboard History Feed

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Add a dashboard-facing Django REST API endpoint that returns a unified chronological history feed for the authenticated manager/user by aggregating existing Phase 4 records into a single read-only timeline.

---

## Scope of implementation

- `GET /api/history/` — unified history feed for authenticated dashboard users
- `HistoryFeedService` — tenant/store-scoped read service with normalization, filtering, sorting, and pagination
- Query parameter validation via `HistoryFeedQuerySerializer`
- Focused API tests for auth, scoping, filtering, pagination, PII safety, and read-only behavior
- Cursor scope rule at `.cursor/rules/step-4.5-history-feed.mdc`

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/history_constants.py` | Created — history item type constants and pagination defaults |
| `backend/operations/history_service.py` | Created — `HistoryFeedService` |
| `backend/operations/dashboard_serializers.py` | Created — query parameter serializer |
| `backend/operations/views.py` | Created — `HistoryFeedView` |
| `backend/operations/urls.py` | Created — dashboard history route |
| `backend/config/urls.py` | Updated — include `operations.urls` under `/api/` |
| `backend/operations/tests/test_history_feed_api.py` | Created — Step 4.5 API tests |
| `.cursor/rules/step-4.5-history-feed.mdc` | Already present — Step 4.5 scope rule |
| `docs/phases/step-4.5.md` | Created — this document |

---

## Endpoint implemented

### `GET /api/history/`

Returns a paginated, reverse-chronological feed of normalized history items.

**Example response (200 OK):**

```json
{
  "count": 42,
  "next": "http://localhost/api/history/?limit=20&offset=20",
  "previous": null,
  "results": [
    {
      "id": "action_event:550e8400-e29b-41d4-a716-446655440000",
      "type": "action_event",
      "title": "Action approved",
      "summary": "Manager approved a restock recommendation.",
      "timestamp": "2026-06-26T10:30:00Z",
      "status": "approved",
      "source": "manager",
      "agent_name": "sales-agent",
      "report_run_id": "report-run-uuid",
      "daily_report_id": null,
      "action_id": "action-uuid",
      "metadata": {
        "event_type": "approved",
        "action_type": "sales.restock",
        "priority": 1,
        "previous_status": "pending_approval"
      }
    }
  ]
}
```

---

## Authentication requirements

- Requires session-based dashboard authentication via `SessionAuthentication`.
- Unauthenticated requests return **401 Unauthorized**.
- Service JWT (`Authorization: Bearer <service_jwt>`) is **not** accepted — AI services cannot use this endpoint.
- Tenant is resolved from `request.user.tenant`.
- Store scoping uses `request.user.store` when set; tenant-wide managers (`store=None`) see all stores within their tenant.

---

## Source models included in the feed

| Model | History item type(s) | Notes |
|-------|---------------------|-------|
| `ReportRun` | `report_run_queued`, `report_run_running`, `report_run_completed`, `report_run_failed` | One item per report run based on current status |
| `DailyReport` | `daily_report_created` | Safe section counts in metadata; full `content` not exposed |
| `AgentOutput` | `agent_output_created` | `output_type` only; raw `output.payload` not exposed |
| `Action` | `action_created` | Title/description only; raw `payload` not exposed |
| `ActionEvent` | `action_event` | Audit transitions (created, approved, rejected, queued) |

---

## Unified feed item schema

Each result item includes:

| Field | Description |
|-------|-------------|
| `id` | Stable prefixed ID, e.g. `action_event:{uuid}` |
| `type` | Explicit history item type (see below) |
| `title` | Short human-readable title |
| `summary` | Concise description; no raw payloads |
| `timestamp` | ISO 8601 UTC timestamp |
| `status` | Domain status when applicable |
| `source` | `manager`, `agent`, `system`, or `coordinator-agent` |
| `agent_name` | Agent attribution when available |
| `report_run_id` | Linked report run UUID when available |
| `daily_report_id` | Linked daily report UUID when available |
| `action_id` | Linked action UUID when available |
| `metadata` | Safe structured metadata only |

---

## Feed item types

| Type | Source |
|------|--------|
| `report_run_queued` | `ReportRun` with status `queued` |
| `report_run_running` | `ReportRun` with status `running` |
| `report_run_completed` | `ReportRun` with status `completed` |
| `report_run_failed` | `ReportRun` with status `failed` |
| `daily_report_created` | `DailyReport` |
| `agent_output_created` | `AgentOutput` |
| `action_created` | `Action` |
| `action_event` | `ActionEvent` |

---

## Sorting behavior

Default sort: **newest first** (reverse chronological by `timestamp`).

Timestamp priority per source:

| Source | Timestamp field |
|--------|-----------------|
| `ReportRun` (queued) | `created_at` |
| `ReportRun` (running/completed/failed) | `updated_at` |
| `DailyReport` | `generated_at` (fallback: `created_at`) |
| `AgentOutput` | `created_at` |
| `Action` | `created_at` |
| `ActionEvent` | `created_at` |

---

## Filtering behavior

Supported query parameters:

| Parameter | Behavior |
|-----------|----------|
| `type` | Exact match on history item type |
| `status` | Exact match on item `status` field |
| `agent_name` | Exact match on `agent_name` |
| `report_run_id` | UUID; items linked to that report run |
| `action_id` | UUID; items linked to that action |
| `from` | ISO 8601 datetime; items with `timestamp >= from` |
| `to` | ISO 8601 datetime; items with `timestamp <= to` |

Validation:

- Invalid UUID values return **400 Bad Request**.
- Invalid datetime values return **400 Bad Request**.
- `from` after `to` returns **400 Bad Request**.
- Unknown query parameters are ignored (DRF serializer default).

All filters preserve tenant/store scoping applied before filtering.

---

## Pagination behavior

MVP limit/offset pagination (no global DRF pagination class exists yet):

| Parameter | Default | Max |
|-----------|---------|-----|
| `limit` | 20 | 100 |
| `offset` | 0 | — |

Response includes `count`, `next`, `previous`, and `results`. Pagination links preserve active filters.

Implementation merges scoped records in memory, sorts, filters, then paginates — acceptable for MVP scale.

---

## Tenant/store scoping behavior

- Tenant is always taken from the authenticated user's `tenant`.
- When `user.store` is set, all queries filter to that store.
- When `user.store` is `None`, the user sees all records for their tenant across stores.
- Cross-tenant records are never returned.
- Cross-store records are excluded for store-scoped users.

---

## PII-safe response rules

The endpoint does **not** expose:

- Raw `Action.payload`
- Raw `AgentOutput.output.payload`
- Raw `DailyReport.content` body
- Customer names, emails, phones, or message bodies

Safe metadata examples:

- `action_type`, `priority`, `requires_approval`, `event_type`
- `output_type`, `report_run_status`, `has_error`
- Section counts from daily reports (`operational_insight_count`, `prioritized_action_count`)

Summaries use action title/description and event reasons only.

---

## Tests added

`backend/operations/tests/test_history_feed_api.py` covers:

1. Authenticated manager can access `GET /api/history/`
2. Unauthenticated request is rejected
3. Service JWT cannot access the dashboard history endpoint
4. Feed includes `ReportRun` items
5. Feed includes `DailyReport` items
6. Feed includes `AgentOutput` items
7. Feed includes `Action` items
8. Feed includes `ActionEvent` items
9. Feed is sorted reverse chronologically
10. Feed is tenant-scoped
11. Cross-tenant records are excluded
12. Store scoping enforced for store-scoped users
13. Tenant-wide manager sees all tenant stores
14. `type` filter works
15. `status` filter works
16. `agent_name` filter works
17. `report_run_id` filter works
18. `action_id` filter works
19. Date range filters work
20. Invalid UUID/date filters return validation errors
21. Pagination works
22. Raw `Action.payload` is not exposed
23. Raw `AgentOutput.payload` is not exposed
24. Endpoint does not mutate records
25. View delegates to `HistoryFeedService`

---

## Validation commands

```bash
cd backend

# Run Step 4.5 tests
python manage.py test operations.tests.test_history_feed_api -v 2

# Run all operations tests
python manage.py test operations -v 2

# Full backend suite
python manage.py test -v 1

# Migration check (no new migrations in this step)
python manage.py makemigrations operations --check
```

---

## Intentionally not implemented

- Celery `reports.generate_daily`
- Celery `actions.execute`
- Coordinator or agent service implementation
- Frontend dashboard UI
- Real Instagram send/publish integration
- External API writes
- Manager approve/reject dashboard endpoints
- Dashboard report/action list/detail CRUD APIs
- New action lifecycle transitions
- New report completion behavior
- New internal AI endpoints
- Billing, onboarding, or SaaS subscription logic

---

## Phase 4 completion notes

Phase 4 is now complete with all five subtasks implemented:

| Step | Deliverable |
|------|-------------|
| 4.1 | `ActionService.create_from_agent_payload()` |
| 4.2 | Approve/reject/queue transitions |
| 4.3 | Internal AI write APIs for actions and agent outputs |
| 4.4 | Internal report run completion API |
| 4.5 | Unified dashboard history feed |

The history feed reads persisted records from Steps 4.1–4.4 as the source of truth. It does not duplicate lifecycle or completion logic.

---

## Notes for Phase 5

- When Celery `reports.generate_daily` creates and updates `ReportRun` records asynchronously, they will appear automatically in the history feed via existing normalization rules.
- Consider database-level union queries or materialized timeline tables if feed volume grows beyond MVP in-memory merge.
- Frontend Phase 11 can consume `GET /api/history/` with filters and pagination metadata as-is.
- Optional future enhancement: deduplicate overlapping report-run and daily-report completion items in the UI layer.

---

## Assumptions

- One history item per `ReportRun` reflects its current status (no separate status-change audit table for report runs).
- `DailyReport.content` is summarized by section counts only, not rendered for the timeline.
- Service JWT on dashboard routes is rejected because only `SessionAuthentication` is configured on the view.
- Unknown query parameters are silently ignored per DRF serializer conventions.
