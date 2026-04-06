"""Room templates, zone definitions, and position helpers."""
from __future__ import annotations

import hashlib
import random
from typing import Sequence

from .models import ZoneType

AGENT_COLORS = [
    "#6366f1", "#f97316", "#06b6d4", "#ec4899", "#10b981", "#f59e0b",
    "#f43f5e", "#0ea5e9", "#8b5cf6", "#14b8a6", "#84cc16", "#d946ef",
]

ROOM_ZONES: dict[ZoneType, dict[str, float]] = {
    ZoneType.CODE_DESK:       {"x": 80,  "y": 120, "w": 300, "h": 200},
    ZoneType.MEMORY_LIBRARY:  {"x": 640, "y": 120, "w": 300, "h": 200},
    ZoneType.REVIEW_STATION:  {"x": 80,  "y": 440, "w": 300, "h": 200},
    ZoneType.DEBUG_LAB:       {"x": 640, "y": 440, "w": 300, "h": 200},
}

LOBBY_ZONES: dict[str, dict[str, float]] = {
    "idle": {"x": 200, "y": 250, "w": 600, "h": 300},
}


def color_index_for_agent(agent_id: str) -> int:
    return int(hashlib.md5(agent_id.encode()).hexdigest()[:8], 16) % len(AGENT_COLORS)


def get_zone_position(
    zone: ZoneType,
    exclude: Sequence[tuple[float, float]] = (),
    min_distance: float = 40.0,
) -> tuple[float, float]:
    rect = ROOM_ZONES[zone]
    for _ in range(50):
        x = random.uniform(rect["x"], rect["x"] + rect["w"])
        y = random.uniform(rect["y"], rect["y"] + rect["h"])
        if all(((x - ex) ** 2 + (y - ey) ** 2) ** 0.5 >= min_distance for ex, ey in exclude):
            return (x, y)
    return (rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] / 2)


def get_lobby_idle_position(exclude: Sequence[tuple[float, float]] = ()) -> tuple[float, float]:
    rect = LOBBY_ZONES["idle"]
    for _ in range(50):
        x = random.uniform(rect["x"], rect["x"] + rect["w"])
        y = random.uniform(rect["y"], rect["y"] + rect["h"])
        if all(((x - ex) ** 2 + (y - ey) ** 2) ** 0.5 >= 40.0 for ex, ey in exclude):
            return (x, y)
    return (rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] / 2)


def get_lobby_door_position(door_index: int) -> tuple[float, float]:
    return (160.0 + door_index * 160, 100.0)
