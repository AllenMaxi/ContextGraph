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
            "agent_id": self.agent_id, "name": self.name, "color_index": self.color_index,
            "expression": self.expression.value, "accessory": self.accessory.value,
            "glow": self.glow.value, "bubble": self.bubble,
            "x": self.x, "y": self.y, "room": self.room,
            "zone": self.zone.value if self.zone else None,
        }


@dataclass
class GameEvent:
    type: GameEventType
    agent_id: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type.value, "agent_id": self.agent_id, "data": self.data}


@dataclass
class RoomInfo:
    room_id: str
    name: str
    agent_count: int = 0

    def to_dict(self) -> dict:
        return {"room_id": self.room_id, "name": self.name, "agent_count": self.agent_count}
