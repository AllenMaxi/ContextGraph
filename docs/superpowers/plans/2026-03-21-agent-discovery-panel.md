# Agent Discovery Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cross-org agent discovery with search/filters, follow-from-UI with agent selector, and enhanced agent profiles with Activity and Trust tabs.

**Architecture:** New `discover_agents()` and `get_agent_activity()` service methods with visibility-based filtering using existing `default_visibility`/`default_access_list` fields. New API endpoints, dashboard pages (discover + enhanced agent detail), SDK/CLI methods. All server-side rendered HTML in existing `dashboard.py` pattern.

**Tech Stack:** Python, FastAPI, pure HTML/CSS/JS (no build step), existing InMemory + Neo4j repos.

**Spec:** `docs/superpowers/specs/2026-03-21-agent-discovery-panel-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `contextgraph/service.py` | Modify | Add `discover_agents()`, `get_agent_activity()`, `update_agent_visibility()` |
| `contextgraph/repository.py` | Modify | Add optional filters to `list_agents()` protocol |
| `contextgraph/in_memory.py` | Modify | Implement filtered `list_agents()` |
| `contextgraph/graph/neo4j_repository.py` | Modify | Implement filtered `list_agents()` |
| `contextgraph/api/schemas.py` | Modify | Add `DiscoverAgentsResponse`, `ActivityItemResponse`, `AgentActivityResponse` |
| `contextgraph/api/routes.py` | Modify | Add `GET /v1/agents/discover`, `GET /v1/agents/{id}/activity` endpoints |
| `contextgraph/api/dashboard.py` | Modify | Add discover page, enhance agent detail with tabs |
| `sdk/contextgraph_sdk/client.py` | Modify | Add `discover()`, `agent_activity()`, `update_agent_visibility()` |
| `sdk/contextgraph_sdk/_local.py` | Modify | Add matching LocalTransport methods |
| `contextgraph/cli.py` | Modify | Add `cg discover` and `cg agents visibility` commands |
| `tests/test_discover.py` | Create | Tests for discovery + activity + visibility |
| `tests/test_discover_api.py` | Create | API integration tests |

---

### Task 1: Repository — Add filtered `list_agents()`

**Files:**
- Modify: `contextgraph/repository.py:23`
- Modify: `contextgraph/in_memory.py:53-55`
- Modify: `contextgraph/graph/neo4j_repository.py` (find `list_agents`)
- Test: `tests/test_discover.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_discover.py
from __future__ import annotations

import unittest

from contextgraph import ContextGraphService
from contextgraph.models import AgentStatus, Visibility


class DiscoverAgentsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()

    def tearDown(self) -> None:
        self.service.close()

    def test_list_agents_filters_by_status(self) -> None:
        a1 = self.service.register_agent("active-agent", "acme", ["research"])
        a2 = self.service.register_agent("suspended-agent", "acme", ["research"])
        self.service.suspend_agent(a2.agent_id, a2.agent_id, reason="manual")

        agents = self.service.repository.list_agents(status="active")
        agent_ids = [a.agent_id for a in agents]
        self.assertIn(a1.agent_id, agent_ids)
        self.assertNotIn(a2.agent_id, agent_ids)

    def test_list_agents_filters_by_org(self) -> None:
        a1 = self.service.register_agent("acme-agent", "acme", ["research"])
        a2 = self.service.register_agent("globex-agent", "globex", ["research"])

        agents = self.service.repository.list_agents(org_id="acme")
        agent_ids = [a.agent_id for a in agents]
        self.assertIn(a1.agent_id, agent_ids)
        self.assertNotIn(a2.agent_id, agent_ids)

    def test_list_agents_filters_by_min_reputation(self) -> None:
        a1 = self.service.register_agent("good-agent", "acme", ["research"])
        a1.reputation_score = 0.8
        self.service.repository.save_agent(a1)

        a2 = self.service.register_agent("new-agent", "acme", ["research"])

        agents = self.service.repository.list_agents(min_reputation=0.5)
        agent_ids = [a.agent_id for a in agents]
        self.assertIn(a1.agent_id, agent_ids)
        self.assertNotIn(a2.agent_id, agent_ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_discover.py -v`
Expected: FAIL — `list_agents()` does not accept keyword arguments

- [ ] **Step 3: Update Repository protocol**

```python
# contextgraph/repository.py line 23, change:
def list_agents(self) -> list[Agent]: ...
# to:
def list_agents(
    self,
    *,
    status: str | None = None,
    org_id: str | None = None,
    min_reputation: float | None = None,
) -> list[Agent]: ...
```

- [ ] **Step 4: Update InMemoryRepository**

```python
# contextgraph/in_memory.py, replace list_agents method:
def list_agents(
    self,
    *,
    status: str | None = None,
    org_id: str | None = None,
    min_reputation: float | None = None,
) -> list[Agent]:
    with self._lock:
        agents = list(self._agents.values())
    if status is not None:
        agents = [a for a in agents if a.status == status]
    if org_id is not None:
        agents = [a for a in agents if a.org_id == org_id]
    if min_reputation is not None:
        agents = [a for a in agents if a.reputation_score >= min_reputation]
    return agents
```

- [ ] **Step 5: Update Neo4jRepository**

Find `list_agents` in `contextgraph/graph/neo4j_repository.py` and add the same optional keyword parameters. Apply Cypher `WHERE` clauses conditionally for each filter.

- [ ] **Step 6: Fix all existing callers of `list_agents()`**

Search for `list_agents()` calls in `service.py`. They call `self.repository.list_agents()` with no args — these still work with the new defaults. Verify no breakage.

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_discover.py -v`
Expected: 3 tests PASS

- [ ] **Step 8: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All existing tests still pass (no breaking changes)

- [ ] **Step 9: Commit**

```bash
git add contextgraph/repository.py contextgraph/in_memory.py contextgraph/graph/neo4j_repository.py tests/test_discover.py
git commit -m "feat: add filtered list_agents() to repository protocol"
```

---

### Task 2: Service — Add `discover_agents()`

**Files:**
- Modify: `contextgraph/service.py:1254` (after `list_agents`)
- Test: `tests/test_discover.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_discover.py`:

```python
    def test_discover_returns_same_org_agents(self) -> None:
        a1 = self.service.register_agent("agent-a", "acme", ["research"])
        a2 = self.service.register_agent("agent-b", "acme", ["coding"])
        result = self.service.discover_agents(requester_agent_id=a1.agent_id)
        agent_ids = [a.agent_id for a in result["items"]]
        self.assertIn(a2.agent_id, agent_ids)

    def test_discover_returns_published_agents_from_other_orgs(self) -> None:
        a1 = self.service.register_agent("acme-agent", "acme", ["research"])
        a2 = self.service.register_agent("globex-agent", "globex", ["coding"])
        # Make globex agent published
        a2.default_visibility = Visibility.PUBLISHED
        a2.updated_at = a2.created_at
        self.service.repository.save_agent(a2)

        result = self.service.discover_agents(requester_agent_id=a1.agent_id)
        agent_ids = [a.agent_id for a in result["items"]]
        self.assertIn(a2.agent_id, agent_ids)

    def test_discover_hides_private_agents_from_other_orgs(self) -> None:
        a1 = self.service.register_agent("acme-agent", "acme", ["research"])
        a2 = self.service.register_agent("globex-agent", "globex", ["coding"])
        # default_visibility is PRIVATE

        result = self.service.discover_agents(requester_agent_id=a1.agent_id)
        agent_ids = [a.agent_id for a in result["items"]]
        self.assertNotIn(a2.agent_id, agent_ids)

    def test_discover_shows_shared_to_access_list(self) -> None:
        a1 = self.service.register_agent("acme-agent", "acme", ["research"])
        a2 = self.service.register_agent("globex-agent", "globex", ["coding"])
        a2.default_visibility = Visibility.SHARED
        a2.default_access_list = ["acme"]
        a2.updated_at = a2.created_at
        self.service.repository.save_agent(a2)

        result = self.service.discover_agents(requester_agent_id=a1.agent_id)
        agent_ids = [a.agent_id for a in result["items"]]
        self.assertIn(a2.agent_id, agent_ids)

    def test_discover_hides_shared_from_non_access_list(self) -> None:
        a1 = self.service.register_agent("acme-agent", "acme", ["research"])
        a2 = self.service.register_agent("globex-agent", "globex", ["coding"])
        a2.default_visibility = Visibility.SHARED
        a2.default_access_list = ["initech"]  # acme not in list
        a2.updated_at = a2.created_at
        self.service.repository.save_agent(a2)

        result = self.service.discover_agents(requester_agent_id=a1.agent_id)
        agent_ids = [a.agent_id for a in result["items"]]
        self.assertNotIn(a2.agent_id, agent_ids)

    def test_discover_text_search_by_name(self) -> None:
        a1 = self.service.register_agent("researcher-bot", "acme", ["research"])
        a2 = self.service.register_agent("coder-bot", "acme", ["coding"])

        result = self.service.discover_agents(requester_agent_id=a1.agent_id, q="researcher")
        agent_ids = [a.agent_id for a in result["items"]]
        self.assertIn(a1.agent_id, agent_ids)
        self.assertNotIn(a2.agent_id, agent_ids)

    def test_discover_text_search_by_capability(self) -> None:
        a1 = self.service.register_agent("bot-a", "acme", ["research", "analysis"])
        a2 = self.service.register_agent("bot-b", "acme", ["coding"])

        result = self.service.discover_agents(requester_agent_id=a1.agent_id, q="analysis")
        agent_ids = [a.agent_id for a in result["items"]]
        self.assertIn(a1.agent_id, agent_ids)
        self.assertNotIn(a2.agent_id, agent_ids)

    def test_discover_excludes_deleted_agents(self) -> None:
        a1 = self.service.register_agent("alive", "acme", ["research"])
        a2 = self.service.register_agent("dead", "acme", ["coding"])
        self.service.delete_agent(a2.agent_id, a2.agent_id)

        result = self.service.discover_agents(requester_agent_id=a1.agent_id)
        agent_ids = [a.agent_id for a in result["items"]]
        self.assertNotIn(a2.agent_id, agent_ids)

    def test_discover_excludes_sentinel_agents(self) -> None:
        """Sentinel agents (role=sentinel) should not appear in discovery."""
        settings = self.service.settings
        settings.sentinel_enabled = True
        service = ContextGraphService(app_settings=settings)
        a1 = service.register_agent("user-agent", "acme", ["research"])

        result = service.discover_agents(requester_agent_id=a1.agent_id)
        names = [a.name for a in result["items"]]
        for name in names:
            self.assertNotIn("sentinel_", name)
        service.close()

    def test_discover_pagination(self) -> None:
        agents = []
        for i in range(5):
            agents.append(self.service.register_agent(f"agent-{i}", "acme", []))

        result = self.service.discover_agents(
            requester_agent_id=agents[0].agent_id, limit=2, offset=0
        )
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["total"], 5)

        result2 = self.service.discover_agents(
            requester_agent_id=agents[0].agent_id, limit=2, offset=2
        )
        self.assertEqual(len(result2["items"]), 2)

    def test_discover_sort_by_reputation(self) -> None:
        a1 = self.service.register_agent("low-rep", "acme", [])
        a2 = self.service.register_agent("high-rep", "acme", [])
        a2.reputation_score = 0.9
        self.service.repository.save_agent(a2)

        result = self.service.discover_agents(
            requester_agent_id=a1.agent_id, sort_by="reputation"
        )
        items = result["items"]
        self.assertEqual(items[0].agent_id, a2.agent_id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_discover.py -v -k "discover"`
Expected: FAIL — `discover_agents` method does not exist

- [ ] **Step 3: Implement `discover_agents()` in service.py**

Add after `list_agents()` (around line 1258):

```python
def discover_agents(
    self,
    requester_agent_id: str,
    q: str = "",
    status: str | None = None,
    min_reputation: float | None = None,
    org_id: str | None = None,
    visibility: str | None = None,
    sort_by: str = "reputation",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    requester = self.get_agent(requester_agent_id)

    # Get all agents (no repo filter for visibility logic — done here)
    all_agents = self.repository.list_agents(
        status=status,
        org_id=org_id,
        min_reputation=min_reputation,
    )

    # Filter: same org OR published OR shared+access_list
    visible = []
    for agent in all_agents:
        if agent.status == AgentStatus.DELETED:
            continue
        if agent.role == AgentRole.SENTINEL:
            continue
        if agent.org_id == requester.org_id:
            visible.append(agent)
        elif agent.default_visibility == Visibility.PUBLISHED:
            visible.append(agent)
        elif agent.default_visibility == Visibility.SHARED:
            if requester.agent_id in agent.default_access_list or requester.org_id in agent.default_access_list:
                visible.append(agent)
        # PRIVATE and ORG from other orgs: skip

    # Visibility filter (user-requested)
    if visibility:
        vis_enum = Visibility(visibility)
        visible = [a for a in visible if a.default_visibility == vis_enum]

    # Text search
    if q:
        q_lower = q.lower()
        visible = [
            a for a in visible
            if q_lower in a.name.lower()
            or any(q_lower in cap.lower() for cap in a.capabilities)
        ]

    total = len(visible)

    # Sort
    if sort_by == "reputation":
        visible.sort(key=lambda a: a.reputation_score, reverse=True)
    elif sort_by == "followers":
        visible.sort(key=lambda a: a.followers_count, reverse=True)
    elif sort_by == "created_at":
        visible.sort(key=lambda a: a.created_at, reverse=True)

    # Paginate
    items = visible[offset : offset + limit]

    return {"items": items, "total": total, "limit": limit, "offset": offset}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_discover.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add contextgraph/service.py tests/test_discover.py
git commit -m "feat: add discover_agents() service method with visibility filtering"
```

---

### Task 3: Service — Add `get_agent_activity()` and `update_agent_visibility()`

**Files:**
- Modify: `contextgraph/repository.py` (add `list_memories_by_agent` to protocol)
- Modify: `contextgraph/in_memory.py` (implement `list_memories_by_agent`)
- Modify: `contextgraph/graph/neo4j_repository.py` (implement `list_memories_by_agent`)
- Modify: `contextgraph/service.py`
- Test: `tests/test_discover.py`

**Before implementing, add `list_memories_by_agent` to the Repository protocol:**

Add to `contextgraph/repository.py` after `get_memory`:
```python
def list_memories_by_agent(self, agent_id: str) -> list[Memory]: ...
```

Add to `contextgraph/in_memory.py`:
```python
def list_memories_by_agent(self, agent_id: str) -> list[Memory]:
    with self._lock:
        return [m for m in self._memories.values() if m.agent_id == agent_id]
```

Add matching implementation to Neo4j repo (Cypher: `MATCH (m:Memory {agent_id: $agent_id}) RETURN m`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_discover.py`:

```python
class AgentActivityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()

    def tearDown(self) -> None:
        self.service.close()

    def test_get_activity_returns_memories_and_claims(self) -> None:
        agent = self.service.register_agent("agent-a", "acme", ["research"])
        self.service.store_memory(
            agent_id=agent.agent_id,
            content="Python is a programming language created by Guido van Rossum",
        )
        result = self.service.get_agent_activity(
            agent_id=agent.agent_id,
            requester_agent_id=agent.agent_id,
        )
        self.assertGreater(len(result["items"]), 0)
        event_types = [item["event_type"] for item in result["items"]]
        self.assertTrue(
            any(et in ("memory_stored", "claim_created") for et in event_types)
        )

    def test_get_activity_cross_org_filters_private(self) -> None:
        a1 = self.service.register_agent("acme-agent", "acme", ["research"])
        a2 = self.service.register_agent("globex-agent", "globex", ["coding"])
        a2.default_visibility = Visibility.PUBLISHED
        self.service.repository.save_agent(a2)
        # Store private memory for a2
        self.service.store_memory(
            agent_id=a2.agent_id,
            content="Internal globex secret data about projects",
            visibility="private",
        )
        result = self.service.get_agent_activity(
            agent_id=a2.agent_id,
            requester_agent_id=a1.agent_id,
        )
        # Cross-org should not see private memories
        for item in result["items"]:
            if item["event_type"] == "memory_stored" and item.get("memory"):
                self.assertNotEqual(item["memory"]["visibility"], "private")

    def test_get_activity_pagination(self) -> None:
        agent = self.service.register_agent("agent", "acme", ["research"])
        for i in range(5):
            self.service.store_memory(
                agent_id=agent.agent_id,
                content=f"Fact number {i}: the sky is blue on clear days",
            )
        result = self.service.get_agent_activity(
            agent_id=agent.agent_id,
            requester_agent_id=agent.agent_id,
            limit=2,
        )
        self.assertLessEqual(len(result["items"]), 2)


class AgentVisibilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()

    def tearDown(self) -> None:
        self.service.close()

    def test_update_visibility_changes_default_visibility(self) -> None:
        agent = self.service.register_agent("agent", "acme", [])
        self.assertEqual(agent.default_visibility, Visibility.PRIVATE)

        updated = self.service.update_agent_visibility(
            agent_id=agent.agent_id,
            requester_agent_id=agent.agent_id,
            visibility="published",
        )
        self.assertEqual(updated.default_visibility, Visibility.PUBLISHED)

    def test_update_visibility_sets_access_list(self) -> None:
        agent = self.service.register_agent("agent", "acme", [])
        updated = self.service.update_agent_visibility(
            agent_id=agent.agent_id,
            requester_agent_id=agent.agent_id,
            visibility="shared",
            access_list=["globex", "initech"],
        )
        self.assertEqual(updated.default_visibility, Visibility.SHARED)
        self.assertEqual(updated.default_access_list, ["globex", "initech"])

    def test_update_visibility_rejects_cross_org(self) -> None:
        a1 = self.service.register_agent("acme-agent", "acme", [])
        a2 = self.service.register_agent("globex-agent", "globex", [])
        from contextgraph.errors import PermissionDeniedError

        with self.assertRaises(PermissionDeniedError):
            self.service.update_agent_visibility(
                agent_id=a2.agent_id,
                requester_agent_id=a1.agent_id,
                visibility="published",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_discover.py -v -k "Activity or Visibility"`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Implement `get_agent_activity()` in service.py**

Add after `discover_agents()`:

```python
def get_agent_activity(
    self,
    agent_id: str,
    requester_agent_id: str,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    target = self.get_agent(agent_id)
    requester = self.get_agent(requester_agent_id)
    cross_org = requester.org_id != target.org_id

    items: list[dict[str, Any]] = []

    # Memories
    all_memories = self.repository.list_memories_by_agent(agent_id)
    for mem in all_memories:
        if cross_org and mem.visibility == Visibility.PRIVATE:
            continue
        items.append({
            "event_type": "memory_stored",
            "timestamp": mem.created_at.isoformat(),
            "memory": to_jsonable(mem),
        })

    # Claims
    all_claims = [c for c in self.repository.list_claims() if c.source_agent_id == agent_id]
    for claim in all_claims:
        if cross_org and claim.visibility == Visibility.PRIVATE:
            continue
        items.append({
            "event_type": "claim_created",
            "timestamp": claim.created_at.isoformat(),
            "claim": to_jsonable(claim),
        })

    # Verdicts received
    for claim in all_claims:
        verdicts = self.repository.list_verdicts_for_claim(claim.claim_id)
        for v in verdicts:
            items.append({
                "event_type": "verdict_received",
                "timestamp": v.timestamp.isoformat(),
                "verdict": to_jsonable(v),
            })

    # Sort by timestamp descending
    items.sort(key=lambda x: x["timestamp"], reverse=True)

    total = len(items)
    items = items[offset : offset + limit]

    return {"items": items, "total": total, "limit": limit, "offset": offset}

```

**Important:** Do NOT use `hasattr(self.repository, "_memories")` to access private repo internals. Instead, add a `list_memories_by_agent(agent_id: str)` method to the `Repository` protocol and implement it in both `InMemoryRepository` and `Neo4jRepository`. In `InMemoryRepository`:

```python
def list_memories_by_agent(self, agent_id: str) -> list[Memory]:
    with self._lock:
        return [m for m in self._memories.values() if m.agent_id == agent_id]
```

Then in the service method, call `self.repository.list_memories_by_agent(agent_id)` instead of `self._list_all_memories()`.

- [ ] **Step 4: Implement `update_agent_visibility()` in service.py**

Add after `get_agent_activity()`:

```python
def update_agent_visibility(
    self,
    agent_id: str,
    requester_agent_id: str,
    visibility: str,
    access_list: list[str] | None = None,
) -> Agent:
    requester = self.get_agent(requester_agent_id)
    target = self.get_agent(agent_id)

    if requester.org_id != target.org_id:
        raise PermissionDeniedError("Only agents in the same org can update visibility.")

    target.default_visibility = Visibility(visibility)
    if access_list is not None:
        target.default_access_list = access_list
    target.updated_at = utcnow()
    self.repository.save_agent(target)

    self._audit(
        "update_agent_visibility",
        actor_agent_id=requester_agent_id,
        details={"agent_id": agent_id, "visibility": visibility},
    )
    return target
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_discover.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add contextgraph/service.py tests/test_discover.py
git commit -m "feat: add get_agent_activity() and update_agent_visibility() service methods"
```

---

### Task 4: API — Add schemas and endpoints

**Files:**
- Modify: `contextgraph/api/schemas.py`
- Modify: `contextgraph/api/routes.py`
- Test: `tests/test_discover_api.py` (create)

- [ ] **Step 1: Add response schemas**

Add to `contextgraph/api/schemas.py` at the end:

```python
class ActivityItemResponse(BaseModel):
    event_type: str
    timestamp: datetime
    memory: MemoryResponse | None = None
    claim: ClaimResponse | None = None
    verdict: SentinelVerdictResponse | None = None
    details: dict[str, str] = Field(default_factory=dict)


class AgentActivityResponse(BaseModel):
    items: list[ActivityItemResponse]
    total: int
    limit: int
    offset: int


class DiscoverAgentsResponse(BaseModel):
    items: list[AgentResponse]
    total: int
    limit: int
    offset: int


class AgentVisibilityUpdateRequest(BaseModel):
    visibility: Visibility
    access_list: list[str] | None = None
```

- [ ] **Step 2: Add API endpoints**

Add to `contextgraph/api/routes.py` inside `register_routes()`. Add the imports for new schemas at the top of the file.

Important: the `GET /v1/agents/discover` route **must be registered before** any `{agent_id}` parameterized routes to avoid FastAPI matching "discover" as an `agent_id`. Place it immediately after the `POST /v1/agents/register` handler (around line 49 of routes.py) and before any `PATCH /v1/agents/{agent_id}` routes.

```python
@app.get("/v1/agents/discover", response_model=DiscoverAgentsResponse)
def discover_agents(
    q: str = "",
    status: str | None = None,
    min_reputation: float | None = None,
    org_id: str | None = None,
    visibility: str | None = None,
    sort_by: str = "reputation",
    limit: int = 20,
    offset: int = 0,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    return to_jsonable(
        graph.discover_agents(
            requester_agent_id=authenticated.agent_id,
            q=q,
            status=status,
            min_reputation=min_reputation,
            org_id=org_id,
            visibility=visibility,
            sort_by=sort_by,
            limit=min(limit, 100),
            offset=max(offset, 0),
        )
    )

@app.get("/v1/agents/{agent_id}/activity", response_model=AgentActivityResponse)
def agent_activity(
    agent_id: str,
    limit: int = 20,
    offset: int = 0,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    return to_jsonable(
        graph.get_agent_activity(
            agent_id=agent_id,
            requester_agent_id=authenticated.agent_id,
            limit=min(limit, 100),
            offset=max(offset, 0),
        )
    )

@app.patch("/v1/agents/{agent_id}/visibility", response_model=AgentResponse)
def update_agent_visibility(
    agent_id: str,
    payload: AgentVisibilityUpdateRequest,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    return to_jsonable(
        graph.update_agent_visibility(
            agent_id=agent_id,
            requester_agent_id=authenticated.agent_id,
            visibility=payload.visibility.value,
            access_list=payload.access_list,
        )
    )
```

- [ ] **Step 3: Add `GET /v1/agents/{agent_id}` endpoint with cross-org visibility guard**

This endpoint does not exist yet in `routes.py`. Create it with a visibility check so cross-org requests return 403 for PRIVATE/ORG agents. Place it **after** the `GET /v1/agents/discover` route (to avoid path conflicts):

```python
@app.get("/v1/agents/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: str,
    authenticated: Any = Depends(authenticated_agent),
) -> Any:
    from fastapi import HTTPException
    from contextgraph.models import Visibility

    target = graph.get_agent(agent_id)
    requester = authenticated

    if target.org_id != requester.org_id:
        if target.default_visibility == Visibility.PRIVATE:
            raise HTTPException(status_code=403, detail="Agent is private")
        if target.default_visibility == Visibility.ORG:
            raise HTTPException(status_code=403, detail="Agent is org-only")
        if target.default_visibility == Visibility.SHARED:
            if requester.agent_id not in target.default_access_list and requester.org_id not in target.default_access_list:
                raise HTTPException(status_code=403, detail="Agent not shared with you")
    # PUBLISHED: allow through

    return to_jsonable(target)
```

- [ ] **Step 4: Write API integration tests**

```python
# tests/test_discover_api.py
from __future__ import annotations

import unittest

from contextgraph import ContextGraphService
from contextgraph.models import Visibility


class DiscoverAPITest(unittest.TestCase):
    """Test discover endpoints via service layer (API-level logic)."""

    def setUp(self) -> None:
        self.service = ContextGraphService()

    def tearDown(self) -> None:
        self.service.close()

    def test_discover_endpoint_returns_paginated_result(self) -> None:
        a1 = self.service.register_agent("agent-1", "acme", ["research"])
        self.service.register_agent("agent-2", "acme", ["coding"])
        result = self.service.discover_agents(
            requester_agent_id=a1.agent_id, limit=10, offset=0
        )
        self.assertIn("items", result)
        self.assertIn("total", result)
        self.assertIn("limit", result)
        self.assertIn("offset", result)

    def test_activity_endpoint_returns_events(self) -> None:
        agent = self.service.register_agent("agent", "acme", ["research"])
        self.service.store_memory(
            agent_id=agent.agent_id,
            content="The Eiffel Tower is located in Paris, France",
        )
        result = self.service.get_agent_activity(
            agent_id=agent.agent_id,
            requester_agent_id=agent.agent_id,
        )
        self.assertIn("items", result)
        self.assertGreater(result["total"], 0)

    def test_visibility_update_endpoint(self) -> None:
        agent = self.service.register_agent("agent", "acme", [])
        updated = self.service.update_agent_visibility(
            agent_id=agent.agent_id,
            requester_agent_id=agent.agent_id,
            visibility="published",
        )
        self.assertEqual(updated.default_visibility, Visibility.PUBLISHED)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_discover.py tests/test_discover_api.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add contextgraph/api/schemas.py contextgraph/api/routes.py tests/test_discover_api.py
git commit -m "feat: add discover, activity, visibility API endpoints and cross-org guard"
```

---

### Task 5: SDK — Add client methods

**Files:**
- Modify: `sdk/contextgraph_sdk/client.py`
- Modify: `sdk/contextgraph_sdk/_local.py`

- [ ] **Step 1: Add to Transport protocol**

In `sdk/contextgraph_sdk/client.py`, add to the `Transport` protocol class (around line 45):

```python
def discover_agents(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def agent_activity(self, payload: dict[str, Any]) -> dict[str, Any]: ...
def update_agent_visibility(self, payload: dict[str, Any]) -> dict[str, Any]: ...
```

- [ ] **Step 2: Add HttpTransport methods**

Add to `HttpTransport` class (around line 200):

```python
def discover_agents(self, payload: dict[str, Any]) -> dict[str, Any]:
    # requester_agent_id not sent over HTTP — API key header handles auth
    params = {}
    for key in ("q", "status", "min_reputation", "org_id", "visibility", "sort_by", "limit", "offset"):
        if payload.get(key) is not None:
            params[key] = payload[key]
    path = "/v1/agents/discover"
    if params:
        path = f"{path}?{urlencode(params)}"
    return self._request("GET", path)

def agent_activity(self, payload: dict[str, Any]) -> dict[str, Any]:
    agent_id = payload["agent_id"]
    params = {}
    if payload.get("limit"):
        params["limit"] = payload["limit"]
    if payload.get("offset"):
        params["offset"] = payload["offset"]
    path = f"/v1/agents/{agent_id}/activity"
    if params:
        path = f"{path}?{urlencode(params)}"
    return self._request("GET", path)

def update_agent_visibility(self, payload: dict[str, Any]) -> dict[str, Any]:
    agent_id = payload["agent_id"]
    body = {"visibility": payload["visibility"]}
    if payload.get("access_list") is not None:
        body["access_list"] = payload["access_list"]
    return self._request("PATCH", f"/v1/agents/{agent_id}/visibility", body)
```

- [ ] **Step 3: Add ContextGraph class methods**

Add to `ContextGraph` class (around line 450):

```python
def discover(
    self,
    q: str = "",
    status: str | None = None,
    min_reputation: float | None = None,
    org_id: str | None = None,
    visibility: str | None = None,
    sort_by: str = "reputation",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    return self.transport.discover_agents({
        "requester_agent_id": self._agent_id,
        "q": q, "status": status, "min_reputation": min_reputation,
        "org_id": org_id, "visibility": visibility, "sort_by": sort_by,
        "limit": limit, "offset": offset,
    })

def agent_activity(
    self, agent_id: str, limit: int = 20, offset: int = 0
) -> dict[str, Any]:
    return self.transport.agent_activity({
        "agent_id": agent_id,
        "requester_agent_id": self._agent_id,
        "limit": limit, "offset": offset,
    })

def update_agent_visibility(
    self,
    visibility: str,
    access_list: list[str] | None = None,
) -> dict[str, Any]:
    return self.transport.update_agent_visibility({
        "agent_id": self._agent_id,
        "requester_agent_id": self._agent_id,
        "visibility": visibility,
        "access_list": access_list,
    })
```

- [ ] **Step 4: Add LocalTransport methods**

Add to `sdk/contextgraph_sdk/_local.py`:

```python
def discover_agents(self, payload: dict[str, Any]) -> dict[str, Any]:
    # requester_agent_id included in payload by SDK client
    return to_jsonable(self.service.discover_agents(**payload))

def agent_activity(self, payload: dict[str, Any]) -> dict[str, Any]:
    # Maps to service.get_agent_activity (note: different method name)
    return to_jsonable(self.service.get_agent_activity(**payload))

def update_agent_visibility(self, payload: dict[str, Any]) -> dict[str, Any]:
    return to_jsonable(self.service.update_agent_visibility(**payload))
```

- [ ] **Step 5: Write SDK tests**

Create `tests/test_sdk_discover.py`:

```python
from __future__ import annotations

import unittest

from contextgraph import ContextGraphService
from contextgraph.models import Visibility
from sdk.contextgraph_sdk._local import LocalTransport
from sdk.contextgraph_sdk.client import ContextGraph


class SDKDiscoverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        transport = LocalTransport(self.service)
        self.agent = self.service.register_agent("sdk-test", "acme", ["research"])
        self.client = ContextGraph(transport)
        self.client._agent_id = self.agent.agent_id

    def tearDown(self) -> None:
        self.service.close()

    def test_discover_returns_agents(self) -> None:
        self.service.register_agent("other-agent", "acme", ["coding"])
        result = self.client.discover()
        self.assertIn("items", result)
        self.assertGreater(result["total"], 0)

    def test_agent_activity_returns_events(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The Eiffel Tower is in Paris, France",
        )
        result = self.client.agent_activity(self.agent.agent_id)
        self.assertIn("items", result)
        self.assertGreater(result["total"], 0)

    def test_update_visibility(self) -> None:
        result = self.client.update_agent_visibility(visibility="published")
        self.assertEqual(result["default_visibility"], "published")
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_sdk_discover.py tests/ -q`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add sdk/contextgraph_sdk/client.py sdk/contextgraph_sdk/_local.py tests/test_sdk_discover.py
git commit -m "feat: add discover, activity, visibility SDK client methods with tests"
```

---

### Task 6: CLI — Add `discover` and `visibility` commands

**Files:**
- Modify: `contextgraph/cli.py`

- [ ] **Step 1: Read cli.py to find where to add commands**

Read `contextgraph/cli.py` to find the pattern for existing commands (likely using `argparse` subcommands or similar). Look for how `sentinel health` and `agents suspend` commands were added.

- [ ] **Step 2: Add `discover` command**

Add a new subcommand `discover` following the existing pattern. The command should:
- Accept `--query`, `--status`, `--min-rep`, `--org`, `--sort`, `--limit` flags
- Call `HttpTransport.discover_agents()` or the appropriate transport
- Print results as a table (agent name, org, reputation, capabilities, visibility, followers)

```python
# In the agents subparser or as a top-level command, depending on CLI structure:
# cg discover --query "research" --min-rep 0.5 --sort reputation
```

- [ ] **Step 3: Add `agents visibility` command**

Add subcommand under `agents`:
- `cg agents visibility <agent_id> --set published|shared|private|org [--access-list org1 org2]`
- Calls `update_agent_visibility()`
- Prints updated agent info

- [ ] **Step 4: Test manually**

Run: `python -m contextgraph.cli discover --help`
Expected: Shows help text with flags

- [ ] **Step 5: Commit**

```bash
git add contextgraph/cli.py
git commit -m "feat: add cg discover and cg agents visibility CLI commands"
```

---

### Task 7: Dashboard — Discover page

**Files:**
- Modify: `contextgraph/api/dashboard.py`

- [ ] **Step 1: Add "Discover" to sidebar navigation**

In `_render_app()` (line 535), add discover to `nav_items` between "agents" and "knowledge":

```python
nav_items = [
    ("overview", "&#x1F4CA;", "Overview"),
    ("agents", "&#x1F916;", "Agents"),
    ("discover", "&#x1F50D;", "Discover"),  # NEW
    ("knowledge", "&#x1F9E0;", "Knowledge"),
    ("feed", "&#x1F4E1;", "Feed"),
    ("graph", "&#x1F578;&#xFE0F;", "Graph Explorer"),
    ("notifications", "&#x1F514;", "Notifications"),
]
```

- [ ] **Step 2: Add route handler for discover page**

In `_render_page()` (line 591), add:

```python
if page == "discover":
    return _render_discover(graph, agent)
```

- [ ] **Step 3: Implement `_render_discover()` function**

Add new function. This renders:
- Search bar at top
- Filter sidebar (left): status dropdown, min reputation input, org input, visibility dropdown, sort dropdown
- Agent card grid (right): responsive 3-column grid

```python
def _render_discover(graph: ContextGraphService, viewer: Any) -> str:
    # Get all discoverable agents for this viewer
    result = graph.discover_agents(requester_agent_id=viewer.agent_id, limit=50)
    agents = result["items"]

    # Get viewer's current subscriptions to show follow state
    following = graph.list_following(agent_id=viewer.agent_id)
    following_targets = {s.target_id for s in following if s.target_type.value == "agent"}

    # Get all agents in viewer's org for the follow dropdown
    org_agents = graph.list_agents(requester_agent_id=viewer.agent_id)

    cards_html = ""
    for a in agents:
        trust_color = "green" if a.reputation_score >= 0.7 else "orange" if a.reputation_score >= 0.4 else "red"
        caps = a.capabilities[:3]
        caps_html = "".join(f'<span class="badge badge-blue" style="font-size:11px">{escape(c)}</span>' for c in caps)
        if len(a.capabilities) > 3:
            caps_html += f'<span class="badge" style="font-size:11px">+{len(a.capabilities) - 3}</span>'

        status_dot = "🟢" if a.status == "active" else "🟡"
        vis_label = a.default_visibility.value
        is_following = a.agent_id in following_targets

        follow_btn = ""
        if a.agent_id != viewer.agent_id:
            if is_following:
                follow_btn = '<span class="badge badge-green">Following</span>'
            else:
                follow_btn = f'<button class="btn btn-sm" onclick="followAgent(\'{a.agent_id}\')">Follow</button>'

        cards_html += f"""\
<div class="item-card" style="margin-bottom:8px">
    <div class="item-header">
        <a href="/dashboard/agents/{a.agent_id}" style="display:flex;align-items:center;gap:10px;text-decoration:none;color:inherit">
            <div class="agent-avatar">{escape(a.name[:2].upper())}</div>
            <div>
                <div class="item-title">{status_dot} {escape(a.name)}</div>
                <div style="font-size:12px;color:var(--text-secondary)">{escape(a.org_id)} · {vis_label}</div>
            </div>
        </a>
        {follow_btn}
    </div>
    <div style="margin:8px 0">{caps_html}</div>
    <div class="item-meta">
        <span>Trust: <b style="color:var(--accent-{trust_color})">{a.reputation_score:.2f}</b></span>
        <span>Followers: <b>{a.followers_count}</b></span>
    </div>
</div>"""

    filter_html = f"""\
<div style="min-width:200px">
    <div style="margin-bottom:16px">
        <input type="text" id="discover-search" placeholder="Search agents..."
               style="width:100%;padding:8px 12px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:6px;color:var(--text-primary);font-size:13px"
               oninput="filterDiscover()">
    </div>
    <div style="margin-bottom:12px">
        <label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px">Status</label>
        <select id="discover-status" onchange="filterDiscover()"
                style="width:100%;padding:6px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)">
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
        </select>
    </div>
    <div style="margin-bottom:12px">
        <label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px">Min Reputation</label>
        <input type="number" id="discover-min-rep" min="0" max="1" step="0.1" value=""
               style="width:100%;padding:6px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)"
               onchange="filterDiscover()">
    </div>
    <div style="margin-bottom:12px">
        <label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px">Sort by</label>
        <select id="discover-sort" onchange="filterDiscover()"
                style="width:100%;padding:6px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;color:var(--text-primary)">
            <option value="reputation">Reputation</option>
            <option value="followers">Followers</option>
            <option value="created_at">Newest</option>
        </select>
    </div>
</div>"""

    js = """\
<script>
function filterDiscover() {
    const q = document.getElementById('discover-search').value;
    const status = document.getElementById('discover-status').value;
    const minRep = document.getElementById('discover-min-rep').value;
    const sort = document.getElementById('discover-sort').value;
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (status) params.set('status', status);
    if (minRep) params.set('min_reputation', minRep);
    params.set('sort_by', sort);
    params.set('limit', '50');
    // Reload page with query params — server re-renders
    window.location.href = '/dashboard/discover?' + params.toString();
}
function followAgent(targetId) {
    const key = document.cookie.split('cg_session=')[1]?.split(';')[0];
    fetch('/v1/follow', {
        method: 'POST',
        headers: {'Content-Type':'application/json', 'X-Agent-Key': key},
        body: JSON.stringify({target_type:'agent', target_id: targetId})
    }).then(() => window.location.reload());
}
</script>"""

    return f"""\
<div class="page-header">
    <h2>Discover Agents</h2>
    <span style="font-size:13px;color:var(--text-secondary)">{result['total']} agents found</span>
</div>
<div style="display:flex;gap:24px">
    {filter_html}
    <div style="flex:1">
        <div class="item-list">{cards_html or '<div style="color:var(--text-muted)">No agents found</div>'}</div>
    </div>
</div>
{js}"""
```

- [ ] **Step 4: Handle query params in discover route**

Update the dashboard route handler to pass query params to the discover page. In `dashboard_page()` (line 46), the page is "discover" but query params aren't passed. Read query params from `request.query_params` and pass them through.

Update `_render_app` and `_render_page` to accept and pass `request` or query params for the discover page specifically.

- [ ] **Step 5: Test manually**

Start the server and navigate to `/dashboard/discover`. Verify:
- Agents appear as cards
- Search input works
- Filter dropdowns work
- Follow button works

- [ ] **Step 6: Commit**

```bash
git add contextgraph/api/dashboard.py
git commit -m "feat: add discover page to dashboard with search, filters, and follow"
```

---

### Task 8: Dashboard — Enhanced agent detail with tabs

**Files:**
- Modify: `contextgraph/api/dashboard.py`

- [ ] **Step 1: Refactor `_render_agent_detail()` to add tabbed layout**

Replace the existing `_render_agent_detail()` function (starting at line 705) with a tabbed version. Keep the existing header/stats, add tab navigation and two tab content sections.

The header should now include:
- Visibility badge
- Follow/Unfollow button
- Following/followers counts

Add Activity tab:
- Call `graph.get_agent_activity()` to get timeline items
- Render as chronological list with event type icons

Add Trust tab:
- SVG pie chart showing attested vs challenged vs unreviewed claims
- Attestation rate progress bar
- Recent verdicts table

```python
def _render_agent_detail(graph: ContextGraphService, viewer: Any, agent_id: str) -> str:
    try:
        target = graph.get_agent(agent_id)
    except Exception:
        return '<div style="color:var(--accent-red)">Agent not found</div>'

    claims = [c for c in graph.repository.list_claims() if c.source_agent_id == agent_id]
    attested = sum(1 for c in claims if c.validation_status == ValidationStatus.ATTESTED)
    challenged = sum(1 for c in claims if c.validation_status == ValidationStatus.CHALLENGED)
    unreviewed = sum(1 for c in claims if c.validation_status == ValidationStatus.UNREVIEWED)
    trust_pct = int(target.reputation_score * 100)
    vis_badge = f'<span class="badge">{target.default_visibility.value}</span>'

    # Follow state
    following = graph.list_following(agent_id=viewer.agent_id)
    is_following = any(
        s.target_id == agent_id and s.target_type.value == "agent"
        for s in following
    )
    follow_btn = ""
    if viewer.agent_id != agent_id:
        if is_following:
            follow_btn = '<span class="badge badge-green">Following</span>'
        else:
            follow_btn = f'<button class="btn btn-sm" onclick="followAgent(\'{agent_id}\')">Follow</button>'

    # Activity data
    activity = graph.get_agent_activity(
        agent_id=agent_id,
        requester_agent_id=viewer.agent_id,
        limit=20,
    )

    activity_html = ""
    for item in activity["items"]:
        et = item["event_type"]
        ts = item["timestamp"][:10]
        icon = {"memory_stored": "📝", "claim_created": "💡", "verdict_received": "⚖️"}.get(et, "📌")
        detail = ""
        if et == "memory_stored" and item.get("memory"):
            detail = escape(str(item["memory"].get("content", ""))[:100])
        elif et == "claim_created" and item.get("claim"):
            detail = escape(str(item["claim"].get("statement", ""))[:100])
        elif et == "verdict_received" and item.get("verdict"):
            detail = f'{item["verdict"].get("decision", "")} — {escape(str(item["verdict"].get("reason", ""))[:80])}'
        activity_html += f"""\
<div class="item-card" style="margin-bottom:6px;padding:10px">
    <div style="display:flex;align-items:center;gap:8px">
        <span>{icon}</span>
        <span style="font-size:12px;color:var(--text-secondary)">{et.replace('_', ' ').title()}</span>
        <span style="font-size:11px;color:var(--text-muted);margin-left:auto">{ts}</span>
    </div>
    <div style="font-size:13px;margin-top:4px;color:var(--text-primary)">{detail}</div>
</div>"""

    # Trust tab — SVG pie chart
    total_claims = max(attested + challenged + unreviewed, 1)
    att_pct = attested / total_claims * 100
    cha_pct = challenged / total_claims * 100
    att_deg = att_pct * 3.6
    cha_deg = cha_pct * 3.6

    # Verdicts table
    verdicts_html = ""
    all_verdicts = []
    for claim in claims[:20]:
        vs = graph.repository.list_verdicts_for_claim(claim.claim_id)
        all_verdicts.extend(vs)
    all_verdicts.sort(key=lambda v: v.timestamp, reverse=True)
    for v in all_verdicts[:10]:
        dec_color = {"pass": "green", "validate": "green", "dispute": "orange", "reject": "red"}.get(v.decision.value, "")
        verdicts_html += f"""\
<tr>
    <td><span class="badge badge-{dec_color}">{v.decision.value}</span></td>
    <td style="font-size:12px">{v.confidence:.0%}</td>
    <td style="font-size:12px;color:var(--text-secondary)">{escape(v.reason[:60])}</td>
    <td style="font-size:11px;color:var(--text-muted)">{v.timestamp.strftime("%b %d")}</td>
</tr>"""

    tab_js = """\
<script>
function switchTab(tab) {
    document.getElementById('tab-activity').style.display = tab === 'activity' ? 'block' : 'none';
    document.getElementById('tab-trust').style.display = tab === 'trust' ? 'block' : 'none';
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
}
function followAgent(targetId) {
    const key = document.cookie.split('cg_session=')[1]?.split(';')[0];
    fetch('/v1/follow', {
        method: 'POST',
        headers: {'Content-Type':'application/json', 'X-Agent-Key': key},
        body: JSON.stringify({target_type:'agent', target_id: targetId})
    }).then(() => window.location.reload());
}
</script>"""

    return f"""\
<div class="page-header">
    <h2 style="display:flex;align-items:center;gap:12px">
        <div class="agent-avatar" style="width:40px;height:40px;font-size:16px">{escape(target.name[:2].upper())}</div>
        <div>
            {escape(target.name)} {vis_badge} {follow_btn}
            <div style="font-size:13px;color:var(--text-secondary);font-weight:400">{escape(target.org_id)} &middot; {escape(agent_id[:16])}...</div>
        </div>
    </h2>
</div>
<div class="stats-grid">
    <div class="stat-card"><div class="stat-label">Trust Score</div>
        <div class="trust-bar"><div class="trust-track"><div class="trust-fill" style="width:{trust_pct}%"></div></div> <b>{target.reputation_score:.2f}</b></div>
    </div>
    <div class="stat-card"><div class="stat-label">Claims</div><div class="stat-value cyan">{len(claims)}</div></div>
    <div class="stat-card"><div class="stat-label">Attested</div><div class="stat-value green">{attested}</div></div>
    <div class="stat-card"><div class="stat-label">Challenged</div><div class="stat-value orange">{challenged}</div></div>
    <div class="stat-card"><div class="stat-label">Followers</div><div class="stat-value purple">{target.followers_count}</div></div>
</div>
<div style="display:flex;gap:8px;margin:16px 0;border-bottom:1px solid var(--border);padding-bottom:8px">
    <button class="btn btn-sm tab-btn active" data-tab="activity" onclick="switchTab('activity')">Activity</button>
    <button class="btn btn-sm tab-btn" data-tab="trust" onclick="switchTab('trust')">Trust</button>
</div>
<div id="tab-activity">
    {activity_html or '<div style="color:var(--text-muted)">No activity yet</div>'}
</div>
<div id="tab-trust" style="display:none">
    <div class="stats-grid" style="margin-bottom:16px">
        <div class="stat-card">
            <div class="stat-label">Attestation Rate</div>
            <div class="trust-bar"><div class="trust-track"><div class="trust-fill" style="width:{att_pct:.0f}%"></div></div> <b>{att_pct:.0f}%</b></div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Challenge Rate</div>
            <div class="trust-bar"><div class="trust-track"><div class="trust-fill" style="width:{cha_pct:.0f}%;background:var(--accent-orange)"></div></div> <b>{cha_pct:.0f}%</b></div>
        </div>
    </div>
    <h3 style="font-size:14px;margin-bottom:8px">Recent Sentinel Verdicts</h3>
    <table style="width:100%;font-size:13px">
        <thead><tr>
            <th style="text-align:left;padding:6px;color:var(--text-secondary)">Decision</th>
            <th style="text-align:left;padding:6px;color:var(--text-secondary)">Confidence</th>
            <th style="text-align:left;padding:6px;color:var(--text-secondary)">Reason</th>
            <th style="text-align:left;padding:6px;color:var(--text-secondary)">Date</th>
        </tr></thead>
        <tbody>{verdicts_html or '<tr><td colspan="4" style="color:var(--text-muted);padding:6px">No verdicts yet</td></tr>'}</tbody>
    </table>
</div>
{tab_js}"""
```

- [ ] **Step 2: Test manually**

Navigate to `/dashboard/agents/{id}`. Verify:
- Header shows visibility badge and follow button
- Activity tab shows timeline of events
- Trust tab shows attestation/challenge rates and verdicts table
- Tab switching works without page reload

- [ ] **Step 3: Commit**

```bash
git add contextgraph/api/dashboard.py
git commit -m "feat: enhance agent detail page with Activity and Trust tabs"
```

---

### Task 9: Verification & cleanup

**Files:** All modified files

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass (existing + ~18 new tests)

- [ ] **Step 2: Run linter**

```bash
ruff check contextgraph/ sdk/ tests/
ruff format --check contextgraph/ sdk/ tests/
```

Fix any issues found.

- [ ] **Step 3: Format code**

```bash
ruff format contextgraph/ sdk/ tests/
```

- [ ] **Step 4: Verify dashboard manually**

Start server and check:
- `/dashboard/discover` — search, filter, follow work
- `/dashboard/agents/{id}` — tabs work, activity loads, trust data displays
- Follow button updates follower count
- Cross-org visibility respected (register agents in different orgs to test)

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: lint and format agent discovery panel"
```

---

## Verification Checklist

```bash
# 1. All tests pass
python -m pytest tests/ -v

# 2. Linter clean
ruff check contextgraph/ sdk/ tests/

# 3. Discover endpoint works
python -c "
from contextgraph import ContextGraphService
s = ContextGraphService()
a1 = s.register_agent('agent-1', 'acme', ['research'])
a2 = s.register_agent('agent-2', 'globex', ['coding'])
# a2 is private, should not appear
result = s.discover_agents(requester_agent_id=a1.agent_id)
print(f'Found {result[\"total\"]} agents')
assert all(a.org_id == 'acme' for a in result['items'])
print('OK: cross-org visibility works')
s.close()
"

# 4. Activity endpoint works
python -c "
from contextgraph import ContextGraphService
s = ContextGraphService()
a = s.register_agent('test', 'acme', ['research'])
s.store_memory(agent_id=a.agent_id, content='Python was created by Guido van Rossum')
result = s.get_agent_activity(agent_id=a.agent_id, requester_agent_id=a.agent_id)
print(f'Found {result[\"total\"]} activity items')
assert result['total'] > 0
print('OK: activity works')
s.close()
"
```

---

## Deferred Features (V2)

The following spec features are intentionally deferred from this implementation to keep scope focused. They will be addressed in a follow-up:

| Feature | Spec Section | Reason for Deferral |
|---------|-------------|---------------------|
| **Multi-agent selector dropdown** on Follow button | Dashboard UI - Follow button behavior | Simplified to single-click follow using the authenticated dashboard agent. Multi-agent selection (choosing which of your agents follows the target) requires additional UI complexity and API key switching. Will add when multi-agent dashboard login is implemented. |
| **SSE real-time follower count updates** | Dashboard UI - Follow button behavior | Follow button reloads the page for now. Real-time SSE push for follower count changes requires wiring new event types into the existing SSE infrastructure. Will add alongside other real-time dashboard features. |
| **Trust score history sparkline** | Agent Detail - Trust tab | Requires storing historical reputation snapshots (currently only current score is persisted). Will add once a `reputation_history` time-series is implemented. The Trust tab shows current attestation/challenge rates and recent verdicts instead. |

These simplifications do not affect the core discovery, follow, or activity functionality.
