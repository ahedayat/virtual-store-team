# Step 0.3 — Agent Dockerfiles & FastAPI Placeholders

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2025-06-25  
**Status:** Implemented

---

## Scope

Step 0.3 delivers an **agent container foundation only**:

- Minimal FastAPI placeholder services for four AI microservices under `agents/`
- Independent Dockerfiles, dependency files, and `/health` endpoints per agent
- Uvicorn binding on `0.0.0.0` with assigned ports (8100–8103)
- Empty `agents/shared/` placeholder for future shared code

**Out of scope for this step:** LangGraph, LLM providers, Django API clients, JWT validation, schemas, prompt templates, inter-agent communication, real agent logic, Prestia-specific logic, docker-compose wiring, and backend/frontend changes.

---

## Files created/changed

| Path | Action |
|------|--------|
| `agents/requirements.txt` | Created — shared canonical FastAPI + Uvicorn deps |
| `agents/.dockerignore` | Created — parent-level ignore patterns |
| `agents/shared/.gitkeep` | Created — placeholder for future shared package |
| `agents/coordinator/app/main.py` | Created — FastAPI app (`coordinator-agent`) |
| `agents/coordinator/requirements.txt` | Created — per-agent deps (same as shared) |
| `agents/coordinator/Dockerfile` | Created — port 8100 |
| `agents/coordinator/.dockerignore` | Created |
| `agents/sales/app/main.py` | Created — FastAPI app (`sales-agent`) |
| `agents/sales/requirements.txt` | Created |
| `agents/sales/Dockerfile` | Created — port 8101 |
| `agents/sales/.dockerignore` | Created |
| `agents/content/app/main.py` | Created — FastAPI app (`content-agent`) |
| `agents/content/requirements.txt` | Created |
| `agents/content/Dockerfile` | Created — port 8102 |
| `agents/content/.dockerignore` | Created |
| `agents/support/app/main.py` | Created — FastAPI app (`support-agent`) |
| `agents/support/requirements.txt` | Created |
| `agents/support/Dockerfile` | Created — port 8103 |
| `agents/support/.dockerignore` | Created |
| `docs/phases/step-0.3.md` | Created — this document |

---

## Agent service layout

```
agents/
├── requirements.txt          # canonical shared dependency list
├── .dockerignore
├── shared/
│   └── .gitkeep              # future: LLM client, Django client, schemas
├── coordinator/
│   ├── app/
│   │   └── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .dockerignore
├── sales/
│   ├── app/
│   │   └── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .dockerignore
├── content/
│   ├── app/
│   │   └── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .dockerignore
└── support/
    ├── app/
    │   └── main.py
    ├── requirements.txt
    ├── Dockerfile
    └── .dockerignore
```

| Service | Directory | Port | Image tag |
|---------|-----------|------|-----------|
| `coordinator-agent` | `agents/coordinator/` | 8100 | `virtual-store-coordinator-agent:step-0.3` |
| `sales-agent` | `agents/sales/` | 8101 | `virtual-store-sales-agent:step-0.3` |
| `content-agent` | `agents/content/` | 8102 | `virtual-store-content-agent:step-0.3` |
| `support-agent` | `agents/support/` | 8103 | `virtual-store-support-agent:step-0.3` |

---

## Implementation details

### FastAPI application (repeated per agent)

Each agent exposes:

- `GET /health` — JSON `{"status": "ok", "service": "<agent-name>"}`
- `GET /` — minimal placeholder JSON identifying the service

Service names: `coordinator-agent`, `sales-agent`, `content-agent`, `support-agent`.

### Dependencies

- `fastapi==0.115.6`
- `uvicorn[standard]==0.32.1`

Each agent Dockerfile uses its local `requirements.txt` (identical content) so builds work with per-agent build context (`./agents/<name>`).

### Dockerfile pattern

- Base: `python:3.12-slim` (matches Step 0.1 backend)
- `WORKDIR /app`
- Install deps from `requirements.txt`
- Copy `app/` package
- `EXPOSE` assigned port
- `CMD` runs Uvicorn on `0.0.0.0` and the assigned port

No entrypoint script — single-process Uvicorn is sufficient for this placeholder step.

---

## Agent Docker build/run notes

### Build

```bash
docker build -t virtual-store-coordinator-agent:step-0.3 ./agents/coordinator
docker build -t virtual-store-sales-agent:step-0.3 ./agents/sales
docker build -t virtual-store-content-agent:step-0.3 ./agents/content
docker build -t virtual-store-support-agent:step-0.3 ./agents/support
```

### Run (one container per terminal)

```bash
docker run --rm -p 8100:8100 virtual-store-coordinator-agent:step-0.3
docker run --rm -p 8101:8101 virtual-store-sales-agent:step-0.3
docker run --rm -p 8102:8102 virtual-store-content-agent:step-0.3
docker run --rm -p 8103:8103 virtual-store-support-agent:step-0.3
```

### Run all four in background (smoke test)

```bash
docker run --rm -d --name vs-coordinator -p 8100:8100 virtual-store-coordinator-agent:step-0.3
docker run --rm -d --name vs-sales -p 8101:8101 virtual-store-sales-agent:step-0.3
docker run --rm -d --name vs-content -p 8102:8102 virtual-store-content-agent:step-0.3
docker run --rm -d --name vs-support -p 8103:8103 virtual-store-support-agent:step-0.3
```

Stop after probing:

```bash
docker stop vs-coordinator vs-sales vs-content vs-support
```

---

## Health check endpoints

| Agent | URL | Expected response |
|-------|-----|-------------------|
| Coordinator | `GET http://localhost:8100/health` | `{"status":"ok","service":"coordinator-agent"}` |
| Sales | `GET http://localhost:8101/health` | `{"status":"ok","service":"sales-agent"}` |
| Content | `GET http://localhost:8102/health` | `{"status":"ok","service":"content-agent"}` |
| Support | `GET http://localhost:8103/health` | `{"status":"ok","service":"support-agent"}` |

---

## Verification commands

```bash
# 1. Python syntax (host)
python3 -m py_compile agents/coordinator/app/main.py \
  agents/sales/app/main.py \
  agents/content/app/main.py \
  agents/support/app/main.py

# 2. Build images
docker build -t virtual-store-coordinator-agent:step-0.3 ./agents/coordinator
docker build -t virtual-store-sales-agent:step-0.3 ./agents/sales
docker build -t virtual-store-content-agent:step-0.3 ./agents/content
docker build -t virtual-store-support-agent:step-0.3 ./agents/support

# 3. Start all agents in background
docker run --rm -d --name vs-coordinator -p 8100:8100 virtual-store-coordinator-agent:step-0.3
docker run --rm -d --name vs-sales -p 8101:8101 virtual-store-sales-agent:step-0.3
docker run --rm -d --name vs-content -p 8102:8102 virtual-store-content-agent:step-0.3
docker run --rm -d --name vs-support -p 8103:8103 virtual-store-support-agent:step-0.3

# 4. Health probes
curl -s http://localhost:8100/health
curl -s http://localhost:8101/health
curl -s http://localhost:8102/health
curl -s http://localhost:8103/health

# 5. Cleanup
docker stop vs-coordinator vs-sales vs-content vs-support
```

---

## Result of verification

| Check | Result |
|-------|--------|
| `python3 -m py_compile` (all four `main.py`) | **Passed** — no syntax errors |
| `docker build` (all four agents) | **Not run** — Docker daemon was not available (`Cannot connect to the Docker daemon`) |
| Container `/health` probes | **Pending** — requires Docker daemon running |

**Action for developer:** Start Docker Desktop (or the local Docker daemon), then run the build and health-check commands above. All should pass on a machine with Docker running.

---

## Decisions made

1. **Per-agent build context** — Each Dockerfile builds from `./agents/<name>` per the step spec; identical `requirements.txt` is duplicated in each agent directory so `COPY requirements.txt .` works without a monorepo build context.
2. **Canonical `agents/requirements.txt`** — Documents the shared dependency set; kept in sync with per-agent copies.
3. **`app/main.py` package layout** — Matches Uvicorn module path `app.main:app` and leaves room for routers, settings, and tests in later steps.
4. **Python 3.12-slim** — Consistent with Step 0.1 backend image.
5. **No entrypoint script** — Unlike backend/frontend, agents only need a single Uvicorn process; a shell entrypoint adds no value at this step.
6. **Empty `agents/shared/`** — `.gitkeep` only; shared LLM/Django client code deferred to a later phase.
7. **No docker-compose changes** — No compose file exists yet; Step 0.4 owns full stack wiring.

---

## What was intentionally not implemented

- LangGraph workflows or orchestration logic
- LLM provider abstraction or external AI dependencies
- Django API clients, JWT validation, or service-to-service auth
- Pydantic schemas, prompt templates, or `/run` workflow endpoints
- Inter-agent HTTP communication
- Celery, Redis, or async task integration from agents
- `docker-compose.yml` or env_file wiring
- Backend or frontend changes
- Prestia-specific logic, seeds, or configuration
- Production hardening (replicas, healthcheck directives in compose, non-root user, etc.)

---

## Dependency on Steps 0.1 and 0.2

Step 0.3 is **independent** of running backend and frontend containers. It mirrors Step 0.1 conventions (`python:3.12-slim`, minimal deps, health JSON endpoint) while establishing the four-agent service layout planned in Step 0.0. Steps 0.1 and 0.2 must exist for the eventual Step 0.4 compose stack, but agent images build and run in isolation.

---

## Next step: Step 0.4 wire compose env_file

Create `docker-compose.yml` (and related env files) to wire backend, frontend, Postgres, Redis, Celery, nginx, and all four agent services with consistent networking, ports, and environment configuration.

---

*End of Step 0.3 implementation document.*
