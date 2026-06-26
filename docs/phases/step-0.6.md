# Step 0.6 — Root README & Developer Onboarding

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Complete

---

## Goal

Enable a new developer to clone the repository, configure environment variables, start the Docker Compose stack, inspect services, run basic smoke tests, and troubleshoot common startup issues **using only the root README** — without reading implementation docs first.

This step is **documentation only**. It does not close Phase 0; steps 0.7–0.11 remain.

---

## Scope

- Create or update root `README.md` with onboarding sections derived from the actual `docker-compose.yml` and `.env.example`.
- Create this step document (`docs/phases/step-0.6.md`).
- Ensure the Phase 0.6 Cursor rule exists at `.cursor/rules/phase-0-6-root-readme.mdc`.

**Out of scope:** nginx, application healthchecks, agent Docker context fixes, bind mounts, backend/frontend/agent code changes, or any infrastructure behavior changes.

---

## Files created or updated

| Path | Action |
|------|--------|
| `README.md` | Created — root developer onboarding guide |
| `docs/phases/step-0.6.md` | Created — this document |
| `.cursor/rules/phase-0-6-root-readme.mdc` | Created — Phase 0.6 documentation-only Cursor rule |

No source code, Dockerfiles, or `docker-compose.yml` changes were made in this step.

---

## README sections added

The root `README.md` includes:

1. **Project title and short description** — multi-tenant SaaS MVP; Prestia as first demo tenant; generic tenant-scoped design.
2. **MVP architecture summary** — Django, Next.js, Postgres, Redis, Celery worker/beat, four FastAPI agents, planned nginx (not yet implemented).
3. **Prerequisites** — Docker, Docker Compose, Git; optional curl.
4. **Environment setup** — `cp .env.example .env`, local-only `.env`, variable categories (Postgres, Redis, Django, JWT, LLM, internal URLs, frontend API base).
5. **Running the stack** — `docker compose build`, `docker compose up`, `--build`, `-d`.
6. **Stopping the stack** — `docker compose down`, cautious use of `docker compose down -v`.
7. **Service list and ports** — table from current `docker-compose.yml` (10 services + planned nginx).
8. **Health checks and smoke tests** — curl examples for backend `/health/`, agent `/health`, frontend `/`; note on Postgres/Redis compose healthchecks; Phase 0.8 for app healthchecks.
9. **Common Docker commands** — `ps`, `logs`, `build --no-cache`, `restart`, `config`.
10. **Troubleshooting** — missing `.env`, port conflicts, DB not ready, unhealthy Postgres/Redis, frontend unreachable, migration failures, agent import errors, stale volumes, Celery crash loops; pointers to Phase 0.7–0.11 for unresolved items.
11. **Phase 0 status** — 0.1–0.5 complete; 0.6 this step; 0.7–0.11 planned; Phase 0 not complete.
12. **Documentation index** — links to `docs/phases/step-0.0.md` through `step-0.6.md`.
13. **Quick start** — copy-paste clone → env → up → curl block.

---

## How the README helps a new developer

| Task | Where in README |
|------|-----------------|
| Understand what the project is | Title and architecture summary |
| Install required tools | Prerequisites |
| Configure secrets and service URLs | Environment setup + `.env.example` categories |
| Start the full stack | Running the stack / Quick start |
| Know which URL/port to open | Service list and ports table |
| Verify services are alive | Health checks and smoke tests |
| Debug a failed startup | Troubleshooting |
| Know what is not done yet | Phase 0 status + troubleshooting “planned steps” table |
| Dive deeper | Documentation index |

---

## Validation checklist

| # | Check | Result |
|---|-------|--------|
| 1 | Root `README.md` exists | **Passed** |
| 2 | README explains `.env` setup (`cp .env.example .env`, local-only) | **Passed** |
| 3 | README explains Docker Compose startup | **Passed** |
| 4 | README lists current services and ports from actual `docker-compose.yml` | **Passed** |
| 5 | README documents current health/smoke endpoints | **Passed** |
| 6 | README marks nginx, full healthchecks, agent Docker contexts, bind mounts, final verification as Phase 0.7–0.11 | **Passed** |
| 7 | `docs/phases/step-0.6.md` exists | **Passed** |
| 8 | No source code or infrastructure behavior was changed | **Passed** |
| 9 | `.cursor/rules/phase-0-6-root-readme.mdc` exists | **Passed** |

---

## What was intentionally not implemented in this step

- nginx service and `nginx/` configuration (Phase 0.7)
- Docker Compose `healthcheck` blocks for backend, frontend, agents, Celery (Phase 0.8)
- Standardized agent Docker build contexts for `agents.shared.*` imports (Phase 0.9)
- `docker-compose.override.yml` bind mounts and hot reload (Phase 0.10)
- Final Phase 0 verification run and `docs/phases/step-0.11.md` (Phase 0.11)
- Any backend, frontend, agent, or compose behavior changes

---

## Remaining Phase 0 steps after 0.6

| Step | Focus |
|------|-------|
| **0.7** | nginx reverse proxy — port 80, `/` → frontend, `/api/` → backend |
| **0.8** | Application healthchecks and appropriate `depends_on` conditions |
| **0.9** | Agent Docker build context alignment (`agents.shared`, per-agent packages) |
| **0.10** | Development bind mounts and hot reload (override compose) |
| **0.11** | Final Phase 0 verification, sign-off, `docs/phases/step-0.11.md` |

Phase 0 exit gate (from `step-0.0.md`): clone → `.env` → full stack via README → nginx on `localhost` → healthy services in `docker compose ps` → agent imports work → dev bind mounts → documented sign-off.

---

## Suggested manual verification commands

Run from the repository root after this documentation step (requires Docker daemon):

```bash
# Confirm only documentation files changed (before commit)
git status
git diff --stat

# Onboarding path from README
cp .env.example .env   # skip if .env already exists
docker compose config
docker compose up --build -d
docker compose ps

curl -s http://localhost:8000/health/
curl -s http://localhost:3000/ | head -5
curl -s http://localhost:8100/health
curl -s http://localhost:8101/health
curl -s http://localhost:8102/health
curl -s http://localhost:8103/health

docker compose logs --tail=50 celery-worker
docker compose down
```

Expected: compose config validates; HTTP probes return 200 where documented; no changes to application behavior from Step 0.6 itself.

---

## Known limitations documented in README

- nginx is not in `docker-compose.yml`; use direct host ports until Phase 0.7.
- Only Postgres and Redis have Compose healthchecks; `docker compose ps` may show app services as `Up` without `(healthy)` until Phase 0.8.
- Coordinator and content agents use `./agents` build context; sales and support use per-agent contexts — import issues may appear until Phase 0.9.
- No dev bind mounts; image rebuild required for code changes until Phase 0.10.

---

## Final status for this step

**Step 0.6 — Root README & Developer Onboarding: COMPLETE**

Phase 0 overall remains **incomplete** pending steps 0.7–0.11.

---

*End of Step 0.6 implementation document.*
