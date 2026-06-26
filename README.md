# Agentic AI Virtual Store Management Team

A multi-tenant SaaS MVP that gives small online store managers a virtual AI operations team: daily briefings, specialized agent outputs, prioritized action recommendations, and human-in-the-loop approvals.

**Prestia** (an online bag store) is the first demo tenant, but the platform is designed to stay **generic and tenant-scoped**. Future stores onboard as new tenants without Prestia-specific code in the core platform.

---

## MVP architecture summary

The local development stack is orchestrated with Docker Compose. Main services:

| Layer | Service | Role |
|-------|---------|------|
| Data | **PostgreSQL** | Primary persistence (Django source of truth) |
| Data | **Redis** | Celery broker and result backend |
| API | **Django backend** | Tenants, stores, business logic, internal AI APIs, dashboard APIs |
| UI | **Next.js frontend** | Manager dashboard (reports, actions, approvals) |
| Async | **Celery worker** | Background jobs (report generation, action execution) |
| Async | **Celery beat** | Scheduled maintenance tasks |
| AI | **coordinator-agent** | LangGraph orchestration (FastAPI, port 8100) |
| AI | **sales-agent** | Sales and inventory analysis (FastAPI, port 8101) |
| AI | **content-agent** | Content drafts (FastAPI, port 8102) |
| AI | **support-agent** | Support message analysis (FastAPI, port 8103) |
| Edge | **nginx** | Single local entrypoint (`/` → frontend, `/api/` → backend) on port 80 |

**nginx is the preferred local entrypoint** on `http://localhost` (port 80). Direct host ports for backend, frontend, and agents remain available for debugging.

High-level flow:

```
Browser → nginx (port 80) → Next.js → Django REST API
                              ↓
                    Postgres, Redis, Celery
                              ↓
              coordinator-agent → sales / content / support agents
```

See [docs/phases/step-0.0.md](docs/phases/step-0.0.md) for the full architecture and phase plan.

---

## Prerequisites

Install on your machine:

| Tool | Purpose |
|------|---------|
| [Docker](https://docs.docker.com/get-docker/) | Build and run containers |
| [Docker Compose](https://docs.docker.com/compose/install/) | Multi-service stack (`docker compose` CLI) |
| [Git](https://git-scm.com/) | Clone the repository |

**Optional but useful:**

- **curl** — smoke-test HTTP endpoints from the examples below
- **Make** — not required by this repo today; all commands use `docker compose` directly

Ensure the Docker daemon is running before building or starting the stack (for example Docker Desktop on macOS).

---

## Environment setup

1. Clone the repository and change into the project root.

2. Create your local environment file from the committed template:

   ```bash
   cp .env.example .env
   ```

3. Edit `.env` for your machine if needed. **`.env` is local-only and must not be committed** (it is listed in `.gitignore`).

Important variable categories in `.env.example`:

| Category | Examples | Used by |
|----------|----------|---------|
| **PostgreSQL** | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL` | `postgres` service, Django (when wired) |
| **Redis / Celery** | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Backend, Celery worker/beat |
| **Django** | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | Backend |
| **JWT / service auth** | `JWT_SERVICE_SECRET`, `JWT_SERVICE_AUDIENCE`, `JWT_SERVICE_ALGORITHM` | Backend, agents (internal APIs) |
| **LLM provider** | `LLM_PROVIDER`, `LLM_MODEL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AI_OUTPUT_LANGUAGE` | Agent services |
| **Internal service URLs** | `DJANGO_INTERNAL_BASE_URL`, `COORDINATOR_AGENT_URL`, `SALES_AGENT_URL`, … | Backend, agents (Docker DNS hostnames) |
| **Frontend API base** | `NEXT_PUBLIC_API_BASE_URL` | Next.js (browser-facing; use `localhost` host ports in dev) |

Use placeholder values from `.env.example` for local development. Replace secrets before any shared or production deployment.

---

## Running the stack

From the repository root (with `.env` present):

```bash
docker compose build
docker compose up
```

Convenience variants:

```bash
# Build images and start in one step
docker compose up --build

# Start detached (background)
docker compose up -d
```

On first start, allow **10–30 seconds** for Postgres/Redis healthchecks, backend migrations, and the Next.js dev server to become ready.

---

## Stopping the stack

Stop containers and remove the compose network (keeps the Postgres data volume):

```bash
docker compose down
```

To also **delete named volumes** (including `postgres_data` — this wipes the database):

```bash
docker compose down -v
```

Use `-v` only when you intentionally want a clean database. For normal daily development, prefer `docker compose down` without `-v`.

---

## Service list and ports

Source of truth: `docker-compose.yml` in the repository root.

| Service | Responsibility | Internal port | Host port | Health / smoke check |
|---------|----------------|---------------|-----------|----------------------|
| `postgres` | Primary database | 5432 | — | Compose: `pg_isready` |
| `redis` | Celery broker / cache | 6379 | — | Compose: `redis-cli ping` |
| `backend` | Django REST API | 8000 | **8000** | Compose: `GET /health/`; host: `curl localhost:8000/health/` |
| `celery-worker` | Celery task worker | — | — | Compose: `celery inspect ping`; logs |
| `celery-beat` | Celery scheduler | — | — | No Compose healthcheck; check logs |
| `frontend` | Next.js dashboard | 3000 | **3000** | Compose: `GET /`; host: `curl localhost:3000/` |
| `coordinator-agent` | Report orchestration stub | 8100 | **8100** | Compose: `GET /health` |
| `sales-agent` | Sales analysis | 8101 | **8101** | Compose: `GET /health` |
| `content-agent` | Content drafts | 8102 | **8102** | Compose: `GET /health` |
| `support-agent` | Support analysis | 8103 | **8103** | Compose: `GET /health` |
| `nginx` | Reverse proxy (preferred entrypoint) | 80 | **80** | Compose: `GET /`; host: `curl localhost/`, `curl localhost/api/health/` |

Postgres and Redis are reachable only inside the `app-network` Docker network. **Use nginx on port 80** for the frontend and API in normal development. Application services also publish direct host ports (8000, 3000, 8100–8103) for debugging.

---

## Health checks and smoke tests

### Through nginx (preferred)

After `docker compose up`, from your host:

```bash
# Frontend placeholder via nginx
curl -s http://localhost/ | head -5
# Expected: HTML containing "Virtual Store Team Dashboard"

# Backend health via nginx
curl -s http://localhost/api/health/
# Expected: {"status": "ok"}
```

### Direct ports (debugging)

```bash
# Backend (direct)
curl -s http://localhost:8000/health/
# Expected: {"status": "ok"}

# Frontend placeholder (direct)
curl -s http://localhost:3000/ | head -5
# Expected: HTML containing "Virtual Store Team Dashboard"

# Agents
curl -s http://localhost:8100/health
curl -s http://localhost:8101/health
curl -s http://localhost:8102/health
curl -s http://localhost:8103/health
# Expected per agent: {"status":"ok","service":"<agent-name>"}
```

### Docker Compose healthchecks (Phase 0.8)

After `docker compose up`, check service health:

```bash
docker compose ps
```

Healthy application and infrastructure services show `(healthy)` in the STATUS column. Allow **60–90 seconds** on first boot for migrations and Next.js dev compile.

| Service | Compose probe |
|---------|---------------|
| `postgres` | `pg_isready` |
| `redis` | `redis-cli ping` |
| `backend` | `GET http://localhost:8000/health/` (Python `urllib`) |
| `frontend` | `GET http://localhost:3000/` (Node `fetch`) |
| `coordinator-agent` | `GET http://localhost:8100/health` |
| `sales-agent` | `GET http://localhost:8101/health` |
| `content-agent` | `GET http://localhost:8102/health` |
| `support-agent` | `GET http://localhost:8103/health` |
| `celery-worker` | `celery -A config inspect ping -d worker@celery-worker` |
| `nginx` | `wget --spider` to `http://127.0.0.1/` |

Inspect detailed health state for a container:

```bash
docker inspect --format='{{json .State.Health}}' <container_name>
```

**`celery-beat`** has no Compose healthcheck (no reliable Celery-native probe). Verify with logs instead.

### Celery

```bash
docker compose logs -f celery-worker
docker compose logs -f celery-beat
```

Look for a successful worker/beat startup without repeated crash loops. The worker is healthy when `celery inspect ping` succeeds inside the container.

---

## Common Docker commands

```bash
# Service status
docker compose ps

# Follow all logs
docker compose logs -f

# Follow logs for one service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f nginx
docker compose logs -f coordinator-agent
docker compose logs -f sales-agent
docker compose logs -f content-agent
docker compose logs -f support-agent
docker compose logs -f celery-worker
docker compose logs -f celery-beat

# Rebuild without cache
docker compose build --no-cache

# Restart one service
docker compose restart backend

# Validate merged compose config (requires .env)
docker compose config
```

---

## Troubleshooting

### Missing `.env`

**Symptom:** `docker compose config` or `docker compose up` fails with missing `env_file` or unset `${POSTGRES_*}` variables.

**Fix:** `cp .env.example .env` and retry. Never commit `.env`.

### Port already in use

**Symptom:** `Bind for 0.0.0.0:80 failed: port is already allocated` (or 8000, 3000, 8100–8103).

**Fix:** Stop the conflicting process or change the host port mapping in `docker-compose.yml` (only if you own that change in a later phase). Common culprits: another web server on port 80, local Django/Next.js dev servers, or a previous compose stack still running (`docker compose down`).

### Database not ready / backend exits during migrate

**Symptom:** Backend logs show connection errors or exit before `runserver` starts.

**Fix:** Ensure Postgres is healthy (`docker compose ps` — `postgres` should show `healthy`). Wait and restart backend: `docker compose restart backend`. Full Postgres engine wiring in Django settings may still be in progress across phases; see backend logs for migration details.

### Unhealthy Postgres or Redis

**Symptom:** `postgres` or `redis` stays `unhealthy` or restarting.

**Fix:** Check logs: `docker compose logs postgres` / `docker compose logs redis`. Verify `POSTGRES_USER`, `POSTGRES_DB`, and `POSTGRES_PASSWORD` in `.env` match what Postgres was initialized with. If credentials changed after first boot, remove the volume with care: `docker compose down -v` (destroys DB data) and start fresh.

### Frontend not reachable

**Symptom:** `curl http://localhost:3000` times out or connection refused.

**Fix:** Confirm `frontend` is `Up` in `docker compose ps`. Next.js dev compile can take several seconds on first request — check `docker compose logs -f frontend`. Try the nginx entrypoint: `curl http://localhost/`. For direct access, use port **3000**.

### Backend migrations failing

**Symptom:** Backend container exits; logs show `migrate` errors.

**Fix:** Read `docker compose logs backend`. For a corrupted local DB volume, `docker compose down -v` and `docker compose up --build` resets Postgres (data loss). Do not patch production data this way.

### Agent container import / startup errors

**Symptom:** `coordinator-agent` or `content-agent` crash with `ModuleNotFoundError` for `agents.shared` or `agents.coordinator`.

**Fix:** Agent Docker build contexts are not fully aligned yet. **Phase 0.9** will standardize contexts so shared packages import correctly. Check `docker compose logs coordinator-agent` (or the failing agent). Per-agent images with context `./agents/sales` and `./agents/support` may behave differently from `./agents` builds.

### Stale Docker volumes or images

**Symptom:** Old schema, wrong credentials, or confusing behavior after env changes.

**Fix:**

```bash
docker compose down -v    # removes postgres_data — destructive
docker compose build --no-cache
docker compose up
```

### Celery worker crash loops

**Symptom:** `celery-worker` or `celery-beat` keeps restarting.

**Fix:** Inspect logs for broker connection errors (`REDIS_URL` / `CELERY_BROKER_URL` should use `redis://redis:6379/0` inside Compose). Ensure `redis` is healthy and backend image includes Celery configuration.

### Unhealthy application services

**Symptom:** `backend`, `frontend`, or an agent shows `unhealthy` in `docker compose ps` after several minutes.

**Fix:** Check logs for the service (`docker compose logs -f <service>`). Backend may still be migrating — wait for `start_period` (60s). Agents with `ModuleNotFoundError` need **Phase 0.9** build context fixes, not healthcheck changes.

### Issues planned for later Phase 0 steps

| Need | Phase |
|------|-------|
| Agent `ModuleNotFoundError` at startup | **0.9** — Docker build context alignment |
| Hot reload via bind mounts | **0.10** — dev override |
| Final stack sign-off checklist | **0.11** — verification |

---

## Phase 0 status

| Step | Status | Summary |
|------|--------|---------|
| **0.1** | Complete | Backend Dockerfile and Django health shell |
| **0.2** | Complete | Frontend Dockerfile and Next.js shell |
| **0.3** | Complete | Four agent Dockerfiles and FastAPI placeholders |
| **0.4** | Complete | Docker Compose and `.env.example` wiring |
| **0.5** | Complete | Initial full-stack Docker verification |
| **0.6** | Complete | Root README and developer onboarding |
| **0.7** | Complete | nginx reverse proxy on port 80 |
| **0.8** | Complete | Application healthchecks in Compose |
| **0.9** | Planned | Agent Docker build context alignment |
| **0.10** | Planned | Dev bind mounts and hot reload |
| **0.11** | Planned | Final Phase 0 verification and sign-off |

**Phase 0 is not complete** until steps **0.9–0.11** are done and documented in `docs/phases/step-0.11.md`.

---

## Documentation index

| Document | Description |
|----------|-------------|
| [docs/phases/step-0.0.md](docs/phases/step-0.0.md) | MVP phase planning and architecture |
| [docs/phases/step-0.1.md](docs/phases/step-0.1.md) | Backend Docker foundation |
| [docs/phases/step-0.2.md](docs/phases/step-0.2.md) | Frontend Docker foundation |
| [docs/phases/step-0.3.md](docs/phases/step-0.3.md) | Agent Docker placeholders |
| [docs/phases/step-0.4.md](docs/phases/step-0.4.md) | Docker Compose and environment wiring |
| [docs/phases/step-0.5.md](docs/phases/step-0.5.md) | Initial full-stack verification |
| [docs/phases/step-0.6.md](docs/phases/step-0.6.md) | Root README and developer onboarding |
| [docs/phases/step-0.7.md](docs/phases/step-0.7.md) | nginx reverse proxy foundation |
| [docs/phases/step-0.8.md](docs/phases/step-0.8.md) | Application healthchecks (this step) |

---

## Quick start (copy-paste)

```bash
git clone <repository-url>
cd virtual_store_team
cp .env.example .env
docker compose up --build
```

In another terminal:

```bash
curl -s http://localhost/
curl -s http://localhost/api/health/
curl -s http://localhost:8100/health
```

When finished: `docker compose down`
