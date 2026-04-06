"""Tests for contextgraph.world.gateway — WorldGateway."""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from contextgraph.events import Event, EventBus, EventType
from contextgraph.models import SessionEvent
from contextgraph.world.gateway import WorldGateway
from contextgraph.world.models import GameEventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ws() -> AsyncMock:
    """Return a mock WebSocket with an async send method."""
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


def make_session_event(
    agent_id: str = "agt_1",
    event_type: str = "file_change",
    content: str = "test content",
    session_id: str = "sess_1",
) -> SessionEvent:
    return SessionEvent(
        event_id="evt_1",
        session_id=session_id,
        agent_id=agent_id,
        event_type=event_type,
        content=content,
        created_at=datetime(2024, 1, 1),
    )


def make_bus_event(
    event_type: EventType = EventType.MEMORY_STORED,
    agent_id: str = "agt_1",
) -> Event:
    return Event(
        event_id="evt_1",
        event_type=event_type,
        data={"agent_id": agent_id, "name": "Agent One"},
        timestamp=datetime(2024, 1, 1),
        agent_id=agent_id,
    )


def make_gateway() -> WorldGateway:
    event_bus = MagicMock(spec=EventBus)
    graph_service = MagicMock()
    return WorldGateway(event_bus=event_bus, graph_service=graph_service)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_empty_viewers(self) -> None:
        gw = make_gateway()
        assert gw._viewers == {}

    def test_stores_event_bus(self) -> None:
        bus = MagicMock(spec=EventBus)
        gw = WorldGateway(event_bus=bus, graph_service=MagicMock())
        assert gw.event_bus is bus

    def test_stores_graph_service(self) -> None:
        svc = MagicMock()
        gw = WorldGateway(event_bus=MagicMock(spec=EventBus), graph_service=svc)
        assert gw.graph_service is svc

    def test_creates_spatial_state(self) -> None:
        from contextgraph.world.spatial import SpatialState
        gw = make_gateway()
        assert isinstance(gw.spatial, SpatialState)


# ---------------------------------------------------------------------------
# add_viewer
# ---------------------------------------------------------------------------

class TestAddViewer:
    @pytest.mark.asyncio
    async def test_stores_viewer_in_dict(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws)
        assert id(ws) in gw._viewers

    @pytest.mark.asyncio
    async def test_default_room_is_lobby(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws)
        assert gw._viewers[id(ws)]["room"] == "lobby"

    @pytest.mark.asyncio
    async def test_custom_room_stored(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="proj_abc")
        assert gw._viewers[id(ws)]["room"] == "proj_abc"

    @pytest.mark.asyncio
    async def test_sends_snapshot_on_add(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws)
        ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_snapshot_is_valid_json(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws)
        payload = ws.send_text.call_args[0][0]
        data = json.loads(payload)
        assert "type" in data

    @pytest.mark.asyncio
    async def test_lobby_snapshot_type(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="lobby")
        payload = ws.send_text.call_args[0][0]
        data = json.loads(payload)
        assert data["type"] == GameEventType.WORLD_SNAPSHOT

    @pytest.mark.asyncio
    async def test_room_snapshot_type_for_non_lobby(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="project_x")
        payload = ws.send_text.call_args[0][0]
        data = json.loads(payload)
        assert data["type"] == GameEventType.ROOM_SNAPSHOT

    @pytest.mark.asyncio
    async def test_multiple_viewers_all_stored(self) -> None:
        gw = make_gateway()
        ws1 = make_ws()
        ws2 = make_ws()
        await gw.add_viewer(ws1)
        await gw.add_viewer(ws2)
        assert len(gw._viewers) == 2


# ---------------------------------------------------------------------------
# remove_viewer
# ---------------------------------------------------------------------------

class TestRemoveViewer:
    @pytest.mark.asyncio
    async def test_removes_viewer(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws)
        gw.remove_viewer(ws)
        assert id(ws) not in gw._viewers

    def test_remove_nonexistent_is_noop(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        # Should not raise
        gw.remove_viewer(ws)

    @pytest.mark.asyncio
    async def test_removes_only_target_viewer(self) -> None:
        gw = make_gateway()
        ws1 = make_ws()
        ws2 = make_ws()
        await gw.add_viewer(ws1)
        await gw.add_viewer(ws2)
        gw.remove_viewer(ws1)
        assert id(ws1) not in gw._viewers
        assert id(ws2) in gw._viewers


# ---------------------------------------------------------------------------
# switch_viewer_room
# ---------------------------------------------------------------------------

class TestSwitchViewerRoom:
    @pytest.mark.asyncio
    async def test_changes_room(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="lobby")
        gw.switch_viewer_room(ws, "project_x")
        assert gw._viewers[id(ws)]["room"] == "project_x"

    @pytest.mark.asyncio
    async def test_switch_back_to_lobby(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="project_x")
        gw.switch_viewer_room(ws, "lobby")
        assert gw._viewers[id(ws)]["room"] == "lobby"

    def test_switch_nonexistent_viewer_is_noop(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        # Should not raise
        gw.switch_viewer_room(ws, "project_x")


# ---------------------------------------------------------------------------
# broadcast_to_room
# ---------------------------------------------------------------------------

class TestBroadcastToRoom:
    @pytest.mark.asyncio
    async def test_sends_to_viewers_in_room(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="lobby")
        ws.send_text.reset_mock()  # ignore snapshot call
        msg = {"type": "test", "data": {}}
        await gw.broadcast_to_room("lobby", msg)
        ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_send_to_viewers_in_other_room(self) -> None:
        gw = make_gateway()
        ws_lobby = make_ws()
        ws_proj = make_ws()
        await gw.add_viewer(ws_lobby, room="lobby")
        await gw.add_viewer(ws_proj, room="project_x")
        ws_lobby.send_text.reset_mock()
        ws_proj.send_text.reset_mock()
        msg = {"type": "test", "data": {}}
        await gw.broadcast_to_room("lobby", msg)
        ws_lobby.send_text.assert_called_once()
        ws_proj.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_json_encoded_message(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="lobby")
        ws.send_text.reset_mock()
        msg = {"type": "agent_move", "agent_id": "agt_1", "data": {}}
        await gw.broadcast_to_room("lobby", msg)
        payload = ws.send_text.call_args[0][0]
        decoded = json.loads(payload)
        assert decoded["type"] == "agent_move"

    @pytest.mark.asyncio
    async def test_removes_dead_connections(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="lobby")
        ws.send_text.reset_mock()
        ws.send_text.side_effect = Exception("connection closed")
        msg = {"type": "test", "data": {}}
        await gw.broadcast_to_room("lobby", msg)
        assert id(ws) not in gw._viewers

    @pytest.mark.asyncio
    async def test_broadcast_empty_room_is_noop(self) -> None:
        gw = make_gateway()
        # Should not raise
        await gw.broadcast_to_room("lobby", {"type": "test"})


# ---------------------------------------------------------------------------
# process_session_event
# ---------------------------------------------------------------------------

class TestProcessSessionEvent:
    @pytest.mark.asyncio
    async def test_registers_agent_if_new(self) -> None:
        gw = make_gateway()
        event = make_session_event(agent_id="agt_new")
        await gw.process_session_event(event)
        assert gw.spatial.get_agent("agt_new") is not None

    @pytest.mark.asyncio
    async def test_updates_spatial_state(self) -> None:
        gw = make_gateway()
        event = make_session_event(agent_id="agt_1", event_type="file_change")
        await gw.process_session_event(event)
        agent = gw.spatial.get_agent("agt_1")
        assert agent is not None

    @pytest.mark.asyncio
    async def test_broadcasts_agent_move(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="lobby")
        ws.send_text.reset_mock()

        # Register agent first so it has a room
        gw.spatial.register_agent("agt_1", "Agent One")
        event = make_session_event(agent_id="agt_1", event_type="file_change")
        await gw.process_session_event(event)
        # Should have broadcast at least one message
        assert ws.send_text.call_count >= 1

    @pytest.mark.asyncio
    async def test_session_event_with_zone_moves_agent(self) -> None:
        gw = make_gateway()
        gw.spatial.register_agent("agt_1", "Agent One")
        gw.spatial.move_agent_to_room("agt_1", "project_x")

        event = make_session_event(agent_id="agt_1", event_type="file_change")
        await gw.process_session_event(event)
        agent = gw.spatial.get_agent("agt_1")
        assert agent is not None


# ---------------------------------------------------------------------------
# process_bus_event — spawn / despawn / normal
# ---------------------------------------------------------------------------

class TestProcessBusEvent:
    @pytest.mark.asyncio
    async def test_spawn_registers_agent(self) -> None:
        gw = make_gateway()
        event = Event(
            event_id="e1",
            event_type=EventType.AGENT_REGISTERED,
            data={"agent_id": "agt_new", "name": "New Agent"},
            timestamp=datetime(2024, 1, 1),
            agent_id="agt_new",
        )
        await gw.process_bus_event(event)
        assert gw.spatial.get_agent("agt_new") is not None

    @pytest.mark.asyncio
    async def test_despawn_removes_agent(self) -> None:
        gw = make_gateway()
        gw.spatial.register_agent("agt_1", "Agent One")
        event = Event(
            event_id="e1",
            event_type=EventType.AGENT_DELETED,
            data={},
            timestamp=datetime(2024, 1, 1),
            agent_id="agt_1",
        )
        await gw.process_bus_event(event)
        assert gw.spatial.get_agent("agt_1") is None

    @pytest.mark.asyncio
    async def test_spawn_broadcasts_to_lobby(self) -> None:
        gw = make_gateway()
        ws = make_ws()
        await gw.add_viewer(ws, room="lobby")
        ws.send_text.reset_mock()

        event = Event(
            event_id="e1",
            event_type=EventType.AGENT_REGISTERED,
            data={"agent_id": "agt_2", "name": "Agent Two"},
            timestamp=datetime(2024, 1, 1),
            agent_id="agt_2",
        )
        await gw.process_bus_event(event)
        assert ws.send_text.call_count >= 1

    @pytest.mark.asyncio
    async def test_normal_bus_event_updates_spatial(self) -> None:
        gw = make_gateway()
        gw.spatial.register_agent("agt_1", "Agent One")
        gw.spatial.move_agent_to_room("agt_1", "project_x")

        event = make_bus_event(EventType.MEMORY_STORED, agent_id="agt_1")
        await gw.process_bus_event(event)
        # Agent should still exist
        assert gw.spatial.get_agent("agt_1") is not None

    @pytest.mark.asyncio
    async def test_bus_event_for_unknown_agent_is_noop(self) -> None:
        gw = make_gateway()
        event = make_bus_event(EventType.MEMORY_STORED, agent_id="nonexistent")
        # Should not raise
        await gw.process_bus_event(event)


# ---------------------------------------------------------------------------
# _build_snapshot
# ---------------------------------------------------------------------------

class TestBuildSnapshot:
    def test_lobby_snapshot_has_world_snapshot_type(self) -> None:
        gw = make_gateway()
        snapshot = gw._build_snapshot("lobby")
        assert snapshot["type"] == GameEventType.WORLD_SNAPSHOT

    def test_room_snapshot_has_room_snapshot_type(self) -> None:
        gw = make_gateway()
        snapshot = gw._build_snapshot("project_x")
        assert snapshot["type"] == GameEventType.ROOM_SNAPSHOT

    def test_lobby_snapshot_includes_agents(self) -> None:
        gw = make_gateway()
        gw.spatial.register_agent("agt_1", "Alice")
        snapshot = gw._build_snapshot("lobby")
        assert "agents" in snapshot

    def test_room_snapshot_includes_agents(self) -> None:
        gw = make_gateway()
        gw.spatial.register_agent("agt_1", "Alice")
        gw.spatial.move_agent_to_room("agt_1", "project_x")
        snapshot = gw._build_snapshot("project_x")
        assert "agents" in snapshot

    def test_lobby_snapshot_includes_rooms(self) -> None:
        gw = make_gateway()
        snapshot = gw._build_snapshot("lobby")
        assert "rooms" in snapshot

    def test_room_snapshot_includes_room_id(self) -> None:
        gw = make_gateway()
        snapshot = gw._build_snapshot("project_x")
        assert snapshot.get("room_id") == "project_x"
