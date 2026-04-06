# ContextGraph World Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-time 2D virtual world (Club Penguin style) where agents appear as animated characters, walk between zones based on activity, interact visually, and can be inspected via click.

**Architecture:** A thin World Gateway module (`contextgraph/world/`) subscribes to ContextGraph's EventBus, translates agent events into spatial game events, and pushes them to browser viewers over WebSocket. A Phaser 3 client renders the 2D world as a static SPA served at `/world`.

**Tech Stack:** Python (FastAPI WebSocket), Phaser 3 (vanilla JS, no build step), Tiled (tilemaps)

**Spec:** `docs/superpowers/specs/2026-04-06-contextgraph-world-design.md`

---

## File Structure

```
contextgraph/
├── config.py                           # MODIFY: add enable_world + world settings
├── web.py                              # MODIFY: conditional mount of world routes
│
├── world/                              # NEW MODULE (all new files below)
│   ├── __init__.py                     # Package init
│   ├── models.py                       # Game-specific dataclasses
│   ├── rooms.py                        # Room templates, zone definitions, positions
│   ├── spatial.py                      # Agent position tracking, zone assignment
│   ├── translator.py                   # CG events → game events mapping
│   ├── gateway.py                      # WebSocket connection manager + event loop
│   ├── routes.py                       # /world + /ws/world endpoint registration
│   └── static/                         # Phaser 3 game client
│       ├── index.html                  # Entry point HTML
│       ├── style.css                   # Inspect panel + UI styles
│       ├── game/
│       │   ├── main.js                 # Phaser boot + config
│       │   ├── scenes/
│       │   │   ├── LobbyScene.js       # Lobby rendering, doors, idle agents
│       │   │   └── RoomScene.js        # Project room rendering, zones, active agents
│       │   ├── sprites/
│       │   │   └── AgentSprite.js      # Multi-layer sprite (body + face + accessory)
│       │   ├── ui/
│       │   │   ├── InspectPanel.js     # DOM overlay panel (8 sections)
│       │   │   ├── SpeechBubble.js     # Floating text bubbles
│       │   │   └── RoomDoor.js         # Clickable door with agent count badge
│       │   └── net/
│       │       └── WorldSocket.js      # WebSocket client + reconnection
│       └── assets/
│           ├── lobby.json              # Tiled tilemap for lobby
│           ├── room.json               # Tiled tilemap for project room template
│           ├── tileset.png             # Shared tileset image
│           ├── agents.png              # Agent sprite sheet (bodies, faces, accessories)
│           └── particles.png           # Sparkle/glow particle sprites

tests/
├── test_world_models.py
├── test_world_translator.py
├── test_world_spatial.py
├── test_world_gateway.py
└── test_world_rooms.py
```

---

## Task 1: Game Data Models

**Files:**
- Create: `contextgraph/world/__init__.py`
- Create: `contextgraph/world/models.py`
- Create: `tests/test_world_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_world_models.py
"""Tests for world game models."""
from contextgraph.world.models import (
    AgentVisual,
    Expression,
    Accessory,
    GlowColor,
    GameEvent,
    GameEventType,
    RoomInfo,
    ZoneType,
)


def test_expression_enum_has_all_states():
    assert set(Expression) == {
        Expression.HAPPY,
        Expression.THINKING,
        Expression.WORRIED,
        Expression.FOCUSED,
        Expression.SOCIAL,
        Expression.SLEEPY,
    }


def test_accessory_enum_has_all_items():
    assert set(Accessory) == {
        Accessory.HARD_HAT,
        Accessory.SIREN,
        Accessory.BOOK,
        Accessory.MAGNIFYING_GLASS,
        Accessory.CLIPBOARD,
        Accessory.SLEEP_BUBBLE,
        Accessory.NONE,
    }


def test_zone_type_enum():
    assert set(ZoneType) == {
        ZoneType.CODE_DESK,
        ZoneType.MEMORY_LIBRARY,
        ZoneType.REVIEW_STATION,
        ZoneType.DEBUG_LAB,
    }


def test_agent_visual_defaults():
    av = AgentVisual(agent_id="alice", name="alice-agent", color_index=0)
    assert av.expression == Expression.HAPPY
    assert av.accessory == Accessory.NONE
    assert av.glow == GlowColor.GRAY
    assert av.bubble is None
    assert av.x == 0.0
    assert av.y == 0.0
    assert av.room == "lobby"
    assert av.zone is None


def test_agent_visual_to_dict():
    av = AgentVisual(agent_id="alice", name="alice-agent", color_index=3)
    d = av.to_dict()
    assert d["agent_id"] == "alice"
    assert d["color_index"] == 3
    assert d["expression"] == "happy"
    assert d["accessory"] == "none"
    assert d["glow"] == "gray"


def test_game_event_to_dict():
    ge = GameEvent(
        type=GameEventType.AGENT_MOVE,
        agent_id="alice",
        data={"zone": "code_desk", "x": 100, "y": 200},
    )
    d = ge.to_dict()
    assert d["type"] == "agent_move"
    assert d["agent_id"] == "alice"
    assert d["data"]["zone"] == "code_desk"


def test_room_info():
    ri = RoomInfo(room_id="api-svc", name="api-svc", agent_count=3)
    d = ri.to_dict()
    assert d["room_id"] == "api-svc"
    assert d["agent_count"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_world_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'contextgraph.world'"

- [ ] **Step 3: Create package init**

```python
# contextgraph/world/__init__.py
"""ContextGraph World — real-time 2D agent visualization."""
```

- [ ] **Step 4: Write minimal implementation**

```python
# contextgraph/world/models.py
"""Game-specific data models for ContextGraph World."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Expression(StrEnum):
    HAPPY = "happy"
    THINKING = "thinking"
    WORRIED = "worried"
    FOCUSED = "focused"
    SOCIAL = "social"
    SLEEPY = "sleepy"


class Accessory(StrEnum):
    HARD_HAT = "hard_hat"
    SIREN = "siren"
    BOOK = "book"
    MAGNIFYING_GLASS = "magnifying_glass"
    CLIPBOARD = "clipboard"
    SLEEP_BUBBLE = "sleep_bubble"
    NONE = "none"


class GlowColor(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    GRAY = "gray"
    BLUE = "blue"


class ZoneType(StrEnum):
    CODE_DESK = "code_desk"
    MEMORY_LIBRARY = "memory_library"
    REVIEW_STATION = "review_station"
    DEBUG_LAB = "debug_lab"


class GameEventType(StrEnum):
    AGENT_MOVE = "agent_move"
    AGENT_STATE = "agent_state"
    AGENT_INTERACT = "agent_interact"
    AGENT_SPAWN = "agent_spawn"
    AGENT_DESPAWN = "agent_despawn"
    WORLD_SNAPSHOT = "world_snapshot"
    ROOM_SNAPSHOT = "room_snapshot"


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

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "color_index": self.color_index,
            "expression": self.expression.value,
            "accessory": self.accessory.value,
            "glow": self.glow.value,
            "bubble": self.bubble,
            "x": self.x,
            "y": self.y,
            "room": self.room,
            "zone": self.zone.value if self.zone else None,
        }


@dataclass
class GameEvent:
    type: GameEventType
    agent_id: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "agent_id": self.agent_id,
            "data": self.data,
        }


@dataclass
class RoomInfo:
    room_id: str
    name: str
    agent_count: int = 0

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "name": self.name,
            "agent_count": self.agent_count,
        }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_world_models.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add contextgraph/world/__init__.py contextgraph/world/models.py tests/test_world_models.py
git commit -m "feat(world): add game data models — expressions, accessories, zones, events"
```

---

## Task 2: Room Templates & Zone Definitions

**Files:**
- Create: `contextgraph/world/rooms.py`
- Create: `tests/test_world_rooms.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_world_rooms.py
"""Tests for world room templates and zone definitions."""
from contextgraph.world.rooms import (
    LOBBY_ZONES,
    ROOM_ZONES,
    AGENT_COLORS,
    get_zone_position,
    get_lobby_door_position,
    color_index_for_agent,
)
from contextgraph.world.models import ZoneType


def test_room_zones_has_all_zone_types():
    assert set(ROOM_ZONES.keys()) == set(ZoneType)


def test_each_zone_has_position_rect():
    for zone_type, rect in ROOM_ZONES.items():
        assert "x" in rect
        assert "y" in rect
        assert "w" in rect
        assert "h" in rect
        assert rect["w"] > 0
        assert rect["h"] > 0


def test_lobby_zones_has_idle_area():
    assert "idle" in LOBBY_ZONES
    assert "x" in LOBBY_ZONES["idle"]


def test_get_zone_position_returns_point_within_rect():
    for _ in range(20):
        x, y = get_zone_position(ZoneType.CODE_DESK, exclude=[])
        rect = ROOM_ZONES[ZoneType.CODE_DESK]
        assert rect["x"] <= x <= rect["x"] + rect["w"]
        assert rect["y"] <= y <= rect["y"] + rect["h"]


def test_get_zone_position_avoids_excluded():
    occupied = [(100.0, 100.0)]
    x, y = get_zone_position(ZoneType.CODE_DESK, exclude=occupied)
    assert (x, y) != (100.0, 100.0)


def test_get_lobby_door_position():
    x, y = get_lobby_door_position(0)
    assert isinstance(x, float)
    assert isinstance(y, float)


def test_agent_colors_has_12():
    assert len(AGENT_COLORS) == 12


def test_color_index_deterministic():
    idx1 = color_index_for_agent("agent-abc-123")
    idx2 = color_index_for_agent("agent-abc-123")
    assert idx1 == idx2
    assert 0 <= idx1 < 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_world_rooms.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# contextgraph/world/rooms.py
"""Room templates, zone definitions, and position helpers."""
from __future__ import annotations

import hashlib
import random
from typing import Sequence

from .models import ZoneType

AGENT_COLORS = [
    "#6366f1", "#f97316", "#06b6d4", "#ec4899",
    "#10b981", "#f59e0b", "#f43f5e", "#0ea5e9",
    "#8b5cf6", "#14b8a6", "#84cc16", "#d946ef",
]

ROOM_ZONES: dict[ZoneType, dict[str, float]] = {
    ZoneType.CODE_DESK: {"x": 80, "y": 120, "w": 300, "h": 200},
    ZoneType.MEMORY_LIBRARY: {"x": 640, "y": 120, "w": 300, "h": 200},
    ZoneType.REVIEW_STATION: {"x": 80, "y": 440, "w": 300, "h": 200},
    ZoneType.DEBUG_LAB: {"x": 640, "y": 440, "w": 300, "h": 200},
}

LOBBY_ZONES: dict[str, dict[str, float]] = {
    "idle": {"x": 200, "y": 250, "w": 600, "h": 300},
}

_DOOR_SPACING = 160
_DOOR_START_X = 160.0
_DOOR_Y = 100.0


def color_index_for_agent(agent_id: str) -> int:
    digest = hashlib.md5(agent_id.encode()).hexdigest()
    return int(digest[:8], 16) % len(AGENT_COLORS)


def get_zone_position(
    zone: ZoneType,
    exclude: Sequence[tuple[float, float]] = (),
    min_distance: float = 40.0,
) -> tuple[float, float]:
    rect = ROOM_ZONES[zone]
    for _ in range(50):
        x = random.uniform(rect["x"], rect["x"] + rect["w"])
        y = random.uniform(rect["y"], rect["y"] + rect["h"])
        if all(
            ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5 >= min_distance
            for ex, ey in exclude
        ):
            return (x, y)
    return (rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] / 2)


def get_lobby_door_position(door_index: int) -> tuple[float, float]:
    x = _DOOR_START_X + door_index * _DOOR_SPACING
    return (x, _DOOR_Y)


def get_lobby_idle_position(
    exclude: Sequence[tuple[float, float]] = (),
) -> tuple[float, float]:
    rect = LOBBY_ZONES["idle"]
    for _ in range(50):
        x = random.uniform(rect["x"], rect["x"] + rect["w"])
        y = random.uniform(rect["y"], rect["y"] + rect["h"])
        if all(
            ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5 >= 40.0
            for ex, ey in exclude
        ):
            return (x, y)
    return (rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] / 2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_world_rooms.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/rooms.py tests/test_world_rooms.py
git commit -m "feat(world): add room templates, zone layouts, and color assignment"
```

---

## Task 3: Event Translator

**Files:**
- Create: `contextgraph/world/translator.py`
- Create: `tests/test_world_translator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_world_translator.py
"""Tests for CG event → game event translation."""
from datetime import datetime, timezone

from contextgraph.world.translator import translate_session_event, translate_bus_event
from contextgraph.world.models import Expression, Accessory, GlowColor, ZoneType


def _make_session_event(event_type, content="", metadata=None):
    from contextgraph.models import SessionEvent
    return SessionEvent(
        event_id="evt-1", session_id="sess-1", agent_id="alice",
        event_type=event_type, content=content,
        created_at=datetime.now(timezone.utc),
        metadata=metadata or {}, sequence=1,
    )


def test_file_change_maps_to_code_desk():
    result = translate_session_event(_make_session_event("file_change", "src/main.py"))
    assert result.zone == ZoneType.CODE_DESK
    assert result.accessory == Accessory.HARD_HAT
    assert result.expression == Expression.FOCUSED
    assert result.glow == GlowColor.GREEN


def test_failure_maps_to_debug_lab():
    result = translate_session_event(_make_session_event("failure", "TypeError"))
    assert result.zone == ZoneType.DEBUG_LAB
    assert result.accessory == Accessory.SIREN
    assert result.expression == Expression.WORRIED
    assert result.glow == GlowColor.RED


def test_resolved_maps_to_happy():
    result = translate_session_event(_make_session_event("resolved", "Fixed the bug"))
    assert result.zone is None
    assert result.expression == Expression.HAPPY
    assert result.glow == GlowColor.GREEN
    assert result.bubble == "Fixed the bug"


def test_decision_shows_bubble():
    result = translate_session_event(_make_session_event("decision", "Use async webhooks"))
    assert result.expression == Expression.THINKING
    assert result.bubble == "Use async webhooks"


def test_context_pressure_maps_to_thinking():
    result = translate_session_event(_make_session_event("context_pressure"))
    assert result.expression == Expression.THINKING
    assert result.glow == GlowColor.YELLOW


def test_command_maps_to_code_desk():
    result = translate_session_event(_make_session_event("command", "pytest"))
    assert result.zone == ZoneType.CODE_DESK
    assert result.accessory == Accessory.HARD_HAT


def test_unknown_event_type_defaults():
    result = translate_session_event(_make_session_event("something_random", "hello"))
    assert result.expression == Expression.HAPPY
    assert result.zone is None


def test_translate_bus_event_memory_stored():
    from contextgraph.events import Event, EventType
    event = Event(event_id="e1", event_type=EventType.MEMORY_STORED,
                  data={"content": "fact"}, timestamp=datetime.now(timezone.utc), agent_id="alice")
    result = translate_bus_event(event)
    assert result.zone == ZoneType.MEMORY_LIBRARY
    assert result.accessory == Accessory.BOOK


def test_translate_bus_event_claim_reviewed():
    from contextgraph.events import Event, EventType
    event = Event(event_id="e2", event_type=EventType.CLAIM_REVIEWED,
                  data={}, timestamp=datetime.now(timezone.utc), agent_id="alice")
    result = translate_bus_event(event)
    assert result.zone == ZoneType.REVIEW_STATION
    assert result.accessory == Accessory.CLIPBOARD
    assert result.expression == Expression.SOCIAL


def test_translate_bus_event_agent_registered():
    from contextgraph.events import Event, EventType
    event = Event(event_id="e3", event_type=EventType.AGENT_REGISTERED,
                  data={"name": "new-agent"}, timestamp=datetime.now(timezone.utc), agent_id="new-agent")
    result = translate_bus_event(event)
    assert result.is_spawn is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_world_translator.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write minimal implementation**

```python
# contextgraph/world/translator.py
"""Translate ContextGraph events into game visual state changes."""
from __future__ import annotations

from dataclasses import dataclass

from contextgraph.events import Event, EventType
from contextgraph.models import SessionEvent

from .models import Accessory, Expression, GlowColor, ZoneType


@dataclass
class TranslationResult:
    zone: ZoneType | None = None
    expression: Expression = Expression.HAPPY
    accessory: Accessory = Accessory.NONE
    glow: GlowColor = GlowColor.GREEN
    bubble: str | None = None
    interact_with: str | None = None
    is_spawn: bool = False
    is_despawn: bool = False


_SESSION_MAP: dict[str, TranslationResult] = {
    "file_change": TranslationResult(zone=ZoneType.CODE_DESK, accessory=Accessory.HARD_HAT, expression=Expression.FOCUSED, glow=GlowColor.GREEN),
    "file_edit": TranslationResult(zone=ZoneType.CODE_DESK, accessory=Accessory.HARD_HAT, expression=Expression.FOCUSED, glow=GlowColor.GREEN),
    "diff": TranslationResult(zone=ZoneType.CODE_DESK, accessory=Accessory.HARD_HAT, expression=Expression.FOCUSED, glow=GlowColor.GREEN),
    "command": TranslationResult(zone=ZoneType.CODE_DESK, accessory=Accessory.HARD_HAT, expression=Expression.FOCUSED, glow=GlowColor.GREEN),
    "tool": TranslationResult(zone=ZoneType.CODE_DESK, accessory=Accessory.HARD_HAT, expression=Expression.FOCUSED, glow=GlowColor.GREEN),
    "bash": TranslationResult(zone=ZoneType.CODE_DESK, accessory=Accessory.HARD_HAT, expression=Expression.FOCUSED, glow=GlowColor.GREEN),
    "failure": TranslationResult(zone=ZoneType.DEBUG_LAB, accessory=Accessory.SIREN, expression=Expression.WORRIED, glow=GlowColor.RED),
    "blocker": TranslationResult(zone=ZoneType.DEBUG_LAB, accessory=Accessory.SIREN, expression=Expression.WORRIED, glow=GlowColor.RED),
    "error": TranslationResult(zone=ZoneType.DEBUG_LAB, accessory=Accessory.SIREN, expression=Expression.WORRIED, glow=GlowColor.RED),
    "resolved": TranslationResult(expression=Expression.HAPPY, glow=GlowColor.GREEN),
    "fix": TranslationResult(expression=Expression.HAPPY, glow=GlowColor.GREEN),
    "done": TranslationResult(expression=Expression.HAPPY, glow=GlowColor.GREEN),
    "decision": TranslationResult(expression=Expression.THINKING, glow=GlowColor.GREEN),
    "context_pressure": TranslationResult(expression=Expression.THINKING, glow=GlowColor.YELLOW),
    "compact": TranslationResult(expression=Expression.THINKING, glow=GlowColor.YELLOW),
    "todo": TranslationResult(expression=Expression.THINKING, glow=GlowColor.GREEN),
    "artifact": TranslationResult(zone=ZoneType.MEMORY_LIBRARY, accessory=Accessory.MAGNIFYING_GLASS, expression=Expression.FOCUSED, glow=GlowColor.GREEN),
    "reference": TranslationResult(zone=ZoneType.MEMORY_LIBRARY, accessory=Accessory.MAGNIFYING_GLASS, expression=Expression.FOCUSED, glow=GlowColor.GREEN),
}

_DEFAULT = TranslationResult(expression=Expression.HAPPY, glow=GlowColor.GREEN)


def translate_session_event(event: SessionEvent) -> TranslationResult:
    event_type = event.event_type.strip().lower()
    base = _SESSION_MAP.get(event_type, _DEFAULT)
    result = TranslationResult(
        zone=base.zone, expression=base.expression, accessory=base.accessory,
        glow=base.glow, bubble=base.bubble, interact_with=base.interact_with,
    )
    content = event.content.strip()
    if event_type in {"resolved", "fix", "done", "decision"} and content:
        result.bubble = content[:120]
    return result


_BUS_MAP: dict[EventType, TranslationResult] = {
    EventType.MEMORY_STORED: TranslationResult(zone=ZoneType.MEMORY_LIBRARY, accessory=Accessory.BOOK, expression=Expression.FOCUSED, glow=GlowColor.GREEN),
    EventType.CLAIM_REVIEWED: TranslationResult(zone=ZoneType.REVIEW_STATION, accessory=Accessory.CLIPBOARD, expression=Expression.SOCIAL, glow=GlowColor.GREEN),
    EventType.CLAIM_CREATED: TranslationResult(zone=ZoneType.MEMORY_LIBRARY, accessory=Accessory.BOOK, expression=Expression.HAPPY, glow=GlowColor.GREEN),
    EventType.AGENT_REGISTERED: TranslationResult(is_spawn=True),
    EventType.AGENT_DELETED: TranslationResult(is_despawn=True),
    EventType.AGENT_SUSPENDED: TranslationResult(is_despawn=True),
}


def translate_bus_event(event: Event) -> TranslationResult:
    base = _BUS_MAP.get(event.event_type, _DEFAULT)
    return TranslationResult(
        zone=base.zone, expression=base.expression, accessory=base.accessory,
        glow=base.glow, bubble=base.bubble, interact_with=base.interact_with,
        is_spawn=base.is_spawn, is_despawn=base.is_despawn,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_world_translator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/translator.py tests/test_world_translator.py
git commit -m "feat(world): add event translator — CG events to game visual states"
```

---

## Task 4: Spatial State Manager

**Files:**
- Create: `contextgraph/world/spatial.py`
- Create: `tests/test_world_spatial.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_world_spatial.py
"""Tests for spatial state manager."""
from contextgraph.world.spatial import SpatialState
from contextgraph.world.models import Expression, GlowColor, ZoneType


def test_register_agent():
    state = SpatialState()
    state.register_agent("alice", "alice-agent")
    agent = state.get_agent("alice")
    assert agent is not None
    assert agent.name == "alice-agent"
    assert agent.room == "lobby"
    assert agent.expression == Expression.SLEEPY
    assert agent.glow == GlowColor.GRAY


def test_register_agent_idempotent():
    state = SpatialState()
    state.register_agent("alice", "alice-agent")
    state.register_agent("alice", "alice-agent")
    assert len(state.get_all_agents()) == 1


def test_move_agent_to_zone():
    state = SpatialState()
    state.register_agent("alice", "alice-agent")
    state.move_agent_to_room("alice", "api-svc")
    state.move_agent_to_zone("alice", ZoneType.CODE_DESK)
    agent = state.get_agent("alice")
    assert agent.room == "api-svc"
    assert agent.zone == ZoneType.CODE_DESK
    assert agent.x > 0
    assert agent.y > 0


def test_update_agent_visual():
    state = SpatialState()
    state.register_agent("alice", "alice-agent")
    state.update_visual("alice", expression=Expression.WORRIED, glow=GlowColor.RED)
    agent = state.get_agent("alice")
    assert agent.expression == Expression.WORRIED
    assert agent.glow == GlowColor.RED


def test_move_agent_to_lobby():
    state = SpatialState()
    state.register_agent("alice", "alice-agent")
    state.move_agent_to_room("alice", "api-svc")
    state.move_agent_to_room("alice", "lobby")
    agent = state.get_agent("alice")
    assert agent.room == "lobby"
    assert agent.zone is None


def test_get_agents_in_room():
    state = SpatialState()
    state.register_agent("alice", "alice-agent")
    state.register_agent("bob", "bob-builder")
    state.move_agent_to_room("alice", "api-svc")
    assert len(state.get_agents_in_room("api-svc")) == 1
    assert len(state.get_agents_in_room("lobby")) == 1


def test_get_room_list():
    state = SpatialState()
    state.register_agent("alice", "alice-agent")
    state.move_agent_to_room("alice", "api-svc")
    state.register_agent("bob", "bob-builder")
    state.move_agent_to_room("bob", "api-svc")
    rooms = state.get_room_list()
    assert any(r.room_id == "api-svc" and r.agent_count == 2 for r in rooms)


def test_remove_agent():
    state = SpatialState()
    state.register_agent("alice", "alice-agent")
    state.remove_agent("alice")
    assert state.get_agent("alice") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_world_spatial.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# contextgraph/world/spatial.py
"""Agent spatial state manager — tracks positions, rooms, and zones."""
from __future__ import annotations

from collections import defaultdict

from .models import Accessory, AgentVisual, Expression, GlowColor, RoomInfo, ZoneType
from .rooms import color_index_for_agent, get_lobby_idle_position, get_zone_position


class SpatialState:
    def __init__(self) -> None:
        self._agents: dict[str, AgentVisual] = {}

    def register_agent(self, agent_id: str, name: str) -> AgentVisual:
        if agent_id in self._agents:
            return self._agents[agent_id]
        occupied = [(a.x, a.y) for a in self._agents.values() if a.room == "lobby"]
        x, y = get_lobby_idle_position(exclude=occupied)
        agent = AgentVisual(
            agent_id=agent_id, name=name,
            color_index=color_index_for_agent(agent_id),
            expression=Expression.SLEEPY, glow=GlowColor.GRAY,
            x=x, y=y, room="lobby",
        )
        self._agents[agent_id] = agent
        return agent

    def get_agent(self, agent_id: str) -> AgentVisual | None:
        return self._agents.get(agent_id)

    def get_all_agents(self) -> list[AgentVisual]:
        return list(self._agents.values())

    def get_agents_in_room(self, room: str) -> list[AgentVisual]:
        return [a for a in self._agents.values() if a.room == room]

    def get_room_list(self) -> list[RoomInfo]:
        counts: dict[str, int] = defaultdict(int)
        for agent in self._agents.values():
            counts[agent.room] += 1
        return [RoomInfo(room_id=rid, name=rid, agent_count=c) for rid, c in counts.items() if rid != "lobby"]

    def move_agent_to_room(self, agent_id: str, room: str) -> None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        agent.room = room
        agent.zone = None
        if room == "lobby":
            occupied = [(a.x, a.y) for a in self._agents.values() if a.room == "lobby" and a.agent_id != agent_id]
            agent.x, agent.y = get_lobby_idle_position(exclude=occupied)
            agent.expression = Expression.SLEEPY
            agent.accessory = Accessory.SLEEP_BUBBLE
            agent.glow = GlowColor.GRAY
        else:
            agent.expression = Expression.HAPPY
            agent.glow = GlowColor.GREEN

    def move_agent_to_zone(self, agent_id: str, zone: ZoneType) -> None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        occupied = [(a.x, a.y) for a in self._agents.values() if a.room == agent.room and a.zone == zone and a.agent_id != agent_id]
        agent.zone = zone
        agent.x, agent.y = get_zone_position(zone, exclude=occupied)

    def update_visual(self, agent_id: str, expression: Expression | None = None, accessory: Accessory | None = None, glow: GlowColor | None = None, bubble: str | None = None) -> None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        if expression is not None:
            agent.expression = expression
        if accessory is not None:
            agent.accessory = accessory
        if glow is not None:
            agent.glow = glow
        if bubble is not None:
            agent.bubble = bubble

    def remove_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_world_spatial.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/spatial.py tests/test_world_spatial.py
git commit -m "feat(world): add spatial state manager — rooms, zones, positions"
```

---

## Task 5: WebSocket Gateway

**Files:**
- Create: `contextgraph/world/gateway.py`
- Create: `tests/test_world_gateway.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_world_gateway.py
"""Tests for the WebSocket gateway."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from contextgraph.world.gateway import WorldGateway


@pytest.fixture
def gateway():
    return WorldGateway(event_bus=MagicMock(), graph_service=MagicMock())


def test_gateway_init(gateway):
    assert gateway.spatial is not None
    assert len(gateway._viewers) == 0


@pytest.mark.asyncio
async def test_add_and_remove_viewer(gateway):
    ws = AsyncMock()
    await gateway.add_viewer(ws, room="lobby")
    assert len(gateway._viewers) == 1
    gateway.remove_viewer(ws)
    assert len(gateway._viewers) == 0


@pytest.mark.asyncio
async def test_add_viewer_sends_snapshot(gateway):
    ws = AsyncMock()
    gateway.spatial.register_agent("alice", "alice-agent")
    await gateway.add_viewer(ws, room="lobby")
    ws.send_json.assert_called_once()
    assert ws.send_json.call_args[0][0]["type"] == "world_snapshot"


@pytest.mark.asyncio
async def test_broadcast_to_room(gateway):
    ws1, ws2 = AsyncMock(), AsyncMock()
    await gateway.add_viewer(ws1, room="api-svc")
    await gateway.add_viewer(ws2, room="lobby")
    await gateway.broadcast_to_room("api-svc", {"type": "test"})
    ws1.send_json.assert_called()
    assert ws2.send_json.call_count == 1  # only snapshot


@pytest.mark.asyncio
async def test_process_session_event(gateway):
    from contextgraph.models import SessionEvent
    gateway.spatial.register_agent("alice", "alice-agent")
    gateway.spatial.move_agent_to_room("alice", "api-svc")
    ws = AsyncMock()
    await gateway.add_viewer(ws, room="api-svc")
    event = SessionEvent(
        event_id="e1", session_id="s1", agent_id="alice",
        event_type="file_change", content="src/main.py",
        created_at=datetime.now(timezone.utc), sequence=1,
    )
    await gateway.process_session_event(event)
    assert ws.send_json.call_count >= 2


@pytest.mark.asyncio
async def test_switch_viewer_room(gateway):
    ws = AsyncMock()
    await gateway.add_viewer(ws, room="lobby")
    gateway.switch_viewer_room(ws, "api-svc")
    assert gateway._viewers[id(ws)]["room"] == "api-svc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_world_gateway.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# contextgraph/world/gateway.py
"""WebSocket gateway — bridges ContextGraph events to game viewers."""
from __future__ import annotations

import logging
from typing import Any

from contextgraph.events import EventBus
from contextgraph.models import SessionEvent
from contextgraph.service import ContextGraphService

from .models import GameEvent, GameEventType
from .spatial import SpatialState
from .translator import translate_bus_event, translate_session_event

logger = logging.getLogger(__name__)


class WorldGateway:
    def __init__(self, event_bus: EventBus, graph_service: ContextGraphService) -> None:
        self.event_bus = event_bus
        self.graph_service = graph_service
        self.spatial = SpatialState()
        self._viewers: dict[int, dict[str, Any]] = {}

    async def add_viewer(self, ws: Any, room: str = "lobby") -> None:
        self._viewers[id(ws)] = {"ws": ws, "room": room}
        await ws.send_json(self._build_snapshot(room))

    def remove_viewer(self, ws: Any) -> None:
        self._viewers.pop(id(ws), None)

    def switch_viewer_room(self, ws: Any, room: str) -> None:
        viewer = self._viewers.get(id(ws))
        if viewer:
            viewer["room"] = room

    async def broadcast_to_room(self, room: str, message: dict) -> None:
        dead: list[int] = []
        for ws_id, viewer in self._viewers.items():
            if viewer["room"] == room:
                try:
                    await viewer["ws"].send_json(message)
                except Exception:
                    dead.append(ws_id)
        for ws_id in dead:
            self._viewers.pop(ws_id, None)

    async def process_session_event(self, event: SessionEvent) -> None:
        agent = self.spatial.get_agent(event.agent_id)
        if agent is None:
            return
        result = translate_session_event(event)
        if result.zone is not None:
            self.spatial.move_agent_to_zone(event.agent_id, result.zone)
            agent = self.spatial.get_agent(event.agent_id)
            await self.broadcast_to_room(agent.room, GameEvent(
                type=GameEventType.AGENT_MOVE, agent_id=event.agent_id,
                data={"zone": result.zone.value, "x": agent.x, "y": agent.y},
            ).to_dict())
        self.spatial.update_visual(event.agent_id, expression=result.expression, accessory=result.accessory, glow=result.glow, bubble=result.bubble)
        agent = self.spatial.get_agent(event.agent_id)
        await self.broadcast_to_room(agent.room, GameEvent(
            type=GameEventType.AGENT_STATE, agent_id=event.agent_id, data=agent.to_dict(),
        ).to_dict())

    async def process_bus_event(self, event: Any) -> None:
        result = translate_bus_event(event)
        if result.is_spawn:
            name = event.data.get("name", event.agent_id)
            agent = self.spatial.register_agent(event.agent_id, name)
            await self.broadcast_to_room("lobby", GameEvent(
                type=GameEventType.AGENT_SPAWN, agent_id=event.agent_id, data=agent.to_dict(),
            ).to_dict())
            return
        if result.is_despawn:
            agent = self.spatial.get_agent(event.agent_id)
            if agent:
                await self.broadcast_to_room(agent.room, GameEvent(
                    type=GameEventType.AGENT_DESPAWN, agent_id=event.agent_id, data={},
                ).to_dict())
                self.spatial.remove_agent(event.agent_id)
            return
        agent = self.spatial.get_agent(event.agent_id)
        if agent is None:
            return
        if result.zone is not None:
            self.spatial.move_agent_to_zone(event.agent_id, result.zone)
            agent = self.spatial.get_agent(event.agent_id)
            await self.broadcast_to_room(agent.room, GameEvent(
                type=GameEventType.AGENT_MOVE, agent_id=event.agent_id,
                data={"zone": result.zone.value, "x": agent.x, "y": agent.y},
            ).to_dict())
        self.spatial.update_visual(event.agent_id, expression=result.expression, accessory=result.accessory, glow=result.glow)
        agent = self.spatial.get_agent(event.agent_id)
        await self.broadcast_to_room(agent.room, GameEvent(
            type=GameEventType.AGENT_STATE, agent_id=event.agent_id, data=agent.to_dict(),
        ).to_dict())

    def _build_snapshot(self, room: str) -> dict:
        if room == "lobby":
            return {
                "type": "world_snapshot",
                "rooms": [r.to_dict() for r in self.spatial.get_room_list()],
                "agents": [a.to_dict() for a in self.spatial.get_agents_in_room("lobby")],
            }
        return {
            "type": "room_snapshot",
            "room": room,
            "agents": [a.to_dict() for a in self.spatial.get_agents_in_room(room)],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_world_gateway.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/gateway.py tests/test_world_gateway.py
git commit -m "feat(world): add WebSocket gateway with event processing and room broadcasting"
```

---

## Task 6: Route Registration & Config Integration

**Files:**
- Create: `contextgraph/world/routes.py`
- Modify: `contextgraph/config.py:80`
- Modify: `contextgraph/web.py:91`

- [ ] **Step 1: Write routes.py**

```python
# contextgraph/world/routes.py
"""World route registration — /world and /ws/world endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from contextgraph.events import EventBus
from contextgraph.service import ContextGraphService

from .gateway import WorldGateway

logger = logging.getLogger(__name__)
_STATIC_DIR = Path(__file__).parent / "static"


def register_world_routes(app: Any, event_bus: EventBus, graph_service: ContextGraphService) -> None:
    from starlette.responses import FileResponse, HTMLResponse
    from starlette.staticfiles import StaticFiles
    from starlette.websockets import WebSocket, WebSocketDisconnect

    gateway = WorldGateway(event_bus=event_bus, graph_service=graph_service)

    try:
        for agent in graph_service.list_agents():
            gateway.spatial.register_agent(agent.agent_id, agent.name)
    except Exception:
        logger.warning("Could not seed world with existing agents")

    async def _event_listener() -> None:
        queue = event_bus.subscribe()
        try:
            while True:
                event = await queue.get()
                try:
                    await gateway.process_bus_event(event)
                except Exception:
                    logger.exception("Error processing bus event in world gateway")
        except asyncio.CancelledError:
            event_bus.unsubscribe(queue)

    @app.on_event("startup")
    async def _start_world_listener() -> None:
        asyncio.create_task(_event_listener())

    if _STATIC_DIR.exists():
        app.mount("/world/static", StaticFiles(directory=str(_STATIC_DIR)), name="world-static")

    @app.get("/world")
    async def world_index() -> Any:
        index_path = _STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path), media_type="text/html")
        return HTMLResponse("<h1>ContextGraph World</h1><p>Static files not found.</p>")

    @app.websocket("/ws/world")
    async def world_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        api_key = websocket.query_params.get("key", "")
        if api_key:
            try:
                graph_service.authenticate_agent(api_key)
            except Exception:
                await websocket.close(code=4003, reason="Invalid API key")
                return

        room = "lobby"
        await gateway.add_viewer(websocket, room=room)
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                msg_type = msg.get("type", "")
                if msg_type == "join_room":
                    room = msg.get("room", "lobby")
                    gateway.switch_viewer_room(websocket, room)
                    await websocket.send_json(gateway._build_snapshot(room))
                elif msg_type == "leave_room":
                    room = "lobby"
                    gateway.switch_viewer_room(websocket, "lobby")
                    await websocket.send_json(gateway._build_snapshot("lobby"))
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            gateway.remove_viewer(websocket)
        except Exception:
            gateway.remove_viewer(websocket)
```

- [ ] **Step 2: Add config settings**

In `contextgraph/config.py`, add after line 80 (`enable_dashboard`):

```python
    # World Visualization
    enable_world: bool = _read_bool("CG_ENABLE_WORLD", False)
    world_max_viewers: int = _read_int("CG_WORLD_MAX_VIEWERS", 50)
```

- [ ] **Step 3: Add conditional mount in web.py**

In `contextgraph/web.py`, add after the streaming block (after line 91):

```python
    if app_settings.enable_world:
        from .world.routes import register_world_routes

        if not app_settings.enable_streaming:
            from .events import EventBus
            event_bus = EventBus()
        register_world_routes(app, event_bus, graph)
```

- [ ] **Step 4: Verify mount works**

Run: `CG_ENABLE_WORLD=true CG_ENABLE_STREAMING=true python -c "from contextgraph.web import create_app; app = create_app(); print('World mounted')"`
Expected: "World mounted"

- [ ] **Step 5: Commit**

```bash
git add contextgraph/world/routes.py contextgraph/config.py contextgraph/web.py
git commit -m "feat(world): add route registration and config integration"
```

---

## Task 7: Phaser Client — Entry Point & Boot

**Files:**
- Create: `contextgraph/world/static/index.html`
- Create: `contextgraph/world/static/style.css`
- Create: `contextgraph/world/static/game/main.js`
- Create: `contextgraph/world/static/game/net/WorldSocket.js`

- [ ] **Step 1: Create the static directory structure and files**

Create all four files. See the spec section "Frontend Implementation Details" for the complete content of each file. Key points:

**index.html**: Loads Phaser 3 from CDN, links style.css, loads game/main.js as ES module, has `#game-container` and `#inspect-panel` divs.

**style.css**: Dark theme matching ContextGraph dashboard. Styles for inspect panel (`.inspect-panel`, `.inspect-section`, `.bucket-grid`, `.timeline-item`), game dimming (`.game-dimmed canvas`), and responsive scaling.

**WorldSocket.js**: ES module class. Builds `ws://` URL from page location with `?key=` param. `connect()`, `send()`, `joinRoom()`, `leaveRoom()` methods. Auto-reconnects on close with 2s delay. Dispatches messages as `ws:<type>` events on the scene.

**main.js**: Imports WorldSocket, LobbyScene, RoomScene. Creates a BootScene that shows "Connecting...", creates WorldSocket, and transitions to LobbyScene on `ws:world_snapshot`. Phaser config: 1024x768, pixelArt mode, FIT scaling.

- [ ] **Step 2: Commit**

```bash
git add contextgraph/world/static/
git commit -m "feat(world): add Phaser client entry point, WebSocket client, and base styles"
```

---

## Task 8: Lobby Scene & Agent Sprites

**Files:**
- Create: `contextgraph/world/static/game/scenes/LobbyScene.js`
- Create: `contextgraph/world/static/game/sprites/AgentSprite.js`
- Create: `contextgraph/world/static/game/ui/RoomDoor.js`

- [ ] **Step 1: Create AgentSprite.js**

ES module. Extends `Phaser.GameObjects.Container`. Constructor takes scene and agent data object. Renders: ellipse body (tinted by color_index), white belly ellipse, two white eyes with dark pupils, arc mouth, two feet ellipses, name tag text, glow ellipse under feet. Methods: `moveTo(x, y, duration)` using `scene.tweens.add`, `setExpression(name)` adjusting eye/mouth shapes, `setGlow(color)`, `showBubble(text)` with 8s auto-dismiss, `updateFromData(data)`. Interactive — emits `inspect-agent` event on click.

- [ ] **Step 2: Create RoomDoor.js**

ES module. Extends `Phaser.GameObjects.Container`. Renders a rectangle door frame, room name label, agent count badge. Interactive — emits `enter-room` event with `roomId` on click. Hover changes door color.

- [ ] **Step 3: Create LobbyScene.js**

ES module Phaser.Scene with key `LobbyScene`. `init(data)` receives socket and snapshot. `create()` renders: dark background, floor area rectangle, title text, doors from `snapshot.rooms` using RoomDoor, agent sprites from `snapshot.agents` using AgentSprite. Listens for `ws:agent_spawn`, `ws:agent_state`, `ws:agent_move`, `ws:agent_despawn` events. `enter-room` event calls `socket.joinRoom()`. `ws:room_snapshot` transitions to RoomScene.

- [ ] **Step 4: Commit**

```bash
git add contextgraph/world/static/game/scenes/LobbyScene.js contextgraph/world/static/game/sprites/AgentSprite.js contextgraph/world/static/game/ui/RoomDoor.js
git commit -m "feat(world): add LobbyScene, AgentSprite, and RoomDoor components"
```

---

## Task 9: Room Scene

**Files:**
- Create: `contextgraph/world/static/game/scenes/RoomScene.js`

- [ ] **Step 1: Create RoomScene.js**

ES module Phaser.Scene with key `RoomScene`. `init(data)` receives socket and snapshot. `create()` renders: background, room title, "< Lobby" back button, four zone rectangles with labels (Code Desk yellow, Memory Library purple, Review Station blue, Debug Lab red), agent sprites from snapshot. Listens for `ws:agent_move`, `ws:agent_state`, `ws:agent_interact` (walks two agents to midpoint with blue glow), `ws:agent_despawn`. Back button calls `socket.leaveRoom()`. `ws:world_snapshot` transitions back to LobbyScene.

- [ ] **Step 2: Commit**

```bash
git add contextgraph/world/static/game/scenes/RoomScene.js
git commit -m "feat(world): add RoomScene with zone rendering and agent interactions"
```

---

## Task 10: Inspect Panel (DOM Overlay)

**Files:**
- Create: `contextgraph/world/static/game/ui/InspectPanel.js`
- Modify: `contextgraph/world/static/game/main.js`

- [ ] **Step 1: Create InspectPanel.js**

ES module class (not Phaser — pure DOM). Constructor gets `#inspect-panel` element, listens for `inspect-agent` CustomEvent on window. `show(agentId)` method: removes `.hidden` class, adds `.game-dimmed` to game container, fetches agent data from `/v1/agents/{id}`, sessions from `/v1/sessions?agent_id={id}&limit=1`, events from `/v1/sessions/{sessionId}/events`. `render(agent, session, events)` method: builds DOM elements using `document.createElement` (not innerHTML) for each section — header, current task, bucket grid, tools, timeline. `hide()` method: adds `.hidden`, removes `.game-dimmed`. All text content set via `textContent` property for safety.

- [ ] **Step 2: Update main.js**

Import InspectPanel and initialize after `new Phaser.Game(config)`:

```javascript
import { InspectPanel } from './ui/InspectPanel.js';
window.__inspectPanel = new InspectPanel();
```

- [ ] **Step 3: Commit**

```bash
git add contextgraph/world/static/game/ui/InspectPanel.js contextgraph/world/static/game/main.js
git commit -m "feat(world): add InspectPanel DOM overlay with session state and timeline"
```

---

## Task 11: Integration Test — Full Round Trip

**Files:**
- Create: `tests/test_world_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_world_integration.py
"""Integration test: CG event → gateway → game event broadcast."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from contextgraph.events import Event, EventBus, EventType
from contextgraph.models import SessionEvent
from contextgraph.world.gateway import WorldGateway


@pytest.fixture
def gateway():
    return WorldGateway(event_bus=EventBus(), graph_service=type("S", (), {"list_agents": lambda self: []})())


@pytest.mark.asyncio
async def test_full_session_event_round_trip(gateway):
    gateway.spatial.register_agent("alice", "alice-agent")
    gateway.spatial.move_agent_to_room("alice", "api-svc")
    ws = AsyncMock()
    await gateway.add_viewer(ws, room="api-svc")
    ws.reset_mock()
    event = SessionEvent(event_id="e1", session_id="s1", agent_id="alice",
        event_type="file_change", content="src/handler.py",
        created_at=datetime.now(timezone.utc), sequence=1)
    await gateway.process_session_event(event)
    agent = gateway.spatial.get_agent("alice")
    assert agent.zone.value == "code_desk"
    assert ws.send_json.call_count >= 1


@pytest.mark.asyncio
async def test_bus_event_agent_registered(gateway):
    ws = AsyncMock()
    await gateway.add_viewer(ws, room="lobby")
    ws.reset_mock()
    event = Event(event_id="e1", event_type=EventType.AGENT_REGISTERED,
        data={"name": "new-bot"}, timestamp=datetime.now(timezone.utc), agent_id="new-bot")
    await gateway.process_bus_event(event)
    assert gateway.spatial.get_agent("new-bot") is not None
    assert ws.send_json.call_count >= 1


@pytest.mark.asyncio
async def test_failure_moves_to_debug_lab(gateway):
    gateway.spatial.register_agent("bob", "bob-builder")
    gateway.spatial.move_agent_to_room("bob", "web-app")
    event = SessionEvent(event_id="e2", session_id="s2", agent_id="bob",
        event_type="failure", content="TypeError",
        created_at=datetime.now(timezone.utc), sequence=1)
    await gateway.process_session_event(event)
    agent = gateway.spatial.get_agent("bob")
    assert agent.zone.value == "debug_lab"
    assert agent.expression.value == "worried"
    assert agent.glow.value == "red"


@pytest.mark.asyncio
async def test_viewer_room_isolation(gateway):
    gateway.spatial.register_agent("alice", "alice-agent")
    gateway.spatial.move_agent_to_room("alice", "api-svc")
    ws_api, ws_lobby = AsyncMock(), AsyncMock()
    await gateway.add_viewer(ws_api, room="api-svc")
    await gateway.add_viewer(ws_lobby, room="lobby")
    ws_api.reset_mock()
    ws_lobby.reset_mock()
    event = SessionEvent(event_id="e3", session_id="s3", agent_id="alice",
        event_type="file_change", content="src/main.py",
        created_at=datetime.now(timezone.utc), sequence=1)
    await gateway.process_session_event(event)
    assert ws_api.send_json.call_count >= 1
    assert ws_lobby.send_json.call_count == 0
```

- [ ] **Step 2: Run all world tests**

Run: `python -m pytest tests/test_world_*.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_world_integration.py
git commit -m "test(world): add integration tests for full event round-trip"
```

---

## Task 12: Final Verification & Smoke Test

- [ ] **Step 1: Run full test suite (world + existing)**

Run: `python -m pytest tests/ -v -x`
Expected: All pass, no regressions.

- [ ] **Step 2: Manual smoke test**

```bash
CG_ENABLE_WORLD=true CG_ENABLE_STREAMING=true python -m contextgraph.server
```

Open `http://localhost:8420/world`. Verify:
- Page loads with "ContextGraph World"
- "Connecting..." appears briefly
- WebSocket connects (browser console: "[World] Connected")
- Lobby renders with any existing agents

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(world): complete MVP — real-time 2D agent visualization world"
```
