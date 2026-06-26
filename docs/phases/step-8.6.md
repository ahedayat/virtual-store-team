# Step 8.6 — Content Action Mapping and Approval Persistence

**Project:** Agentic AI Virtual Store Management Team (SaaS)  
**Date:** 2026-06-26  
**Status:** Implemented

---

## Goal

Map validated `ContentDraft` items from the Content Agent to Django-compatible approval-required action payloads and persist them through the existing Django internal action workflow (`POST /internal/ai/actions/` → `ActionService.create_from_agent_payload()`).

This step connects Step 8.3 schema validation and Step 8.4/8.5 pipeline output to Phase 4 action persistence without introducing publishing, auto-approval, or external side effects.

---

## Scope and non-goals

### In scope

- Map `ContentDraft` / `ContentSuggestions` to Django internal action request bodies
- Support only `content.instagram_draft` and `content.product_description`
- Force `requires_approval=true` on all mapped content actions
- Persist via shared `DjangoClient.create_action()` → `POST /internal/ai/actions/`
- Preserve `report_run_id` scoping when provided (draft mapper arg or `ContentSuggestions.metadata`)
- Deterministic unit tests with fixtures and mocked HTTP (no real LLM or Django container)

### Out of scope (deferred)

| Step | Deferred work |
|------|----------------|
| 8.7 | `docs/examples/content_output.json` and final acceptance proof |
| — | Coordinator/LangGraph orchestration calling persistence |
| — | `POST /run` side effects (persistence remains an explicit separate call) |
| — | Real Instagram publishing, sending, or external integrations |
| — | Auto-approval or auto-execution of content actions |
| — | Frontend dashboard changes |

---

## Files changed

| File | Change |
|------|--------|
| `agents/content/action_mapping.py` | Created — mapping and persistence helpers |
| `agents/shared/django_client/client.py` | Updated — `create_action()` convenience method |
| `agents/content/tests/test_action_mapping.py` | Created — Step 8.6 mapping/persistence tests |
| `backend/operations/tests/test_action_service.py` | Updated — content action `pending_approval` tests |
| `.cursor/rules/phase-8-6-content-action-mapping.mdc` | Present — scope rule for this step |
| `docs/phases/step-8.6.md` | Created — this document |

---

## Mapping design

### Entry points

| Function | Purpose |
|----------|---------|
| `map_content_draft_to_action_payload(draft, *, report_run_id=None)` | Map one validated draft to a Django internal action request body |
| `map_content_suggestions_to_actions(suggestions, *, report_run_id=None)` | Map all drafts in a `ContentSuggestions` object |
| `persist_content_actions(suggestions, *, django_client, report_run_id=None, agent_output_id=None)` | Map and POST each action to Django |

`ContentActionMappingError` is raised for unsupported action types or missing required mapping fields.

### Resolution order for `report_run_id`

1. Explicit `report_run_id` argument to mapper/persist helpers
2. Otherwise `ContentSuggestions.metadata.report_run_id`

Tenant and store scope are **not** embedded in mapped payloads. They come from the service JWT on `DjangoClient` when persisting (Phase 4.3 convention).

### Priority

- Use `ContentDraft.priority` when set (1–5 per schema)
- Default to `3` (medium) when missing

---

## Supported action types

| `action_type` | When used | Approval |
|---------------|-----------|----------|
| `content.instagram_draft` | Instagram caption/post drafts | Required (`pending_approval`) |
| `content.product_description` | Product page copy drafts | Required (`pending_approval`) |

Unsupported types (for example `content.publish_instagram`) are rejected by the mapper with `ContentActionMappingError`.

---

## Action payload shape

### Internal API request body (`POST /internal/ai/actions/`)

```json
{
  "action_type": "content.instagram_draft",
  "title": "Instagram caption: Everyday Leather Tote",
  "description": "Instagram caption draft for manager review.",
  "priority": 3,
  "requires_approval": true,
  "payload": {
    "draft_text": "Everyday leather tote — clean and versatile.",
    "rationale": "Seasonal campaign angle fits the featured product.",
    "product_id": "00000000-0000-4000-8000-000000000001",
    "campaign_angle": "New arrivals",
    "output_language": "en"
  },
  "report_run_id": "optional-uuid",
  "agent_output_id": "optional-uuid"
}
```

### Inner `payload` rules

- `draft_text` and `rationale` are always copied from the draft
- `product_id` is included when present; required for `content.product_description`
- `campaign_angle` and `output_language` are included when present
- Extra keys from `ContentDraft.payload` are merged without overwriting canonical fields

---

## Approval-required behavior

- Mapper always sets `requires_approval: true`
- Django `ActionService` default policy for both content action types is approval-required
- Created actions receive `status: pending_approval`
- No content action is queued for auto-execution in this step
- `persist_content_actions()` only creates suggested actions; it does not approve, reject, execute, publish, or send

---

## Persistence behavior

```
ContentSuggestions
  → map_content_suggestions_to_actions()
  → DjangoClient.create_action() per draft
  → POST /internal/ai/actions/
  → ActionService.create_from_agent_payload()
  → Action(status=pending_approval)
```

### Django client usage

```python
from agents.content.action_mapping import persist_content_actions
from agents.shared.django_client import DjangoClient

client = DjangoClient(
    service_token="<service-jwt>",
    request_id="correlation-id",
)

persisted = persist_content_actions(
    suggestions,
    django_client=client,
    report_run_id="run-uuid",
    agent_output_id="optional-output-uuid",
)
```

`DjangoClient` forwards:

- `Authorization: Bearer <service_token>`
- `X-Request-ID` when `request_id` is set

POST retries remain disabled by default (Step 6.2 policy).

### Integration with `/run`

`POST /run` (Step 8.5) is unchanged and returns schema-validated `ContentSuggestions` only. Callers that want persistence must invoke `persist_content_actions()` explicitly after analysis — for example the future coordinator workflow.

---

## Tenant/store/report scoping

| Scope | Source |
|-------|--------|
| `tenant_id` / `store_id` | Service JWT on `DjangoClient` (trusted; not from action body) |
| `report_run_id` | Mapper argument or suggestions metadata; validated by Django against JWT scope |
| `agent_output_id` | Optional persist argument; validated by Django against JWT scope |

Mapped bodies must not include `tenant_id` or `store_id` (ignored by Django if present).

---

## Tests and validation commands

### Agent tests

```bash
PYTHONPATH=. python -m unittest agents.content.tests.test_action_mapping -v
```

### Content Agent regression suite

```bash
PYTHONPATH=. python -m unittest \
  agents.content.tests.test_prompts \
  agents.content.tests.test_draft_limit \
  agents.content.tests.test_schema_validation \
  agents.content.tests.test_runtime_pipeline \
  agents.content.tests.test_run_endpoint \
  agents.content.tests.test_action_mapping \
  -v
```

### Django client regression

```bash
PYTHONPATH=. python -m unittest agents.shared.tests.test_django_client -v
```

### Backend action service tests

```bash
cd backend && python manage.py test operations.tests.test_action_service -v 2
```

### Coverage highlights

- Instagram draft → `content.instagram_draft`
- Product description → `content.product_description`
- `requires_approval=true` on mapped bodies
- Unsupported action type rejection
- `product_id` and `draft_text` preserved in inner payload
- Priority default (3) and explicit preservation
- `report_run_id` propagation
- Persistence posts to `/internal/ai/actions/` with mocked HTTP
- Persisted responses remain `pending_approval` (no execute/publish paths)
- Backend `ActionService` creates content actions as `pending_approval`

---

## Known limitations

- `/run` does not persist actions automatically; coordinator integration is deferred
- `DjangoClient` does not mint service JWTs — callers must supply a valid content-agent token
- Persistence tests use mocked HTTP, not a live Django container
- No batch/transaction API — one HTTP POST per draft
- Mapped actions are not linked to a persisted `AgentOutput` unless `agent_output_id` is supplied

---

## Deferred work

| Step | Work |
|------|------|
| **8.7** | Prestia-style acceptance proof and `docs/examples/content_output.json` |
| **10** | Coordinator node: run content analysis, then `persist_content_actions()` |

---

## Acceptance criteria (Step 8.6)

- [x] Validated `ContentDraft` items map to Django-compatible action payloads
- [x] Only `content.instagram_draft` and `content.product_description` are supported
- [x] Mapped content actions are approval-required
- [x] Persistence uses Django internal actions endpoint via shared client
- [x] No auto-approval, auto-execution, or external publishing
- [x] Tenant/store/report scoping follows existing conventions
- [x] Tests pass with fixtures/mocks and no real LLM API keys
- [x] `docs/phases/step-8.6.md` documents the implementation
