# Step 0.4 — Docker Compose & Environment Wiring

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2025-06-25  
**Status:** Implemented

---

## Scope

Step 0.4 delivers **Docker Compose and environment wiring only**:

- Root-level `docker-compose.yml` wiring backend, frontend, Postgres, Redis, and four placeholder agent services
- Root-level `.env.example` with shared placeholder configuration
- Single shared network (`app-network`) and named Postgres volume (`postgres_data`)
- All application services use `env_file` pointing to the root `.env` file

**Out of scope for this step:** nginx, Celery workers, Django Postgres settings, business logic, LLM behavior, LangGraph, auth, tenant logic, and Prestia-specific configuration.

---

## Files created/changed

| Path | Action |
|------|--------|
| `docker-compose.yml` | Created — full stack compose wiring |
| `.env.example` | Created — committed placeholder environment template |
| `.gitignore` | Created — ignores root `.env` (secrets stay local) |
| `docs/phases/step-0.4.md` | Created — this document |

**Not created (intentional):**

| Path | Reason |
|------|--------|
| `.env` | Local-only; copied from `.env.example` for verification; never committed |

---

## Docker Compose services added or updated

| Service | Image / build | Host port | `env_file` | Depends on |
|---------|---------------|-----------|------------|------------|
| `postgres` | `postgres:16-alpine` | — (internal) | `.env` | — |
| `redis` | `redis:7-alpine` | — (internal) | — | — |
| `backend` | `./backend` | `8000` | `.env` | `postgres` (healthy), `redis` (healthy) |
| `frontend` | `./frontend` (target: `development`) | `3000` | `.env` | `backend` |
| `coordinator-agent` | `./agents/coordinator` | `8100` | `.env` | — |
| `sales-agent` | `./agents/sales` | `8101` | `.env` | — |
| `content-agent` | `./agents/content` | `8102` | `.env` | — |
| `support-agent` | `./agents/support` | `8103` | `.env` | — |

**Intentionally omitted:**

| Service | Reason |
|---------|--------|
| `celery-worker` | Celery is not installed or configured in the backend yet (Step 0.1 uses SQLite only; no `celery` in `requirements.txt`). Adding worker services now would crash-loop. Deferred to the Celery phase (Phase 5). |
| `celery-beat` | Same as `celery-worker` — deferred until Celery is implemented. |
| `nginx` | Not in scope for Step 0.4; routing can be added in a later step. |

---

## Environment variable strategy

1. **Single source of truth:** Root `.env` (local, gitignored) is created by copying `.env.example`.
2. **Committed template:** `.env.example` holds placeholder values only — no real secrets.
3. **Application services:** `backend`, `frontend`, and all four agents declare `env_file: [.env]` so they receive the full shared variable set.
4. **Postgres service:** Also uses `env_file: [.env]` plus explicit `POSTGRES_*` mapping for image initialization.
5. **Compose overrides:** `backend` sets `DATABASE_HOST=postgres` and `DATABASE_PORT=5432` in the compose `environment` block so the Step 0.1 entrypoint waits for Postgres before migrations (Postgres engine wiring in Django settings is a later step).
6. **Variable substitution:** Compose reads `.env` for `${POSTGRES_DB}`, `${POSTGRES_USER}`, and `${POSTGRES_PASSWORD}` in the Postgres healthcheck and environment blocks.

---

## `.env.example` contents overview

| Category | Variables |
|----------|-----------|
| PostgreSQL | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL` |
| Redis | `REDIS_URL` |
| Django | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` |
| JWT (future) | `JWT_SERVICE_SECRET`, `JWT_SERVICE_AUDIENCE` |
| AI / LLM (placeholders) | `AI_OUTPUT_LANGUAGE`, `LLM_PROVIDER`, `LLM_MODEL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |
| Internal service URLs | `DJANGO_INTERNAL_BASE_URL`, `COORDINATOR_AGENT_URL`, `SALES_AGENT_URL`, `CONTENT_AGENT_URL`, `SUPPORT_AGENT_URL` |
| Frontend | `NEXT_PUBLIC_API_BASE_URL` |

All secret values use placeholders such as `change-me-in-production` or `sk-placeholder`.

---

## Network and volume decisions

| Resource | Name | Purpose |
|----------|------|---------|
| Network | `app-network` | Single bridge network for all services; Docker DNS resolves service names (`backend`, `postgres`, `coordinator-agent`, etc.) |
| Volume | `postgres_data` | Named volume for Postgres data persistence across `docker compose down` (volume is not removed unless explicitly pruned) |

Postgres and Redis are **not** exposed to the host — only application dev ports (`8000`, `3000`, `8100`–`8103`) are published.

---

## Service URL conventions

| Variable | Value | Used by |
|----------|-------|---------|
| `DJANGO_INTERNAL_BASE_URL` | `http://backend:8000` | Agents (future Django API client) |
| `COORDINATOR_AGENT_URL` | `http://coordinator-agent:8100` | Backend / other agents (future) |
| `SALES_AGENT_URL` | `http://sales-agent:8101` | Coordinator (future) |
| `CONTENT_AGENT_URL` | `http://content-agent:8102` | Coordinator (future) |
| `SUPPORT_AGENT_URL` | `http://support-agent:8103` | Coordinator (future) |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Browser-facing frontend (host port, not Docker DNS) |

Internal URLs use Docker Compose service names. `NEXT_PUBLIC_*` uses `localhost` because the browser runs outside the container network.

---

## Verification commands

```bash
# 1. Validate compose file (requires .env for env_file references)
cp .env.example .env
docker compose config

# 2. Build all images
docker compose build

# 3. Start stack in background
docker compose up -d

# 4. Health / HTTP probes
curl -s http://localhost:8000/health/
curl -s http://localhost:3000/ | head -20
curl -s http://localhost:8100/health
curl -s http://localhost:8101/health
curl -s http://localhost:8102/health
curl -s http://localhost:8103/health

# 5. Container status
docker compose ps

# 6. Tear down (keeps postgres_data volume)
docker compose down
```

---

## Result of verification

| Check | Result |
|-------|--------|
| `cp .env.example .env` | **Passed** — local `.env` created for verification |
| `.env` gitignored | **Passed** — `git check-ignore -v .env` → `.gitignore:1:.env` |
| `docker compose config` | **Passed** — valid merged config with all services, network, and volume |
| `docker compose build` | **Not run** — Docker daemon was not available (`Cannot connect to the Docker daemon`) |
| `docker compose up` | **Not run** — requires Docker daemon |
| HTTP health probes | **Pending** — requires Docker daemon running |
| `docker compose ps` | **Pending** — requires Docker daemon running |
| `docker compose down` | **Pending** — requires Docker daemon running |

**Action for developer:** Start Docker Desktop (or the local Docker daemon), then run the verification commands above. All should pass on a machine with Docker running.

---

## Decisions made

1. **Frontend `development` build target** — Uses hot-reload dev server for local compose; production multi-stage image remains available via `docker build` without compose.
2. **Postgres health gate for backend** — `depends_on` with `service_healthy` plus `DATABASE_HOST=postgres` ensures the entrypoint waits before migrate; Django still uses SQLite in settings until a later Postgres wiring step.
3. **Redis without `env_file`** — Redis needs no credentials in this step; `REDIS_URL` is present in `.env.example` for future backend/Celery use.
4. **No Celery services** — Backend has no Celery package or app config; adding `celery-worker` / `celery-beat` would crash-loop. Documented as deferred.
5. **No nginx** — Per step scope; services expose dev ports directly.
6. **Root `.gitignore`** — Repository had only `frontend/.gitignore`; added minimal root `.gitignore` with `.env` only.
7. **Agents independent of backend `depends_on`** — Placeholder agents have no Django dependency yet; they start in parallel.

---

## What was intentionally not implemented

- `celery-worker` and `celery-beat` compose services
- nginx reverse proxy
- Django `DATABASE_URL` / Postgres engine configuration
- Redis usage in application code
- CORS middleware or JWT validation
- LLM calls, LangGraph, or real agent workflows
- Prestia-specific logic or seeds
- Compose healthchecks on application services (Postgres and Redis only)
- Dev bind-mounts for hot reload (can be added in a later polish step)

---

## Dependency on Steps 0.1, 0.2, and 0.3

| Step | Contribution to Step 0.4 |
|------|--------------------------|
| **0.1** | `backend/Dockerfile`, `entrypoint.sh` (migrate + `DATABASE_HOST` wait), `/health/` endpoint on port `8000` |
| **0.2** | `frontend/Dockerfile` with `development` and `production` targets, Next.js shell on port `3000` |
| **0.3** | Four agent Dockerfiles with FastAPI `/health` on ports `8100`–`8103` |

Step 0.4 does not modify backend, frontend, or agent source code — only root-level compose and env files.

---

## Next step: Step 0.5 verify all containers healthy with `docker compose ps`

With Docker running:

1. `cp .env.example .env` (if not already done)
2. `docker compose up -d --build`
3. Confirm all services are `healthy` or `running` via `docker compose ps`
4. Probe `/health` endpoints and frontend home page

---

*End of Step 0.4 implementation document.*
