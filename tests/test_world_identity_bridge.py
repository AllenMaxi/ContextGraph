"""Tests for identity_bridge — registration, upgrade, spawn, despawn."""

from __future__ import annotations

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
    gw.spatial = state
    return gw


# ── Task 9: register_identity ─────────────────────────────────────────


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
    # 12 + 4 = 16 → MAGE (threshold 16–30)
    assert agent.rank == AgentRank.MAGE


def test_register_identity_is_idempotent(gateway):
    from contextgraph.world.identity_bridge import register_identity

    register_identity(
        gateway,
        actor_id="claude",
        name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        tools_count=2,
        skills_count=1,
    )
    register_identity(
        gateway,
        actor_id="claude",
        name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        tools_count=2,
        skills_count=1,
    )
    assert len(gateway.spatial.get_all_agents()) == 1


# ── Task 10: upgrade_identity ─────────────────────────────────────────


def test_upgrade_identity_broadcasts_on_rank_change(gateway, monkeypatch):
    from contextgraph.world import identity_bridge

    identity_bridge.register_identity(
        gateway,
        actor_id="claude",
        name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        tools_count=2,
        skills_count=1,
    )

    broadcasts = []

    async def capture(room, msg):
        broadcasts.append((room, msg))

    monkeypatch.setattr(gateway, "broadcast_to_room", capture)

    result = identity_bridge.upgrade_identity(
        gateway,
        actor_id="claude",
        tools_count=15,
        skills_count=5,
    )
    assert result["rank_changed"] is True
    assert result["old_rank"] == "novice"
    assert result["new_rank"] == "mage"

    types = [msg["type"] for _, msg in broadcasts]
    assert "agent_upgrade" in types


def test_upgrade_identity_no_broadcast_when_rank_same(gateway, monkeypatch):
    from contextgraph.world import identity_bridge

    identity_bridge.register_identity(
        gateway,
        actor_id="claude",
        name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        tools_count=2,
        skills_count=1,
    )

    broadcasts = []

    async def capture(room, msg):
        broadcasts.append((room, msg))

    monkeypatch.setattr(gateway, "broadcast_to_room", capture)
    result = identity_bridge.upgrade_identity(
        gateway,
        actor_id="claude",
        tools_count=3,
        skills_count=1,
    )
    assert result["rank_changed"] is False
    upgrade_events = [m for _, m in broadcasts if m.get("type") == "agent_upgrade"]
    assert upgrade_events == []


# ── Task 11: spawn_subagent + archetype_for_subagent_type ─────────────


@pytest.mark.parametrize(
    "subagent_type,expected",
    [
        ("Explore", AgentArchetype.SCOUT),
        ("Plan", AgentArchetype.ORACLE),
        ("code-reviewer", AgentArchetype.SCRIBE),
        ("superpowers:code-reviewer", AgentArchetype.SCRIBE),
        ("general-purpose", AgentArchetype.APPRENTICE),
        ("statusline-setup", AgentArchetype.ARTIFICER),
        ("claude-code-guide", AgentArchetype.SAGE),
        ("made-up-thing", AgentArchetype.UNKNOWN),
    ],
)
def test_archetype_for_subagent_type(subagent_type, expected):
    from contextgraph.world.identity_bridge import archetype_for_subagent_type

    assert archetype_for_subagent_type(subagent_type) == expected


def test_spawn_subagent_creates_child_linked_to_parent(gateway, monkeypatch):
    from contextgraph.world import identity_bridge

    identity_bridge.register_identity(
        gateway,
        actor_id="claude",
        name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        tools_count=2,
        skills_count=1,
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


# ── Task 12: despawn_subagent + handoff orb ───────────────────────────


def test_despawn_subagent_emits_handoff_orb_and_despawn(gateway, monkeypatch):
    from contextgraph.world import identity_bridge

    identity_bridge.register_identity(
        gateway,
        actor_id="claude",
        name="Claude",
        archetype=AgentArchetype.ARCHMAGE,
        tools_count=2,
        skills_count=1,
    )
    spawn = identity_bridge.spawn_subagent(
        gateway,
        parent_actor_id="claude",
        subagent_type="Explore",
        description="x",
        invocation_id="1",
    )
    child_id = spawn["actor_id"]

    broadcasts = []

    async def capture(room, msg):
        broadcasts.append((room, msg))

    monkeypatch.setattr(gateway, "broadcast_to_room", capture)

    res = identity_bridge.despawn_subagent(
        gateway,
        actor_id=child_id,
        result_summary="Found 3 auth files",
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
        gateway,
        actor_id="never_was",
        result_summary="",
    )
    assert res["ok"] is False


# ── Tasks 14-15: HTTP endpoints ───────────────────────────────────────


def _make_http_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from contextgraph.events import EventBus
    from contextgraph.world.routes import register_world_routes

    app = FastAPI()
    event_bus = EventBus()
    service = MagicMock()
    service.repository.list_agents.return_value = []
    register_world_routes(app, event_bus, service)
    return TestClient(app)


def test_http_identity_endpoint():
    client = _make_http_client()
    r = client.post(
        "/v1/world/identity",
        json={
            "actor": "claude",
            "name": "Claude",
            "archetype": "archmage",
            "tools_count": 5,
            "skills_count": 2,
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_http_identity_upgrade_endpoint():
    client = _make_http_client()
    client.post(
        "/v1/world/identity",
        json={
            "actor": "claude",
            "name": "Claude",
            "archetype": "archmage",
            "tools_count": 5,
            "skills_count": 0,
        },
    )
    r = client.post(
        "/v1/world/identity/upgrade",
        json={
            "actor": "claude",
            "tools_count": 20,
            "skills_count": 5,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["rank_changed"] is True
    assert body["new_rank"] == "mage"


def test_http_spawn_and_despawn():
    client = _make_http_client()
    client.post(
        "/v1/world/identity",
        json={
            "actor": "claude",
            "name": "Claude",
            "archetype": "archmage",
            "tools_count": 2,
            "skills_count": 1,
        },
    )
    r = client.post(
        "/v1/world/spawn",
        json={
            "parent": "claude",
            "subagent_type": "Explore",
            "description": "find files",
            "invocation_id": "42",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["actor_id"] == "claude.Explore.42"

    r = client.post(
        "/v1/world/despawn",
        json={
            "actor": body["actor_id"],
            "result_summary": "done",
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
