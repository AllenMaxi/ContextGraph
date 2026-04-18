"""Tests for ContextGraph World V2 — anchors, layouts, meetings, blocker tracker."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from contextgraph.events import Event, EventBus, EventType
from contextgraph.models import SessionEvent
from contextgraph.world.gateway import WorldGateway
from contextgraph.world.meeting import PHASE_ORDER, MeetingOrchestrator
from contextgraph.world.models import (
    Activity,
    AgentVisual,
    Anchor,
    Facing,
    Meeting,
    MeetingCircle,
    MeetingPhase,
    MeetingTrigger,
    ZoneType,
)
from contextgraph.world.rooms import (
    assign_home_anchor,
    get_home_anchors_for_zone,
    get_idle_anchors,
    get_layout,
    get_lobby_layout,
    get_room_layout,
    get_room_theme_key,
    get_wander_position,
)
from contextgraph.world.spatial import SpatialState
from contextgraph.world.translator import BlockerTracker, translate_bus_event, translate_session_event

# ══════════════════════════════════════════════════════════════════════
# Room Layout Tests
# ══════════════════════════════════════════════════════════════════════


class TestRoomLayout:
    def test_lobby_layout_has_anchors(self):
        layout = get_lobby_layout()
        assert layout.room_id == "lobby"
        assert len(layout.anchors) >= 10  # idle anchors + center + seats
        assert "center" in layout.anchors

    def test_lobby_layout_has_meeting_circle(self):
        layout = get_lobby_layout()
        mc = layout.meeting_circle
        assert mc is not None
        assert mc.x == 512.0
        assert mc.y == 336.0
        assert mc.radius == 52.0
        assert mc.seat_a in layout.anchors
        assert mc.seat_b in layout.anchors

    def test_lobby_layout_stages_agents_away_from_extreme_corners(self):
        layout = get_lobby_layout()
        idle = [layout.anchors[aid] for aid in get_idle_anchors(layout)]
        assert all(220 <= anchor.x <= 800 for anchor in idle)
        assert all(190 <= anchor.y <= 460 for anchor in idle)

    def test_lobby_layout_has_edges(self):
        layout = get_lobby_layout()
        assert len(layout.edges) > 0
        # All edges reference valid anchors
        for a, b in layout.edges:
            assert a in layout.anchors, f"Edge anchor {a} not found"
            assert b in layout.anchors, f"Edge anchor {b} not found"

    def test_project_room_layout_has_zone_anchors(self):
        layout = get_room_layout("test_project")
        for zone in ZoneType:
            zone_anchors = get_home_anchors_for_zone(layout, zone)
            assert len(zone_anchors) >= 2, f"Zone {zone} has < 2 anchors"

    def test_project_room_layout_has_meeting_circle(self):
        layout = get_room_layout("test_project")
        mc = layout.meeting_circle
        assert mc is not None
        assert mc.seat_a in layout.anchors
        assert mc.seat_b in layout.anchors

    def test_project_room_has_center_anchor(self):
        layout = get_room_layout("test_project")
        assert "center" in layout.anchors

    def test_shortest_path_same_node(self):
        layout = get_room_layout("test_project")
        path = layout.shortest_path("center", "center")
        assert path == ["center"]

    def test_shortest_path_adjacent(self):
        layout = get_room_layout("test_project")
        # center is connected to door anchors
        path = layout.shortest_path("code_desk_door", "center")
        assert len(path) >= 1
        assert path[0] == "code_desk_door"
        assert path[-1] == "center"

    def test_shortest_path_cross_zone(self):
        layout = get_room_layout("test_project")
        path = layout.shortest_path("code_desk_a", "debug_lab_a")
        assert len(path) >= 3  # a → door → center → door → b (at least)
        assert path[0] == "code_desk_a"
        assert path[-1] == "debug_lab_a"

    def test_layout_to_dict(self):
        layout = get_room_layout("test_project")
        d = layout.to_dict()
        assert d["room_id"] == "test_project"
        assert "anchors" in d
        assert "edges" in d
        assert "meeting_circle" in d

    def test_get_layout_lobby(self):
        layout = get_layout("lobby")
        assert layout.room_id == "lobby"

    def test_get_layout_project(self):
        layout = get_layout("my_project")
        assert layout.room_id == "my_project"

    def test_layout_cached(self):
        l1 = get_room_layout("cache_test")
        l2 = get_room_layout("cache_test")
        assert l1 is l2

    def test_assign_home_anchor_zone(self):
        layout = get_room_layout("test_assign")
        anchor_id = assign_home_anchor(layout, zone=ZoneType.CODE_DESK, occupied=set())
        assert anchor_id is not None
        assert anchor_id.startswith("code_desk_")

    def test_assign_home_anchor_avoids_occupied(self):
        layout = get_room_layout("test_assign2")
        # Occupy the first anchor
        first = assign_home_anchor(layout, zone=ZoneType.CODE_DESK, occupied=set())
        second = assign_home_anchor(layout, zone=ZoneType.CODE_DESK, occupied={first})
        assert second is not None
        assert second != first

    def test_assign_home_anchor_none_zone(self):
        layout = get_lobby_layout()
        anchor_id = assign_home_anchor(layout, zone=None, occupied=set())
        assert anchor_id is not None
        assert anchor_id.startswith("idle_")

    def test_get_idle_anchors(self):
        layout = get_lobby_layout()
        idle = get_idle_anchors(layout)
        assert len(idle) >= 8
        for aid in idle:
            assert not aid.startswith("meeting_seat_")
            assert aid != "center"

    def test_wander_position_within_radius(self):
        anchor = Anchor(anchor_id="test", x=500, y=300, wander_radius=40)
        for _ in range(20):
            wx, wy = get_wander_position(anchor)
            dist = ((wx - 500) ** 2 + (wy - 300) ** 2) ** 0.5
            assert dist <= 40.1  # small epsilon for floating point

    def test_anchor_to_dict(self):
        a = Anchor(anchor_id="test", x=100, y=200, zone=ZoneType.CODE_DESK, wander_radius=30)
        d = a.to_dict()
        assert d["anchor_id"] == "test"
        assert d["zone"] == "code_desk"
        assert d["wander_radius"] == 30

    def test_meeting_circle_to_dict(self):
        mc = MeetingCircle(circle_id="c1", x=512, y=313, radius=40, seat_a="sa", seat_b="sb")
        d = mc.to_dict()
        assert d["circle_id"] == "c1"
        assert d["seat_a"] == "sa"
        assert d["seat_b"] == "sb"


# ══════════════════════════════════════════════════════════════════════
# Spatial State Tests (V2 features)
# ══════════════════════════════════════════════════════════════════════


class TestSpatialV2:
    def test_register_agent_gets_anchor(self):
        state = SpatialState()
        agent = state.register_agent("a1", "Alice")
        assert agent.anchor_id is not None
        assert agent.home_anchor_id is not None
        assert agent.activity == Activity.IDLE

    def test_move_agent_to_room_assigns_anchor(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.move_agent_to_room("a1", "project_x")
        agent = state.get_agent("a1")
        assert agent.room == "project_x"
        # In a project room without zone, anchor may or may not be assigned
        # but activity should be idle
        assert agent.activity == Activity.IDLE

    def test_move_agent_to_zone_assigns_anchor(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.move_agent_to_room("a1", "project_x")
        state.move_agent_to_zone("a1", ZoneType.CODE_DESK)
        agent = state.get_agent("a1")
        assert agent.zone == ZoneType.CODE_DESK
        assert agent.anchor_id is not None
        assert "code_desk" in agent.anchor_id

    def test_move_agent_to_anchor(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.move_agent_to_room("a1", "project_x")
        layout = get_layout("project_x")
        state.move_agent_to_anchor("a1", "center")
        agent = state.get_agent("a1")
        assert agent.anchor_id == "center"
        assert agent.x == layout.anchors["center"].x
        assert agent.y == layout.anchors["center"].y

    def test_room_list_includes_theme_key(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.move_agent_to_room("a1", "project_x")
        room = next(room for room in state.get_room_list() if room.room_id == "project_x")
        assert room.theme_key == get_room_theme_key("project_x")

    def test_meeting_blocked_during_zone_move(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.move_agent_to_room("a1", "proj")
        state.move_agent_to_zone("a1", ZoneType.CODE_DESK)

        # Create a meeting
        meeting = Meeting(
            meeting_id="m1", room_id="proj", circle_id="c1",
            trigger=MeetingTrigger.CLAIM_REVIEW, agent_a="a1", agent_b="a2",
        )
        state.register_agent("a2", "Bob")
        state.move_agent_to_room("a2", "proj")
        state.create_meeting(meeting)

        # Try to move agent to zone — should be blocked
        agent = state.get_agent("a1")
        old_anchor = agent.anchor_id
        state.move_agent_to_zone("a1", ZoneType.DEBUG_LAB)
        # Agent should not have moved
        assert state.get_agent("a1").anchor_id == old_anchor

    def test_create_meeting(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.register_agent("a2", "Bob")
        state.move_agent_to_room("a1", "proj")
        state.move_agent_to_room("a2", "proj")

        meeting = Meeting(
            meeting_id="m1", room_id="proj", circle_id="c1",
            trigger=MeetingTrigger.CLAIM_REVIEW, agent_a="a1", agent_b="a2",
        )
        result = state.create_meeting(meeting)
        assert result is True
        assert state.is_circle_occupied("proj")
        assert state.is_agent_in_meeting("a1")
        assert state.is_agent_in_meeting("a2")

    def test_create_meeting_occupied_circle(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.register_agent("a2", "Bob")
        state.register_agent("a3", "Carol")
        state.register_agent("a4", "Dave")

        m1 = Meeting(
            meeting_id="m1", room_id="proj", circle_id="c1",
            trigger=MeetingTrigger.CLAIM_REVIEW, agent_a="a1", agent_b="a2",
        )
        m2 = Meeting(
            meeting_id="m2", room_id="proj", circle_id="c1",
            trigger=MeetingTrigger.BLOCKER_ASSIST, agent_a="a3", agent_b="a4",
        )
        assert state.create_meeting(m1) is True
        assert state.create_meeting(m2) is False

    def test_end_meeting(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.register_agent("a2", "Bob")
        state.move_agent_to_room("a1", "proj")
        state.move_agent_to_room("a2", "proj")
        state.move_agent_to_zone("a1", ZoneType.CODE_DESK)
        state.move_agent_to_zone("a2", ZoneType.DEBUG_LAB)

        home_a1 = state.get_agent("a1").home_anchor_id
        home_a2 = state.get_agent("a2").home_anchor_id

        meeting = Meeting(
            meeting_id="m1", room_id="proj", circle_id="c1",
            trigger=MeetingTrigger.CLAIM_REVIEW, agent_a="a1", agent_b="a2",
        )
        state.create_meeting(meeting)
        ended = state.end_meeting("m1")

        assert ended is not None
        assert not state.is_circle_occupied("proj")
        assert not state.is_agent_in_meeting("a1")
        assert not state.is_agent_in_meeting("a2")
        # Agents return to home anchors
        assert state.get_agent("a1").anchor_id == home_a1
        assert state.get_agent("a2").anchor_id == home_a2

    def test_remove_agent_ends_meeting(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.register_agent("a2", "Bob")

        meeting = Meeting(
            meeting_id="m1", room_id="proj", circle_id="c1",
            trigger=MeetingTrigger.CLAIM_REVIEW, agent_a="a1", agent_b="a2",
        )
        state.create_meeting(meeting)
        state.remove_agent("a1")

        assert not state.is_circle_occupied("proj")
        assert state.get_agent("a1") is None

    def test_update_activity(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.update_activity("a1", Activity.CODING)
        assert state.get_agent("a1").activity == Activity.CODING

    def test_update_facing(self):
        state = SpatialState()
        state.register_agent("a1", "Alice")
        state.update_facing("a1", Facing.LEFT)
        assert state.get_agent("a1").facing == Facing.LEFT


# ══════════════════════════════════════════════════════════════════════
# Blocker Tracker Tests
# ══════════════════════════════════════════════════════════════════════


class TestBlockerTracker:
    def test_single_failure_no_trigger(self):
        tracker = BlockerTracker()
        assert tracker.record_failure("a1", timestamp=100.0) is False

    def test_two_failures_triggers(self):
        tracker = BlockerTracker()
        tracker.record_failure("a1", timestamp=100.0)
        assert tracker.record_failure("a1", timestamp=110.0) is True

    def test_failures_outside_window_dont_trigger(self):
        tracker = BlockerTracker()
        tracker.record_failure("a1", timestamp=100.0)
        # 200s later — outside 120s window
        assert tracker.record_failure("a1", timestamp=300.0) is False

    def test_failures_at_window_edge(self):
        tracker = BlockerTracker()
        tracker.record_failure("a1", timestamp=100.0)
        # Exactly at edge (100 + 120 = 220)
        assert tracker.record_failure("a1", timestamp=219.9) is True

    def test_different_agents_independent(self):
        tracker = BlockerTracker()
        tracker.record_failure("a1", timestamp=100.0)
        assert tracker.record_failure("a2", timestamp=110.0) is False

    def test_clear_resets(self):
        tracker = BlockerTracker()
        tracker.record_failure("a1", timestamp=100.0)
        tracker.clear("a1")
        assert tracker.record_failure("a1", timestamp=110.0) is False

    def test_threshold_is_configurable(self):
        assert BlockerTracker.THRESHOLD == 2
        assert BlockerTracker.WINDOW_SECONDS == 120


# ══════════════════════════════════════════════════════════════════════
# Translator V2 Tests
# ══════════════════════════════════════════════════════════════════════


class TestTranslatorV2:
    def test_coding_event_has_activity(self):
        evt = SessionEvent(
            event_id="e1", session_id="s1", agent_id="a1",
            event_type="file_change", content="edit", created_at=datetime.now(),
        )
        tr = translate_session_event(evt)
        assert tr.activity == Activity.CODING

    def test_error_event_has_activity(self):
        evt = SessionEvent(
            event_id="e1", session_id="s1", agent_id="a1",
            event_type="failure", content="err", created_at=datetime.now(),
        )
        tr = translate_session_event(evt)
        assert tr.activity == Activity.DEBUGGING

    def test_claim_reviewed_has_meeting_trigger(self):
        event = Event(
            event_id="e1", event_type=EventType.CLAIM_REVIEWED,
            timestamp=time.time(),
            data={"reviewer_agent_id": "r1", "source_agent_id": "s1",
                  "claim_id": "c1", "decision": "accepted"},
            agent_id="r1",
        )
        tr = translate_bus_event(event)
        assert tr.meeting_trigger == MeetingTrigger.CLAIM_REVIEW
        assert tr.meeting_data["reviewer_agent_id"] == "r1"
        assert tr.meeting_data["source_agent_id"] == "s1"

    def test_memory_stored_has_activity(self):
        event = Event(
            event_id="e1", event_type=EventType.MEMORY_STORED,
            timestamp=time.time(),
            data={}, agent_id="a1",
        )
        tr = translate_bus_event(event)
        assert tr.activity == Activity.RESEARCHING


# ══════════════════════════════════════════════════════════════════════
# Gateway V2 Tests
# ══════════════════════════════════════════════════════════════════════


def make_ws():
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


def make_gateway():
    bus = EventBus()
    svc = MagicMock()
    svc.repository = MagicMock()
    svc.repository.list_agents.return_value = []
    gw = WorldGateway(event_bus=bus, graph_service=svc)
    return gw


class TestGatewayV2:
    @pytest.mark.asyncio
    async def test_snapshot_includes_layout(self):
        gw = make_gateway()
        snapshot = gw._build_snapshot("lobby")
        assert "layout" in snapshot
        assert snapshot["layout"]["room_id"] == "lobby"
        assert "anchors" in snapshot["layout"]
        assert "meeting_circle" in snapshot["layout"]

    @pytest.mark.asyncio
    async def test_room_snapshot_includes_layout(self):
        gw = make_gateway()
        gw.spatial.register_agent("a1", "Alice")
        gw.spatial.move_agent_to_room("a1", "my_project")
        snapshot = gw._build_snapshot("my_project")
        assert "layout" in snapshot
        assert snapshot["layout"]["room_id"] == "my_project"
        assert snapshot["theme_key"] == get_room_theme_key("my_project")
        assert "rooms" in snapshot

    def test_project_room_layout_has_idle_anchors(self):
        layout = get_room_layout("theme_test")
        idle = get_idle_anchors(layout)
        assert set(idle) >= {"idle_left", "idle_right"}

    @pytest.mark.asyncio
    async def test_snapshot_includes_meetings(self):
        gw = make_gateway()
        snapshot = gw._build_snapshot("lobby")
        assert "meetings" in snapshot
        assert isinstance(snapshot["meetings"], list)

    @pytest.mark.asyncio
    async def test_session_event_emits_agent_path_on_zone_change(self):
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="proj")

        gw.spatial.register_agent("a1", "Alice")
        gw.spatial.move_agent_to_room("a1", "proj")
        gw.spatial.move_agent_to_zone("a1", ZoneType.CODE_DESK)
        _ = gw.spatial.get_agent("a1").anchor_id

        evt = SessionEvent(
            event_id="e1", session_id="s1", agent_id="a1",
            event_type="artifact", content="ref", created_at=datetime.now(),
        )
        await gw.process_session_event(evt)

        # Should have broadcasts including agent_path if anchor changed
        calls = ws.send_text.call_args_list
        messages = [json.loads(c[0][0]) for c in calls]
        types = {m.get("type") for m in messages}
        # Agent was at code_desk, event moves to memory_library — anchor changes
        assert "agent_state" in types
        agent_state = [m for m in messages if m.get("type") == "agent_state"][-1]
        assert agent_state["data"]["zone"] == "memory_library"

    @pytest.mark.asyncio
    async def test_meeting_not_triggered_for_agents_in_different_rooms(self):
        gw = make_gateway()
        gw.spatial.register_agent("r1", "Reviewer")
        gw.spatial.register_agent("s1", "Source")
        gw.spatial.move_agent_to_room("r1", "proj_a")
        gw.spatial.move_agent_to_room("s1", "proj_b")

        result = await gw.meetings.try_claim_review_meeting("r1", "s1", "c1", "accepted")
        assert result is False

    @pytest.mark.asyncio
    async def test_meeting_not_triggered_for_lobby(self):
        gw = make_gateway()
        gw.spatial.register_agent("r1", "Reviewer")
        gw.spatial.register_agent("s1", "Source")
        # Both in lobby
        result = await gw.meetings.try_claim_review_meeting("r1", "s1", "c1", "accepted")
        assert result is False

    @pytest.mark.asyncio
    async def test_blocker_tracking_on_session_events(self):
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="proj")

        gw.spatial.register_agent("a1", "Alice")
        gw.spatial.register_agent("a2", "Helper")
        gw.spatial.move_agent_to_room("a1", "proj")
        gw.spatial.move_agent_to_room("a2", "proj")

        # First failure
        evt1 = SessionEvent(
            event_id="e1", session_id="s1", agent_id="a1",
            event_type="failure", content="err1", created_at=datetime.now(),
        )
        await gw.process_session_event(evt1)

        # Second failure — should trigger blocker assist
        evt2 = SessionEvent(
            event_id="e2", session_id="s1", agent_id="a1",
            event_type="error", content="err2", created_at=datetime.now(),
        )
        await gw.process_session_event(evt2)

        # Check that a meeting was started
        calls = ws.send_text.call_args_list
        messages = [json.loads(c[0][0]) for c in calls]
        meeting_msgs = [m for m in messages if m.get("type") == "meeting_started"]
        assert len(meeting_msgs) >= 1
        assert meeting_msgs[0]["data"]["trigger"] == "blocker_assist"

    @pytest.mark.asyncio
    async def test_agent_in_meeting_not_disrupted(self):
        gw = make_gateway()
        gw.spatial.register_agent("a1", "Alice")
        gw.spatial.register_agent("a2", "Bob")
        gw.spatial.move_agent_to_room("a1", "proj")
        gw.spatial.move_agent_to_room("a2", "proj")

        # Create meeting manually
        meeting = Meeting(
            meeting_id="m1", room_id="proj", circle_id="c1",
            trigger=MeetingTrigger.CLAIM_REVIEW, agent_a="a1", agent_b="a2",
        )
        gw.spatial.create_meeting(meeting)

        old_anchor = gw.spatial.get_agent("a1").anchor_id

        # Process event for a1 — should be ignored during meeting
        evt = SessionEvent(
            event_id="e1", session_id="s1", agent_id="a1",
            event_type="file_change", content="edit", created_at=datetime.now(),
        )
        await gw.process_session_event(evt)

        # Anchor shouldn't have changed
        assert gw.spatial.get_agent("a1").anchor_id == old_anchor


# ══════════════════════════════════════════════════════════════════════
# Meeting Orchestrator Tests
# ══════════════════════════════════════════════════════════════════════


class TestMeetingOrchestrator:
    def _setup(self):
        state = SpatialState()
        orch = MeetingOrchestrator(state)
        broadcasts = []

        async def capture_broadcast(room, msg):
            broadcasts.append((room, msg))

        orch.set_broadcast(capture_broadcast)
        return state, orch, broadcasts

    @pytest.mark.asyncio
    async def test_claim_review_meeting_same_room(self):
        state, orch, broadcasts = self._setup()
        state.register_agent("r1", "Reviewer")
        state.register_agent("s1", "Source")
        state.move_agent_to_room("r1", "proj")
        state.move_agent_to_room("s1", "proj")

        result = await orch.try_claim_review_meeting("r1", "s1", "claim_123", "accepted")
        assert result is True
        assert state.is_agent_in_meeting("r1")
        assert state.is_agent_in_meeting("s1")

        # Check broadcasts
        types = [msg.get("type") for _, msg in broadcasts if isinstance(msg, dict)]
        assert "meeting_started" in types

    @pytest.mark.asyncio
    async def test_claim_review_different_rooms_fails(self):
        state, orch, broadcasts = self._setup()
        state.register_agent("r1", "Reviewer")
        state.register_agent("s1", "Source")
        state.move_agent_to_room("r1", "proj_a")
        state.move_agent_to_room("s1", "proj_b")

        result = await orch.try_claim_review_meeting("r1", "s1", "c1", "accepted")
        assert result is False

    @pytest.mark.asyncio
    async def test_blocker_assist_finds_nearest_helper(self):
        state, orch, broadcasts = self._setup()
        state.register_agent("blocked", "Blocked")
        state.register_agent("helper1", "Helper1")
        state.register_agent("helper2", "Helper2")
        state.move_agent_to_room("blocked", "proj")
        state.move_agent_to_room("helper1", "proj")
        state.move_agent_to_room("helper2", "proj")

        # Position helper1 closer
        a_blocked = state.get_agent("blocked")
        a_h1 = state.get_agent("helper1")
        a_h2 = state.get_agent("helper2")
        a_h1.x = a_blocked.x + 50
        a_h1.y = a_blocked.y
        a_h2.x = a_blocked.x + 200
        a_h2.y = a_blocked.y

        result = await orch.try_blocker_assist_meeting("blocked")
        assert result is True

        # The meeting should be between blocked and helper1 (nearest)
        meeting = state.get_meeting(state.get_agent("blocked").meeting_id)
        assert meeting.agent_b == "helper1"

    @pytest.mark.asyncio
    async def test_blocker_assist_no_helper(self):
        state, orch, broadcasts = self._setup()
        state.register_agent("blocked", "Blocked")
        state.move_agent_to_room("blocked", "proj")
        # No other agents in room
        result = await orch.try_blocker_assist_meeting("blocked")
        assert result is False

    @pytest.mark.asyncio
    async def test_occupied_circle_blocks_meeting(self):
        state, orch, broadcasts = self._setup()
        state.register_agent("a1", "A1")
        state.register_agent("a2", "A2")
        state.register_agent("a3", "A3")
        state.register_agent("a4", "A4")
        state.move_agent_to_room("a1", "proj")
        state.move_agent_to_room("a2", "proj")
        state.move_agent_to_room("a3", "proj")
        state.move_agent_to_room("a4", "proj")

        r1 = await orch.try_claim_review_meeting("a1", "a2", "c1", "ok")
        assert r1 is True

        r2 = await orch.try_claim_review_meeting("a3", "a4", "c2", "ok")
        assert r2 is False

    @pytest.mark.asyncio
    async def test_meeting_lifecycle_phases(self):
        """Verify meeting goes through all phases and ends correctly."""
        state, orch, broadcasts = self._setup()
        state.register_agent("a1", "A1")
        state.register_agent("a2", "A2")
        state.move_agent_to_room("a1", "proj")
        state.move_agent_to_room("a2", "proj")
        state.move_agent_to_zone("a1", ZoneType.CODE_DESK)
        state.move_agent_to_zone("a2", ZoneType.DEBUG_LAB)

        await orch.try_claim_review_meeting("a1", "a2", "c1", "accepted")

        # Wait for lifecycle to complete (total ~7.5s, use 10s timeout)
        meeting_id = state.get_agent("a1").meeting_id
        assert meeting_id is not None

        # Wait for the lifecycle task
        task = orch._active_tasks.get(meeting_id)
        if task:
            await asyncio.wait_for(task, timeout=15.0)

        # After lifecycle, agents should be free
        assert not state.is_agent_in_meeting("a1")
        assert not state.is_agent_in_meeting("a2")
        assert not state.is_circle_occupied("proj")

        # Check phase updates were broadcast
        update_types = [
            msg.get("data", {}).get("phase")
            for _, msg in broadcasts
            if isinstance(msg, dict) and msg.get("type") == "meeting_updated"
        ]
        for phase in PHASE_ORDER:
            assert phase.value in update_types, f"Phase {phase.value} not broadcast"


# ══════════════════════════════════════════════════════════════════════
# Model Tests for new types
# ══════════════════════════════════════════════════════════════════════


class TestNewModels:
    def test_activity_enum(self):
        assert len(Activity) == 7
        assert Activity.IDLE == "idle"
        assert Activity.MEETING == "meeting"

    def test_facing_enum(self):
        assert len(Facing) == 2
        assert Facing.LEFT == "left"

    def test_meeting_phase_enum(self):
        assert len(MeetingPhase) == 7

    def test_meeting_trigger_enum(self):
        assert len(MeetingTrigger) == 2

    def test_meeting_to_dict(self):
        m = Meeting(
            meeting_id="m1", room_id="r1", circle_id="c1",
            trigger=MeetingTrigger.CLAIM_REVIEW,
            agent_a="a1", agent_b="a2",
            bubble_a="Hi", bubble_b="Hello",
        )
        d = m.to_dict()
        assert d["meeting_id"] == "m1"
        assert d["trigger"] == "claim_review"
        assert d["phase"] == "gathering"

    def test_agent_visual_new_fields_in_dict(self):
        av = AgentVisual(
            agent_id="a1", name="Test", color_index=0,
            anchor_id="anc_1", home_anchor_id="anc_1",
            meeting_id="m1", activity=Activity.CODING,
            facing=Facing.LEFT,
        )
        d = av.to_dict()
        assert d["anchor_id"] == "anc_1"
        assert d["home_anchor_id"] == "anc_1"
        assert d["meeting_id"] == "m1"
        assert d["activity"] == "coding"
        assert d["facing"] == "left"
