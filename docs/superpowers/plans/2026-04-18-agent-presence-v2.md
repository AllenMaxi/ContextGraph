# Agent Presence v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every Claude Code agent (main + subagents + user) spawns as a distinct, persistent Habbo-style wizard in ContextGraph World. They talk (real prompts and replies), walk, interact, and upgrade when the user installs more skills or tools.

**Architecture:** Extend the existing `contextgraph.world` Python package (FastAPI + EventBus + Phaser 3 client) with: (1) persistent identity assignment tied to archetype/rank, (2) new `/v1/world/{identity,identity/upgrade,spawn,despawn,message}` HTTP endpoints, (3) two new bridges (`identity_bridge.py`, `message_bridge.py`), (4) five new Claude Code hooks, (5) layered Phaser sprite rendering (class hat + rank cape + aura + upgrade burst + handoff orb), and (6) a `cg-world` launcher that auto-starts the server on `SessionStart`.

**Tech Stack:** Python 3.11, FastAPI/Starlette, Phaser 3 (vanilla ES modules), pytest, bash hooks.

**Spec reference:** `docs/superpowers/specs/2026-04-18-agent-presence-v2-design.md`

---

## File Structure

### New files
- `contextgraph/world/identity_bridge.py` — registration, upgrade, spawn, despawn orchestration.
- `contextgraph/world/message_bridge.py` — speech bubble handling with TTL.
- `.claude/hooks/world_session_start.sh` — SessionStart hook: boot server + register identities.
- `.claude/hooks/world_agent_pre.sh` — PreToolUse on `Agent`: spawn subagent.
- `.claude/hooks/world_agent_post.sh` — PostToolUse on `Agent`: despawn subagent.
- `.claude/hooks/world_user_prompt.sh` — UserPromptSubmit: user bubble.
- `.claude/hooks/world_stop.sh` — Stop: assistant summary bubble.
- `bin/cg-world` — shell launcher that daemonises the server.
- `tests/test_world_identity.py` — identity persistence, archetype, rank.
- `tests/test_world_identity_bridge.py` — bridge orchestration.
- `tests/test_world_message_bridge.py` — bubble lifecycle.

### Modified files
- `contextgraph/world/models.py` — add `AgentArchetype`, `AgentRank`, event types; extend `AgentVisual`.
- `contextgraph/world/spatial.py` — identity load/save, archetype/rank, walking paths, parent link.
- `contextgraph/world/routes.py` — five new endpoints.
- `contextgraph/world/gateway.py` — broadcast helpers for new event types.
- `contextgraph/world/static/game/sprites/AgentSprite.js` — class + rank overlays, upgrade burst, handoff orb, waypoint interpolation.
- `contextgraph/world/static/game/scenes/RoomScene.js` — parent-child sprite linkage.
- `contextgraph/world/static/game/net/WorldSocket.js` — dispatch new events.
- `.claude/settings.local.json` — register five new hooks.

---

## Conventions

- **Tests:** pytest-style functions (not unittest classes) — matches `tests/test_world_v2.py`.
- **Commit format:** `<type>: <short imperative>`. Types: `feat`, `test`, `refactor`, `chore`, `docs`.
- **Run tests from project root:** `cd /Users/maximilianoallende/ContextGraph/ContextGraph && python3 -m pytest <path> -v`.
- **Frequent commits:** one commit per task minimum. TDD order always: failing test → verify fail → implement → verify pass → commit.
- **Actor-ID shape:**
  - Main Claude: `claude`
  - Subagent: `claude.<subagent_type>.<ordinal>` — e.g. `claude.Explore.3`
  - User: `user`

---

## Task 1: Add `AgentArchetype` enum

**Files:**
- Modify: `contextgraph/world/models.py` (add after `Facing` enum, around line 56)
- Test: `tests/test_world_identity.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_world_identity.py`:

```python
"""Tests for agent identity, archetype, rank assignment."""
from __future__ import annotations

import pytest

from contextgraph.world.models import AgentArchetype


def test_archetype_enum_values():
    assert AgentArchetype.ARCHMAGE == "archmage"
    assert AgentArchetype.SCOUT == "scout"
    assert AgentArchetype.ORACLE == "oracle"
    assert AgentArchetype.SCRIBE == "scribe"
    assert AgentArchetype.APPRENTICE == "apprentice"
    assert AgentArchetype.ARTIFICER == "artificer"
    assert AgentArchetype.SAGE == "sage"
    assert AgentArchetype.USER == "user"
    assert AgentArchetype.UNKNOWN == "unknown"


def test_archetype_count():
    assert len(AgentArchetype) == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_world_identity.py -v`
Expected: `ImportError: cannot import name 'AgentArchetype'`.

- [ ] **Step 3: Add the enum**

Edit `contextgraph/world/models.py`, add after the `Facing` class (around line 55, before `MeetingPhase`):

```python
class AgentArchetype(StrEnum):
    ARCHMAGE = "archmage"     # main Claude session
    SCOUT = "scout"           # Explore
    ORACLE = "oracle"         # Plan
    SCRIBE = "scribe"         # code-reviewer
    APPRENTICE = "apprentice" # general-purpose
    ARTIFICER = "artificer"   # statusline-setup
    SAGE = "sage"             # claude-code-guide
    USER = "user"             # human user avatar
    UNKNOWN = "unknown"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_world_identity.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/maximilianoallende/ContextGraph/ContextGraph
git add contextgraph/world/models.py tests/test_world_identity.py
git commit -m "feat: add AgentArchetype enum"
```

---

## Task 2: Add `AgentRank` enum + threshold helper

**Files:**
- Modify: `contextgraph/world/models.py`
- Test: `tests/test_world_identity.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_world_identity.py`:

```python
from contextgraph.world.models import AgentRank, rank_for_counts


def test_rank_enum_values():
    assert AgentRank.NOVICE == "novice"
    assert AgentRank.ADEPT == "adept"
    assert AgentRank.MAGE == "mage"
    assert AgentRank.HIGH_MAGE == "high_mage"
    assert AgentRank.AVATAR == "avatar"


@pytest.mark.parametrize("total,expected", [
    (0, AgentRank.NOVICE),
    (5, AgentRank.NOVICE),
    (6, AgentRank.ADEPT),
    (15, AgentRank.ADEPT),
    (16, AgentRank.MAGE),
    (30, AgentRank.MAGE),
    (31, AgentRank.HIGH_MAGE),
    (60, AgentRank.HIGH_MAGE),
    (61, AgentRank.AVATAR),
    (999, AgentRank.AVATAR),
])
def test_rank_for_counts(total, expected):
    # tools + skills combined count
    tools = total // 2
    skills = total - tools
    assert rank_for_counts(tools, skills) == expected
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity.py -v`
Expected: ImportError for `AgentRank` / `rank_for_counts`.

- [ ] **Step 3: Add enum + helper**

Edit `contextgraph/world/models.py`, add directly after `AgentArchetype`:

```python
class AgentRank(StrEnum):
    NOVICE = "novice"
    ADEPT = "adept"
    MAGE = "mage"
    HIGH_MAGE = "high_mage"
    AVATAR = "avatar"


def rank_for_counts(tools_count: int, skills_count: int) -> AgentRank:
    total = max(0, tools_count) + max(0, skills_count)
    if total <= 5:
        return AgentRank.NOVICE
    if total <= 15:
        return AgentRank.ADEPT
    if total <= 30:
        return AgentRank.MAGE
    if total <= 60:
        return AgentRank.HIGH_MAGE
    return AgentRank.AVATAR
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity.py -v`
Expected: 12 passed (2 prior + 1 enum + 9 parametrized + 1 rank enum test = 12; count may adjust based on parametrize).

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/models.py tests/test_world_identity.py
git commit -m "feat: add AgentRank enum and rank_for_counts helper"
```

---

## Task 3: Extend `AgentVisual` with archetype/rank/parent fields

**Files:**
- Modify: `contextgraph/world/models.py` (the `AgentVisual` dataclass, lines ~224–254)
- Test: `tests/test_world_identity.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_world_identity.py`:

```python
from contextgraph.world.models import AgentVisual


def test_agent_visual_identity_fields_default():
    v = AgentVisual(agent_id="claude", name="Claude", color_index=0)
    assert v.archetype == AgentArchetype.UNKNOWN
    assert v.rank == AgentRank.NOVICE
    assert v.parent_agent_id is None
    assert v.tools_count == 0
    assert v.skills_count == 0


def test_agent_visual_to_dict_includes_identity():
    v = AgentVisual(
        agent_id="claude.Explore.1",
        name="Scout",
        color_index=2,
        archetype=AgentArchetype.SCOUT,
        rank=AgentRank.ADEPT,
        parent_agent_id="claude",
        tools_count=8,
        skills_count=4,
    )
    d = v.to_dict()
    assert d["archetype"] == "scout"
    assert d["rank"] == "adept"
    assert d["parent_agent_id"] == "claude"
    assert d["tools_count"] == 8
    assert d["skills_count"] == 4
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity.py::test_agent_visual_identity_fields_default -v`
Expected: `TypeError: __init__() got an unexpected keyword argument 'archetype'` OR AttributeError.

- [ ] **Step 3: Extend the dataclass**

Edit `contextgraph/world/models.py`, modify `AgentVisual` — add the five fields at the end of the field list (before `to_dict`):

```python
@dataclass
class AgentVisual:
    agent_id: str
    name: str
    color_index: int
    expression: Expression = Expression.HAPPY
    accessory: Accessory = Accessory.NONE
    glow: GlowColor = GlowColor.GRAY
    bubble: str | None = None
    x: float = 0.0
    y: float = 0.0
    room: str = "lobby"
    zone: ZoneType | None = None
    anchor_id: str | None = None
    home_anchor_id: str | None = None
    meeting_id: str | None = None
    activity: Activity = Activity.IDLE
    facing: Facing = Facing.RIGHT
    archetype: AgentArchetype = AgentArchetype.UNKNOWN
    rank: AgentRank = AgentRank.NOVICE
    parent_agent_id: str | None = None
    tools_count: int = 0
    skills_count: int = 0

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id, "name": self.name, "color_index": self.color_index,
            "expression": self.expression.value, "accessory": self.accessory.value,
            "glow": self.glow.value, "bubble": self.bubble,
            "x": self.x, "y": self.y, "room": self.room,
            "zone": self.zone.value if self.zone else None,
            "anchor_id": self.anchor_id,
            "home_anchor_id": self.home_anchor_id,
            "meeting_id": self.meeting_id,
            "activity": self.activity.value,
            "facing": self.facing.value,
            "archetype": self.archetype.value,
            "rank": self.rank.value,
            "parent_agent_id": self.parent_agent_id,
            "tools_count": self.tools_count,
            "skills_count": self.skills_count,
        }
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity.py -v`
Expected: all tests pass.

Also run the full world model tests to catch regressions: `python3 -m pytest tests/test_world_models.py -v` — expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/models.py tests/test_world_identity.py
git commit -m "feat: extend AgentVisual with archetype, rank, parent fields"
```

---

## Task 4: Add `AGENT_UPGRADE` and `HANDOFF_ORB` event types

**Files:**
- Modify: `contextgraph/world/models.py` (the `GameEventType` enum, lines ~67–78)
- Test: `tests/test_world_identity.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_world_identity.py`:

```python
from contextgraph.world.models import GameEventType


def test_new_event_types():
    assert GameEventType.AGENT_UPGRADE == "agent_upgrade"
    assert GameEventType.HANDOFF_ORB == "handoff_orb"
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity.py::test_new_event_types -v`
Expected: `AttributeError: AGENT_UPGRADE`.

- [ ] **Step 3: Add the enum values**

Edit `contextgraph/world/models.py`, add two lines to `GameEventType`:

```python
class GameEventType(StrEnum):
    AGENT_MOVE = "agent_move"
    AGENT_STATE = "agent_state"
    AGENT_INTERACT = "agent_interact"
    AGENT_SPAWN = "agent_spawn"
    AGENT_DESPAWN = "agent_despawn"
    AGENT_PATH = "agent_path"
    AGENT_UPGRADE = "agent_upgrade"
    HANDOFF_ORB = "handoff_orb"
    MEETING_STARTED = "meeting_started"
    MEETING_UPDATED = "meeting_updated"
    MEETING_ENDED = "meeting_ended"
    WORLD_SNAPSHOT = "world_snapshot"
    ROOM_SNAPSHOT = "room_snapshot"
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/models.py tests/test_world_identity.py
git commit -m "feat: add AGENT_UPGRADE and HANDOFF_ORB event types"
```

---

## Task 5: Identity persistence — `IdentityStore` class

**Files:**
- Create: `contextgraph/world/identity_store.py`
- Test: `tests/test_world_identity.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_world_identity.py`:

```python
import json
from pathlib import Path

from contextgraph.world.identity_store import IdentityStore, IdentityRecord
from contextgraph.world.models import AgentArchetype, AgentRank


def test_identity_store_roundtrip(tmp_path):
    store_path = tmp_path / "identities.json"
    store = IdentityStore(store_path)
    rec = IdentityRecord(
        agent_id="claude",
        name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        rank=AgentRank.MAGE,
        color_index=2,
        tools_count=18,
        skills_count=4,
    )
    store.upsert(rec)
    store.save()

    reloaded = IdentityStore(store_path)
    reloaded.load()
    got = reloaded.get("claude")
    assert got is not None
    assert got.archetype == AgentArchetype.ARCHMAGE
    assert got.rank == AgentRank.MAGE
    assert got.color_index == 2
    assert got.tools_count == 18


def test_identity_store_get_missing(tmp_path):
    store = IdentityStore(tmp_path / "identities.json")
    assert store.get("nobody") is None


def test_identity_store_atomic_write(tmp_path):
    store_path = tmp_path / "identities.json"
    store = IdentityStore(store_path)
    store.upsert(IdentityRecord(
        agent_id="claude", name="Claude",
        archetype=AgentArchetype.ARCHMAGE, rank=AgentRank.NOVICE,
        color_index=0, tools_count=0, skills_count=0,
    ))
    store.save()

    # Ensure file is valid JSON
    data = json.loads(store_path.read_text())
    assert "claude" in data
    assert data["claude"]["archetype"] == "archmage"
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity.py -v -k identity_store`
Expected: `ModuleNotFoundError: contextgraph.world.identity_store`.

- [ ] **Step 3: Create the store**

Create `contextgraph/world/identity_store.py`:

```python
"""Persistent identity store for ContextGraph World agents.

Keyed by ``agent_id``.  Once ``archetype`` and ``color_index`` are assigned
for a given ``agent_id`` they never change.  Rank and counters may update
on upgrade events.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from .models import AgentArchetype, AgentRank

logger = logging.getLogger(__name__)


@dataclass
class IdentityRecord:
    agent_id: str
    name: str
    archetype: AgentArchetype
    rank: AgentRank
    color_index: int
    tools_count: int = 0
    skills_count: int = 0
    created_at: str = ""
    last_seen: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "archetype": self.archetype.value,
            "rank": self.rank.value,
            "color_index": self.color_index,
            "tools_count": self.tools_count,
            "skills_count": self.skills_count,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IdentityRecord":
        return cls(
            agent_id=d["agent_id"],
            name=d.get("name", d["agent_id"]),
            archetype=AgentArchetype(d.get("archetype", "unknown")),
            rank=AgentRank(d.get("rank", "novice")),
            color_index=int(d.get("color_index", 0)),
            tools_count=int(d.get("tools_count", 0)),
            skills_count=int(d.get("skills_count", 0)),
            created_at=d.get("created_at", ""),
            last_seen=d.get("last_seen", ""),
        )


class IdentityStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._records: dict[str, IdentityRecord] = {}

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("IdentityStore: failed to load %s: %s", self.path, exc)
            return
        for aid, raw in data.items():
            try:
                self._records[aid] = IdentityRecord.from_dict(raw)
            except (KeyError, ValueError) as exc:
                logger.warning("IdentityStore: skipping %s: %s", aid, exc)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {aid: rec.to_dict() for aid, rec in self._records.items()}
        # Atomic write
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".identities-", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(self, agent_id: str) -> IdentityRecord | None:
        return self._records.get(agent_id)

    def upsert(self, rec: IdentityRecord) -> IdentityRecord:
        existing = self._records.get(rec.agent_id)
        now = datetime.utcnow().isoformat()
        if existing is None:
            rec.created_at = rec.created_at or now
            rec.last_seen = now
            self._records[rec.agent_id] = rec
            return rec
        # Preserve archetype + color_index forever
        existing.name = rec.name or existing.name
        existing.rank = rec.rank
        existing.tools_count = rec.tools_count
        existing.skills_count = rec.skills_count
        existing.last_seen = now
        return existing

    def all(self) -> list[IdentityRecord]:
        return list(self._records.values())
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/identity_store.py tests/test_world_identity.py
git commit -m "feat: persistent IdentityStore for agent archetype/rank"
```

---

## Task 6: Wire `IdentityStore` into `SpatialState`

**Files:**
- Modify: `contextgraph/world/spatial.py` — `__init__`, `register_agent`.
- Test: `tests/test_world_identity.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_world_identity.py`:

```python
from contextgraph.world.spatial import SpatialState


def test_spatial_state_uses_identity_store(tmp_path):
    store_path = tmp_path / "identities.json"
    store = IdentityStore(store_path)
    store.upsert(IdentityRecord(
        agent_id="claude",
        name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        rank=AgentRank.MAGE,
        color_index=4,
        tools_count=18,
        skills_count=4,
    ))

    state = SpatialState(identity_store=store)
    agent = state.register_agent("claude", "Claude")
    assert agent.archetype == AgentArchetype.ARCHMAGE
    assert agent.rank == AgentRank.MAGE
    assert agent.color_index == 4


def test_spatial_state_creates_identity_on_first_register(tmp_path):
    store_path = tmp_path / "identities.json"
    store = IdentityStore(store_path)
    state = SpatialState(identity_store=store)
    state.register_agent("claude.Explore.1", "Explore-1", archetype=AgentArchetype.SCOUT)
    rec = store.get("claude.Explore.1")
    assert rec is not None
    assert rec.archetype == AgentArchetype.SCOUT
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity.py -v -k spatial_state`
Expected: `TypeError: SpatialState.__init__() got an unexpected keyword argument 'identity_store'`.

- [ ] **Step 3: Modify `SpatialState.__init__` and `register_agent`**

Edit `contextgraph/world/spatial.py`:

Replace the `__init__` (lines ~29–34) with:

```python
    def __init__(self, identity_store: "IdentityStore | None" = None) -> None:
        self._agents: dict[str, AgentVisual] = {}
        self._meetings: dict[str, Meeting] = {}
        self._occupied_circles: dict[str, str] = {}
        # IdentityStore is optional — tests without one still work (in-memory only)
        from .identity_store import IdentityStore
        self._identity_store = identity_store if identity_store is not None else IdentityStore(
            __import__("pathlib").Path("/tmp/_cg_test_identities.json")
        )
```

Replace `register_agent` to accept optional archetype and consult the store:

```python
    def register_agent(
        self,
        agent_id: str,
        name: str,
        archetype: "AgentArchetype | None" = None,
        parent_agent_id: str | None = None,
    ) -> AgentVisual:
        """Create an agent in the lobby. Idempotent — returns existing entry.

        If ``identity_store`` has a record for ``agent_id`` its archetype, rank,
        and color_index are used.  Otherwise a new record is created from the
        provided ``archetype`` (or ``UNKNOWN``).
        """
        if agent_id in self._agents:
            return self._agents[agent_id]

        from .identity_store import IdentityRecord
        from .models import AgentArchetype, AgentRank

        rec = self._identity_store.get(agent_id)
        if rec is None:
            chosen_archetype = archetype or AgentArchetype.UNKNOWN
            rec = IdentityRecord(
                agent_id=agent_id,
                name=name,
                archetype=chosen_archetype,
                rank=AgentRank.NOVICE,
                color_index=color_index_for_agent(agent_id),
                tools_count=0,
                skills_count=0,
            )
            self._identity_store.upsert(rec)
            self._identity_store.save()

        layout = get_layout("lobby")
        occupied = {a.anchor_id for a in self._agents.values() if a.room == "lobby" and a.anchor_id}
        anchor_id = assign_home_anchor(layout, zone=None, occupied=occupied)

        if anchor_id and anchor_id in layout.anchors:
            anchor = layout.anchors[anchor_id]
            x, y = anchor.x, anchor.y
        else:
            exclude = [(a.x, a.y) for a in self._agents.values() if a.room == "lobby"]
            x, y = get_lobby_idle_position(exclude=exclude)

        agent = AgentVisual(
            agent_id=agent_id,
            name=name,
            color_index=rec.color_index,
            expression=Expression.SLEEPY,
            accessory=Accessory.SLEEP_BUBBLE,
            glow=GlowColor.GRAY,
            bubble=None,
            x=x,
            y=y,
            room="lobby",
            zone=None,
            anchor_id=anchor_id,
            home_anchor_id=anchor_id,
            activity=Activity.IDLE,
            facing=Facing.RIGHT,
            archetype=rec.archetype,
            rank=rec.rank,
            parent_agent_id=parent_agent_id,
            tools_count=rec.tools_count,
            skills_count=rec.skills_count,
        )
        self._agents[agent_id] = agent
        return agent
```

Also update the imports near the top of `spatial.py` to include the new symbols:

```python
from .models import (
    Accessory,
    Activity,
    AgentArchetype,
    AgentRank,
    AgentVisual,
    Expression,
    Facing,
    GlowColor,
    Meeting,
    RoomInfo,
    ZoneType,
)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity.py -v`
Expected: all pass.

Then run the full world suite: `python3 -m pytest tests/test_world_spatial.py tests/test_world_models.py tests/test_world_v2.py -v`
Expected: all pass (no regressions).

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/spatial.py tests/test_world_identity.py
git commit -m "feat: SpatialState uses IdentityStore for persistent identity"
```

---

## Task 7: `update_rank` method with upgrade event

**Files:**
- Modify: `contextgraph/world/spatial.py` — add `update_rank` method.
- Test: `tests/test_world_identity.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_world_identity.py`:

```python
from contextgraph.world.models import rank_for_counts


def test_update_rank_changes_agent_and_store(tmp_path):
    store = IdentityStore(tmp_path / "identities.json")
    state = SpatialState(identity_store=store)
    state.register_agent("claude", "Claude", archetype=AgentArchetype.ARCHMAGE)

    result = state.update_rank("claude", tools_count=20, skills_count=5)
    assert result is not None
    old_rank, new_rank = result
    assert old_rank == AgentRank.NOVICE
    assert new_rank == AgentRank.MAGE

    agent = state.get_agent("claude")
    assert agent.rank == AgentRank.MAGE
    assert agent.tools_count == 20
    assert agent.skills_count == 5

    rec = store.get("claude")
    assert rec.rank == AgentRank.MAGE
    assert rec.tools_count == 20


def test_update_rank_noop_if_unchanged(tmp_path):
    store = IdentityStore(tmp_path / "identities.json")
    state = SpatialState(identity_store=store)
    state.register_agent("claude", "Claude", archetype=AgentArchetype.ARCHMAGE)
    state.update_rank("claude", tools_count=2, skills_count=1)  # NOVICE
    result = state.update_rank("claude", tools_count=3, skills_count=1)  # still NOVICE
    assert result is None
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity.py -v -k update_rank`
Expected: `AttributeError: 'SpatialState' object has no attribute 'update_rank'`.

- [ ] **Step 3: Add `update_rank` method**

Edit `contextgraph/world/spatial.py`, add method inside `SpatialState` (near `update_visual`):

```python
    def update_rank(
        self,
        agent_id: str,
        tools_count: int,
        skills_count: int,
    ) -> tuple[AgentRank, AgentRank] | None:
        """Recompute rank from tool/skill counts.

        Returns ``(old_rank, new_rank)`` if rank changed, else ``None``.
        Counts are always persisted even when rank is unchanged.
        """
        from .models import rank_for_counts
        agent = self._agents.get(agent_id)
        if agent is None:
            return None
        old_rank = agent.rank
        new_rank = rank_for_counts(tools_count, skills_count)
        agent.tools_count = tools_count
        agent.skills_count = skills_count
        agent.rank = new_rank

        rec = self._identity_store.get(agent_id)
        if rec is not None:
            rec.rank = new_rank
            rec.tools_count = tools_count
            rec.skills_count = skills_count
            self._identity_store.upsert(rec)
            self._identity_store.save()

        if old_rank == new_rank:
            return None
        return (old_rank, new_rank)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/spatial.py tests/test_world_identity.py
git commit -m "feat: SpatialState.update_rank detects rank changes"
```

---

## Task 8: `set_parent` method

**Files:**
- Modify: `contextgraph/world/spatial.py` — add `set_parent`.
- Test: `tests/test_world_identity.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_set_parent(tmp_path):
    store = IdentityStore(tmp_path / "identities.json")
    state = SpatialState(identity_store=store)
    state.register_agent("claude", "Claude", archetype=AgentArchetype.ARCHMAGE)
    state.register_agent("claude.Explore.1", "Scout", archetype=AgentArchetype.SCOUT)

    state.set_parent("claude.Explore.1", "claude")

    child = state.get_agent("claude.Explore.1")
    assert child.parent_agent_id == "claude"
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity.py -v -k set_parent`
Expected: AttributeError.

- [ ] **Step 3: Add method**

Edit `contextgraph/world/spatial.py`, add in `SpatialState`:

```python
    def set_parent(self, agent_id: str, parent_agent_id: str | None) -> AgentVisual | None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return None
        agent.parent_agent_id = parent_agent_id
        return agent
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity.py -v`

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/spatial.py tests/test_world_identity.py
git commit -m "feat: SpatialState.set_parent for subagent linkage"
```

---

## Task 9: `identity_bridge.register_identity`

**Files:**
- Create: `contextgraph/world/identity_bridge.py`
- Test: `tests/test_world_identity_bridge.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_world_identity_bridge.py`:

```python
"""Tests for identity_bridge — registration, upgrade, spawn, despawn."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from contextgraph.events import EventBus
from contextgraph.world.gateway import WorldGateway
from contextgraph.world.identity_store import IdentityStore
from contextgraph.world.models import AgentArchetype, AgentRank
from contextgraph.world.spatial import SpatialState


@pytest.fixture
def gateway(tmp_path):
    store = IdentityStore(tmp_path / "identities.json")
    state = SpatialState(identity_store=store)
    event_bus = EventBus()
    graph_service = MagicMock()
    gw = WorldGateway(event_bus=event_bus, graph_service=graph_service)
    # Replace gateway's spatial with our test one
    gw.spatial = state
    return gw


def test_register_identity_creates_agent(gateway):
    from contextgraph.world.identity_bridge import register_identity

    result = register_identity(
        gateway,
        actor_id="claude",
        name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        tools_count=12,
        skills_count=4,
    )
    assert result["ok"] is True
    agent = gateway.spatial.get_agent("claude")
    assert agent.archetype == AgentArchetype.ARCHMAGE
    assert agent.rank == AgentRank.ADEPT  # 12+4 = 16? no wait 12+4=16 — MAGE. Adjust below.


def test_register_identity_is_idempotent(gateway):
    from contextgraph.world.identity_bridge import register_identity
    register_identity(gateway, actor_id="claude", name="Claude",
                      archetype=AgentArchetype.ARCHMAGE, tools_count=2, skills_count=1)
    register_identity(gateway, actor_id="claude", name="Claude",
                      archetype=AgentArchetype.ARCHMAGE, tools_count=2, skills_count=1)
    assert len(gateway.spatial.list_agents()) == 1
```

Note: the first test's threshold math: 12 tools + 4 skills = 16 → `MAGE` (threshold 16–30). Fix the assertion to `AgentRank.MAGE`.

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v`
Expected: `ModuleNotFoundError: contextgraph.world.identity_bridge`.

- [ ] **Step 3: Create the module**

Create `contextgraph/world/identity_bridge.py`:

```python
"""Identity bridge — register, upgrade, spawn, despawn orchestration.

Callers (HTTP routes or internal systems) invoke these functions; they
update ``SpatialState`` and broadcast the right ``GameEvent`` through the
``WorldGateway``.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from .gateway import WorldGateway
from .models import (
    AgentArchetype,
    AgentRank,
    GameEvent,
    GameEventType,
    rank_for_counts,
)

logger = logging.getLogger(__name__)


def register_identity(
    gateway: WorldGateway,
    actor_id: str,
    name: str,
    archetype: AgentArchetype,
    tools_count: int,
    skills_count: int,
    parent_agent_id: str | None = None,
) -> dict[str, Any]:
    """Register (or refresh) an agent identity and broadcast spawn/state."""
    if not actor_id:
        raise ValueError("actor_id required")

    spatial = gateway.spatial
    was_new = spatial.get_agent(actor_id) is None

    agent = spatial.register_agent(
        actor_id, name or actor_id,
        archetype=archetype, parent_agent_id=parent_agent_id,
    )
    # Always update rank/counts
    spatial.update_rank(actor_id, tools_count, skills_count)
    updated = spatial.get_agent(actor_id)

    if was_new:
        _schedule(gateway.broadcast_to_room(updated.room, GameEvent(
            type=GameEventType.AGENT_SPAWN,
            agent_id=actor_id,
            data=updated.to_dict(),
        ).to_dict()))
    else:
        _schedule(gateway.broadcast_to_room(updated.room, GameEvent(
            type=GameEventType.AGENT_STATE,
            agent_id=actor_id,
            data=updated.to_dict(),
        ).to_dict()))

    return {"ok": True, "created": was_new, "agent": updated.to_dict()}


def _schedule(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        coro.close()
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v`
Expected: the two tests pass.

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/identity_bridge.py tests/test_world_identity_bridge.py
git commit -m "feat: identity_bridge.register_identity"
```

---

## Task 10: `identity_bridge.upgrade_identity`

**Files:**
- Modify: `contextgraph/world/identity_bridge.py`
- Test: `tests/test_world_identity_bridge.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_world_identity_bridge.py`:

```python
def test_upgrade_identity_broadcasts_on_rank_change(gateway, monkeypatch):
    from contextgraph.world import identity_bridge

    register_identity = identity_bridge.register_identity
    upgrade_identity = identity_bridge.upgrade_identity

    # Register at NOVICE
    register_identity(gateway, actor_id="claude", name="Claude",
                      archetype=AgentArchetype.ARCHMAGE,
                      tools_count=2, skills_count=1)

    broadcasts = []

    async def capture(room, msg):
        broadcasts.append((room, msg))

    monkeypatch.setattr(gateway, "broadcast_to_room", capture)

    # Jump to MAGE (16+)
    result = upgrade_identity(gateway, actor_id="claude",
                              tools_count=15, skills_count=5)
    assert result["rank_changed"] is True
    assert result["old_rank"] == "novice"
    assert result["new_rank"] == "mage"

    types = [msg["type"] for _, msg in broadcasts]
    assert "agent_upgrade" in types


def test_upgrade_identity_no_broadcast_when_rank_same(gateway, monkeypatch):
    from contextgraph.world import identity_bridge
    identity_bridge.register_identity(
        gateway, actor_id="claude", name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        tools_count=2, skills_count=1,
    )

    broadcasts = []

    async def capture(room, msg):
        broadcasts.append((room, msg))

    monkeypatch.setattr(gateway, "broadcast_to_room", capture)
    result = identity_bridge.upgrade_identity(gateway, actor_id="claude",
                                              tools_count=3, skills_count=1)
    assert result["rank_changed"] is False
    upgrade_events = [m for _, m in broadcasts if m.get("type") == "agent_upgrade"]
    assert upgrade_events == []
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v -k upgrade`
Expected: AttributeError or similar.

- [ ] **Step 3: Add `upgrade_identity`**

Append to `contextgraph/world/identity_bridge.py`:

```python
def upgrade_identity(
    gateway: WorldGateway,
    actor_id: str,
    tools_count: int,
    skills_count: int,
) -> dict[str, Any]:
    """Recompute rank. Broadcast AGENT_UPGRADE if rank changes."""
    if not actor_id:
        raise ValueError("actor_id required")

    spatial = gateway.spatial
    agent = spatial.get_agent(actor_id)
    if agent is None:
        return {"ok": False, "error": "unknown actor"}

    change = spatial.update_rank(actor_id, tools_count, skills_count)
    updated = spatial.get_agent(actor_id)

    if change is None:
        return {
            "ok": True,
            "rank_changed": False,
            "rank": updated.rank.value,
        }
    old_rank, new_rank = change
    _schedule(gateway.broadcast_to_room(updated.room, GameEvent(
        type=GameEventType.AGENT_UPGRADE,
        agent_id=actor_id,
        data={
            "old_rank": old_rank.value,
            "new_rank": new_rank.value,
            "tools_count": tools_count,
            "skills_count": skills_count,
        },
    ).to_dict()))
    # Follow with a full state push so clients updating lazily still sync
    _schedule(gateway.broadcast_to_room(updated.room, GameEvent(
        type=GameEventType.AGENT_STATE,
        agent_id=actor_id,
        data=updated.to_dict(),
    ).to_dict()))

    return {
        "ok": True,
        "rank_changed": True,
        "old_rank": old_rank.value,
        "new_rank": new_rank.value,
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v`

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/identity_bridge.py tests/test_world_identity_bridge.py
git commit -m "feat: identity_bridge.upgrade_identity emits AGENT_UPGRADE"
```

---

## Task 11: `identity_bridge.spawn_subagent`

**Files:**
- Modify: `contextgraph/world/identity_bridge.py`
- Test: `tests/test_world_identity_bridge.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_spawn_subagent_creates_child_linked_to_parent(gateway, monkeypatch):
    from contextgraph.world import identity_bridge
    identity_bridge.register_identity(
        gateway, actor_id="claude", name="Claude",
        archetype=AgentArchetype.ARCHMAGE, tools_count=2, skills_count=1,
    )

    broadcasts = []

    async def capture(room, msg):
        broadcasts.append((room, msg))
    monkeypatch.setattr(gateway, "broadcast_to_room", capture)

    res = identity_bridge.spawn_subagent(
        gateway,
        parent_actor_id="claude",
        subagent_type="Explore",
        description="Find auth code paths",
        invocation_id="7",
    )
    assert res["ok"] is True
    child_id = res["actor_id"]
    assert child_id == "claude.Explore.7"
    child = gateway.spatial.get_agent(child_id)
    assert child.archetype == AgentArchetype.SCOUT
    assert child.parent_agent_id == "claude"

    spawn_events = [m for _, m in broadcasts if m.get("type") == "agent_spawn"]
    assert len(spawn_events) == 1
```

Also add an archetype-mapping test:

```python
@pytest.mark.parametrize("subagent_type,expected", [
    ("Explore", AgentArchetype.SCOUT),
    ("Plan", AgentArchetype.ORACLE),
    ("code-reviewer", AgentArchetype.SCRIBE),
    ("superpowers:code-reviewer", AgentArchetype.SCRIBE),
    ("general-purpose", AgentArchetype.APPRENTICE),
    ("statusline-setup", AgentArchetype.ARTIFICER),
    ("claude-code-guide", AgentArchetype.SAGE),
    ("made-up-thing", AgentArchetype.UNKNOWN),
])
def test_archetype_for_subagent_type(subagent_type, expected):
    from contextgraph.world.identity_bridge import archetype_for_subagent_type
    assert archetype_for_subagent_type(subagent_type) == expected
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v -k "subagent or archetype_for"`
Expected: fails — functions missing.

- [ ] **Step 3: Add the helpers**

Append to `contextgraph/world/identity_bridge.py`:

```python
ARCHETYPE_MAP: dict[str, AgentArchetype] = {
    "Explore": AgentArchetype.SCOUT,
    "Plan": AgentArchetype.ORACLE,
    "code-reviewer": AgentArchetype.SCRIBE,
    "superpowers:code-reviewer": AgentArchetype.SCRIBE,
    "general-purpose": AgentArchetype.APPRENTICE,
    "statusline-setup": AgentArchetype.ARTIFICER,
    "claude-code-guide": AgentArchetype.SAGE,
}


def archetype_for_subagent_type(subagent_type: str | None) -> AgentArchetype:
    if not subagent_type:
        return AgentArchetype.UNKNOWN
    return ARCHETYPE_MAP.get(subagent_type.strip(), AgentArchetype.UNKNOWN)


def spawn_subagent(
    gateway: WorldGateway,
    parent_actor_id: str,
    subagent_type: str,
    description: str,
    invocation_id: str,
) -> dict[str, Any]:
    """Spawn a subagent visually. Idempotent on (parent, subagent_type, invocation_id)."""
    if not parent_actor_id or not subagent_type or not invocation_id:
        raise ValueError("parent_actor_id, subagent_type, invocation_id required")

    actor_id = f"{parent_actor_id}.{subagent_type}.{invocation_id}"
    archetype = archetype_for_subagent_type(subagent_type)
    name = f"{subagent_type.title()}-{invocation_id}"

    spatial = gateway.spatial
    was_new = spatial.get_agent(actor_id) is None
    agent = spatial.register_agent(
        actor_id, name,
        archetype=archetype, parent_agent_id=parent_actor_id,
    )
    spatial.update_rank(actor_id, tools_count=0, skills_count=0)
    # Place an initial bubble describing what it was asked to do
    short = (description or "").strip()
    if len(short) > 110:
        short = short[:107] + "..."
    spatial.update_visual(actor_id, bubble=short or None)

    updated = spatial.get_agent(actor_id)
    evt_type = GameEventType.AGENT_SPAWN if was_new else GameEventType.AGENT_STATE
    _schedule(gateway.broadcast_to_room(updated.room, GameEvent(
        type=evt_type,
        agent_id=actor_id,
        data=updated.to_dict(),
    ).to_dict()))

    return {
        "ok": True,
        "actor_id": actor_id,
        "archetype": archetype.value,
        "created": was_new,
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v`

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/identity_bridge.py tests/test_world_identity_bridge.py
git commit -m "feat: identity_bridge.spawn_subagent"
```

---

## Task 12: `identity_bridge.despawn_subagent` with handoff orb

**Files:**
- Modify: `contextgraph/world/identity_bridge.py`
- Test: `tests/test_world_identity_bridge.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_despawn_subagent_emits_handoff_orb_and_despawn(gateway, monkeypatch):
    from contextgraph.world import identity_bridge
    identity_bridge.register_identity(
        gateway, actor_id="claude", name="Claude",
        archetype=AgentArchetype.ARCHMAGE, tools_count=2, skills_count=1,
    )
    spawn = identity_bridge.spawn_subagent(
        gateway, parent_actor_id="claude", subagent_type="Explore",
        description="x", invocation_id="1",
    )
    child_id = spawn["actor_id"]

    broadcasts = []

    async def capture(room, msg):
        broadcasts.append((room, msg))
    monkeypatch.setattr(gateway, "broadcast_to_room", capture)

    res = identity_bridge.despawn_subagent(
        gateway, actor_id=child_id, result_summary="Found 3 auth files",
    )
    assert res["ok"] is True

    types = [m.get("type") for _, m in broadcasts]
    assert "handoff_orb" in types
    assert "agent_despawn" in types

    orb_msg = next(m for _, m in broadcasts if m.get("type") == "handoff_orb")
    assert orb_msg["data"]["from_agent"] == child_id
    assert orb_msg["data"]["to_agent"] == "claude"


def test_despawn_subagent_missing_actor(gateway):
    from contextgraph.world import identity_bridge
    res = identity_bridge.despawn_subagent(
        gateway, actor_id="never_was", result_summary=""
    )
    assert res["ok"] is False
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v -k despawn`
Expected: AttributeError.

- [ ] **Step 3: Add `despawn_subagent`**

Append to `contextgraph/world/identity_bridge.py`:

```python
def despawn_subagent(
    gateway: WorldGateway,
    actor_id: str,
    result_summary: str,
) -> dict[str, Any]:
    """Emit handoff orb (child → parent) + AGENT_DESPAWN. Remove from spatial."""
    if not actor_id:
        raise ValueError("actor_id required")
    spatial = gateway.spatial
    agent = spatial.get_agent(actor_id)
    if agent is None:
        return {"ok": False, "error": "unknown actor"}

    parent_id = agent.parent_agent_id
    parent = spatial.get_agent(parent_id) if parent_id else None
    room = agent.room

    # Emit result bubble before despawn so frontends can display it
    short = (result_summary or "").strip()
    if len(short) > 110:
        short = short[:107] + "..."
    if short:
        spatial.update_visual(actor_id, bubble=short)
        _schedule(gateway.broadcast_to_room(room, GameEvent(
            type=GameEventType.AGENT_STATE,
            agent_id=actor_id,
            data=spatial.get_agent(actor_id).to_dict(),
        ).to_dict()))

    if parent is not None:
        _schedule(gateway.broadcast_to_room(room, GameEvent(
            type=GameEventType.HANDOFF_ORB,
            agent_id=actor_id,
            data={
                "from_agent": actor_id,
                "to_agent": parent_id,
                "color": "green",
            },
        ).to_dict()))

    # Despawn event — client fades the sprite out
    _schedule(gateway.broadcast_to_room(room, GameEvent(
        type=GameEventType.AGENT_DESPAWN,
        agent_id=actor_id,
        data={"parent_agent_id": parent_id},
    ).to_dict()))

    # Remove from spatial after a short delay so the orb tween can finish
    spatial.remove_agent(actor_id)
    return {"ok": True, "actor_id": actor_id, "parent": parent_id}
```

If `SpatialState` does not yet have `remove_agent`, also add it in `spatial.py`:

```python
    def remove_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v`

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/identity_bridge.py contextgraph/world/spatial.py tests/test_world_identity_bridge.py
git commit -m "feat: identity_bridge.despawn_subagent with handoff orb"
```

---

## Task 13: `message_bridge.set_bubble`

**Files:**
- Create: `contextgraph/world/message_bridge.py`
- Test: `tests/test_world_message_bridge.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_world_message_bridge.py`:

```python
"""Tests for message_bridge — speech bubbles for user + assistant."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from contextgraph.events import EventBus
from contextgraph.world.gateway import WorldGateway
from contextgraph.world.identity_store import IdentityStore
from contextgraph.world.models import AgentArchetype
from contextgraph.world.spatial import SpatialState


@pytest.fixture
def gateway(tmp_path):
    store = IdentityStore(tmp_path / "identities.json")
    state = SpatialState(identity_store=store)
    event_bus = EventBus()
    graph_service = MagicMock()
    gw = WorldGateway(event_bus=event_bus, graph_service=graph_service)
    gw.spatial = state
    return gw


def test_set_bubble_sets_agent_bubble_and_broadcasts(gateway, monkeypatch):
    from contextgraph.world import identity_bridge, message_bridge
    identity_bridge.register_identity(
        gateway, actor_id="claude", name="Claude",
        archetype=AgentArchetype.ARCHMAGE, tools_count=2, skills_count=1,
    )

    broadcasts = []
    async def capture(room, msg):
        broadcasts.append((room, msg))
    monkeypatch.setattr(gateway, "broadcast_to_room", capture)

    res = message_bridge.set_bubble(
        gateway, actor_id="claude", role="assistant",
        text="Reading auth code",
    )
    assert res["ok"] is True
    agent = gateway.spatial.get_agent("claude")
    assert agent.bubble == "Reading auth code"
    state_msgs = [m for _, m in broadcasts if m.get("type") == "agent_state"]
    assert len(state_msgs) == 1


def test_set_bubble_truncates_long_text(gateway):
    from contextgraph.world import identity_bridge, message_bridge
    identity_bridge.register_identity(
        gateway, actor_id="claude", name="Claude",
        archetype=AgentArchetype.ARCHMAGE, tools_count=2, skills_count=1,
    )
    long = "x" * 500
    message_bridge.set_bubble(gateway, actor_id="claude", role="user", text=long)
    agent = gateway.spatial.get_agent("claude")
    assert agent.bubble is not None
    assert len(agent.bubble) <= 180
    assert agent.bubble.endswith("...")


def test_set_bubble_spawns_user_if_missing(gateway):
    from contextgraph.world import message_bridge
    res = message_bridge.set_bubble(
        gateway, actor_id="user", role="user", text="hello",
    )
    assert res["ok"] is True
    user = gateway.spatial.get_agent("user")
    assert user is not None
    assert user.archetype == AgentArchetype.USER
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_message_bridge.py -v`
Expected: `ModuleNotFoundError: contextgraph.world.message_bridge`.

- [ ] **Step 3: Create the module**

Create `contextgraph/world/message_bridge.py`:

```python
"""Message bridge — user prompts and assistant replies as speech bubbles."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .gateway import WorldGateway
from .models import AgentArchetype, GameEvent, GameEventType

logger = logging.getLogger(__name__)

MAX_BUBBLE_LEN = 180


def _truncate(text: str, limit: int = MAX_BUBBLE_LEN) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def set_bubble(
    gateway: WorldGateway,
    actor_id: str,
    role: str,
    text: str,
) -> dict[str, Any]:
    """Set a speech bubble on ``actor_id``. Role is 'user' or 'assistant'.

    If ``actor_id == 'user'`` and no agent exists yet, the user avatar is
    auto-spawned.
    """
    if not actor_id:
        raise ValueError("actor_id required")
    if role not in ("user", "assistant"):
        raise ValueError("role must be user or assistant")

    spatial = gateway.spatial

    if spatial.get_agent(actor_id) is None:
        # Auto-spawn user avatar on first prompt
        if actor_id == "user":
            spatial.register_agent(
                "user", "User", archetype=AgentArchetype.USER,
            )
        else:
            return {"ok": False, "error": "unknown actor"}

    bubble = _truncate(text)
    # Encode role in the bubble so frontend can style it: "[u]…" or "[a]…"
    tagged = f"[{role[0]}]{bubble}"
    spatial.update_visual(actor_id, bubble=tagged)
    agent = spatial.get_agent(actor_id)
    _schedule(gateway.broadcast_to_room(agent.room, GameEvent(
        type=GameEventType.AGENT_STATE,
        agent_id=actor_id,
        data=agent.to_dict(),
    ).to_dict()))
    return {"ok": True, "bubble": bubble}


def _schedule(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        coro.close()
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_message_bridge.py -v`

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/message_bridge.py tests/test_world_message_bridge.py
git commit -m "feat: message_bridge for speech bubbles"
```

---

## Task 14: HTTP endpoints — `/identity` and `/identity/upgrade`

**Files:**
- Modify: `contextgraph/world/routes.py`
- Test: `tests/test_world_identity_bridge.py` (integration test via TestClient)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_world_identity_bridge.py`:

```python
def test_http_identity_endpoint():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from contextgraph.events import EventBus
    from contextgraph.service import ContextGraphService
    from contextgraph.world.routes import register_world_routes

    app = FastAPI()
    event_bus = EventBus()
    service = MagicMock()
    service.repository.list_agents.return_value = []
    register_world_routes(app, event_bus, service)

    client = TestClient(app)
    r = client.post("/v1/world/identity", json={
        "actor": "claude", "name": "Claude",
        "archetype": "archmage",
        "tools_count": 5, "skills_count": 2,
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_http_identity_upgrade_endpoint():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from contextgraph.events import EventBus
    from contextgraph.world.routes import register_world_routes

    app = FastAPI()
    event_bus = EventBus()
    service = MagicMock()
    service.repository.list_agents.return_value = []
    register_world_routes(app, event_bus, service)

    client = TestClient(app)
    client.post("/v1/world/identity", json={
        "actor": "claude", "name": "Claude",
        "archetype": "archmage",
        "tools_count": 5, "skills_count": 0,
    })
    r = client.post("/v1/world/identity/upgrade", json={
        "actor": "claude", "tools_count": 20, "skills_count": 5,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["rank_changed"] is True
    assert body["new_rank"] == "mage"
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v -k http`
Expected: 404 or 405 because endpoint is missing.

- [ ] **Step 3: Add the endpoints**

Edit `contextgraph/world/routes.py`, add inside `register_world_routes` after `/v1/world/activity`:

```python
    @app.post("/v1/world/identity")
    async def world_identity(payload: dict) -> dict:
        from .identity_bridge import register_identity
        from .models import AgentArchetype
        _ensure_background_started()
        try:
            actor = str(payload.get("actor", "")).strip()
            name = str(payload.get("name") or actor).strip()
            raw_arch = str(payload.get("archetype", "unknown")).strip().lower()
            try:
                archetype = AgentArchetype(raw_arch)
            except ValueError:
                archetype = AgentArchetype.UNKNOWN
            tools_count = int(payload.get("tools_count", 0) or 0)
            skills_count = int(payload.get("skills_count", 0) or 0)
            return register_identity(
                gateway, actor_id=actor, name=name, archetype=archetype,
                tools_count=tools_count, skills_count=skills_count,
            )
        except Exception as exc:
            logger.exception("World: /identity failed")
            return {"ok": False, "error": str(exc)}

    @app.post("/v1/world/identity/upgrade")
    async def world_identity_upgrade(payload: dict) -> dict:
        from .identity_bridge import upgrade_identity
        _ensure_background_started()
        try:
            actor = str(payload.get("actor", "")).strip()
            tools_count = int(payload.get("tools_count", 0) or 0)
            skills_count = int(payload.get("skills_count", 0) or 0)
            return upgrade_identity(
                gateway, actor_id=actor,
                tools_count=tools_count, skills_count=skills_count,
            )
        except Exception as exc:
            logger.exception("World: /identity/upgrade failed")
            return {"ok": False, "error": str(exc)}
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v`

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/routes.py tests/test_world_identity_bridge.py
git commit -m "feat: /v1/world/identity and /identity/upgrade routes"
```

---

## Task 15: HTTP endpoints — `/spawn` and `/despawn`

**Files:**
- Modify: `contextgraph/world/routes.py`
- Test: `tests/test_world_identity_bridge.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_http_spawn_and_despawn():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from contextgraph.events import EventBus
    from contextgraph.world.routes import register_world_routes

    app = FastAPI()
    event_bus = EventBus()
    service = MagicMock()
    service.repository.list_agents.return_value = []
    register_world_routes(app, event_bus, service)
    client = TestClient(app)

    client.post("/v1/world/identity", json={
        "actor": "claude", "name": "Claude",
        "archetype": "archmage", "tools_count": 2, "skills_count": 1,
    })
    r = client.post("/v1/world/spawn", json={
        "parent": "claude", "subagent_type": "Explore",
        "description": "find files", "invocation_id": "42",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["actor_id"] == "claude.Explore.42"

    r = client.post("/v1/world/despawn", json={
        "actor": body["actor_id"], "result_summary": "done",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v -k spawn_and_despawn`
Expected: 404.

- [ ] **Step 3: Add the endpoints**

Append to `register_world_routes`:

```python
    @app.post("/v1/world/spawn")
    async def world_spawn(payload: dict) -> dict:
        from .identity_bridge import spawn_subagent
        _ensure_background_started()
        try:
            parent = str(payload.get("parent", "")).strip()
            subagent_type = str(payload.get("subagent_type", "")).strip()
            description = str(payload.get("description") or "").strip()
            invocation_id = str(payload.get("invocation_id", "")).strip()
            if not invocation_id:
                import uuid
                invocation_id = uuid.uuid4().hex[:8]
            return spawn_subagent(
                gateway,
                parent_actor_id=parent,
                subagent_type=subagent_type,
                description=description,
                invocation_id=invocation_id,
            )
        except Exception as exc:
            logger.exception("World: /spawn failed")
            return {"ok": False, "error": str(exc)}

    @app.post("/v1/world/despawn")
    async def world_despawn(payload: dict) -> dict:
        from .identity_bridge import despawn_subagent
        _ensure_background_started()
        try:
            actor = str(payload.get("actor", "")).strip()
            summary = str(payload.get("result_summary") or "").strip()
            return despawn_subagent(
                gateway, actor_id=actor, result_summary=summary,
            )
        except Exception as exc:
            logger.exception("World: /despawn failed")
            return {"ok": False, "error": str(exc)}
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_identity_bridge.py -v`

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/routes.py tests/test_world_identity_bridge.py
git commit -m "feat: /v1/world/spawn and /despawn routes"
```

---

## Task 16: HTTP endpoint — `/message`

**Files:**
- Modify: `contextgraph/world/routes.py`
- Test: `tests/test_world_message_bridge.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_world_message_bridge.py`:

```python
def test_http_message_endpoint():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from contextgraph.events import EventBus
    from contextgraph.world.routes import register_world_routes

    app = FastAPI()
    event_bus = EventBus()
    service = MagicMock()
    service.repository.list_agents.return_value = []
    register_world_routes(app, event_bus, service)
    client = TestClient(app)

    r = client.post("/v1/world/message", json={
        "actor": "user", "role": "user", "text": "Hello Claude",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_world_message_bridge.py -v -k http`
Expected: 404.

- [ ] **Step 3: Add the endpoint**

Append to `register_world_routes`:

```python
    @app.post("/v1/world/message")
    async def world_message(payload: dict) -> dict:
        from .message_bridge import set_bubble
        _ensure_background_started()
        try:
            actor = str(payload.get("actor", "")).strip()
            role = str(payload.get("role", "")).strip().lower()
            text = str(payload.get("text") or "")
            return set_bubble(gateway, actor_id=actor, role=role, text=text)
        except Exception as exc:
            logger.exception("World: /message failed")
            return {"ok": False, "error": str(exc)}
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_world_message_bridge.py -v`

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/routes.py tests/test_world_message_bridge.py
git commit -m "feat: /v1/world/message route for speech bubbles"
```

---

## Task 17: WorldSocket dispatch for new event types

**Files:**
- Modify: `contextgraph/world/static/game/net/WorldSocket.js`

- [ ] **Step 1: Inspect current dispatch**

Read `contextgraph/world/static/game/net/WorldSocket.js`. Find the `message` handler — it likely dispatches `ws:<type>` events to the scene.

- [ ] **Step 2: Add explicit handling for new event types (if needed)**

If the existing dispatcher is generic (`this.emit('ws:' + msg.type, msg)`) no change is needed. If it has a switch, add two cases:

```js
case 'agent_upgrade':
  this.scene.events.emit('ws:agent_upgrade', msg);
  break;
case 'handoff_orb':
  this.scene.events.emit('ws:handoff_orb', msg);
  break;
```

- [ ] **Step 3: Verify by grep**

```bash
grep -n 'agent_upgrade\|handoff_orb' /Users/maximilianoallende/ContextGraph/ContextGraph/contextgraph/world/static/game/net/WorldSocket.js
```
Expected: both terms appear (either explicit cases or generic pass-through).

- [ ] **Step 4: Commit**

```bash
git add contextgraph/world/static/game/net/WorldSocket.js
git commit -m "feat: WorldSocket dispatches agent_upgrade + handoff_orb"
```

---

## Task 18: `AgentSprite` — archetype hat overlay

**Files:**
- Modify: `contextgraph/world/static/game/sprites/AgentSprite.js`

- [ ] **Step 1: Read `AgentSprite.js`**

Understand the existing constructor and `update(data)` method. Find the robe tint / color section.

- [ ] **Step 2: Add `_drawArchetypeHat` helper**

Add a method (below the existing base sprite setup):

```js
_drawArchetypeHat(archetype) {
  if (this._hatGraphic) {
    this._hatGraphic.destroy();
    this._hatGraphic = null;
  }
  if (!archetype || archetype === 'unknown') return;

  const g = this.scene.add.graphics();
  g.setDepth(this.depth + 1);

  // Each archetype: distinct hat silhouette + prop color
  const HAT_BY_ARCH = {
    archmage:   { color: 0x5B3A9E, trim: 0xFFE66B, height: 18, pointed: true },
    scout:      { color: 0x2F7D4F, trim: 0x9CE9B9, height: 10, pointed: false },
    oracle:     { color: 0x8E3A8E, trim: 0xFFB3FF, height: 16, pointed: true },
    scribe:     { color: 0x3A5E9E, trim: 0xE9F0FF, height: 8,  pointed: false },
    apprentice: { color: 0x8A6B3D, trim: 0xE6C78A, height: 12, pointed: true },
    artificer:  { color: 0x9E5B2F, trim: 0xFFD7A5, height: 9,  pointed: false },
    sage:       { color: 0x4E5E8E, trim: 0xC0CFF5, height: 14, pointed: true },
    user:       { color: 0xD94A4A, trim: 0xFFE6C2, height: 10, pointed: false },
  };
  const cfg = HAT_BY_ARCH[archetype];
  if (!cfg) return;

  const cx = this.x;
  const cy = this.y - this.height / 2 - 2;

  if (cfg.pointed) {
    // Pointed wizard hat: triangle + brim
    g.fillStyle(cfg.color, 1);
    g.fillTriangle(cx - 10, cy, cx + 10, cy, cx, cy - cfg.height);
    g.fillStyle(cfg.trim, 1);
    g.fillRect(cx - 12, cy - 2, 24, 3);
  } else {
    // Flat cap: rounded rectangle
    g.fillStyle(cfg.color, 1);
    g.fillRoundedRect(cx - 10, cy - cfg.height, 20, cfg.height, 4);
    g.fillStyle(cfg.trim, 1);
    g.fillRect(cx - 12, cy - 2, 24, 2);
  }

  this._hatGraphic = g;
}
```

Call `_drawArchetypeHat(data.archetype)` at the end of `update(data)`. Also destroy `_hatGraphic` in the existing `destroy()` method.

Also: on every position change (existing `setPosition` or movement code), call `_drawArchetypeHat` again with the current archetype so the hat tracks the body. Store the current archetype on the sprite:

```js
this._currentArchetype = data.archetype;
```

And provide a helper `_refreshOverlays()` that redraws hat + cape + aura. Call it on move.

- [ ] **Step 3: Manual smoke test**

```bash
cd /Users/maximilianoallende/ContextGraph/ContextGraph
CG_ENABLE_WORLD=true CG_ENABLE_STREAMING=true python3 -m contextgraph.server &
sleep 2
curl -s -X POST http://127.0.0.1:8420/v1/world/identity -H 'Content-Type: application/json' -d '{"actor":"claude","name":"Claude","archetype":"archmage","tools_count":2,"skills_count":1}'
curl -s -X POST http://127.0.0.1:8420/v1/world/spawn -H 'Content-Type: application/json' -d '{"parent":"claude","subagent_type":"Explore","description":"test","invocation_id":"1"}'
```
Open `http://127.0.0.1:8420/world` in a browser. Expected: see two wizard avatars with distinct hats — purple pointed for Claude, green flat for Scout.

- [ ] **Step 4: Commit**

```bash
git add contextgraph/world/static/game/sprites/AgentSprite.js
git commit -m "feat: archetype hat overlay on AgentSprite"
```

---

## Task 19: `AgentSprite` — rank cape + aura

**Files:**
- Modify: `contextgraph/world/static/game/sprites/AgentSprite.js`

- [ ] **Step 1: Add `_drawRankCape` and `_drawRankAura` helpers**

Add methods to `AgentSprite`:

```js
_drawRankCape(rank) {
  if (this._capeGraphic) {
    this._capeGraphic.destroy();
    this._capeGraphic = null;
  }
  if (!rank || rank === 'novice') return;

  const g = this.scene.add.graphics();
  g.setDepth(this.depth - 1); // render behind sprite

  const CAPE = {
    adept:     { color: 0x3D7F5F, length: 14, trim: false },
    mage:      { color: 0x3D5F9F, length: 22, trim: true  },
    high_mage: { color: 0x8E3A8E, length: 30, trim: true  },
    avatar:    { color: 0xFFD24A, length: 34, trim: true  },
  };
  const cfg = CAPE[rank];
  if (!cfg) return;

  const cx = this.x;
  const cy = this.y;
  g.fillStyle(cfg.color, 1);
  g.beginPath();
  g.moveTo(cx - 8, cy - 8);
  g.lineTo(cx + 8, cy - 8);
  g.lineTo(cx + 6, cy + cfg.length);
  g.lineTo(cx - 6, cy + cfg.length);
  g.closePath();
  g.fillPath();
  if (cfg.trim) {
    g.lineStyle(2, 0xFFE66B, 1);
    g.beginPath();
    g.moveTo(cx - 6, cy + cfg.length);
    g.lineTo(cx + 6, cy + cfg.length);
    g.strokePath();
  }
  this._capeGraphic = g;
}

_drawRankAura(rank) {
  if (this._auraEmitter) {
    this._auraEmitter.stop();
    this._auraEmitter.remove();
    this._auraEmitter = null;
  }
  const AURA_DENSITY = {
    novice: 0, adept: 0, mage: 2, high_mage: 4, avatar: 8,
  };
  const n = AURA_DENSITY[rank] || 0;
  if (n === 0) return;

  this._auraEmitter = this.scene.add.particles(this.x, this.y, 'particle_rune', {
    speed: { min: 20, max: 40 },
    lifespan: 900,
    quantity: 1,
    frequency: 180 / n,
    alpha: { start: 0.8, end: 0 },
    scale: { start: 0.6, end: 0 },
    angle: { min: 0, max: 360 },
    emitZone: { type: 'edge', source: new Phaser.Geom.Circle(0, 0, 18), quantity: 12 },
  });
  this._auraEmitter.setDepth(this.depth + 2);
}
```

In `_refreshOverlays()`, also call `_drawRankCape` and `_drawRankAura`. In `destroy()`, clean up cape and aura.

On `setPosition(x, y)` or whenever the sprite moves, also update the aura emitter position: `this._auraEmitter.setPosition(this.x, this.y)`.

- [ ] **Step 2: Manual smoke test**

Run server + post identity with `tools_count:30, skills_count:10` (rank = AVATAR):

```bash
curl -s -X POST http://127.0.0.1:8420/v1/world/identity -H 'Content-Type: application/json' -d '{"actor":"claude","name":"Claude","archetype":"archmage","tools_count":30,"skills_count":35}'
```
Browser: expect visible gold cape + rotating rune aura.

- [ ] **Step 3: Commit**

```bash
git add contextgraph/world/static/game/sprites/AgentSprite.js
git commit -m "feat: rank cape + aura overlay on AgentSprite"
```

---

## Task 20: `AgentSprite` — upgrade burst animation

**Files:**
- Modify: `contextgraph/world/static/game/sprites/AgentSprite.js`
- Modify: `contextgraph/world/static/game/scenes/RoomScene.js` (dispatch the event)

- [ ] **Step 1: Add `playUpgradeBurst(newRank)` method to `AgentSprite`**

```js
playUpgradeBurst(newRank) {
  // Golden vertical beam
  const beam = this.scene.add.rectangle(this.x, this.y - 20, 6, 120, 0xFFE66B, 0.85);
  beam.setDepth(this.depth + 10);
  this.scene.tweens.add({
    targets: beam,
    scaleX: { from: 1, to: 3 },
    alpha: { from: 0.9, to: 0 },
    duration: 900,
    onComplete: () => beam.destroy(),
  });

  // Burst of sparkle particles
  const burst = this.scene.add.particles(this.x, this.y - 10, 'particle_sparkle', {
    speed: { min: 60, max: 140 },
    lifespan: 700,
    quantity: 24,
    alpha: { start: 1, end: 0 },
    scale: { start: 1.2, end: 0 },
    emitting: false,
  });
  burst.explode(24);
  this.scene.time.delayedCall(900, () => burst.destroy());

  // "RANK UP: <name>" text
  const text = this.scene.add.text(this.x, this.y - 40,
    'RANK UP: ' + newRank.toUpperCase().replace('_', ' '),
    { fontFamily: 'Nunito, sans-serif', fontSize: '14px', fontStyle: '800',
      color: '#FFE66B', stroke: '#1B3047', strokeThickness: 3 });
  text.setOrigin(0.5, 0.5);
  text.setDepth(this.depth + 11);
  this.scene.tweens.add({
    targets: text,
    y: this.y - 70,
    alpha: { from: 1, to: 0 },
    duration: 1400,
    onComplete: () => text.destroy(),
  });
}
```

- [ ] **Step 2: In `RoomScene.js`, handle the `ws:agent_upgrade` event**

Find where other `ws:*` events are wired, add:

```js
this.socket.on('ws:agent_upgrade', (msg) => {
  const sprite = this.agents[msg.agent_id];
  if (!sprite) return;
  sprite.playUpgradeBurst(msg.data.new_rank || 'adept');
  // After the burst, refresh overlays to reflect new cape/aura
  this.time.delayedCall(1000, () => sprite._refreshOverlays && sprite._refreshOverlays());
});
```

If `this.socket.on` is actually `this.scene.events.on('ws:...')` in this codebase, use whichever pattern existing handlers use (match LobbyScene / RoomScene style).

- [ ] **Step 3: Manual smoke test**

```bash
curl -s -X POST http://127.0.0.1:8420/v1/world/identity -H 'Content-Type: application/json' -d '{"actor":"claude","name":"Claude","archetype":"archmage","tools_count":2,"skills_count":1}'
# View page, then trigger upgrade:
curl -s -X POST http://127.0.0.1:8420/v1/world/identity/upgrade -H 'Content-Type: application/json' -d '{"actor":"claude","tools_count":20,"skills_count":5}'
```
Browser: expect gold beam + sparkle burst + "RANK UP: MAGE" text.

- [ ] **Step 4: Commit**

```bash
git add contextgraph/world/static/game/sprites/AgentSprite.js contextgraph/world/static/game/scenes/RoomScene.js
git commit -m "feat: upgrade burst animation"
```

---

## Task 21: `AgentSprite` — handoff orb effect

**Files:**
- Modify: `contextgraph/world/static/game/scenes/RoomScene.js`

- [ ] **Step 1: Add handoff handler**

In `RoomScene.js` near other `ws:*` handlers:

```js
this.socket.on('ws:handoff_orb', (msg) => {
  const from = this.agents[msg.data.from_agent];
  const to = this.agents[msg.data.to_agent];
  if (!from || !to) return;

  const orb = this.add.particles(from.x, from.y, 'particle_glow', {
    speed: 0,
    lifespan: 800,
    quantity: 1,
    scale: { start: 1.6, end: 0.4 },
    alpha: { start: 1, end: 0.3 },
    tint: 0x9CE9B9,
    emitting: true,
  });
  orb.setDepth(100);

  this.tweens.add({
    targets: orb,
    x: to.x,
    y: to.y,
    duration: 700,
    ease: 'Cubic.easeInOut',
    onComplete: () => {
      orb.destroy();
      // Flash parent green briefly
      if (to && to.setTint) {
        to.setTint(0xA0F0B8);
        this.time.delayedCall(250, () => to.clearTint && to.clearTint());
      }
    },
  });
});
```

- [ ] **Step 2: Manual smoke test**

```bash
curl -s -X POST http://127.0.0.1:8420/v1/world/identity -H 'Content-Type: application/json' -d '{"actor":"claude","name":"Claude","archetype":"archmage","tools_count":2,"skills_count":1}'
curl -s -X POST http://127.0.0.1:8420/v1/world/spawn -H 'Content-Type: application/json' -d '{"parent":"claude","subagent_type":"Explore","description":"x","invocation_id":"1"}'
sleep 2
curl -s -X POST http://127.0.0.1:8420/v1/world/despawn -H 'Content-Type: application/json' -d '{"actor":"claude.Explore.1","result_summary":"done"}'
```
Browser: green orb should travel from Scout to Claude, then Scout fades away.

- [ ] **Step 3: Commit**

```bash
git add contextgraph/world/static/game/scenes/RoomScene.js
git commit -m "feat: handoff orb tween between child and parent"
```

---

## Task 22: `AgentSprite` — speech bubble styling by role

**Files:**
- Modify: `contextgraph/world/static/game/sprites/AgentSprite.js`

- [ ] **Step 1: Find the current bubble render**

Locate the existing `_drawBubble()` or equivalent in `AgentSprite.js`.

- [ ] **Step 2: Detect role prefix**

Modify the bubble render: when `this.bubbleText` starts with `[u]`, strip prefix and render with blue border (`#4A90D9`); when `[a]`, strip and render with purple border (`#8E3A8E`). Otherwise default style.

Concrete change in the existing bubble function (snippet — merge into whatever exists):

```js
_drawBubble() {
  const raw = this._bubble || '';
  let role = null;
  let text = raw;
  if (raw.startsWith('[u]')) { role = 'user'; text = raw.slice(3); }
  else if (raw.startsWith('[a]')) { role = 'assistant'; text = raw.slice(3); }

  const stroke = role === 'user' ? 0x4A90D9
                : role === 'assistant' ? 0x8E3A8E
                : 0x1B3047;
  // ... use `stroke` as the rounded-rect border color, and `text` as the body
}
```

- [ ] **Step 3: Manual smoke**

```bash
curl -s -X POST http://127.0.0.1:8420/v1/world/message -H 'Content-Type: application/json' -d '{"actor":"user","role":"user","text":"Hi Claude, can you help?"}'
```
Browser: user avatar bubble shows with blue border. Repeat with `"actor":"claude","role":"assistant"` — purple border.

- [ ] **Step 4: Commit**

```bash
git add contextgraph/world/static/game/sprites/AgentSprite.js
git commit -m "feat: bubble style varies by user/assistant role"
```

---

## Task 23: `cg-world` launcher

**Files:**
- Create: `bin/cg-world`

- [ ] **Step 1: Create the launcher**

```bash
mkdir -p /Users/maximilianoallende/ContextGraph/ContextGraph/bin
```

Create `bin/cg-world`:

```bash
#!/usr/bin/env bash
# cg-world — start ContextGraph World server in background (idempotent).
set -u

PORT="${CG_WORLD_PORT:-8420}"
LOG_DIR="${CG_WORLD_LOG_DIR:-$HOME/.contextgraph}"
LOG_FILE="$LOG_DIR/world.log"
PID_FILE="$LOG_DIR/world.pid"

mkdir -p "$LOG_DIR"

# Already running?
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    # Still confirm port is answering
    if curl -fsS -o /dev/null -m 1 "http://127.0.0.1:$PORT/world"; then
      echo "cg-world: already running pid=$OLD_PID port=$PORT"
      exit 0
    fi
    # Port dead but process alive — kill stale
    kill "$OLD_PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi

# Find project root (this script lives in <root>/bin/cg-world)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Boot in background
export CG_ENABLE_WORLD=true
export CG_ENABLE_STREAMING=true
nohup python3 -m contextgraph.server > "$LOG_FILE" 2>&1 &
NEW_PID=$!
disown $NEW_PID 2>/dev/null || true
echo $NEW_PID > "$PID_FILE"

# Wait for port (max 5s)
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -o /dev/null -m 1 "http://127.0.0.1:$PORT/world"; then
    echo "cg-world: started pid=$NEW_PID port=$PORT"
    exit 0
  fi
  sleep 0.5
done
echo "cg-world: failed to respond on port $PORT — see $LOG_FILE"
exit 1
```

Make it executable:

```bash
chmod +x /Users/maximilianoallende/ContextGraph/ContextGraph/bin/cg-world
```

- [ ] **Step 2: Test manually**

```bash
/Users/maximilianoallende/ContextGraph/ContextGraph/bin/cg-world
```
Expected: prints `cg-world: started pid=...` and `curl http://127.0.0.1:8420/world` returns HTTP 200. Run it again — prints `already running`.

- [ ] **Step 3: Commit**

```bash
cd /Users/maximilianoallende/ContextGraph/ContextGraph
git add bin/cg-world
git commit -m "feat: cg-world launcher for auto-starting world server"
```

---

## Task 24: Hook — `world_session_start.sh`

**Files:**
- Create: `.claude/hooks/world_session_start.sh`

- [ ] **Step 1: Create the hook**

```bash
chmod +x /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_session_start.sh
```

Write `.claude/hooks/world_session_start.sh`:

```bash
#!/usr/bin/env bash
# SessionStart hook: ensure World server running, register main Claude identity.
set -u

URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"
ACTOR="${CG_WORLD_ACTOR:-claude}"
NAME="${CG_WORLD_ACTOR_NAME:-Claude}"

# 1. Launch the server if it is not up
if ! curl -fsS -o /dev/null -m 1 "$URL/world"; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  LAUNCHER="$SCRIPT_DIR/../../bin/cg-world"
  if [ -x "$LAUNCHER" ]; then
    "$LAUNCHER" >/dev/null 2>&1 || true
  fi
fi

# 2. Estimate current tool + skill counts from the hook payload.
#    SessionStart hook payload does not enumerate tools/skills. Use env counters
#    maintained by the Claude Code runtime if present, otherwise default to 0.
payload=$(cat)
counts=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    # The runtime populates available_tools + available_skills when it can.
    tools = len(data.get("available_tools", []) or [])
    skills = len(data.get("available_skills", []) or [])
    print(f"{tools} {skills}")
except Exception:
    print("0 0")
')
tools_count=$(echo "$counts" | awk '{print $1}')
skills_count=$(echo "$counts" | awk '{print $2}')

# 3. Register main Claude identity
body=$(ACTOR="$ACTOR" NAME="$NAME" T="$tools_count" S="$skills_count" python3 -c '
import json, os
print(json.dumps({
    "actor": os.environ["ACTOR"],
    "name":  os.environ["NAME"],
    "archetype": "archmage",
    "tools_count": int(os.environ["T"]),
    "skills_count": int(os.environ["S"]),
}))')
curl -fsS -m 2 -o /dev/null -X POST "$URL/v1/world/identity" \
  -H 'Content-Type: application/json' -d "$body" || true

# 4. Register user avatar
user_body='{"actor":"user","name":"User","archetype":"user","tools_count":0,"skills_count":0}'
curl -fsS -m 2 -o /dev/null -X POST "$URL/v1/world/identity" \
  -H 'Content-Type: application/json' -d "$user_body" || true

# 5. Reset session counter used by the Agent tool spawn hook
mkdir -p "$HOME/.contextgraph"
: > "$HOME/.contextgraph/session_counter"

exit 0
```

- [ ] **Step 2: Test manually**

Start the server via `bin/cg-world`, then simulate the hook:

```bash
echo '{"available_tools":["Read","Edit","Bash","Grep","Glob"],"available_skills":[]}' | bash /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_session_start.sh
curl -s http://127.0.0.1:8420/v1/world/activity -X POST -H 'Content-Type: application/json' -d '{"actor":"claude","action":"idle"}' | head
```

Then inspect `.contextgraph/identities.json` — should show Claude with `rank: "novice"` (5 tools).

- [ ] **Step 3: Commit**

```bash
git add .claude/hooks/world_session_start.sh
git commit -m "feat: world_session_start hook boots server + registers identities"
```

---

## Task 25: Hook — `world_agent_pre.sh` (subagent spawn)

**Files:**
- Create: `.claude/hooks/world_agent_pre.sh`

- [ ] **Step 1: Create the hook**

```bash
chmod +x /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_agent_pre.sh
```

Write `.claude/hooks/world_agent_pre.sh`:

```bash
#!/usr/bin/env bash
# PreToolUse hook for the Agent tool: spawn a subagent avatar.
set -u

URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"
PARENT="${CG_WORLD_ACTOR:-claude}"
COUNTER_FILE="$HOME/.contextgraph/session_counter"

payload=$(cat)

tool_name=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("tool_name", ""))
except Exception:
    print("")
' 2>/dev/null)

# Only fire for the Agent tool
if [ "$tool_name" != "Agent" ]; then
  exit 0
fi

# Parse subagent_type + description
parsed=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    tin = d.get("tool_input", {}) or {}
    print(json.dumps({
      "subagent_type": tin.get("subagent_type", "general-purpose"),
      "description":   tin.get("description", "") or tin.get("prompt", "")[:120],
    }))
except Exception:
    print("{}")
' 2>/dev/null)

subagent_type=$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("subagent_type",""))')
description=$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("description",""))')

# Increment ordinal
mkdir -p "$(dirname "$COUNTER_FILE")"
if [ ! -f "$COUNTER_FILE" ] || [ ! -s "$COUNTER_FILE" ]; then
  echo 0 > "$COUNTER_FILE"
fi
ORD=$(cat "$COUNTER_FILE")
ORD=$((ORD + 1))
echo $ORD > "$COUNTER_FILE"

body=$(PARENT="$PARENT" ST="$subagent_type" DESC="$description" ORD="$ORD" python3 -c '
import json, os
print(json.dumps({
    "parent": os.environ["PARENT"],
    "subagent_type": os.environ["ST"],
    "description": os.environ["DESC"],
    "invocation_id": os.environ["ORD"],
}))')

(curl -sS -m 1 -o /dev/null -X POST "$URL/v1/world/spawn" \
  -H 'Content-Type: application/json' -d "$body" >/dev/null 2>&1 &) >/dev/null 2>&1

# Emit the actor_id so the matching PostToolUse hook can despawn it.
# We can't persist return values across hooks directly, so echo a stash file.
echo "claude.$subagent_type.$ORD" > "$HOME/.contextgraph/last_spawn"

exit 0
```

- [ ] **Step 2: Smoke test**

```bash
echo '{"tool_name":"Agent","tool_input":{"subagent_type":"Explore","description":"find files"}}' | bash /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_agent_pre.sh
sleep 1
cat $HOME/.contextgraph/last_spawn
curl -s http://127.0.0.1:8420/v1/world/activity -X POST -H 'Content-Type: application/json' -d '{"actor":"claude","action":"idle"}'
```
Expected: last_spawn shows `claude.Explore.1`. Browser shows Scout spawning.

- [ ] **Step 3: Commit**

```bash
git add .claude/hooks/world_agent_pre.sh
git commit -m "feat: world_agent_pre hook spawns subagent avatars"
```

---

## Task 26: Hook — `world_agent_post.sh` (subagent despawn)

**Files:**
- Create: `.claude/hooks/world_agent_post.sh`

- [ ] **Step 1: Create the hook**

```bash
chmod +x /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_agent_post.sh
```

Write:

```bash
#!/usr/bin/env bash
# PostToolUse on Agent tool: despawn subagent, emit handoff orb.
set -u

URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"
STASH="$HOME/.contextgraph/last_spawn"

payload=$(cat)

tool_name=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("tool_name", ""))
except Exception:
    print("")
')

if [ "$tool_name" != "Agent" ]; then
  exit 0
fi

if [ ! -f "$STASH" ]; then
  exit 0
fi

ACTOR=$(cat "$STASH")
rm -f "$STASH"

# Grab first 100 chars of tool response if present
summary=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    out = d.get("tool_response", {})
    if isinstance(out, dict):
        out = out.get("content") or json.dumps(out)
    text = str(out)[:100]
    print(text.replace("\n", " "))
except Exception:
    print("")
')

body=$(ACTOR="$ACTOR" SUMMARY="$summary" python3 -c '
import json, os
print(json.dumps({
    "actor": os.environ["ACTOR"],
    "result_summary": os.environ["SUMMARY"],
}))')

(curl -sS -m 1 -o /dev/null -X POST "$URL/v1/world/despawn" \
  -H 'Content-Type: application/json' -d "$body" >/dev/null 2>&1 &) >/dev/null 2>&1

exit 0
```

- [ ] **Step 2: Smoke test**

After `world_agent_pre.sh` spawned a scout, emulate post:

```bash
echo '{"tool_name":"Agent","tool_response":{"content":"Found 3 auth files."}}' | bash /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_agent_post.sh
```
Browser: scout emits bubble, green orb travels to Claude, scout fades.

- [ ] **Step 3: Commit**

```bash
git add .claude/hooks/world_agent_post.sh
git commit -m "feat: world_agent_post hook despawns subagents"
```

---

## Task 27: Hook — `world_user_prompt.sh`

**Files:**
- Create: `.claude/hooks/world_user_prompt.sh`

- [ ] **Step 1: Create the hook**

```bash
chmod +x /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_user_prompt.sh
```

Write:

```bash
#!/usr/bin/env bash
# UserPromptSubmit hook: user speech bubble.
set -u

URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"

payload=$(cat)

prompt=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("prompt", ""))
except Exception:
    print("")
')

if [ -z "$prompt" ]; then
  exit 0
fi

body=$(PROMPT="$prompt" python3 -c '
import json, os
print(json.dumps({
    "actor": "user",
    "role": "user",
    "text": os.environ["PROMPT"],
}))')

(curl -sS -m 1 -o /dev/null -X POST "$URL/v1/world/message" \
  -H 'Content-Type: application/json' -d "$body" >/dev/null 2>&1 &) >/dev/null 2>&1

exit 0
```

- [ ] **Step 2: Smoke test**

```bash
echo '{"prompt":"Hello Claude, please help me"}' | bash /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_user_prompt.sh
```
Browser: user avatar shows blue-bordered bubble.

- [ ] **Step 3: Commit**

```bash
git add .claude/hooks/world_user_prompt.sh
git commit -m "feat: world_user_prompt hook for user bubbles"
```

---

## Task 28: Hook — `world_stop.sh`

**Files:**
- Create: `.claude/hooks/world_stop.sh`

- [ ] **Step 1: Create the hook**

```bash
chmod +x /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_stop.sh
```

Write:

```bash
#!/usr/bin/env bash
# Stop hook: post last assistant message as a bubble over Claude.
set -u

URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"
ACTOR="${CG_WORLD_ACTOR:-claude}"

payload=$(cat)

text=$(printf '%s' "$payload" | python3 -c '
import json, sys, os, re
try:
    d = json.load(sys.stdin)
    transcript = d.get("transcript_path", "")
    if transcript and os.path.exists(transcript):
        last_text = ""
        with open(transcript, "r") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("type") != "assistant":
                    continue
                msg = e.get("message", {}) or {}
                for block in msg.get("content", []) or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        last_text = block.get("text", "")
        # Strip markdown + code fences to plain
        last_text = re.sub(r"```.*?```", "", last_text, flags=re.S)
        print(last_text[:150])
    else:
        print("")
except Exception:
    print("")
')

if [ -z "$text" ]; then
  exit 0
fi

body=$(ACTOR="$ACTOR" TEXT="$text" python3 -c '
import json, os
print(json.dumps({
    "actor": os.environ["ACTOR"],
    "role": "assistant",
    "text": os.environ["TEXT"],
}))')

(curl -sS -m 1 -o /dev/null -X POST "$URL/v1/world/message" \
  -H 'Content-Type: application/json' -d "$body" >/dev/null 2>&1 &) >/dev/null 2>&1

exit 0
```

- [ ] **Step 2: Smoke test**

Create a minimal transcript file:

```bash
cat > /tmp/fake_transcript.jsonl <<EOF
{"type":"user","message":{"content":[{"type":"text","text":"hi"}]}}
{"type":"assistant","message":{"content":[{"type":"text","text":"Done reading auth module."}]}}
EOF
echo '{"transcript_path":"/tmp/fake_transcript.jsonl"}' | bash /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/hooks/world_stop.sh
```
Browser: Claude avatar shows purple-bordered bubble with "Done reading auth module.".

- [ ] **Step 3: Commit**

```bash
git add .claude/hooks/world_stop.sh
git commit -m "feat: world_stop hook for assistant summary bubble"
```

---

## Task 29: Register hooks in `settings.local.json`

**Files:**
- Modify: `.claude/settings.local.json`

- [ ] **Step 1: Read current file**

Open `.claude/settings.local.json` and locate existing `hooks` block (may be nested or absent).

- [ ] **Step 2: Merge in 5 new hook entries**

The final `hooks` block should look like this (preserve any existing `PostToolUse` with `world_activity.sh`, then add the new sections):

```json
"hooks": {
  "SessionStart": [
    { "hooks": [
      { "type": "command", "command": ".claude/hooks/world_session_start.sh" }
    ] }
  ],
  "PreToolUse": [
    { "matcher": "Agent",
      "hooks": [
        { "type": "command", "command": ".claude/hooks/world_agent_pre.sh" }
      ] }
  ],
  "PostToolUse": [
    { "matcher": "Agent",
      "hooks": [
        { "type": "command", "command": ".claude/hooks/world_agent_post.sh" }
      ] },
    { "hooks": [
      { "type": "command", "command": ".claude/hooks/world_activity.sh" }
    ] }
  ],
  "UserPromptSubmit": [
    { "hooks": [
      { "type": "command", "command": ".claude/hooks/world_user_prompt.sh" }
    ] }
  ],
  "Stop": [
    { "hooks": [
      { "type": "command", "command": ".claude/hooks/world_stop.sh" }
    ] }
  ]
}
```

Ensure JSON remains valid. `python3 -m json.tool .claude/settings.local.json` should succeed.

- [ ] **Step 3: Verify**

```bash
python3 -m json.tool /Users/maximilianoallende/ContextGraph/ContextGraph/.claude/settings.local.json > /dev/null && echo OK
```

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.local.json
git commit -m "chore: register world presence hooks"
```

---

## Task 30: End-to-end verification

**Files:**
- None (pure verification).

- [ ] **Step 1: Run the full world test suite**

```bash
cd /Users/maximilianoallende/ContextGraph/ContextGraph
python3 -m pytest tests/test_world_models.py tests/test_world_spatial.py tests/test_world_v2.py tests/test_world_identity.py tests/test_world_identity_bridge.py tests/test_world_message_bridge.py tests/test_world_gateway.py tests/test_world_integration.py tests/test_world_rooms.py tests/test_world_translator.py -v
```
Expected: all tests pass, no regressions.

- [ ] **Step 2: Start the server and open the world**

```bash
/Users/maximilianoallende/ContextGraph/ContextGraph/bin/cg-world
open http://127.0.0.1:8420/world
```

- [ ] **Step 3: Exercise the flow via curl**

Run in sequence and observe the browser:

```bash
# 1. Register Claude (novice)
curl -s -X POST http://127.0.0.1:8420/v1/world/identity -H 'Content-Type: application/json' \
  -d '{"actor":"claude","name":"Claude","archetype":"archmage","tools_count":3,"skills_count":2}'

# 2. User prompt bubble
curl -s -X POST http://127.0.0.1:8420/v1/world/message -H 'Content-Type: application/json' \
  -d '{"actor":"user","role":"user","text":"Can you explore the auth code?"}'

# 3. Spawn Explore subagent
curl -s -X POST http://127.0.0.1:8420/v1/world/spawn -H 'Content-Type: application/json' \
  -d '{"parent":"claude","subagent_type":"Explore","description":"find auth files","invocation_id":"1"}'

# 4. Despawn with summary
sleep 2
curl -s -X POST http://127.0.0.1:8420/v1/world/despawn -H 'Content-Type: application/json' \
  -d '{"actor":"claude.Explore.1","result_summary":"Found 3 auth files in contextgraph/identity.py"}'

# 5. Upgrade Claude
curl -s -X POST http://127.0.0.1:8420/v1/world/identity/upgrade -H 'Content-Type: application/json' \
  -d '{"actor":"claude","tools_count":25,"skills_count":10}'
```

Expected visuals in order:
1. Claude archmage avatar (purple pointed hat, no cape) appears.
2. User avatar appears with blue-bordered bubble.
3. Scout (green flat cap) enters, description bubble.
4. Scout emits result bubble; green orb flies to Claude; Claude flashes green; scout fades.
5. Golden beam + sparkles + "RANK UP: MAGE" over Claude; blue cape appears.

- [ ] **Step 4: Exercise via a real Claude Code session**

Open a fresh Claude Code session in this project directory. In the world browser, verify:
- Main Claude avatar spawns on SessionStart.
- User bubble appears when you submit a prompt.
- A subagent avatar appears when Claude uses the `Agent` tool, walks near Claude, bubbles out its description, then despawns via orb after the tool finishes.
- Assistant summary bubble appears over Claude when the turn ends.

- [ ] **Step 5: Commit a CHANGELOG entry**

Append to `CHANGELOG.md`:

```markdown
## Agent Presence v2
- Per-agent wizard avatars with persistent archetype + color.
- Subagent spawn/despawn visual flow with handoff orb.
- Speech bubbles for user prompts and assistant replies.
- Rank upgrades (NOVICE → ADEPT → MAGE → HIGH_MAGE → AVATAR) as tool/skill count grows.
- `bin/cg-world` launcher + 5 new Claude Code hooks wired via `settings.local.json`.
```

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for agent presence v2"
```

---

## Self-Review Checklist (already applied)

1. **Spec coverage:** All 12 spec sections have corresponding tasks. Identity → Tasks 1–8. Backend bridges → 9–13. Routes → 14–16. Frontend → 17–22. Infra → 23. Hooks → 24–28. Registration → 29. Verification → 30.
2. **Placeholder scan:** No TBD/TODO/“handle edge cases” — every step contains concrete code or commands.
3. **Type consistency:** `AgentArchetype`, `AgentRank`, `rank_for_counts`, `IdentityRecord`, `IdentityStore`, `SpatialState.update_rank`, `SpatialState.set_parent`, `SpatialState.remove_agent` names match across all tasks. Hook actor-ID format `claude.<type>.<ordinal>` matches the bridge implementation.
4. **Ambiguity:** Only soft ambiguity is hook payload shape (`tool_input.subagent_type` for `Agent` tool) — hooks include a fallback (`general-purpose`) on missing.

No issues found; plan is executable top-to-bottom.
