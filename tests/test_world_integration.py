"""Integration test: CG event → gateway → game event broadcast."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from contextgraph.events import Event, EventBus, EventType
from contextgraph.models import SessionEvent
from contextgraph.world.gateway import WorldGateway


@pytest.fixture
def gateway():
    svc = type("S", (), {"list_agents": lambda self: []})()
    return WorldGateway(event_bus=EventBus(), graph_service=svc)


def _session_event(agent_id, event_type, content="", seq=1):
    return SessionEvent(
        event_id=f"e-{seq}",
        session_id="s1",
        agent_id=agent_id,
        event_type=event_type,
        content=content,
        created_at=datetime.now(UTC),
        sequence=seq,
    )


@pytest.mark.asyncio
async def test_full_session_event_round_trip(gateway):
    gateway.spatial.register_agent("alice", "alice-agent")
    gateway.spatial.move_agent_to_room("alice", "api-svc")
    ws = AsyncMock()
    await gateway.add_viewer(ws, room="api-svc")
    ws.reset_mock()

    await gateway.process_session_event(_session_event("alice", "file_change", "src/handler.py"))

    agent = gateway.spatial.get_agent("alice")
    assert agent.zone is not None
    assert agent.zone.value == "code_desk"
    assert ws.send_text.call_count >= 1


@pytest.mark.asyncio
async def test_bus_event_agent_registered(gateway):
    ws = AsyncMock()
    await gateway.add_viewer(ws, room="lobby")
    ws.reset_mock()

    event = Event(
        event_id="e1",
        event_type=EventType.AGENT_REGISTERED,
        data={"name": "new-bot"},
        timestamp=datetime.now(UTC),
        agent_id="new-bot",
    )
    await gateway.process_bus_event(event)
    assert gateway.spatial.get_agent("new-bot") is not None
    assert ws.send_text.call_count >= 1


@pytest.mark.asyncio
async def test_failure_moves_to_debug_lab(gateway):
    gateway.spatial.register_agent("bob", "bob-builder")
    gateway.spatial.move_agent_to_room("bob", "web-app")

    await gateway.process_session_event(_session_event("bob", "failure", "TypeError"))

    agent = gateway.spatial.get_agent("bob")
    assert agent.zone.value == "debug_lab"
    assert agent.expression.value == "worried"
    assert agent.glow.value == "red"


@pytest.mark.asyncio
async def test_resolved_sets_happy(gateway):
    gateway.spatial.register_agent("alice", "alice-agent")
    gateway.spatial.move_agent_to_room("alice", "api-svc")

    await gateway.process_session_event(_session_event("alice", "resolved", "Fixed the bug"))

    agent = gateway.spatial.get_agent("alice")
    assert agent.expression.value == "happy"
    assert agent.glow.value == "green"


@pytest.mark.asyncio
async def test_viewer_room_isolation(gateway):
    gateway.spatial.register_agent("alice", "alice-agent")
    gateway.spatial.move_agent_to_room("alice", "api-svc")

    ws_api = AsyncMock()
    ws_lobby = AsyncMock()
    await gateway.add_viewer(ws_api, room="api-svc")
    await gateway.add_viewer(ws_lobby, room="lobby")
    ws_api.reset_mock()
    ws_lobby.reset_mock()

    await gateway.process_session_event(_session_event("alice", "file_change", "src/main.py"))

    assert ws_api.send_text.call_count >= 1
    assert ws_lobby.send_text.call_count == 0


@pytest.mark.asyncio
async def test_agent_despawn(gateway):
    gateway.spatial.register_agent("alice", "alice-agent")
    ws = AsyncMock()
    await gateway.add_viewer(ws, room="lobby")
    ws.reset_mock()

    event = Event(
        event_id="e2",
        event_type=EventType.AGENT_DELETED,
        data={},
        timestamp=datetime.now(UTC),
        agent_id="alice",
    )
    await gateway.process_bus_event(event)
    assert gateway.spatial.get_agent("alice") is None
    assert ws.send_text.call_count >= 1


@pytest.mark.asyncio
async def test_memory_stored_moves_to_library(gateway):
    gateway.spatial.register_agent("carol", "carol-ops")
    gateway.spatial.move_agent_to_room("carol", "infra")

    event = Event(
        event_id="e3",
        event_type=EventType.MEMORY_STORED,
        data={"content": "stored a fact"},
        timestamp=datetime.now(UTC),
        agent_id="carol",
    )
    await gateway.process_bus_event(event)
    agent = gateway.spatial.get_agent("carol")
    assert agent.zone.value == "memory_library"
