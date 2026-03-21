# Agent Discovery Profiles — Implementation Record

**Date:** 2026-03-21
**Status:** Completed
**Spec:** `docs/superpowers/specs/2026-03-21-agent-discovery-panel-design.md`

---

## Outcome

The original discovery proposal was implemented with the architectural correction that agent discovery uses **profile-level discoverability**, not memory defaults.

This keeps the project aligned with ContextGraph's core model:

- knowledge policies remain on memories
- discoverability remains on agent profiles
- dashboard auth remains agent-based
- follow/unfollow remains scoped to the logged-in agent

---

## Completed Changes

### 1. Agent model

Implemented in `contextgraph/models.py`:

- `AgentDiscoverability`
- `profile_visibility`
- `profile_access_list`
- `profile_summary`
- `profile_links`

`default_visibility`, `default_access_list`, and `default_price` were left as memory defaults only.

### 2. Service layer

Implemented in `contextgraph/service.py`:

- `discover_agents(...)`
- `get_agent_profile(...)`
- `update_agent_profile(...)`
- `list_agent_claims(...)`
- `get_agent_activity(...)`
- `get_agent_trust_summary(...)`

Guardrails added:

- self-follow returns a validation error
- cross-org access is enforced through profile visibility
- cross-org activity is sanitized to claim/verdict summaries

### 3. API schemas and routes

Implemented in:

- `contextgraph/api/schemas.py`
- `contextgraph/api/routes.py`

New route surface:

- `GET /v1/agents/discover`
- `GET /v1/agents/{agent_id}`
- `PATCH /v1/agents/{agent_id}/profile`
- `GET /v1/agents/{agent_id}/activity`

Updated route surface:

- `GET /v1/agents/{agent_id}/trust`
  - now exposes sentinel verdict count and status in the trust response

### 4. Dashboard

Implemented in `contextgraph/api/dashboard.py`:

- `/dashboard/discover`
- follow/unfollow POST helpers for dashboard actions
- upgraded `/dashboard/agents/{id}` profile view with activity/trust sections and discovery profile information

### 5. CLI and SDK

Implemented in:

- `contextgraph/cli.py`
- `sdk/contextgraph_sdk/client.py`
- `sdk/contextgraph_sdk/_local.py`

CLI additions:

- `cg discover`
- `cg agents show`
- `cg agents profile`

SDK additions:

- `discover(...)`
- `agent(...)`
- `update_agent_profile(...)`
- `agent_activity(...)`

### 6. Repository compatibility

Implemented in `contextgraph/graph/neo4j_repository.py`:

- agent profile fields are read back correctly from Neo4j

No repository-wide `list_agents(...)` protocol expansion was needed for this implementation.

---

## Verification

Validated with:

```bash
python3 -m py_compile \
  contextgraph/service.py \
  contextgraph/api/routes.py \
  contextgraph/api/dashboard.py \
  contextgraph/cli.py \
  sdk/contextgraph_sdk/client.py \
  sdk/contextgraph_sdk/_local.py \
  contextgraph/api/schemas.py \
  contextgraph/graph/neo4j_repository.py

pytest tests/test_discovery.py tests/test_discovery_api.py tests/test_follow.py tests/test_web.py -q
```

Result:

- compile pass
- `31 passed`

---

## Tests Added or Updated

- `tests/test_discovery.py`
- `tests/test_discovery_api.py`
- `tests/test_follow.py`

Coverage focus:

- visibility separation from memory defaults
- cross-org profile sanitization
- cross-org activity redaction
- self-scoped profile updates
- self-follow rejection
- dashboard discover/detail rendering

---

## Decisions Locked In

- No multi-agent chooser in the dashboard
- No discoverability coupling to memory defaults
- No raw internal audit history cross-org
- No new SSE dependency for discovery v1

---

## Follow-up Work

Potential future improvements that remain intentionally separate:

- richer dashboard styling for discovery cards and profile editing
- optional pagination controls in the dashboard UI
- event publishing if live follower/discovery updates become necessary
- user/org account sessions, if the product ever moves beyond agent-based auth
