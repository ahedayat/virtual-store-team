# Step 0.9 — Agent Docker Build Context Alignment

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Complete

---

## Goal

Standardize Docker build contexts for all four FastAPI agent services so each container can import `agents.shared.*` and its own `agents.<agent>.*` package without `ModuleNotFoundError` at startup.

Phase 0.9 keeps agent behavior as Phase 0 placeholders (health endpoints and existing stub/`/run` code paths only). It does not add dev bind mounts, hot reload, or final Phase 0 sign-off.

---

## Scope

- Align `docker-compose.yml` build `context` and `dockerfile` paths for all agent services.
- Standardize all four agent Dockerfiles to the same layout: repo-root context, `PYTHONPATH=/app`, copy `agents/shared/` + per-agent tree.
- Add missing package markers (`__init__.py`) where required for `agents.support.*` imports.
- Preserve Phase 0.8 healthchecks and existing service ports (8100–8103).
- Update README troubleshooting and Phase 0 status for Step 0.9.
- Create Phase 0.9 Cursor rule.

**Out of scope:** new agent business logic, real LLM behavior, nginx changes, bind mounts / hot reload (Phase 0.10), final verification sign-off (Phase 0.11).

---

## Files created or updated

| Path | Action |
|------|--------|
| `docker-compose.yml` | Updated — all four agents use repository root build context |
| `agents/coordinator/Dockerfile` | Updated — root-relative `COPY` paths |
| `agents/sales/Dockerfile` | Updated — aligned with shared-package import layout |
| `agents/content/Dockerfile` | Updated — root-relative `COPY` paths |
| `agents/support/Dockerfile` | Updated — aligned with shared-package import layout |
| `agents/support/__init__.py` | Created — package marker |
| `agents/support/app/__init__.py` | Created — package marker for `agents.support.app` |
| `.cursor/rules/phase-0-9-agent-docker-context.mdc` | Created/updated — Phase 0.9 scope and constraints |
| `README.md` | Updated — Phase 0.9 build context note and status |
| `docs/phases/step-0.9.md` | Created — this document |

---

## Original issue or risk

Before Step 0.9, agent services used **inconsistent** Docker build contexts:

| Service | Previous context | Problem |
|---------|------------------|---------|
| `coordinator-agent` | `./agents` | Worked for `agents.coordinator` + `agents.shared`, but differed from other agents |
| `sales-agent` | `./agents/sales` | Copied only `app/`; `uvicorn` used `app.main:app` while application code imports `agents.sales.*` and `agents.shared.*` → **import failure** |
| `content-agent` | `./agents` | Similar to coordinator; inconsistent with sales/support |
| `support-agent` | `./agents/support` | Copied only `app/`; used `app.main:app`; missing `agents.support` package layout |

Risk: `ModuleNotFoundError` at container startup, unhealthy agents in `docker compose ps`, and divergent Dockerfile maintenance.

---

## Final build context strategy

**Single strategy for all agent services:**

```yaml
build:
  context: .
  dockerfile: agents/<agent>/Dockerfile
```

- **Build context:** repository root (`.`)
- **Image layout:** `/app/agents/` with `PYTHONPATH=/app`
- **Copied into each image:** `agents/__init__.py`, `agents/shared/`, and `agents/<agent>/` only
- **Not copied:** other agent packages, backend, frontend, or nginx (smaller images; each service remains isolated)

This matches how application code already imports modules (`agents.coordinator.app.main`, `agents.sales.app.main`, etc.).

---

## Dockerfile strategy by agent

All four Dockerfiles follow the same pattern:

1. Base image: `python:3.12-slim`
2. `ENV PYTHONPATH=/app`, `WORKDIR /app`
3. Install dependencies from `agents/<agent>/requirements.txt`
4. `COPY agents/__init__.py`, `agents/shared/`, `agents/<agent>/`
5. `uvicorn agents.<agent>.app.main:app` on the assigned port

| Agent | Dockerfile | Uvicorn module | Port |
|-------|------------|----------------|------|
| coordinator | `agents/coordinator/Dockerfile` | `agents.coordinator.app.main:app` | 8100 |
| sales | `agents/sales/Dockerfile` | `agents.sales.app.main:app` | 8101 |
| content | `agents/content/Dockerfile` | `agents.content.app.main:app` | 8102 |
| support | `agents/support/Dockerfile` | `agents.support.app.main:app` | 8103 |

**Sales/support change:** replaced legacy `app.main:app` entrypoint and `./agents/<agent>`-only context with the shared layout above.

---

## Import paths verified

### Required per container

| Container | Must import | Notes |
|-----------|-------------|-------|
| `coordinator-agent` | `agents.shared`, `agents.coordinator` | Uses shared schemas in stub endpoint |
| `sales-agent` | `agents.shared`, `agents.sales` | `/run` pipeline imports shared schemas + sales modules |
| `content-agent` | `agents.shared`, `agents.content` | `/run` pipeline imports shared schemas + content modules |
| `support-agent` | `agents.shared`, `agents.support` | Placeholder app; shared package copied for consistency |

### Cross-agent packages

Other agent packages (`agents.coordinator`, `agents.sales`, etc.) are **not** copied into every image. Each container only needs **shared + its own** package for current code. Full monorepo `agents.*` tree import is verified on the **host** for development; per-container copies are intentionally minimal.

### Checks performed

**Host (repo root, `PYTHONPATH=.`):**

```bash
python3 -c "import agents.shared"
python3 -c "import agents.coordinator"
python3 -c "import agents.sales"
python3 -c "import agents.content"
python3 -c "import agents.support"
```

Result: **all imports succeeded**.

**Inside containers (manual — run when Docker is available):**

```bash
for svc in coordinator-agent sales-agent content-agent support-agent; do
  docker compose exec "$svc" python -c "import agents.shared; import agents.${svc%-agent}; print('ok', '$svc')"
done
```

Adjust the inline import per service (`agents.coordinator`, `agents.sales`, `agents.content`, `agents.support`).

---

## Validation commands

```bash
docker compose config
docker compose build coordinator-agent sales-agent content-agent support-agent
docker compose up -d coordinator-agent sales-agent content-agent support-agent
docker compose ps
docker compose logs --tail=100 coordinator-agent
docker compose logs --tail=100 sales-agent
docker compose logs --tail=100 content-agent
docker compose logs --tail=100 support-agent
```

**Health checks (host ports exposed):**

```bash
curl -s http://localhost:8100/health
curl -s http://localhost:8101/health
curl -s http://localhost:8102/health
curl -s http://localhost:8103/health
```

Expected per agent: `{"status":"ok","service":"<agent-name>"}`.

---

## Validation results (this implementation run)

| Command | Result |
|---------|--------|
| `docker compose config` | **Passed** — all four agents show `context: .` and correct `dockerfile` paths |
| `docker compose build …` | **Not run** — Docker daemon unavailable in implementation environment (`Cannot connect to the Docker daemon`) |
| `docker compose up` / health curls | **Not run** — requires local Docker; use commands above |

Re-run build/up/health checks locally after `docker compose build` when Docker Desktop (or the daemon) is running.

---

## Expected results

After rebuild and start:

- All four agent containers start without `ModuleNotFoundError`.
- `GET /health` returns HTTP 200 on ports 8100–8103.
- `docker compose ps` shows agents `healthy` after `start_period` (30s), assuming no unrelated failures.
- Logs show Uvicorn listening on `0.0.0.0:<port>` with no import tracebacks.

---

## Known limitations

- **No dev bind mounts:** source changes on the host do not hot-reload inside containers until Phase 0.10.
- **Minimal copy set:** each image contains only `agents/shared/` and one agent package; importing another agent's package inside a container will fail by design.
- **Large build context upload:** root context sends the full repo to the Docker daemon unless a root `.dockerignore` is added in a later step; COPY instructions still limit what enters the image.
- **Root-context builds** include backend/frontend files in the build context tarball (not in the final image); acceptable for Phase 0.9; optimization deferred.

---

## What was intentionally not implemented

- Development bind mounts and hot reload (**Phase 0.10**)
- Final Phase 0 verification checklist and sign-off (**Phase 0.11**)
- nginx routing changes
- New healthcheck behavior beyond preserving Phase 0.8 checks
- New agent business logic or real LLM integration
- Prestia-specific configuration

Phase 0.9 does **not** perform final Phase 0 sign-off. Phase 0.10 is still required for dev bind mounts and hot reload. Phase 0.11 is still required for final verification and sign-off.

---

## Remaining Phase 0 steps after 0.9

| Step | Name | Status after 0.9 |
|------|------|------------------|
| **0.10** | Dev bind mounts & hot reload | Required |
| **0.11** | Final Phase 0 verification & sign-off | Required |

---

## Final status for this step

**Step 0.9 is complete** for build-context alignment, standardized Dockerfiles, package markers, documentation, and `docker compose config` validation.

**Phase 0 is not complete** until Steps 0.10 and 0.11 are implemented and `docs/phases/step-0.11.md` records final verification.
