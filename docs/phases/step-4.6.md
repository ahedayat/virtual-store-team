# Step 4.6 — Dashboard Reports Read APIs

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Expose dashboard-facing read-only APIs so managers can list and inspect report runs (and linked daily report summaries) with tenant/store isolation.

---

## Scope of implementation

- `GET /api/reports/` — paginated report run list, newest first
- `GET /api/reports/{id}/` — report run detail with daily report section summaries
- `DashboardReportService` and `DashboardScopeService` for scoping and serialization
- `DashboardPaginationQuerySerializer` for `limit`/`offset`
- Focused API tests in `operations.tests.test_dashboard_reports_api`

---

## Files changed

| Path | Action |
|------|--------|
| `backend/operations/dashboard_service.py` | Created — scoping, report list/detail serialization, pagination |
| `backend/operations/dashboard_serializers.py` | Updated — pagination query serializer |
| `backend/operations/views.py` | Updated — `ReportListView`, `ReportDetailView` |
| `backend/operations/urls.py` | Updated — report list/detail routes |
| `backend/operations/tests/test_dashboard_reports_api.py` | Created — Step 4.6 API tests |
| `docs/phases/step-4.6.md` | Created — this document |

---

## Endpoints

### `GET /api/reports/`

Returns paginated report runs visible to the authenticated user.

**Query parameters:** `limit` (default 20, max 100), `offset` (default 0)

**Response fields per item:** `id`, `status`, `store_id`, `created_at`, `updated_at`, `generated_at`, `summary`, `error_message` (when failed), `coordinator`

### `GET /api/reports/{id}/`

Returns a single report run with `daily_report` section summaries and related `counts`.

---

## Authentication and scoping

- Session authentication (`SessionAuthentication`) — same as `GET /api/history/`
- Store-scoped users see only their store; tenant managers (`store=None`) see all stores in the tenant
- Cross-tenant or cross-store access returns `404`
- Service JWT is rejected (`401`)

---

## Validation commands

```bash
cd backend
python manage.py test operations.tests.test_dashboard_reports_api -v 2
```

---

## Acceptance criteria

- [x] Authenticated list and detail access
- [x] Tenant/store isolation
- [x] Unauthenticated and service JWT rejected
- [x] Newest-first ordering
- [x] Pagination with `limit`/`offset`
- [x] Safe summaries (no raw daily report payload dump on list)

---

## Next step

Step 4.7 — Dashboard Actions Read APIs
