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
    assert agent.bubble == "[a]Reading auth code"
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
    # Tagged "[u]" prefix + truncated body
    assert agent.bubble.startswith("[u]")
    body = agent.bubble[3:]
    assert len(body) <= 180
    assert body.endswith("...")


def test_set_bubble_spawns_user_if_missing(gateway):
    from contextgraph.world import message_bridge
    res = message_bridge.set_bubble(
        gateway, actor_id="user", role="user", text="hello",
    )
    assert res["ok"] is True
    user = gateway.spatial.get_agent("user")
    assert user is not None
    assert user.archetype == AgentArchetype.USER


# ── Task 16: HTTP /message endpoint ──────────────────────────────────

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
