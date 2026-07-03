# Coordinator Agent and Dashboard APIs

APIs needed by the **Coordinator Agent** and **admin dashboard** for daily reports, orchestration, and manager workflows.

## Architecture note

The Coordinator and dashboard **do not call Prestia directly** in the current codebase. They consume **Botkonak Django data** (populated from Prestia via a future connector). This document maps:

1. What Prestia must expose so Botkonak can build the **context bundle equivalent**
2. What the dashboard needs indirectly through synced data

---

## Coordinator Agent: context bundle equivalent

The coordinator's `fetch_context` node calls Django:

`GET /internal/ai/context/{report_run_id}/` (`agents/coordinator/nodes.py`)

This bundles all Prestia read APIs required for one daily report:

| Context bundle section | Prestia API source | Doc |
|------------------------|-------------------|-----|
| `tenant`, `store` | `GET /v1/store` | [02-store-profile-apis.md](./02-store-profile-apis.md) |
| `products` | `GET /v1/products` | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| `sales_summary` | `GET /v1/sales/summary` | [04-order-and-sales-apis.md](./04-order-and-sales-apis.md) |
| `inventory` | `GET /v1/inventory/low-stock` | [03-product-and-inventory-apis.md](./03-product-and-inventory-apis.md) |
| `messages` | `GET /v1/messages/recent` | [08-support-agent-apis.md](./08-support-agent-apis.md) |
| `warnings` | Partial failures during aggregation | Built by Botkonak connector |

### API: Aggregated Store Context (optional Prestia shortcut)

| Property | Value |
|----------|-------|
| **API name** | Get Aggregated Store Context |
| **HTTP method** | `GET` |
| **Suggested endpoint path** | `/v1/context` |
| **Botkonak consumer** | Background sync, Coordinator (via connector) |
| **Why Botkonak needs this** | Single round-trip alternative to five endpoints before daily report. **Not required** if Botkonak composes locally. |
| **Requirement type** | Inferred |
| **Priority** | P1 |

#### Query parameters

| Parameter | Description |
|-----------|-------------|
| `include` | Comma-separated: `products,sales,inventory,messages` |
| `reference_at` | For sales period computation |

#### Successful response shape

Same top-level keys as Botkonak context bundle (`docs/phases/step-3.5.md` example), minus `report_run_id` (Botkonak adds that).

#### Related files

- `backend/catalog/context.py` — `build_context_bundle`
- `docs/phases/step-3.5.md`

---

## Coordinator workflow (Botkonak-internal, not Prestia)

For completeness — these are **not** Prestia APIs:

| Method | Botkonak internal path | Purpose |
|--------|------------------------|---------|
| `GET` | `/internal/ai/context/{report_run_id}/` | Fetch context (data from Prestia via sync) |
| `POST` | `/internal/ai/agent-outputs/` | Persist specialist outputs |
| `POST` | `/internal/ai/report-runs/{id}/complete/` | Submit merged daily report |

Coordinator triggers specialist agents with context derived from Prestia-sourced data (`agents/coordinator/graph.py`).

### Merged daily report fields (from Prestia-sourced data)

`build_merged_daily_report` (`agents/coordinator/merge.py`) includes:

| Field | Prestia data dependency |
|-------|-------------------------|
| `sales_summary` | Sales summary API |
| `prioritized_actions` | From sales agent (sales + inventory) |
| `content_suggestions` | From content agent (products + store settings) |
| `support_insights` | From support agent (messages) |
| `warnings`, `partial`, `missing_sections` | Pipeline metadata |

---

## Dashboard APIs (Botkonak — data originally from Prestia)

The Next.js dashboard reads **Botkonak REST APIs**, not Prestia. Prestia must supply underlying data through sync.

| Dashboard feature | Botkonak API | Prestia data needed |
|-------------------|--------------|---------------------|
| Trigger daily report | `POST /api/reports/generate/` | Fresh catalog/orders/messages |
| Report list/detail | `GET /api/reports/`, `GET /api/reports/{id}/` | Merged report from agent run |
| Actions list/approve | `GET /api/actions/`, `POST .../approve/` | Agent recommendations (not Prestia writes) |
| History feed | `GET /api/history/` | Actions, reports, events |
| Store profile | `GET /api/stores/{store_id}/` | Store profile API |

### Store detail for dashboard

| Property | Value |
|----------|-------|
| **Prestia API** | `GET /v1/store` |
| **Botkonak consumer** | Admin Dashboard |
| **Requirement type** | Direct (indirect via sync) |
| **Priority** | P0 |

Frontend hooks (`use-products`, `use-customers`, `use-recommendations`, `use-content-items`) still use **mock data** — not wired to Django APIs. Prestia integration for dashboard product/customer lists is Future when hooks are implemented.

---

## Agent activity and task status

| Need | Source in Botkonak | Prestia API? |
|------|-------------------|--------------|
| Report run status | `ReportRun` model, Celery task | No |
| Agent outputs | `AgentOutput` model | No |
| Task progress | Coordinator HTTP response | No |
| Specialist timeouts | Coordinator warnings | No |

**No Prestia API required** for orchestration metadata.

---

## Recommendations on dashboard

Actions/recommendations are **created by agents inside Botkonak** (`operations.models.Action`), not fetched from Prestia. Prestia supplies **inputs** (sales, inventory, products, messages) only.

---

## Evidence from codebase

| File | Relevance |
|------|-----------|
| `agents/coordinator/nodes.py` | Workflow nodes, specialist payloads |
| `agents/coordinator/merge.py` | Merged report shape |
| `backend/operations/tasks.py` | `generate_daily` Celery task |
| `backend/operations/views.py` | Dashboard report/action APIs |
| `backend/operations/urls.py` | Dashboard routes |
| `frontend/app/dashboard/page.tsx` | Dashboard UI |
| `docs/agents/coordinator.md` | Coordinator documentation |

## Open questions

1. Dashboard live wiring to Django vs mock data timeline.
2. Whether managers trigger Prestia re-sync manually from dashboard before report generation.
