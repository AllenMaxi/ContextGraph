"""Tests for contextgraph.world.spatial — SpatialState."""

from __future__ import annotations

from contextgraph.world.models import (
    Accessory,
    Expression,
    GlowColor,
    ZoneType,
)
from contextgraph.world.rooms import DEMO_ROOM_SPECS
from contextgraph.world.spatial import SpatialState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_state(*agent_specs: tuple[str, str]) -> SpatialState:
    """Return a SpatialState with the given (agent_id, name) pairs registered."""
    state = SpatialState()
    for agent_id, name in agent_specs:
        state.register_agent(agent_id, name)
    return state


# ---------------------------------------------------------------------------
# register_agent
# ---------------------------------------------------------------------------


class TestRegisterAgent:
    def test_creates_agent_in_lobby(self):
        state = SpatialState()
        agent = state.register_agent("a1", "Alice")
        assert agent.agent_id == "a1"
        assert agent.name == "Alice"
        assert agent.room == "lobby"

    def test_initial_expression_is_sleepy(self):
        state = SpatialState()
        agent = state.register_agent("a1", "Alice")
        assert agent.expression == Expression.SLEEPY

    def test_initial_glow_is_gray(self):
        state = SpatialState()
        agent = state.register_agent("a1", "Alice")
        assert agent.glow == GlowColor.GRAY

    def test_initial_accessory_is_sleep_bubble(self):
        state = SpatialState()
        agent = state.register_agent("a1", "Alice")
        assert agent.accessory == Accessory.SLEEP_BUBBLE

    def test_initial_zone_is_none(self):
        state = SpatialState()
        agent = state.register_agent("a1", "Alice")
        assert agent.zone is None

    def test_idempotent_returns_same_object(self):
        state = SpatialState()
        first = state.register_agent("a1", "Alice")
        second = state.register_agent("a1", "Alice")
        assert first is second

    def test_color_index_is_deterministic(self):
        state1 = SpatialState()
        state2 = SpatialState()
        a1 = state1.register_agent("deterministic-id", "X")
        a2 = state2.register_agent("deterministic-id", "X")
        assert a1.color_index == a2.color_index

    def test_multiple_agents_get_unique_positions(self):
        state = SpatialState()
        agents = [state.register_agent(f"a{i}", f"Agent{i}") for i in range(5)]
        positions = [(a.x, a.y) for a in agents]
        # All positions should be distinct (collision avoidance)
        assert len(set(positions)) == len(positions)


# ---------------------------------------------------------------------------
# get_agent / get_all_agents
# ---------------------------------------------------------------------------


class TestGetters:
    def test_get_agent_returns_none_for_unknown(self):
        state = SpatialState()
        assert state.get_agent("nope") is None

    def test_get_agent_returns_registered(self):
        state = make_state(("a1", "Alice"))
        assert state.get_agent("a1") is not None

    def test_get_all_agents_empty(self):
        assert SpatialState().get_all_agents() == []

    def test_get_all_agents_count(self):
        state = make_state(("a1", "A"), ("a2", "B"), ("a3", "C"))
        assert len(state.get_all_agents()) == 3


# ---------------------------------------------------------------------------
# get_agents_in_room
# ---------------------------------------------------------------------------


class TestGetAgentsInRoom:
    def test_all_new_agents_in_lobby(self):
        state = make_state(("a1", "A"), ("a2", "B"))
        assert len(state.get_agents_in_room("lobby")) == 2

    def test_moved_agent_leaves_lobby(self):
        state = make_state(("a1", "A"), ("a2", "B"))
        state.move_agent_to_room("a1", "workshop")
        assert len(state.get_agents_in_room("lobby")) == 1
        assert len(state.get_agents_in_room("workshop")) == 1

    def test_unknown_room_returns_empty(self):
        state = make_state(("a1", "A"))
        assert state.get_agents_in_room("nonexistent") == []


# ---------------------------------------------------------------------------
# get_room_list
# ---------------------------------------------------------------------------


class TestGetRoomList:
    def test_lobby_returns_demo_rooms_but_not_lobby(self):
        state = make_state(("a1", "A"), ("a2", "B"))
        rooms = state.get_room_list()
        room_ids = {room.room_id for room in rooms}
        assert "lobby" not in room_ids
        assert set(DEMO_ROOM_SPECS).issubset(room_ids)
        assert all(room.agent_count == 0 for room in rooms if room.room_id in DEMO_ROOM_SPECS)

    def test_room_list_counts_agents(self):
        state = make_state(("a1", "A"), ("a2", "B"), ("a3", "C"))
        state.move_agent_to_room("a1", "workshop")
        state.move_agent_to_room("a2", "workshop")
        state.move_agent_to_room("a3", "lab")
        rooms = {r.room_id: r.agent_count for r in state.get_room_list()}
        assert rooms["workshop"] == 2
        assert rooms["lab"] == 1

    def test_room_list_room_info_has_name(self):
        state = make_state(("a1", "A"))
        state.move_agent_to_room("a1", "code_desk")
        rooms = {room.room_id: room for room in state.get_room_list()}
        assert "code_desk" in rooms
        assert rooms["code_desk"].name  # non-empty string


# ---------------------------------------------------------------------------
# move_agent_to_room
# ---------------------------------------------------------------------------


class TestMoveAgentToRoom:
    def test_move_to_non_lobby_sets_happy_green(self):
        state = make_state(("a1", "A"))
        state.move_agent_to_room("a1", "workshop")
        agent = state.get_agent("a1")
        assert agent.expression == Expression.HAPPY
        assert agent.glow == GlowColor.GREEN

    def test_move_back_to_lobby_resets_to_sleepy_gray(self):
        state = make_state(("a1", "A"))
        state.move_agent_to_room("a1", "workshop")
        state.move_agent_to_room("a1", "lobby")
        agent = state.get_agent("a1")
        assert agent.expression == Expression.SLEEPY
        assert agent.glow == GlowColor.GRAY
        assert agent.accessory == Accessory.SLEEP_BUBBLE

    def test_move_resets_zone(self):
        state = make_state(("a1", "A"))
        state.move_agent_to_room("a1", "workshop")
        state.move_agent_to_zone("a1", ZoneType.CODE_DESK)
        state.move_agent_to_room("a1", "lobby")
        agent = state.get_agent("a1")
        assert agent.zone is None

    def test_move_unknown_agent_is_noop(self):
        state = SpatialState()
        state.move_agent_to_room("ghost", "workshop")  # must not raise


# ---------------------------------------------------------------------------
# move_agent_to_zone
# ---------------------------------------------------------------------------


class TestMoveAgentToZone:
    def test_zone_is_set(self):
        state = make_state(("a1", "A"))
        state.move_agent_to_zone("a1", ZoneType.CODE_DESK)
        agent = state.get_agent("a1")
        assert agent.zone == ZoneType.CODE_DESK

    def test_position_within_zone_bounds(self):
        from contextgraph.world.rooms import ROOM_ZONES

        state = make_state(("a1", "A"))
        state.move_agent_to_zone("a1", ZoneType.CODE_DESK)
        agent = state.get_agent("a1")
        rect = ROOM_ZONES[ZoneType.CODE_DESK]
        assert rect["x"] <= agent.x <= rect["x"] + rect["w"]
        assert rect["y"] <= agent.y <= rect["y"] + rect["h"]

    def test_multiple_agents_in_zone_spaced_out(self):
        state = make_state(("a1", "A"), ("a2", "B"))
        state.move_agent_to_zone("a1", ZoneType.MEMORY_LIBRARY)
        state.move_agent_to_zone("a2", ZoneType.MEMORY_LIBRARY)
        a1 = state.get_agent("a1")
        a2 = state.get_agent("a2")
        dist = ((a1.x - a2.x) ** 2 + (a1.y - a2.y) ** 2) ** 0.5
        assert dist >= 40.0

    def test_unknown_agent_is_noop(self):
        state = SpatialState()
        state.move_agent_to_zone("ghost", ZoneType.DEBUG_LAB)  # must not raise


# ---------------------------------------------------------------------------
# update_visual
# ---------------------------------------------------------------------------


class TestUpdateVisual:
    def test_update_expression(self):
        state = make_state(("a1", "A"))
        state.update_visual("a1", expression=Expression.FOCUSED)
        assert state.get_agent("a1").expression == Expression.FOCUSED

    def test_update_glow(self):
        state = make_state(("a1", "A"))
        state.update_visual("a1", glow=GlowColor.RED)
        assert state.get_agent("a1").glow == GlowColor.RED

    def test_update_accessory(self):
        state = make_state(("a1", "A"))
        state.update_visual("a1", accessory=Accessory.HARD_HAT)
        assert state.get_agent("a1").accessory == Accessory.HARD_HAT

    def test_update_bubble(self):
        state = make_state(("a1", "A"))
        state.update_visual("a1", bubble="Hello!")
        assert state.get_agent("a1").bubble == "Hello!"

    def test_none_fields_not_overwritten(self):
        state = make_state(("a1", "A"))
        state.update_visual("a1", expression=Expression.WORRIED)
        # Call again with only glow; expression must not be reset
        state.update_visual("a1", glow=GlowColor.BLUE)
        agent = state.get_agent("a1")
        assert agent.expression == Expression.WORRIED
        assert agent.glow == GlowColor.BLUE

    def test_update_unknown_agent_is_noop(self):
        state = SpatialState()
        state.update_visual("ghost", expression=Expression.HAPPY)  # must not raise


# ---------------------------------------------------------------------------
# remove_agent
# ---------------------------------------------------------------------------


class TestRemoveAgent:
    def test_remove_deletes_agent(self):
        state = make_state(("a1", "A"))
        state.remove_agent("a1")
        assert state.get_agent("a1") is None

    def test_remove_reduces_count(self):
        state = make_state(("a1", "A"), ("a2", "B"))
        state.remove_agent("a1")
        assert len(state.get_all_agents()) == 1

    def test_remove_unknown_agent_is_noop(self):
        state = SpatialState()
        state.remove_agent("ghost")  # must not raise
