"""Tests for contextgraph.world.rooms — room layout definitions and position helpers."""
from __future__ import annotations

import math

import pytest

from contextgraph.world.models import ZoneType
from contextgraph.world.rooms import (
    AGENT_COLORS,
    DEMO_ROOM_SPECS,
    LOBBY_ZONES,
    ROOM_ZONES,
    color_index_for_agent,
    get_demo_room_info,
    get_lobby_door_position,
    get_lobby_idle_position,
    get_room_display_name,
    get_room_theme_key,
    get_zone_position,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestAgentColors:
    def test_has_12_colors(self):
        assert len(AGENT_COLORS) == 12

    def test_all_hex_strings(self):
        for color in AGENT_COLORS:
            assert color.startswith("#"), f"{color!r} should start with #"
            assert len(color) == 7, f"{color!r} should be 7 chars"

    def test_exact_colors(self):
        expected = [
            "#6366f1", "#f97316", "#06b6d4", "#ec4899", "#10b981", "#f59e0b",
            "#f43f5e", "#0ea5e9", "#8b5cf6", "#14b8a6", "#84cc16", "#d946ef",
        ]
        assert AGENT_COLORS == expected


class TestRoomZones:
    def test_has_all_zone_types(self):
        assert set(ROOM_ZONES.keys()) == set(ZoneType)

    def test_each_zone_has_xywh(self):
        for zone, rect in ROOM_ZONES.items():
            for key in ("x", "y", "w", "h"):
                assert key in rect, f"Zone {zone} missing {key!r}"

    def test_code_desk(self):
        z = ROOM_ZONES[ZoneType.CODE_DESK]
        assert z == {"x": 80, "y": 120, "w": 300, "h": 200}

    def test_memory_library(self):
        z = ROOM_ZONES[ZoneType.MEMORY_LIBRARY]
        assert z == {"x": 640, "y": 120, "w": 300, "h": 200}

    def test_review_station(self):
        z = ROOM_ZONES[ZoneType.REVIEW_STATION]
        assert z == {"x": 80, "y": 440, "w": 300, "h": 200}

    def test_debug_lab(self):
        z = ROOM_ZONES[ZoneType.DEBUG_LAB]
        assert z == {"x": 640, "y": 440, "w": 300, "h": 200}


class TestLobbyZones:
    def test_has_idle_key(self):
        assert "idle" in LOBBY_ZONES

    def test_idle_rect(self):
        assert LOBBY_ZONES["idle"] == {"x": 220, "y": 190, "w": 580, "h": 300}


# ---------------------------------------------------------------------------
# color_index_for_agent
# ---------------------------------------------------------------------------


class TestColorIndexForAgent:
    def test_returns_int(self):
        idx = color_index_for_agent("agent-abc")
        assert isinstance(idx, int)

    def test_in_range(self):
        for agent_id in ["a", "b", "c", "agent-1", "agent-xyz-999"]:
            idx = color_index_for_agent(agent_id)
            assert 0 <= idx < 12, f"{agent_id!r} gave out-of-range index {idx}"

    def test_deterministic(self):
        idx1 = color_index_for_agent("stable-agent")
        idx2 = color_index_for_agent("stable-agent")
        assert idx1 == idx2

    def test_different_agents_can_differ(self):
        indices = {color_index_for_agent(f"agent-{i}") for i in range(50)}
        # With 50 agents and 12 slots, at least a few distinct values expected
        assert len(indices) > 1


class TestRoomThemeKey:
    def test_is_deterministic(self):
        assert get_room_theme_key("stable_room") == get_room_theme_key("stable_room")

    def test_uses_allowed_theme_keys(self):
        assert get_room_theme_key("project_alpha") in {"library", "observatory", "alchemy", "workshop"}

    def test_demo_rooms_use_explicit_theme_mapping(self):
        for room_id, spec in DEMO_ROOM_SPECS.items():
            assert get_room_theme_key(room_id) == spec["theme_key"]


class TestRoomCatalog:
    def test_demo_room_catalog_has_all_demo_rooms(self):
        rooms = get_demo_room_info()
        assert len(rooms) == len(DEMO_ROOM_SPECS)
        assert {room["room_id"] for room in rooms} == set(DEMO_ROOM_SPECS)

    def test_demo_room_display_name_is_human_friendly(self):
        assert get_room_display_name("ancient_library") == "Ancient Library"

    def test_custom_room_display_name_falls_back_to_title_case(self):
        assert get_room_display_name("project_alpha") == "Project Alpha"


# ---------------------------------------------------------------------------
# get_zone_position
# ---------------------------------------------------------------------------


class TestGetZonePosition:
    def _within_rect(self, x: float, y: float, rect: dict) -> bool:
        return rect["x"] <= x <= rect["x"] + rect["w"] and rect["y"] <= y <= rect["y"] + rect["h"]

    def test_returns_tuple_of_two_floats(self):
        pos = get_zone_position(ZoneType.CODE_DESK, [])
        assert isinstance(pos, tuple)
        assert len(pos) == 2

    def test_position_within_zone_rect(self):
        rect = ROOM_ZONES[ZoneType.CODE_DESK]
        for _ in range(20):
            x, y = get_zone_position(ZoneType.CODE_DESK, [])
            assert self._within_rect(x, y, rect), f"({x}, {y}) outside {rect}"

    def test_avoids_excluded_positions(self):
        """With min_distance=40, returned position should be >= 40 from all excludes."""
        min_dist = 40
        # Use a point near the centre of the zone
        rect = ROOM_ZONES[ZoneType.CODE_DESK]
        cx = rect["x"] + rect["w"] / 2
        cy = rect["y"] + rect["h"] / 2
        exclude = [(cx, cy)]

        found_far = False
        for _ in range(100):
            x, y = get_zone_position(ZoneType.CODE_DESK, exclude, min_distance=min_dist)
            d = math.hypot(x - cx, y - cy)
            if d >= min_dist:
                found_far = True
                break
        assert found_far, "get_zone_position never returned a position far from the excluded point"

    def test_all_zone_types_work(self):
        for zone in ZoneType:
            pos = get_zone_position(zone, [])
            assert len(pos) == 2


# ---------------------------------------------------------------------------
# get_lobby_door_position
# ---------------------------------------------------------------------------


class TestGetLobbyDoorPosition:
    def test_returns_tuple(self):
        pos = get_lobby_door_position(0)
        assert isinstance(pos, tuple) and len(pos) == 2

    def test_first_door_x(self):
        x, y = get_lobby_door_position(0)
        assert x == 160

    def test_y_is_112(self):
        for i in range(5):
            _, y = get_lobby_door_position(i)
            assert y == 112

    def test_spacing_is_160(self):
        x0, _ = get_lobby_door_position(0)
        x1, _ = get_lobby_door_position(1)
        x2, _ = get_lobby_door_position(2)
        assert x1 - x0 == 160
        assert x2 - x1 == 160


# ---------------------------------------------------------------------------
# get_lobby_idle_position
# ---------------------------------------------------------------------------


class TestGetLobbyIdlePosition:
    def test_returns_tuple(self):
        pos = get_lobby_idle_position([])
        assert isinstance(pos, tuple) and len(pos) == 2

    def test_within_idle_rect(self):
        rect = LOBBY_ZONES["idle"]
        for _ in range(20):
            x, y = get_lobby_idle_position([])
            assert rect["x"] <= x <= rect["x"] + rect["w"], f"x={x} out of bounds"
            assert rect["y"] <= y <= rect["y"] + rect["h"], f"y={y} out of bounds"

    def test_returns_different_positions(self):
        positions = [get_lobby_idle_position([]) for _ in range(10)]
        unique = set(positions)
        assert len(unique) > 1, "Expected different positions each call"
