# Step 0.0 — MVP Phase Planning Document

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Document version:** 0.0  
**Status:** Planning only — no implementation in this step  
**First tenant (demo):** Prestia (online bag store)  
**Target:** Small, modular, end-to-end MVP with clean service boundaries

---

## 1. Product Summary

We are building a **multi-tenant SaaS platform** that acts as a virtual AI operations team for small online stores. A store manager uses a web dashboard to:

- Trigger a **manual daily briefing** on demand
- Review outputs from specialized AI agents
- See **prioritized action recommendations**
- **Approve or reject** actions that require human oversight
- Browse **history** of reports, agent outputs, and action outcomes

The system is **not tied to Prestia**. Prestia is the first real tenant and demo customer, but all domain models, APIs, and agent logic must be **generic and tenant-scoped**. Future stores onboard as new tenants without code changes to core platform logic.

**MVP success:** A manager opens the dashboard, clicks “Generate daily report,” Django prepares tenant store data, the coordinator agent orchestrates sales/content/support agents via LangGraph, agents return structured outputs through Django APIs only, the coordinator produces a readable daily report, and the dashboard shows the report plus actionable items with correct approval states.

---

## 2. Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Store Manager (Browser)                          │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTPS
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  nginx  →  Next.js Frontend  →  Django REST API  (source of truth)    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
    ┌──────────┐            ┌──────────┐            ┌──────────────┐
    │ Postgres │            │  Redis   │            │ Celery worker│
    │          │            │          │            │ + Celery beat│
    └──────────┘            └──────────┘            └──────────────┘
                                  │
                                  │ async jobs (report runs, integrations)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              FastAPI AI Microservices (JWT → Django APIs only)           │
│  ┌─────────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ coordinator     │  │ sales-agent │  │content-agent│  │support-agent│ │
│  │ (LangGraph)     │  │             │  │             │  │             │ │
│  └────────┬────────┘  └──────┬──────┘  └──────┬──────┘  └──────┬─────┘ │
│           └──────────────────┴────────────────┴────────────────┘       │
│                    HTTP between agents (orchestrated by coordinator)      │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         External LLM provider(s)
                         (abstracted — not hardcoded)
```

**Principles:**

| Principle | Rule |
|-----------|------|
| Source of truth | Django + Postgres only |
| AI data access | Django internal APIs with JWT service auth — **no direct DB from agents** |
| Service boundaries | One FastAPI container per agent; coordinator is its own service |
| Orchestration | LangGraph inside coordinator-agent |
| Human in the loop | Manager above agents; approval workflow enforced in Django |
| Multi-tenancy | Every request and record is tenant-scoped from day one |
| PII | Masked/filtered before any LLM call |

---

## 3. Main Services and Responsibilities

### 3.1 Django Backend (`backend`)

| Area | Responsibility |
|------|----------------|
| SaaS core | Tenants, stores, users, teams, roles, permissions |
| Business logic | Action lifecycle, approvals, audit/history |
| Data | Sales, orders, inventory, products, categories, messages (tenant data) |
| Integrations | Instagram DM ingestion (MVP: webhook/polling stub or minimal real hook) |
| Internal APIs | Read-only and write endpoints for AI services (scoped by tenant + service identity) |
| Public APIs | Dashboard-facing REST/JSON for Next.js (session or token auth) |
| Async dispatch | Enqueue Celery tasks for long-running workflows |
| PII gateway | Central place to sanitize payloads before they leave for AI services |

### 3.2 Next.js Frontend (`frontend`)

| Area | Responsibility |
|------|----------------|
| Dashboard | Reports, agent outputs, actions, history |
| Actions UI | Approve/reject, view status and agent attribution |
| Triggers | Manual “Generate daily report” button |
| Auth UX | Login, tenant context (implicit via user) |
| i18n display | Show Persian content by default; UI chrome can follow `AI_OUTPUT_LANGUAGE` or separate UI locale later |

### 3.3 FastAPI AI Microservices

Each service: health check, LangGraph (where applicable), LLM calls via shared abstraction library, HTTP client to Django internal APIs.

| Service | Role |
|---------|------|
| `coordinator-agent` | LangGraph workflow; delegates to other agents; merges outputs; writes final report payload back via Django |
| `sales-agent` | Sales/inventory analysis; structured action recommendations |
| `content-agent` | Instagram captions, product copy, campaign text |
| `support-agent` | Instagram DM analysis and safe reply drafts; scoped support actions |

### 3.4 Infrastructure Services

| Service | Role |
|---------|------|
| `postgres` | Primary persistence |
| `redis` | Celery broker + optional short-lived workflow state cache |
| `celery-worker` | Async task execution |
| `celery-beat` | Scheduler placeholder (minimal jobs in MVP; room for future scheduled reports) |
| `nginx` | Reverse proxy, TLS termination (dev: single entrypoint) |

---

## 4. Multi-Tenant SaaS Boundaries

### 4.1 Core Entities (conceptual)

```
Tenant
  └── Store(s)          # MVP: one store per tenant is enough
        └── Users (manager, staff)
        └── Products, Orders, Inventory, Messages, ...
        └── DailyReports, AgentRuns, Actions
```

### 4.2 Isolation Rules

1. **Every table** that holds business data includes `tenant_id` (and usually `store_id`).
2. **Django middleware / queryset managers** enforce tenant filtering on all ORM access.
3. **JWT for AI services** embeds `tenant_id`, `store_id`, and `service_name` (e.g. `sales-agent`). Django rejects cross-tenant IDs in URLs or body.
4. **No Prestia-specific tables or branches.** Prestia is seeded as `Tenant(slug='prestia')` with demo data.
5. **Per-tenant configuration** (output language, integration credentials, approval policies) lives in Django models or encrypted settings — not in agent code.

### 4.3 What “generic” means for Prestia

- Product categories, Instagram handle, and bag-specific copy are **tenant data**, not hardcoded constants in agents.
- Agents receive **structured context** from Django APIs (product list, sales aggregates) without knowing the tenant brand name unless provided as data field `store_display_name`.

---

## 5. Agent Responsibilities and Boundaries

### 5.1 Coordinator Agent

**May:**

- Start daily report workflow
- Call sales, content, support agents (HTTP)
- Aggregate and normalize agent JSON outputs
- Produce final daily report document (sections, priorities, next steps)
- Request Django to persist report and proposed actions

**May not:**

- Bypass approval rules (e.g. auto-execute approval-required actions)
- Query database directly
- Perform sales analysis, content writing, or customer replies itself (delegates only)
- Access PII beyond what Django APIs already sanitized

### 5.2 Sales Analyst Agent

**May:**

- Analyze sales/inventory data from Django APIs
- Emit structured recommendations: restock, discount, follow-up, prioritize SKU
- Assign priority scores and rationale (non-PII)

**May not:**

- Post to Instagram, reply to customers, or change prices in external systems without going through Django action workflow
- Access raw customer PII for LLM reasoning

### 5.3 Content Agent

**May:**

- Generate Instagram captions, product descriptions, campaign snippets
- Propose content actions (e.g. “post draft ready for review”)

**May not:**

- Publish to Instagram automatically in MVP (draft/recommendation only unless explicit auto action type exists and is approved)
- Scrape competitor websites in MVP (architecture note only for future)
- Handle support conversations

### 5.4 Support Agent

**May:**

- Read sanitized message threads from Django
- Draft safe replies
- Propose support actions with correct approval class

**May not:**

- Issue refunds, change orders, or share sensitive data in replies
- Perform sales or marketing tasks
- Send messages without Django recording action + approval state

### 5.5 Cross-Agent Rules

- Agents communicate **only** via coordinator orchestration or explicit HTTP agent-to-agent calls initiated by coordinator (MVP: prefer **star topology** — coordinator calls each agent; avoid agent mesh complexity).
- Each agent returns **JSON schema-validated** payloads.
- Out-of-scope requests return a structured `scope_violation` error to coordinator.

---

## 6. Data Flow Between Django and AI Services

### 6.1 High-Level Daily Report Data Flow

```
1. Manager → Frontend → Django: POST /api/reports/generate/
2. Django: create ReportRun(status=queued), enqueue Celery task
3. Celery worker:
   a. Build sanitized context bundle (sales, inventory, messages summary)
   b. Mint short-lived service JWT (tenant + store + coordinator scope)
   c. POST coordinator-agent /workflows/daily-report { report_run_id, context_ref }
4. Coordinator (LangGraph):
   a. Fetch full context from Django: GET /internal/ai/context/{report_run_id}/
   b. Parallel node calls: sales-agent, content-agent, support-agent
   c. Each agent: GET subset endpoints, run LLM, return structured output to coordinator
   d. Coordinator merges → POST /internal/ai/report-runs/{id}/complete/
5. Django: persist AgentOutputs, create Action records, set ReportRun=completed
6. Frontend polls or receives websocket (MVP: polling) → display report
```

### 6.2 Django Internal API Categories (for AI services)

| Category | Example endpoints (illustrative) | Notes |
|----------|-------------------------------|-------|
| Context | `GET /internal/ai/context/{report_run_id}/` | Pre-assembled, PII-safe bundle |
| Sales | `GET /internal/ai/stores/{store_id}/sales/summary/` | Aggregates only |
| Inventory | `GET /internal/ai/stores/{store_id}/inventory/low-stock/` | SKU-level, no customer data |
| Products | `GET /internal/ai/stores/{store_id}/products/` | Metadata, image URLs |
| Messages | `GET /internal/ai/stores/{store_id}/messages/recent/` | Sanitized threads |
| Actions write | `POST /internal/ai/actions/` | Agents propose actions |
| Report complete | `POST /internal/ai/report-runs/{id}/complete/` | Final report payload |
| Agent output | `POST /internal/ai/agent-outputs/` | Per-agent raw structured output |

All endpoints require `Authorization: Bearer <service_jwt>` and validate tenant/store match.

### 6.3 Data Django Sends vs. Withholds

| Sent to AI (sanitized) | Never sent to LLM |
|------------------------|-------------------|
| Aggregated sales by SKU/period | Full customer names (use “Customer #1234”) |
| Product titles, categories, prices | Phone, email, address |
| Inventory counts | Payment card data |
| Message text with PII redacted | Government IDs |
| Order status counts | Raw Instagram user IDs if policy requires masking |
| Historical action summaries | Unredacted DM attachments with embedded PII |

---

## 7. Authentication and Security Plan

### 7.1 Human Users (Dashboard)

| Item | MVP approach |
|------|----------------|
| Auth | Django session or JWT (access + refresh) issued by Django |
| Tenant binding | User belongs to one `Tenant`; optional `Store` scope for staff |
| Permissions | Role-based: `manager` (approve actions, trigger reports), `viewer` (read-only) — MVP can start with manager-only |
| Frontend | Next.js calls Django API with httpOnly cookie or Bearer token |

### 7.2 Service-to-Service (Django ↔ AI agents)

| Item | MVP approach |
|------|----------------|
| Mechanism | JWT signed by Django (`HS256` or `RS256` with shared secret/key in env) |
| Claims | `sub` (service name), `tenant_id`, `store_id`, `report_run_id` (optional), `exp`, `iat`, `aud=ai-services` |
| Issuance | Django Celery task mints token per workflow run (short TTL: 15–30 min) |
| Validation | Each FastAPI service validates signature, audience, expiry; forwards token to Django on API calls |
| Rotation | `JWT_SERVICE_SECRET` in env; document rotation procedure (no code in MVP) |

### 7.3 Agent-to-Agent

- MVP: Agents do not call each other directly; coordinator holds token and calls agents.
- Agent endpoints protected by shared internal network + optional `X-Internal-Service` header check.

### 7.4 Tenant Isolation

- DB: composite indexes on `(tenant_id, id)`; middleware sets `request.tenant` from user or JWT.
- AI context endpoint returns **404** if `report_run_id` does not belong to JWT tenant (no information leakage).

### 7.5 Permission Boundaries

| Actor | Can approve actions | Can trigger report | Can call internal AI APIs |
|-------|--------------------|--------------------|---------------------------|
| Manager user | Yes | Yes | No |
| AI service | No | No | Yes (scoped) |
| Coordinator | No | No | Yes (write report/actions) |

### 7.6 Minimal Security Baseline

- HTTPS via nginx in compose (self-signed dev cert acceptable)
- Secrets in `.env` (not committed); `.env.example` documents keys
- CORS restricted to frontend origin
- Rate limit report generation (e.g. 1 concurrent run per store) in Django
- Audit log table for approve/reject and action state changes

---

## 8. PII Handling Plan

### 8.1 Policy

**No raw PII in LLM prompts.** Django is responsible for redaction **before** data crosses the AI boundary.

### 8.2 MVP Redaction Pipeline (Django)

```
Raw DB record → PiiSanitizer (rules engine) → AI-safe DTO → JSON to agents
```

**Techniques:**

| Data type | Treatment |
|-----------|-----------|
| Phone numbers | Replace with `[PHONE_REDACTED]` or hash token `phone_hash_abc` |
| Email | Replace with `customer_<id>@redacted.local` |
| Physical address | Omit or replace with city-level only if needed for ops |
| Customer display name | `Customer #<internal_id>` |
| Instagram handle | Optional: keep public handle if business context requires; configurable per tenant |
| Message body | Regex + library pass (phones, emails, URLs with tokens) |

### 8.3 Support Agent Specifics

- Draft replies must not invent account details or promise refunds unless backed by order facts from API.
- Replies referencing order status use opaque `order_ref` not full customer name.

### 8.4 Logging

- Celery and agent logs must not dump full API responses; log `report_run_id`, `tenant_id`, durations, error codes only.
- Separate `pii_access_log` optional in MVP — at minimum, document “no PII in logs.”

### 8.5 Verification

- Phase acceptance: unit tests on `PiiSanitizer` with Persian and Latin phone/email patterns.
- Manual checklist: inspect coordinator context JSON before LLM call in dev tools.

---

## 9. Action Lifecycle and Status Model

### 9.1 Action Types

| Type code | Description | Default execution mode |
|-----------|-------------|------------------------|
| `sales.restock` | Restock recommendation | `approval_required` |
| `sales.discount` | Suggest discount/promo | `approval_required` |
| `sales.follow_up` | Customer follow-up suggestion | `approval_required` |
| `content.instagram_draft` | Caption/post draft | `approval_required` (MVP) |
| `content.product_description` | Product copy update | `approval_required` |
| `support.reply_draft` | DM reply draft | `auto_executable` if low-risk policy matches, else `approval_required` |
| `support.escalate` | Escalate to human | `approval_required` |

Execution mode can be overridden per tenant in `ActionPolicy` config (Django).

### 9.2 Action Status State Machine

```
                    ┌──────────────┐
                    │  suggested   │  (created by agent via Django)
                    └──────┬───────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
   (auto_executable)  (approval_required)  │
           │               │               │
           ▼               ▼               │
    ┌────────────┐   ┌───────────┐        │
    │  queued    │   │  pending  │        │
    │  (auto)    │   │ _approval │        │
    └─────┬──────┘   └─────┬─────┘        │
          │                │              │
          │         ┌──────┼──────┐       │
          │         ▼      ▼      ▼       │
          │    approved rejected cancelled│
          │         │      │              │
          ▼         ▼      └──────────────┘
    ┌─────────────────────────┐
    │       executing         │
    └────────────┬────────────┘
                 │
         ┌───────┴───────┐
         ▼               ▼
    ┌──────────┐   ┌──────────┐
    │ executed │   │  failed  │
    └──────────┘   └──────────┘
```

### 9.3 Status Definitions

| Status | Meaning |
|--------|---------|
| `suggested` | Agent proposed action; Django recorded metadata |
| `pending_approval` | Waiting for manager decision |
| `approved` | Manager approved; eligible for execution |
| `rejected` | Manager rejected; terminal |
| `cancelled` | System or user cancelled before execution; terminal |
| `queued` | Auto action approved by policy; waiting for worker |
| `executing` | Side effect in progress (e.g. sending DM stub) |
| `executed` | Successfully completed; terminal |
| `failed` | Execution error; terminal (retry may create new action in future) |

### 9.4 Action Record Fields (conceptual)

- `id`, `tenant_id`, `store_id`, `report_run_id` (nullable)
- `agent_name` (`sales`, `content`, `support`, `coordinator`)
- `action_type`, `title`, `description`, `payload` (JSON)
- `priority` (1–5), `requires_approval` (bool)
- `status`, `status_reason`, `created_at`, `updated_at`
- `decided_by` (user, nullable), `decided_at`
- `executed_at`, `execution_result` (JSON)

### 9.5 MVP Execution Scope

- **Auto-executable:** Django marks `executed` with simulated/stub handler (log + timestamp) — proves workflow without real Instagram API write in phase 1.
- **Approval-required:** Manager button triggers execution stub after approval.
- Real external side effects (Instagram publish/send) are post-MVP unless explicitly added as final integration sub-phase.

---

## 10. Daily Report Generation Flow

### 10.1 Trigger

- Manager clicks **“Generate daily report”** on dashboard.
- Django validates no concurrent `in_progress` run for store.

### 10.2 Report Run Lifecycle

| ReportRun status | Description |
|------------------|-------------|
| `queued` | Created, Celery task pending |
| `running` | Coordinator workflow started |
| `completed` | Report available |
| `failed` | Error with `error_message` |

### 10.3 Report Content Structure (JSON + rendered view)

```json
{
  "generated_at": "ISO8601",
  "period": { "from": "...", "to": "..." },
  "sales_summary": { "total_revenue", "order_count", "top_products", "low_performers" },
  "operational_insights": ["..."],
  "prioritized_actions": [ { "action_id", "priority", "summary" } ],
  "content_suggestions": [ { "type", "draft_preview" } ],
  "support_insights": [ { "theme", "message_count", "summary" } ],
  "next_steps": ["..."],
  "agent_outputs_ref": ["uuid", "..."]
}
```

### 10.4 Coordinator Responsibilities in Flow

1. Validate inputs and fetch context
2. Invoke specialist agents (parallel where possible)
3. Normalize and deduplicate overlapping recommendations
4. Rank actions by priority
5. Write agent outputs and actions to Django
6. Submit final report document

### 10.5 Scheduling (future)

- `celery-beat` included in compose but MVP only runs housekeeping (health, stale run cleanup).
- Scheduled daily report: **not MVP**; DB model supports `scheduled_at` nullable for future.

---

## 11. Dashboard Requirements

### 11.1 Pages / Views (MVP)

| View | Features |
|------|----------|
| Login | Email/password (or demo login for Prestia seed) |
| Home / Overview | Latest report status, quick stats, CTA to generate report |
| Daily Reports | List historical reports; detail view with sections |
| Agent Outputs | Filter by agent, report run, date |
| Actions | Tabs: pending approval, all, executed, failed, rejected |
| Action Detail | Approve / Reject buttons, payload preview, agent attribution |
| History | Unified timeline: reports, outputs, action state changes |

### 11.2 UX Requirements

- Show loading state while report generates (poll every 3–5s)
- Persian as default for AI-generated text; UI labels can remain English or Persian (product decision in implementation)
- Clear badges for action status and `requires_approval`
- Error toast if report fails with retry option
- Empty states for new tenant

### 11.3 API Endpoints (dashboard-facing, illustrative)

- `POST /api/reports/generate/`
- `GET /api/reports/`, `GET /api/reports/{id}/`
- `GET /api/agent-outputs/`
- `GET /api/actions/?status=pending_approval`
- `POST /api/actions/{id}/approve/`, `POST /api/actions/{id}/reject/`
- `GET /api/history/`

---

## 12. Docker Compose Service Plan

### 12.1 Services

| Service | Image / build | Ports (dev) | Depends on |
|---------|---------------|-------------|------------|
| `postgres` | `postgres:16` | internal | — |
| `redis` | `redis:7` | internal | — |
| `backend` | Dockerfile `backend/` | internal 8000 | postgres, redis |
| `celery-worker` | same as backend | — | backend, redis, postgres |
| `celery-beat` | same as backend | — | backend, redis, postgres |
| `frontend` | Dockerfile `frontend/` | internal 3000 | backend |
| `nginx` | `nginx:alpine` + config | 80, 443 | frontend, backend |
| `coordinator-agent` | Dockerfile `agents/coordinator/` | internal 8100 | backend |
| `sales-agent` | Dockerfile `agents/sales/` | internal 8101 | backend |
| `content-agent` | Dockerfile `agents/content/` | internal 8102 | backend |
| `support-agent` | Dockerfile `agents/support/` | internal 8103 | backend |

### 12.2 Volumes and Networks

- Named volume: `postgres_data`
- Single compose network: `app-network`
- Dev bind-mounts for hot reload on backend, frontend, agents

### 12.3 Healthchecks

- Each service exposes `/health` or `/healthz`
- `depends_on` with condition `service_healthy` where supported
- Django migrations run via entrypoint on backend start

### 12.4 Repository Layout (planned)

```
virtual_store_team/
├── docker-compose.yml
├── .env.example
├── nginx/
├── backend/                 # Django
├── frontend/                # Next.js
├── agents/
│   ├── shared/              # LLM client, Django API client, schemas
│   ├── coordinator/
│   ├── sales/
│   ├── content/
│   └── support/
└── docs/
    └── phases/
```

---

## 13. Celery / Redis Usage Plan

### 13.1 Redis Roles

| Use | MVP |
|-----|-----|
| Celery broker | Yes |
| Celery result backend | Yes (or django-celery-results in Postgres — pick one in implementation) |
| Workflow state cache | Optional; LangGraph state in coordinator memory is enough for MVP |
| Rate limiting | Optional future |

### 13.2 Synchronous vs Asynchronous

| Operation | Mode | Reason |
|-----------|------|--------|
| Dashboard CRUD reads | Sync HTTP | Fast |
| Login, approve/reject action | Sync HTTP | User waiting |
| Daily report generation | **Async** (Celery) | Multi-agent, LLM latency |
| Action execution stub | Async Celery | Consistency with future real integrations |
| Instagram message ingestion | Async | Polling/webhook handler enqueues processing |
| PII sanitization before AI call | Sync in Celery task | Must complete before agent call |
| Individual agent LLM call | Sync HTTP inside coordinator workflow | Orchestrator waits per node |
| Coordinator workflow overall | Async from Django POV | Entire graph runs inside one Celery task chain or coordinator async endpoint called by Celery |

### 13.3 Celery Tasks (MVP)

| Task | Description |
|------|-------------|
| `reports.generate_daily` | Main entry: sanitize → call coordinator → handle result |
| `actions.execute` | Process approved/auto actions (stub) |
| `integrations.poll_instagram_messages` | Optional periodic ingest (beat schedule every N minutes) |
| `maintenance.cleanup_stale_report_runs` | Mark stuck runs failed after timeout |

### 13.4 Concurrency and Timeouts

- Hard timeout per report run: 10 minutes (configurable)
- One active report per store at a time
- Celery worker concurrency: 2–4 for MVP

---

## 14. LLM Provider Abstraction Plan

### 14.1 Design

Shared Python package `agents/shared/llm/`:

```
LLMProvider (Protocol)
  ├── complete(messages, schema=None) → LLMResponse
  ├── embed(text) → vector          # optional, not MVP-critical
  └── model_id: str

Implementations:
  ├── OpenAIProvider
  ├── AnthropicProvider
  └── MockProvider (tests/dev without API key)
```

Factory: `get_llm_provider()` reads `LLM_PROVIDER` and provider-specific env vars.

### 14.2 Agent Usage Rules

- Agents import only `get_llm_provider()` — never `openai` directly in business logic.
- Structured outputs: use JSON schema / tool calling when provider supports; fallback to parse JSON from markdown fence.
- Prompt templates live per agent; language instruction injected from `AI_OUTPUT_LANGUAGE`.

### 14.3 Configuration

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `openai`, `anthropic`, `mock` |
| `LLM_MODEL` | Model name |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Provider secrets |
| `LLM_TIMEOUT_SECONDS` | Default 60 |
| `LLM_MAX_RETRIES` | Default 2 |

---

## 15. Environment Variables Plan

### 15.1 Core

| Variable | Example | Used by |
|----------|---------|---------|
| `DATABASE_URL` | `postgres://...` | backend, celery |
| `REDIS_URL` | `redis://redis:6379/0` | backend, celery |
| `DJANGO_SECRET_KEY` | random | backend |
| `DJANGO_DEBUG` | `true` / `false` | backend |
| `ALLOWED_HOSTS` | `localhost` | backend |
| `CORS_ALLOWED_ORIGINS` | `http://localhost` | backend |

### 15.2 Auth

| Variable | Example | Used by |
|----------|---------|---------|
| `JWT_SERVICE_SECRET` | random | backend, all agents |
| `JWT_SERVICE_AUDIENCE` | `ai-services` | backend, agents |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | `30` | backend |

### 15.3 AI / Language

| Variable | Example | Used by |
|----------|---------|---------|
| `AI_OUTPUT_LANGUAGE` | `fa` or `en` | all agents |
| `LLM_PROVIDER` | `openai` | all agents |
| `LLM_MODEL` | `gpt-4o-mini` | all agents |
| `OPENAI_API_KEY` | sk-... | agents (if openai) |

### 15.4 Service URLs (internal DNS)

| Variable | Example |
|----------|---------|
| `DJANGO_INTERNAL_BASE_URL` | `http://backend:8000` |
| `COORDINATOR_AGENT_URL` | `http://coordinator-agent:8100` |
| `SALES_AGENT_URL` | `http://sales-agent:8101` |
| `CONTENT_AGENT_URL` | `http://content-agent:8102` |
| `SUPPORT_AGENT_URL` | `http://support-agent:8103` |

### 15.5 Frontend

| Variable | Example |
|----------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost/api` |

### 15.6 Conventions

- Single `.env` for compose; `.env.example` committed with placeholders
- Per-tenant secrets (Instagram tokens) in DB, not env

---

## 16. Minimal Logging and Monitoring Plan

### 16.1 Logging (MVP)

| Layer | Format | Fields |
|-------|--------|--------|
| Django | JSON structured (or key=value) | `timestamp`, `level`, `tenant_id`, `request_id`, `message` |
| Celery | Same | `task_name`, `task_id`, `report_run_id`, `duration_ms` |
| FastAPI agents | Same | `service_name`, `report_run_id`, `node_name` (LangGraph) |

- Log levels: INFO default, DEBUG in dev
- **Never log** sanitized payload bodies at INFO; DEBUG only in local dev with flag `LOG_SENSITIVE_DEBUG=false` default

### 16.2 Correlation ID

- `X-Request-ID` generated at nginx or Django; propagated to Celery task kwargs and agent HTTP headers
- Report run ID ties cross-service traces together

### 16.3 Monitoring (MVP minimal)

| Capability | Approach |
|------------|----------|
| Health | `/health` on all services; docker healthchecks |
| Errors | Django `500` logging + Celery task failure signal |
| Metrics | Deferred — optional `GET /metrics` stub or simple admin counters in DB (`ReportRun` counts, failure rate) |
| Alerting | Not MVP — document manual dashboard review |

### 16.4 Admin Visibility

- Django admin enabled for: Tenant, Store, ReportRun, Action, AgentOutput (read-only for outputs)
- Helps debug Prestia demo without custom tooling

---

## 17. MVP Phases Overview

| Phase | Name | Focus |
|-------|------|-------|
| 0 | Foundation & Docker | Repo scaffold, compose, healthchecks |
| 1 | Django Core & Multi-Tenancy | Models, tenant isolation, admin |
| 2 | Auth & Users | Manager login, service JWT issuance |
| 3 | Store Data & Internal APIs | Products, sales seed, PII sanitizer, AI read APIs |
| 4 | Actions, Reports & History | Action model, ReportRun, audit trail |
| 5 | Celery & Async Wiring | Report task skeleton, redis broker |
| 6 | Agent Scaffold & LLM Abstraction | Shared lib, four FastAPI services, mock LLM |
| 7 | Sales Agent | Real sales analysis logic |
| 8 | Content Agent | Instagram-focused drafts |
| 9 | Support Agent | DM drafts + approval classification |
| 10 | Coordinator & LangGraph | Daily report orchestration end-to-end |
| 11 | Frontend Dashboard | UI for reports, actions, approval |
| 12 | Prestia Seed & E2E Demo | Demo data, manual QA, polish |

---

## 18. Phase Details

---

### Phase 0 — Foundation & Docker

**Goal:** Runnable compose stack with placeholder services, nginx as the single entrypoint, developer onboarding docs, application healthchecks, correct agent Docker build contexts, dev bind mounts with hot reload, and a documented final verification sign-off.

**Status:** Partially complete — subphases **0.1–0.5** are done; subphases **0.6–0.11** remain before Phase 0 can close.

**Deliverables (full Phase 0 scope):**

- `docker-compose.yml` with all planned services (postgres, redis, backend, celery-worker, celery-beat, frontend, nginx, four agent services)
- Dockerfiles for backend, frontend, and each agent (minimal hello-world / health-only placeholders)
- `.env.example` and documented `.env` setup
- Root `README.md` with onboarding and troubleshooting
- `nginx/` config directory and nginx service routing `/api/` → backend, `/` → frontend on port 80
- Application healthchecks for backend, frontend, agents, and Celery services where applicable
- Standardized agent Docker build contexts supporting shared package imports
- Development bind mounts and hot reload via `docker-compose.override.yml` (or equivalent) without clobbering dependency directories
- Final verification documented in `docs/phases/step-0.11.md` (created during subphase 0.11 implementation, not in this planning step)

**Tasks:**

1. Initialize monorepo directory structure
2. Configure postgres, redis, networks, volumes
3. Stub backend (Django project shell), frontend (Next.js shell), agents (FastAPI `/health`)
4. Wire compose services, env files, and initial full-stack verification
5. Add root README and developer onboarding
6. Add nginx reverse proxy as the Phase 0 entrypoint
7. Add application healthchecks and appropriate `depends_on` conditions
8. Align agent Docker build contexts for shared imports
9. Add dev bind mounts and hot reload safely
10. Run final Phase 0 verification and sign-off

**Subphases:**

#### Completed (0.1–0.5)

| Subphase | Name | Summary |
|----------|------|---------|
| **0.1** | Backend Docker foundation | `backend/Dockerfile` + entrypoint (migrate + runserver/gunicorn) |
| **0.2** | Frontend Docker foundation | `frontend/Dockerfile` |
| **0.3** | Agent placeholder services | Agent Dockerfiles (shared base image optional); FastAPI `/health` stubs |
| **0.4** | Docker Compose wiring | `docker-compose.yml` services, networks, volumes, `env_file` |
| **0.5** | Initial full-stack Docker verification | Containers build and start; basic stack smoke test |

#### Remaining (0.6–0.11)

**0.6 — Root README & Developer Onboarding**

Add a root `README.md` that enables a new developer to run the stack without reading implementation docs. It must include:

- Project overview
- Required tools (Docker, Docker Compose, etc.)
- `.env` setup from `.env.example`
- `docker compose up` instructions
- Service list and ports
- Health endpoint list
- Common Docker commands (`build`, `logs`, `ps`, `down`, etc.)
- Basic troubleshooting (port conflicts, unhealthy services, missing env vars)

**0.7 — Nginx Reverse Proxy Foundation**

Add nginx as the Phase 0 reverse proxy with:

- `nginx/` config directory
- nginx service in `docker-compose.yml`
- `/api/` routed to backend
- `/` routed to frontend
- port `80` exposed on the host
- Validation that the frontend works through `http://localhost`
- Validation that the API works through `http://localhost/api/...`

**0.8 — Application Healthchecks**

Add Docker Compose healthchecks for application services:

- `backend`
- `frontend`
- `coordinator-agent`
- `sales-agent`
- `content-agent`
- `support-agent`
- `celery-worker`, if it remains part of the Phase 0 stack
- `celery-beat`, if a reliable healthcheck is practical

Use `depends_on.condition: service_healthy` only where it is appropriate and does not create fragile startup coupling (e.g. avoid unnecessary chains that block unrelated services).

**0.9 — Agent Docker Build Context Alignment**

Fix and standardize agent Docker build contexts so all agent containers can import their local package and shared package modules correctly, including:

- `agents.shared.*`
- `agents.coordinator.*`
- `agents.sales.*`
- `agents.content.*`
- `agents.support.*`

This step must prevent `ModuleNotFoundError` at container startup and keep agent behavior as Phase 0 placeholders only (no real agent business logic).

**0.10 — Dev Bind Mounts & Hot Reload**

Add development bind mounts and hot-reload support where appropriate:

- Backend source bind mount
- Frontend source bind mount
- Agent source bind mounts
- Protection against overwriting dependency directories (`node_modules`, `.next`, Python `__pycache__`, virtual environments, etc.)
- Use `docker-compose.override.yml` if that is the cleanest way to keep dev-only behavior separate from production-like compose defaults

**0.11 — Final Phase 0 Verification & Sign-off**

Perform the final Phase 0 verification checklist, including:

- Clean Docker build (`docker compose build --no-cache` or equivalent fresh build)
- Full stack startup (`docker compose up`)
- `docker compose config` validates without errors
- `docker compose ps` shows expected services healthy
- Direct backend health check (e.g. `GET` backend `/health` on internal port)
- Backend health through nginx (`http://localhost/api/...` health path)
- Frontend direct access (internal port, if exposed for debugging)
- Frontend through nginx on port 80 (`http://localhost`)
- All agent health checks return 200
- Postgres and Redis health checks pass
- Celery worker/beat verification if present in the stack
- Final clean `git status` (no unintended generated artifacts)
- Creation of `docs/phases/step-0.11.md` documenting commands run, results, and any known limitations

**Dependencies:** None

**Final Phase 0 acceptance criteria:**

- Root `README.md` exists and explains how to run the stack
- Docker Compose stack starts successfully
- Nginx exposes the frontend on port 80
- Nginx routes API traffic to backend (`/api/` → backend)
- Backend, frontend, agents, Postgres, Redis, and Celery services are healthy where applicable
- All agent Docker builds work with shared imports (`agents.shared.*`, per-agent packages) without `ModuleNotFoundError`
- Development bind mounts / hot reload are configured safely (dependency dirs not overwritten)
- Final verification is documented in `docs/phases/step-0.11.md`

**Phase 0 exit gate (before Phase 1):**

Phase 0 is **not complete** until subphases **0.6–0.11** are implemented and all final acceptance criteria above pass. Do not begin Phase 1 (Django Core & Multi-Tenancy) until:

1. A developer can clone the repo, copy `.env.example` → `.env`, and start the full stack using only the root README.
2. `http://localhost` serves the frontend placeholder and `http://localhost/api/...` reaches the backend through nginx.
3. `docker compose ps` reports healthy status for backend, frontend, all four agents, Postgres, Redis, and Celery services (where present).
4. Agent containers start without import errors and respond on their health endpoints.
5. Dev override bind mounts work for local iteration without breaking installed dependencies inside containers.
6. `docs/phases/step-0.11.md` records the final verification run and sign-off.

---

### Phase 1 — Django Core & Multi-Tenancy

**Goal:** Tenant-scoped data model, enforced isolation, and an explicit tenant-scoping contract suitable for MVP.

**Status:** Complete — subphases **1.1–1.9** are implemented, verified, and documented in `docs/phases/step-1.9.md`.

**Deliverables (full Phase 1 scope):**

- Django apps: `tenants`, `stores`, `accounts`
- Models: `Tenant`, `Store`, `User` (custom user with `tenant_id`)
- `TenantMiddleware` resolving `request.tenant` on every request (MVP: session/user-based)
- Tenant-scoped queryset/manager primitives (`TenantScopedModel`, `for_tenant`, `get_for_tenant`, `for_request`, or equivalent)
- Django admin registration for tenant-owned models
- Initial and follow-up migrations with no drift (`makemigrations --check --dry-run` passes)
- Minimal tenant-scoped store read API path with HTTP-level cross-tenant isolation tests
- `seed_prestia` baseline: idempotent Prestia tenant and main store creation (catalog seeding deferred to later phases)
- Documented tenant scoping contract for tenant-facing vs admin/system access paths
- Final verification documented in `docs/phases/step-1.9.md` (created during subphase 1.9 implementation, not in this planning step)

**Dependencies:** Phase 0

**Subphases:**

#### Completed (1.1–1.9)

| Subphase | Name | Summary |
|----------|------|---------|
| **1.1** | Tenant model | `Tenant` model (`id`, `slug`, `name`, `settings` JSON); admin registration; initial migration. Documented in `docs/phases/step-1.1.md`. |
| **1.2** | Store model | `Store` model (`tenant`, `name`, `slug`, `timezone`, `currency`); tenant-scoped slug uniqueness; admin registration. Documented in `docs/phases/step-1.2.md`. |
| **1.3** | Tenant middleware | `TenantMiddleware` sets `request.tenant` from authenticated user/session (MVP: no subdomain resolution). Documented in `docs/phases/step-1.3.md`. |
| **1.4** | Cross-tenant access denial (queryset/middleware) | `TenantScopedModel`, `TenantScopedManager`, and scoped accessors (`for_tenant`, `get_for_tenant`, `for_request`); queryset/middleware-level cross-tenant denial tests. Documented in `docs/phases/step-1.4.md`. |
| **1.5** | Accounts migration drift closure | `accounts/0002_alter_user_managers.py`; `makemigrations --check --dry-run` passes. Documented in `docs/phases/step-1.5.md`. |
| **1.6** | Tenant-scoped Store API acceptance | `GET /api/stores/<store_id>/`; HTTP-level cross-tenant isolation tests. Documented in `docs/phases/step-1.6.md`. |
| **1.7** | `seed_prestia` baseline alignment | Idempotent Prestia tenant and main store; catalog seeding attributed to later phases. Documented in `docs/phases/step-1.7.md`. |
| **1.8** | Tenant scoping contract finalization | Explicit scoped-access MVP contract; tenant-facing path audit. Documented in `docs/phases/step-1.8.md`. |
| **1.9** | Phase 1 final verification & closure | Full verification, test/migration results, sign-off. Documented in `docs/phases/step-1.9.md`. |

#### Subphase reference (1.5–1.9 detail)

**1.5 — Accounts Migration Drift Closure**

Fix the migration drift for `accounts.User`. Ensure the custom `accounts.managers.UserManager` is reflected in migrations and `python manage.py makemigrations --check --dry-run` passes.

*Scope:*

- Fix the migration drift for `accounts.User`.
- Ensure the custom `accounts.managers.UserManager` is reflected in migrations.
- Ensure `python manage.py makemigrations --check --dry-run` passes.

*Expected deliverables:*

- Missing accounts migration committed.
- Migration check passes.
- Relevant accounts/tenants/stores tests pass.
- Documentation file to be created later: `docs/phases/step-1.5.md`.

*Acceptance criteria:*

- No pending migration is reported for `accounts`.
- `AUTH_USER_MODEL = "accounts.User"` remains valid.
- User manager state is consistent between model code and migrations.

**1.6 — Tenant-Scoped Store API Acceptance**

Add or complete a minimal tenant-scoped store read API path. Prove via HTTP-level tests that a user from one tenant cannot read another tenant's store by ID.

*Scope:*

- Add or complete a minimal tenant-scoped store read API path.
- Prove via HTTP-level tests that a user from one tenant cannot read another tenant's store by ID.

*Expected deliverables:*

- Minimal store read endpoint or existing endpoint hardening.
- API tests for same-tenant access.
- API tests for cross-tenant denial.
- Documentation file to be created later: `docs/phases/step-1.6.md`.

*Acceptance criteria:*

- Authenticated Prestia user can read the Prestia store when allowed.
- Authenticated Prestia user cannot read another tenant's store by direct ID.
- Cross-tenant access returns 404 or 403 according to project convention.
- The Phase 1 API acceptance criterion is explicitly satisfied.

**1.7 — Phase 1 Seed Prestia Baseline Alignment**

Clarify the Phase 1 baseline responsibility of `seed_prestia`. Ensure the Phase 1 baseline is tenant/store creation, not later catalog seeding. Keep later catalog/product/category seed behavior attributed to later phases.

*Scope:*

- Clarify the Phase 1 baseline responsibility of `seed_prestia`.
- Ensure the Phase 1 baseline is tenant/store creation, not later catalog seeding.
- Keep later catalog/product/category seed behavior attributed to later phases.

*Expected deliverables:*

- Verified idempotent Prestia tenant creation.
- Verified idempotent main Prestia store creation.
- Clear distinction between Phase 1 tenant/store baseline and later catalog seed data.
- Documentation file to be created later: `docs/phases/step-1.7.md`.

*Acceptance criteria:*

- `seed_prestia` guarantees a `prestia` tenant.
- `seed_prestia` guarantees a main store for Prestia.
- Running the command repeatedly does not create duplicate tenant/store records.
- Later catalog data is not incorrectly treated as a Phase 1 requirement.

**1.8 — Tenant Scoping Contract Finalization**

Finalize the tenant scoping contract for the MVP. Resolve the wording mismatch between “automatic tenant filtering” and explicit scoped access. Decide and document whether the accepted Phase 1 contract is fully automatic filtering through default managers, or explicit scoped access through approved manager/queryset methods.

*Scope:*

- Finalize the tenant scoping contract for the MVP.
- Resolve the wording mismatch between “automatic tenant filtering” and explicit scoped access.
- Decide and document whether the accepted Phase 1 contract is:
  - fully automatic filtering through default managers, or
  - explicit scoped access through approved manager/queryset methods.

*Preferred MVP contract:*

- Explicit tenant-scoped access is acceptable if all tenant-facing code paths use `for_tenant`, `get_for_tenant`, `for_request`, or equivalent safe accessors.
- Unscoped access may remain available only for admin/system-level use where intentional.

*Expected deliverables:*

- Clear tenant scoping contract.
- Verification that tenant-facing API/public paths do not rely on unsafe unscoped access.
- Documentation file to be created later: `docs/phases/step-1.8.md`.

*Acceptance criteria:*

- The Phase 1 documentation no longer ambiguously requires unsafe or undefined automatic filtering.
- Tenant-facing access paths are required to use scoped access.
- Admin/system escape hatches are intentional and documented.

**1.9 — Phase 1 Final Verification & Closure**

Final review after completing Phase 1.5–1.8. Confirm Phase 1 can be closed before moving forward.

*Scope:*

- Final review after completing Phase 1.5–1.8.
- Confirm Phase 1 can be closed before moving forward.

*Expected deliverables:*

- Full Phase 1 verification.
- Test and migration check results.
- Final completion decision.
- Documentation file to be created later: `docs/phases/step-1.9.md`.

*Acceptance criteria:*

- All Phase 1 subphases 1.1–1.9 are complete.
- Tenant, store, middleware, accounts, seed baseline, and API isolation requirements are satisfied.
- `makemigrations --check --dry-run` passes.
- Relevant tests pass.
- Phase 1 can be marked complete.

**Final Phase 1 acceptance criteria:**

- Admin can create tenant and store
- `AUTH_USER_MODEL = "accounts.User"` is valid with no accounts migration drift
- `seed_prestia` creates an idempotent Prestia tenant and main store baseline (no catalog seeding required in Phase 1)
- Tenant-facing access uses explicit scoped accessors per the finalized contract
- API request as Prestia user cannot read another tenant's store ID (proven at HTTP level)
- Final verification is documented in `docs/phases/step-1.9.md`

**Phase 1 Completion Gate:**

Phase 1 is **complete** as of 2026-06-26. Subphases **1.1 through 1.9** are implemented and documented. All gate requirements are satisfied and recorded in `docs/phases/step-1.9.md`:

1. Subphases 1.1–1.9 are implemented and documented.
2. Migration drift is resolved (`makemigrations --check --dry-run` passes; no pending `accounts` migrations).
3. API-level cross-tenant store isolation is proven (HTTP tests, not queryset/middleware tests alone).
4. `seed_prestia` baseline is aligned (idempotent tenant/store creation; catalog seeding attributed to later phases).
5. Tenant scoping contract is explicit (scoped accessors for tenant-facing paths; intentional admin/system escape hatches).
6. Final verification passes and is recorded in `docs/phases/step-1.9.md`.

Phase 2 (Auth & Users) may proceed.

---

### Phase 2 — Manager Authentication & Internal Service JWT

**Goal:** Manager session authentication for the dashboard and service JWT infrastructure so FastAPI AI agents can call Django internal APIs with scoped Bearer tokens.

**Status:** Complete — subphases **2.1–2.4** are implemented, verified, and documented in `docs/phases/step-2.1.md` through `docs/phases/step-2.4.md`.

**Deliverables (full Phase 2 scope):**

- Manager auth endpoints: `POST /api/auth/login/`, `POST /api/auth/logout/`, `GET /api/auth/me/`
- Django session-based authentication for manager/dashboard access
- Service JWT minting and decoding utilities (`mint_service_jwt`, `decode_service_jwt`)
- Configurable service JWT settings and `.env.example` placeholders
- Allowed AI service registry constants
- `InternalAIAuthentication` for `/internal/ai/*` routes (Bearer token only)
- Protected internal auth-check endpoint (`GET /internal/ai/auth-check/`)
- Safe `401` rejection for invalid, malformed, expired, or wrong-audience service tokens
- Unit and integration tests for manager auth, internal AI auth, JWT lifecycle, and token rejection
- Final verification documented in `docs/phases/step-2.4.md` (created during subphase 2.4 implementation, not in this planning step)

**Dependencies:** Phase 1

**Subphases:**

#### Completed (2.1–2.4)

| Subphase | Name | Summary |
|----------|------|---------|
| **2.1** | Manager Session Authentication | `POST /api/auth/login/`, `POST /api/auth/logout/`, `GET /api/auth/me/`; Django session auth for managers; login/logout/me tests. Documented in `docs/phases/step-2.1.md`. |
| **2.2** | Service JWT Infrastructure | Service JWT mint/decode utilities; required claims (`sub`, `tenant_id`, `store_id`, `iat`, `exp`, `aud`); configurable JWT settings; `.env.example` placeholders; allowed AI service registry. Documented in `docs/phases/step-2.2.md`. |
| **2.3** | Internal AI Authentication | `InternalAIAuthentication`; Bearer-only auth for `/internal/ai/*`; protected auth-check endpoint; safe `401` for invalid/malformed/expired/wrong-audience tokens; session users blocked from internal AI routes. Documented in `docs/phases/step-2.3.md`. |
| **2.4** | Phase 2 Verification & Token Lifecycle Tests | Unit tests for service JWT mint/decode lifecycle; integration tests for protected internal AI endpoints; coverage for valid, invalid, expired, wrong-audience, and missing-credential cases; Phase 2 accounts/auth test modules pass. Documented in `docs/phases/step-2.4.md`. |

#### Subphase reference (2.1–2.4 detail)

**2.1 — Manager Session Authentication**

Implemented human dashboard authentication endpoints and Django session-based manager auth.

*Implemented:*

- `POST /api/auth/login/` — email/password login for manager users
- `POST /api/auth/logout/` — end the current Django session
- `GET /api/auth/me/` — return authenticated manager profile with tenant/store context
- Django session-based authentication for manager/dashboard access
- Relevant tests for login, logout, and current-user session behavior (`accounts.tests.test_auth`)

*Documented in:* `docs/phases/step-2.1.md`

**2.2 — Service JWT Infrastructure**

Implemented service JWT minting/decoding utilities and configuration for internal AI service authentication.

*Implemented:*

- Service JWT minting and decoding utilities (`mint_service_jwt`, `decode_service_jwt`)
- Required JWT claims: `sub`, `tenant_id`, `store_id`, `iat`, `exp`, and `aud`
- Configurable service JWT settings (`JWT_SERVICE_SECRET`, `JWT_SERVICE_AUDIENCE`, `JWT_SERVICE_ALGORITHM`, `JWT_SERVICE_TOKEN_LIFETIME_MINUTES`)
- `.env.example` placeholders for JWT service configuration
- Allowed AI service registry constants:
  - `coordinator-agent`
  - `sales-agent`
  - `content-agent`
  - `support-agent`

*Documented in:* `docs/phases/step-2.2.md`

**2.3 — Internal AI Authentication**

Implemented DRF authentication for internal AI routes and hardened rejection of invalid service tokens.

*Implemented:*

- `InternalAIAuthentication` DRF authentication class
- Bearer-token-only authentication for `/internal/ai/*` routes
- Protected internal auth-check endpoint (`GET /internal/ai/auth-check/`)
- Rejection of invalid, malformed, expired, or wrong-audience tokens with safe `401` responses
- Prevention of human/session-authenticated users from accessing internal AI routes

*Documented in:* `docs/phases/step-2.3.md`

**2.4 — Phase 2 Verification & Token Lifecycle Tests**

Completed Phase 2 verification with comprehensive JWT lifecycle and internal AI endpoint tests.

*Implemented:*

- Unit tests for service JWT mint/decode lifecycle (`accounts.tests.test_service_jwt`)
- Integration tests for protected internal AI endpoints
- Tests for valid tokens, invalid tokens, expired tokens, wrong-audience tokens, and missing credentials
- Confirmation that Phase 2 account/auth test modules pass (`test_auth`, `test_internal_ai_auth`, `test_internal_ai_auth_401`, `test_service_jwt`)

*Documented in:* `docs/phases/step-2.4.md`

**Final Phase 2 acceptance criteria:**

- Manager can authenticate via `POST /api/auth/login/` and retrieve profile via `GET /api/auth/me/`
- Valid service JWT accesses `GET /internal/ai/auth-check/`; invalid token is rejected with `401`
- Human session-authenticated user cannot access internal AI routes without a valid service JWT
- Service JWT carries required claims and allowed service names from the registry
- Phase 2 accounts/auth test modules pass
- Final verification is documented in `docs/phases/step-2.4.md`

**Phase 2 Completion Gate:**

Phase 2 is **complete** as of 2026-06-26. Subphases **2.1 through 2.4** are implemented and documented. All gate requirements are satisfied and recorded in `docs/phases/step-2.4.md`:

1. Subphases 2.1–2.4 are implemented and documented.
2. Manager session auth endpoints work with tenant/store context.
3. Service JWT mint/decode utilities enforce required claims and allowed service names.
4. `InternalAIAuthentication` protects `/internal/ai/*` with Bearer-only access.
5. Invalid, expired, and wrong-audience tokens return safe `401` responses.
6. Human/session auth does not grant access to internal AI routes.
7. JWT lifecycle and internal AI integration tests pass.

Phase 3 (Store Data, PII & Internal Read APIs) may proceed.

**Note:** Phase 2 is complete. No Phase 2.5+ implementation tasks are currently required. Non-blocking follow-ups such as frontend cookie/CORS wiring, Celery-driven production token issuance, and tenant/store route-parameter matching belong to later phases.

---

### Phase 3 — Store Data, PII & Internal Read APIs

**Goal:** Generic store commerce models and sanitized AI-facing read APIs.

**Deliverables:**

- Models: `Product`, `Category`, `Order`, `OrderItem`, `InventoryLevel`, `Customer` (PII stored, not exported raw), `MessageThread`, `Message`
- `PiiSanitizer` module with tests
- Internal APIs: sales summary, products, low stock, recent messages (sanitized)
- Prestia seed data: sample bags, orders, messages

**Tasks:**

1. Design normalized product/order schema (generic e-commerce)
2. Implement sanitizer pipeline
3. Build read endpoints with tenant scoping
4. Seed realistic Prestia demo data

**Subtasks:**

- 3.1 Product/category CRUD via admin + seed command
- 3.2 Sales aggregation queries (today, last 7 days)
- 3.3 Low-stock query (`inventory < threshold`)
- 3.4 Message ingest model (manual admin entry or JSON import for MVP)
- 3.5 `GET /internal/ai/context/{report_run_id}/` stub returning sanitized bundle

**Dependencies:** Phase 2

**Acceptance criteria:**

- Internal API returns sales and inventory data for Prestia store
- Raw phone/email never appear in API JSON destined for AI
- PiiSanitizer tests pass for FA/EN patterns

---

### Phase 4 — Actions, Reports & History

**Goal:** Persist reports, agent outputs, and action lifecycle in Django; expose dashboard read APIs and manager approve/reject endpoints.

**Status:** Complete — subphases **4.1–4.9** are implemented, verified, and documented in `docs/phases/step-4.1.md` through `docs/phases/step-4.9.md`.

**Deliverables (full Phase 4 scope):**

- Models: `ReportRun`, `DailyReport`, `AgentOutput`, `Action`, `ActionEvent` (audit)
- `ActionService` state transition service (create, approve, reject, queue execution)
- Internal AI write APIs: actions, agent outputs, report run completion
- Dashboard history feed: `GET /api/history/`
- Dashboard report read APIs: `GET /api/reports/`, `GET /api/reports/{id}/`
- Dashboard action read APIs: `GET /api/actions/`, `GET /api/actions/{id}/`
- Manager approve/reject APIs: `POST /api/actions/{id}/approve/`, `POST /api/actions/{id}/reject/`
- Final verification documented in `docs/phases/step-4.9.md`

**Dependencies:** Phase 3

**Subphases:**

#### Completed (4.1–4.9)

| Subphase | Name | Summary |
|----------|------|---------|
| **4.1** | Action creation service | `ActionService.create_from_agent_payload()` with policy defaults, tenant/store scoping, and `ActionEvent` audit on create. Documented in `docs/phases/step-4.1.md`. |
| **4.2** | Action state transitions | `ActionService.approve()`, `.reject()`, `.queue_execution()` with strict state machine and audit events. Documented in `docs/phases/step-4.2.md`. |
| **4.3** | Internal AI write APIs | `POST /internal/ai/actions/`, `POST /internal/ai/agent-outputs/` delegating to service layer. Documented in `docs/phases/step-4.3.md`. |
| **4.4** | Report run completion | `POST /internal/ai/report-runs/{id}/complete/` via `ReportRunService`. Documented in `docs/phases/step-4.4.md`. |
| **4.5** | Unified history feed | `GET /api/history/` tenant/store-scoped timeline from existing records. Documented in `docs/phases/step-4.5.md`. |
| **4.6** | Dashboard reports read APIs | `GET /api/reports/`, `GET /api/reports/{id}/` with pagination, newest-first ordering, and safe summaries. Documented in `docs/phases/step-4.6.md`. |
| **4.7** | Dashboard actions read APIs | `GET /api/actions/`, `GET /api/actions/{id}/` with status/type/agent/date filters and safe payload summaries. Documented in `docs/phases/step-4.7.md`. |
| **4.8** | Manager approve/reject APIs | `POST /api/actions/{id}/approve/`, `POST /api/actions/{id}/reject/` delegating to `ActionService`. Documented in `docs/phases/step-4.8.md`. |
| **4.9** | Phase 4 alignment & verification | Full Phase 4 deliverable checklist, test verification, and closure. Documented in `docs/phases/step-4.9.md`. |

#### Subphase reference (4.1–4.9 detail)

**4.1 — Action Creation Service**

*Implemented:*

- `ActionService.create_from_agent_payload()` with payload validation and default action policy
- Initial status `pending_approval` or `queued` based on policy
- `ActionEvent` audit record on creation
- Tenant/store scoping from trusted server context

*Documented in:* `docs/phases/step-4.1.md`

**4.2 — Action State Transitions**

*Implemented:*

- `ActionService.approve()` — `pending_approval` → `approved`
- `ActionService.reject()` — `pending_approval` → `rejected`
- `ActionService.queue_execution()` — `approved` → `queued`
- `ActionEvent` audit trail for every transition
- `decided_by` / `decided_at` on human decisions

*Documented in:* `docs/phases/step-4.2.md`

**4.3 — Internal AI Write APIs**

*Implemented:*

- `POST /internal/ai/actions/` — agent action proposals via `ActionService.create_from_agent_payload()`
- `POST /internal/ai/agent-outputs/` — structured agent output persistence
- Service JWT authentication; tenant/store from token, not request body

*Documented in:* `docs/phases/step-4.3.md`

**4.4 — Report Run Completion**

*Implemented:*

- `POST /internal/ai/report-runs/{id}/complete/` — coordinator completes a running report run
- `DailyReport` persistence and `ReportRun` → `completed` in one transaction
- Referenced agent outputs and actions validated for tenant/store scope

*Documented in:* `docs/phases/step-4.4.md`

**4.5 — Unified History Feed**

*Implemented:*

- `GET /api/history/` — dashboard-facing unified timeline
- Aggregates `ReportRun`, `DailyReport`, `AgentOutput`, `Action`, `ActionEvent`
- Session authentication, tenant/store scoping, filtering, pagination, PII-safe summaries

*Documented in:* `docs/phases/step-4.5.md`

**4.6 — Dashboard Reports Read APIs**

*Implemented:*

- `GET /api/reports/` — paginated report run list (newest first)
- `GET /api/reports/{id}/` — report run detail with daily report section summaries
- Session authentication consistent with other dashboard APIs
- Tenant/store scoping; cross-tenant/cross-store returns `404`
- Read-only serializers; no raw sensitive payloads

*Acceptance criteria:*

- Authenticated manager/user can list and retrieve scoped reports
- Unauthenticated and service JWT requests are rejected
- Pagination matches existing dashboard conventions (`limit`/`offset`)
- Focused API tests pass

*Documented in:* `docs/phases/step-4.6.md`

**4.7 — Dashboard Actions Read APIs**

*Implemented:*

- `GET /api/actions/` — paginated action list (newest first)
- `GET /api/actions/{id}/` — action detail for manager approval dashboard
- Filters: `status`, `action_type`, `agent`/`agent_name`, `requires_approval`, date range (`from`/`to`)
- Safe `payload_summary` (operational keys only; PII/sensitive fields excluded)
- `decided_by`, `decided_at`, agent metadata, and timestamps included

*Acceptance criteria:*

- List and detail access for authenticated scoped users
- `status=pending_approval` filtering works
- Cross-tenant/store isolation enforced
- Unauthorized access rejected
- Focused API tests pass

*Documented in:* `docs/phases/step-4.7.md`

**4.8 — Manager Approve/Reject APIs**

*Implemented:*

- `POST /api/actions/{id}/approve/` — delegates to `ActionService.approve()`
- `POST /api/actions/{id}/reject/` — delegates to `ActionService.reject()`; non-empty `reason` required
- Manager-only (or staff); tenant/store scoping before transition
- Returns updated action representation; `ActionEvent` audit via service layer
- Invalid transitions return `400`; unauthorized users return `403`; cross-scope returns `404`

*Acceptance criteria:*

- Manager can approve/reject pending actions
- Reject without reason fails validation
- Invalid status transitions fail
- Audit events created through service layer
- Focused API tests pass

*Documented in:* `docs/phases/step-4.8.md`

**4.9 — Phase 4 Alignment and Verification**

*Scope:*

- Re-check all Phase 4 deliverables against implementation
- Resolve prior inconsistency (Step 4.5 service foundations vs missing dashboard APIs)
- Run focused test suites for action service, internal AI writes, report completion, history, reports, actions, approve/reject
- Record completion decision in `docs/phases/step-4.9.md`

*Acceptance criteria:*

- All Phase 4 subphases 4.1–4.9 complete and documented
- All Phase 4 dashboard and internal APIs implemented and tested
- Phase 4 can be marked complete

*Documented in:* `docs/phases/step-4.9.md`

**Final Phase 4 acceptance criteria:**

- Agent can POST suggested action → appears as `pending_approval` or `queued`
- Manager approve transitions to executable state; reject records reason and terminal state
- History shows chronological events
- Dashboard can list/detail reports and actions with tenant/store isolation
- Manager approve/reject endpoints work through `ActionService` with audit trail
- Internal AI write and report completion APIs remain functional
- Relevant Phase 4 tests pass
- Final verification is documented in `docs/phases/step-4.9.md`

**Phase 4 Completion Gate:**

Phase 4 is **complete** when subphases **4.1 through 4.9** are implemented, documented, and verified. All gate requirements are recorded in `docs/phases/step-4.9.md`:

1. Action state machine and `ActionEvent` audit trail implemented (4.1–4.2).
2. Internal AI write APIs and report completion API implemented (4.3–4.4).
3. Dashboard history feed implemented (4.5).
4. Dashboard report and action read APIs implemented (4.6–4.7).
5. Manager approve/reject APIs implemented (4.8).
6. Full Phase 4 verification passes (4.9).

Phase 5 (Celery & Async Wiring) may proceed once Phase 4 is closed.

---

### Phase 5 — Celery & Async Wiring

**Goal:** Async daily report job orchestration from Django.

**Deliverables:**

- Celery app configured with Redis
- `reports.generate_daily` task (skeleton calling coordinator HTTP)
- `actions.execute` stub task
- celery-beat with stale-run cleanup schedule
- `POST /api/reports/generate/` enqueueing task

**Tasks:**

1. Celery config in Django
2. Report generation task with status updates
3. Error handling and timeouts
4. Beat schedule for maintenance only

**Subtasks:**

- 5.1 Configure `CELERY_BROKER_URL`, worker entrypoint in compose
- 5.2 Task: create ReportRun → `running` → call coordinator → `completed`/`failed`
- 5.3 Prevent duplicate concurrent runs per store
- 5.4 Integration test with mock coordinator HTTP server

**Dependencies:** Phase 4

**Acceptance criteria:**

- API trigger enqueues Celery task visible in worker logs
- ReportRun status progresses through lifecycle
- Failed coordinator call sets `failed` with error message

---

### Phase 6 — Agent Scaffold & LLM Abstraction

**Goal:** Shared agent library and working FastAPI containers with mock LLM.

**Deliverables:**

- `agents/shared/`: `llm/`, `django_client/`, `schemas/`, `language.py`
- Each agent: FastAPI app, settings, `/health`, `/run` or workflow endpoint
- `MockProvider` returning deterministic JSON
- Docker compose integration with env vars

**Tasks:**

1. Implement LLM provider protocol and factory
2. Django HTTP client with JWT forwarding
3. Pydantic schemas for agent I/O
4. Wire all four agents to echo mock responses

**Subtasks:**

- 6.1 `AI_OUTPUT_LANGUAGE` prompt prefix helper (Persian default)
- 6.2 `DjangoClient` with retry and correlation ID header
- 6.3 JSON schema validation on agent responses
- 6.4 Coordinator stub endpoint accepting report job

**Dependencies:** Phase 5

**Acceptance criteria:**

- Each agent container starts and responds to `/health`
- Setting `LLM_PROVIDER=mock` produces structured output without API key
- Agent can call Django internal API with service JWT

---

### Phase 7 — Sales Agent

**Goal:** Useful sales and inventory analysis with structured action recommendations.

**Deliverables:**

- Sales agent LangGraph or pipeline (single-agent graph)
- Prompts for sales analysis in `AI_OUTPUT_LANGUAGE`
- Output schema: `SalesAnalysisResult` with `recommendations[]`
- Integration with Django: POST actions of types `sales.*`

**Tasks:**

1. Fetch sales/inventory from Django client
2. LLM analysis with structured output
3. Map recommendations to Action payloads
4. Unit tests with mock data

**Subtasks:**

- 7.1 Define recommendation priority rubric in prompt
- 7.2 Handle empty sales gracefully
- 7.3 Validate JSON against schema before return
- 7.4 Document example output in `docs/examples/sales_output.json`

**Dependencies:** Phase 6

**Acceptance criteria:**

- Given Prestia seed data, agent returns at least one restock or discount recommendation
- Recommendations include `priority`, `action_type`, `payload` fields
- No PII in agent logs or LLM prompts

---

### Phase 8 — Content Agent

**Goal:** Instagram-oriented content drafts tied to store products.

**Deliverables:**

- Content Agent prompt and brand voice handling
- Content Agent runtime pipeline
- Output schema: `ContentSuggestions` / `ContentDraft`
- Draft limit enforcement
- FastAPI `/run` endpoint
- Mock/LLM generation path
- Action payload mapping for `content.instagram_draft` and `content.product_description`
- Approval-required behavior
- Example output document (`docs/examples/content_output.json`)

**Tasks:**

1. Pull or consume top/relevant products from Django internal APIs or coordinator-provided context.
2. Generate Persian captions by default using the configured brand voice and campaign angle.
3. Support English output when `AI_OUTPUT_LANGUAGE=en`.
4. Return reviewable drafts only.
5. Validate all generated output against schema.
6. Limit draft count to the configured maximum.
7. Map validated drafts to approval-required content actions.
8. Provide deterministic tests using MockProvider or fixtures.

**Subtasks:**

#### 8.1 Prompt template with brand voice from `store.settings`

- Reusable Content Agent prompt template for Instagram captions and product descriptions.
- Brand voice extraction from `store.settings` (or structured store context) with a safe generic fallback when settings are missing or malformed.
- No Prestia-specific hardcoding in agent code; tenant/store data comes from input only.
- Persian default and English mode via `AI_OUTPUT_LANGUAGE` and the shared language helper.
- Reviewable, approval-required draft intent; no publish/send side effects.

#### 8.2 Limit drafts to N per run

- Deterministic max-drafts-per-run mechanism with MVP default of **3**.
- Configurable via request override, `store.settings.content_agent.max_drafts_per_run`, environment variable, and documented defaults where applicable.
- Defensive validation for missing, non-integer, or out-of-range values.
- Code-level enforcement after LLM/mock output is parsed — not prompt-only.
- Hard MVP upper bound (e.g. 5) to prevent runaway output.

#### 8.3 Schema validation tests

- `ContentSuggestions` and `ContentDraft` Pydantic schemas with strict validation.
- Valid and invalid output tests using fixtures or mock dicts; no real LLM API keys required.
- Only allowed action types: `content.instagram_draft`, `content.product_description`.
- `requires_approval` must be `true` on content suggestions.
- Draft limit applied before validation; invalid outputs rejected or handled per project conventions.

#### 8.4 Content Agent runtime pipeline

- Implement `run_content_analysis()` (or equivalent) as the main pipeline entry point.
- Consume product context from Django client, coordinator-provided context, or validated request input.
- Build prompts using Step 8.1; call `get_llm_provider()` / `MockProvider` for structured generation.
- Parse, normalize, apply draft limit (Step 8.2), and schema-validate (Step 8.3) before return.
- Handle empty or missing product data gracefully without hallucinating catalog facts.
- No external publishing, sending, or side effects.

#### 8.5 FastAPI `/run` endpoint

- Add runnable `POST /run` on `content-agent`, aligned with the Sales Agent `/run` pattern where practical.
- Request and response schemas wired to the runtime pipeline; response is schema-validated `ContentSuggestions`.
- Preserve existing `/health` endpoint.
- Deterministic endpoint tests (success, validation failure, empty context) without real LLM keys.

#### 8.6 Content action mapping and approval persistence

- Map validated `ContentDraft` items to Django-compatible action payloads.
- Support only `content.instagram_draft` and `content.product_description`.
- Ensure approval-required behavior (`pending_approval` / `requires_approval`) per action policy defaults.
- Integrate with Django internal actions endpoint or existing `ActionService` creation pattern; no direct external publishing.
- All side effects remain inside the Django action workflow (suggest → review → approve).

#### 8.7 Phase 8 acceptance proof and example output

- Deterministic tests with Prestia-style product fixtures or seeded Prestia catalog data.
- Prove at least one Instagram caption is generated for a product fixture.
- Prove Persian default output path and English mode with `AI_OUTPUT_LANGUAGE=en` end-to-end.
- Prove approval-required action compatibility when drafts are mapped/persisted.
- Add `docs/examples/content_output.json` validated against `ContentSuggestions`.
- Document final validation commands for the full Content Agent test suite.

**Dependencies:**

- Phase 6 (shared language helper, Django client, schema validation, agent scaffold)
- Phase 8.1–8.3 for Steps 8.4–8.7
- Phase 4 action model and internal AI write APIs for action persistence behavior (Step 8.6)
- May proceed in parallel with Phase 7 after Phase 6 completes

**Acceptance criteria:**

- Content Agent produces at least one Instagram caption for a Prestia-style product fixture or seeded Prestia product.
- Content Agent supports product description drafts.
- Generated drafts are schema-validated (`ContentSuggestions`).
- Generated drafts respect the configured max draft limit.
- English output works when `AI_OUTPUT_LANGUAGE=en`.
- Outputs are reviewable and approval-required when mapped/persisted as actions.
- Only `content.instagram_draft` and `content.product_description` are accepted for content actions.
- No real Instagram publishing or external side effects are introduced.
- No Prestia-specific business logic is hardcoded in agent code.
- Tests run with MockProvider/fixtures and do not require real LLM API keys.
- `docs/examples/content_output.json` exists by the end of Step 8.7.

**Non-goals:**

- Real Instagram publishing
- Competitor scraping
- Website article generation
- Support Agent logic
- Coordinator/LangGraph orchestration
- Frontend dashboard changes
- Real external side effects

---

### Phase 9 — Support Agent

**Goal:** Safe handling of customer message threads with approval-aware reply drafts.

**Deliverables:**

- Support agent pipeline
- Classification: low-risk vs sensitive (approval required)
- Output schema: `SupportInsights`, `reply_drafts[]`
- Scope guardrails in system prompt

**Tasks:**

1. Consume sanitized message threads API
2. Summarize themes and sentiment (non-PII)
3. Draft replies with safety constraints
4. Assign correct `requires_approval` flag

**Subtasks:**

- 9.1 Policy table for auto vs approval (e.g. generic FAQ → auto draft only, refund mention → approval)
- 9.2 Refusal behavior for out-of-scope requests
- 9.3 Tests for unsafe prompt injection from message text

**Dependencies:** Phase 6 (parallel with Phases 7–8)

**Acceptance criteria:**

- Support agent summarizes recent threads without leaking PII
- Sensitive drafts created with `pending_approval`
- Agent refuses to perform sales tasks when asked in message

---

### Phase 10 — Coordinator & LangGraph

**Goal:** End-to-end orchestrated daily report across all agents.

**Deliverables:**

- LangGraph workflow in coordinator-agent
- Nodes: `fetch_context`, `run_sales`, `run_content`, `run_support`, `merge`, `submit`
- Parallel execution of specialist agents where possible
- Final `DailyReport` payload to Django

**Tasks:**

1. Define graph state typed dict
2. Implement HTTP calls to specialist agents
3. Merge and prioritize actions (dedupe by product/SKU)
4. Error handling: partial failure still produces report with warnings

**Subtasks:**

- 10.1 Star topology only (no agent-to-agent)
- 10.2 Timeout per node
- 10.3 Persist intermediate `AgentOutput` records via Django client
- 10.4 Integration test: full graph with mock LLM across services

**Dependencies:** Phases 7, 8, 9

**Acceptance criteria:**

- Celery task → coordinator → all agents → Django `ReportRun=completed`
- Daily report contains sales summary, actions, content and support sections
- Coordinator does not auto-approve actions
- Partial agent failure documented in report `warnings[]`

---

### Phase 11 — Frontend Dashboard

**Goal:** Manager-facing UI fulfilling all dashboard requirements.

**Deliverables:**

- Auth pages and protected routes
- Report list and detail views
- Generate report button with polling
- Actions list with approve/reject
- Agent outputs and history timeline
- Basic responsive layout

**Tasks:**

1. API client layer
2. Report generation UX
3. Action approval workflow UI
4. History view

**Subtasks:**

- 11.1 Login flow with token/cookie handling
- 11.2 Report detail rendering markdown/sections from JSON
- 11.3 Status badges and filters
- 11.4 Error and empty states
- 11.5 Persian text rendering (RTL support where needed)

**Dependencies:** Phases 4, 5, 10

**Acceptance criteria:**

- Manager can login, trigger report, see completed report within reasonable time
- Pending actions show approve/reject; state updates without page reload (or on refresh)
- All MVP dashboard requirements from Section 11 are met

---

### Phase 12 — Prestia Seed & E2E Demo

**Goal:** Polished demo proving MVP success criteria on Prestia tenant.

**Deliverables:**

- Complete `seed_prestia` with products, orders, inventory, messages
- Demo manager account credentials in README (not production secrets)
- E2E test script or checklist document
- Bug fixes and performance tuning

**Tasks:**

1. Enrich seed data for compelling report output
2. Run full manual E2E walkthrough
3. Fix integration issues
4. Document known limitations

**Subtasks:**

- 12.1 Verify Persian output quality with real LLM
- 12.2 Review PII in coordinator context one final time
- 12.3 Stabilize docker compose for fresh clone
- 12.4 Write `docs/demo/prestia_walkthrough.md` (optional short guide)

**Dependencies:** Phase 11

**Acceptance criteria:**

- **MVP success criteria met** (Section 1 and user requirements)
- Fresh `docker compose up` + seed + login + generate report works
- Dashboard shows prioritized actions and agent outputs
- Approval workflow demonstrable on at least one action

---

## 19. Suggested Implementation Order

```
Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → (7 ∥ 8 ∥ 9) → 10 → 11 → 12
```

**Rationale:**

1. Infrastructure and Django tenancy first — everything depends on scoped data.
2. Internal APIs and action model before agents — agents have somewhere to write.
3. Celery before real agents — async contract is stable early.
4. Agent scaffold with mock LLM before real prompts — validates boundaries cheaply.
5. Specialist agents in parallel — independent teams/paths possible.
6. Coordinator only after specialists work — integration risk isolated.
7. Frontend after backend E2E path exists — can use admin/API for interim testing.
8. Prestia polish last — demo quality without blocking architecture.

**Critical path:** 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 10 → 11 → 12

---

## 20. Risks and Simplifications for MVP

| Risk | Mitigation / simplification |
|------|----------------------------|
| LangGraph complexity | Star topology; single workflow (`daily_report` only); in-memory state |
| LLM cost/latency | Use small models; `MockProvider` for CI; cache product list per run |
| Instagram API access | MVP uses seeded messages; send/publish is stubbed |
| PII leakage | Central Django sanitizer; automated tests; manual QA checklist |
| Multi-agent failure modes | Partial report with warnings; coordinator timeout per node |
| Over-engineering tenancy | Single store per tenant in MVP; schema still has `store_id` |
| Persian LLM quality | Prompt explicitly requests formal Persian; allow `AI_OUTPUT_LANGUAGE=en` fallback for demos |
| JWT secret leakage | Dev-only secrets in `.env`; document production KMS later |
| Celery debugging | Log `report_run_id`; Django admin shows run status |
| Scope creep | Explicit “not in MVP” list (Section 21) |

**Intentional simplifications:**

- Action execution is **stubbed** (log + status) unless minimal Instagram write is added late
- No scheduled daily reports (manual trigger only)
- No competitor scraping for content agent
- No billing/subscription for SaaS
- No multi-store per tenant UI (schema ready)
- Coordinator is the only orchestrator; no peer agent calls

---

## 21. What Should Explicitly NOT Be Implemented in the First MVP

| Excluded | Reason |
|----------|--------|
| Scheduled/automatic daily reports (cron) | Manual trigger sufficient; beat only for maintenance |
| Real Instagram publish/send integration | High scope; stub execution proves workflow |
| Competitor website scraping | Content agent future feature |
| Multiple LLM providers wired simultaneously | Abstraction yes; one active provider in MVP |
| Direct database access from agents | Architecture violation |
| Prestia-hardcoded business rules in code | Use tenant data and settings only |
| Collapsing agents into monolith service | Violates service boundary requirement |
| Customer-facing portal | Manager dashboard only |
| Billing, plans, Stripe | Post-MVP SaaS commercialization |
| Self-serve tenant signup | Admin/seed creates tenants |
| Advanced RBAC beyond manager/viewer | Start with manager-only if needed |
| Kubernetes / cloud deploy | Docker Compose only |
| Full observability stack (Prometheus/Grafana) | Minimal health + structured logs |
| Vector DB / RAG over documents | Not required for structured store APIs |
| Auto-execution of approval-required actions | Human approval must be demonstrated |
| Sending raw PII to LLM | Non-negotiable exclusion |
| Website article generation | Content agent focuses Instagram + product copy |
| Multi-language UI i18n framework | AI output language only via env |
| Real-time websocket updates | Polling is enough |
| Agent mesh (peer-to-peer without coordinator) | Adds complexity without MVP value |
| Custom workflow builder for managers | Fixed daily report workflow only |

---

## Appendix A — Example Action Payload (Sales Restock)

```json
{
  "action_type": "sales.restock",
  "title": "Restock: Leather Tote Model A",
  "description": "Only 2 units left; sold 14 in last 7 days.",
  "priority": 1,
  "requires_approval": true,
  "payload": {
    "product_id": "uuid",
    "sku": "BAG-001",
    "current_stock": 2,
    "suggested_order_qty": 20,
    "rationale": "High velocity relative to stock"
  }
}
```

## Appendix B — Correlation and IDs

- `report_run_id` — UUID, primary trace key for one daily report generation
- `action_id` — UUID, stable across approval and execution
- `agent_output_id` — UUID, raw structured agent response before merge

## Appendix C — Document Maintenance

- Update this document when phase scope changes before implementation of that phase.
- Implementation steps should reference `step-0.1`, `step-0.2`, etc. as subsequent planning/execution docs per phase.

---

*End of Step 0.0 planning document.*
