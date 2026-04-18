"""Identity bridge — register, upgrade, spawn, despawn orchestration.

Callers (HTTP routes or internal systems) invoke these functions; they
update ``SpatialState`` and broadcast the right ``GameEvent`` through
the ``WorldGateway``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .gateway import WorldGateway
from .models import (
    AgentArchetype,
    GameEvent,
    GameEventType,
)

logger = logging.getLogger(__name__)


ARCHETYPE_MAP: dict[str, AgentArchetype] = {
    "Explore": AgentArchetype.SCOUT,
    "Plan": AgentArchetype.ORACLE,
    "code-reviewer": AgentArchetype.SCRIBE,
    "superpowers:code-reviewer": AgentArchetype.SCRIBE,
    "general-purpose": AgentArchetype.APPRENTICE,
    "statusline-setup": AgentArchetype.ARTIFICER,
    "claude-code-guide": AgentArchetype.SAGE,
}


def archetype_for_subagent_type(subagent_type: str | None) -> AgentArchetype:
    if not subagent_type:
        return AgentArchetype.UNKNOWN
    return ARCHETYPE_MAP.get(subagent_type.strip(), AgentArchetype.UNKNOWN)


def register_identity(
    gateway: WorldGateway,
    actor_id: str,
    name: str,
    archetype: AgentArchetype,
    tools_count: int,
    skills_count: int,
    parent_agent_id: str | None = None,
) -> dict[str, Any]:
    """Register (or refresh) an agent identity and broadcast spawn/state."""
    if not actor_id:
        raise ValueError("actor_id required")

    spatial = gateway.spatial
    was_new = spatial.get_agent(actor_id) is None

    spatial.register_agent(
        actor_id,
        name or actor_id,
        archetype=archetype,
        parent_agent_id=parent_agent_id,
    )
    spatial.update_rank(actor_id, tools_count, skills_count)
    updated = spatial.get_agent(actor_id)

    evt_type = GameEventType.AGENT_SPAWN if was_new else GameEventType.AGENT_STATE
    _schedule(
        gateway.broadcast_to_room(
            updated.room,
            GameEvent(
                type=evt_type,
                agent_id=actor_id,
                data=updated.to_dict(),
            ).to_dict(),
        )
    )

    return {"ok": True, "created": was_new, "agent": updated.to_dict()}


def upgrade_identity(
    gateway: WorldGateway,
    actor_id: str,
    tools_count: int,
    skills_count: int,
) -> dict[str, Any]:
    """Recompute rank. Broadcast AGENT_UPGRADE if rank changes."""
    if not actor_id:
        raise ValueError("actor_id required")

    spatial = gateway.spatial
    agent = spatial.get_agent(actor_id)
    if agent is None:
        return {"ok": False, "error": "unknown actor"}

    change = spatial.update_rank(actor_id, tools_count, skills_count)
    updated = spatial.get_agent(actor_id)

    if change is None:
        return {
            "ok": True,
            "rank_changed": False,
            "rank": updated.rank.value,
        }
    old_rank, new_rank = change
    _schedule(
        gateway.broadcast_to_room(
            updated.room,
            GameEvent(
                type=GameEventType.AGENT_UPGRADE,
                agent_id=actor_id,
                data={
                    "old_rank": old_rank.value,
                    "new_rank": new_rank.value,
                    "tools_count": tools_count,
                    "skills_count": skills_count,
                },
            ).to_dict(),
        )
    )
    # Follow with state so lazy clients still sync
    _schedule(
        gateway.broadcast_to_room(
            updated.room,
            GameEvent(
                type=GameEventType.AGENT_STATE,
                agent_id=actor_id,
                data=updated.to_dict(),
            ).to_dict(),
        )
    )

    return {
        "ok": True,
        "rank_changed": True,
        "old_rank": old_rank.value,
        "new_rank": new_rank.value,
    }


def spawn_subagent(
    gateway: WorldGateway,
    parent_actor_id: str,
    subagent_type: str,
    description: str,
    invocation_id: str,
) -> dict[str, Any]:
    """Spawn a subagent visually. Idempotent on (parent, subagent_type, invocation_id)."""
    if not parent_actor_id or not subagent_type or not invocation_id:
        raise ValueError("parent_actor_id, subagent_type, invocation_id required")

    actor_id = f"{parent_actor_id}.{subagent_type}.{invocation_id}"
    archetype = archetype_for_subagent_type(subagent_type)
    name = f"{subagent_type.title()}-{invocation_id}"

    spatial = gateway.spatial
    was_new = spatial.get_agent(actor_id) is None
    spatial.register_agent(
        actor_id,
        name,
        archetype=archetype,
        parent_agent_id=parent_actor_id,
    )
    spatial.update_rank(actor_id, tools_count=0, skills_count=0)

    short = (description or "").strip()
    if len(short) > 110:
        short = short[:107] + "..."
    spatial.update_visual(actor_id, bubble=short or None)

    updated = spatial.get_agent(actor_id)
    evt_type = GameEventType.AGENT_SPAWN if was_new else GameEventType.AGENT_STATE
    _schedule(
        gateway.broadcast_to_room(
            updated.room,
            GameEvent(
                type=evt_type,
                agent_id=actor_id,
                data=updated.to_dict(),
            ).to_dict(),
        )
    )

    return {
        "ok": True,
        "actor_id": actor_id,
        "archetype": archetype.value,
        "created": was_new,
    }


def despawn_subagent(
    gateway: WorldGateway,
    actor_id: str,
    result_summary: str,
) -> dict[str, Any]:
    """Emit handoff orb (child → parent) + AGENT_DESPAWN. Remove from spatial."""
    if not actor_id:
        raise ValueError("actor_id required")
    spatial = gateway.spatial
    agent = spatial.get_agent(actor_id)
    if agent is None:
        return {"ok": False, "error": "unknown actor"}

    parent_id = agent.parent_agent_id
    parent = spatial.get_agent(parent_id) if parent_id else None
    room = agent.room

    short = (result_summary or "").strip()
    if len(short) > 110:
        short = short[:107] + "..."
    if short:
        spatial.update_visual(actor_id, bubble=short)
        _schedule(
            gateway.broadcast_to_room(
                room,
                GameEvent(
                    type=GameEventType.AGENT_STATE,
                    agent_id=actor_id,
                    data=spatial.get_agent(actor_id).to_dict(),
                ).to_dict(),
            )
        )

    if parent is not None:
        _schedule(
            gateway.broadcast_to_room(
                room,
                GameEvent(
                    type=GameEventType.HANDOFF_ORB,
                    agent_id=actor_id,
                    data={
                        "from_agent": actor_id,
                        "to_agent": parent_id,
                        "color": "green",
                    },
                ).to_dict(),
            )
        )

    _schedule(
        gateway.broadcast_to_room(
            room,
            GameEvent(
                type=GameEventType.AGENT_DESPAWN,
                agent_id=actor_id,
                data={"parent_agent_id": parent_id},
            ).to_dict(),
        )
    )

    spatial.remove_agent(actor_id)
    return {"ok": True, "actor_id": actor_id, "parent": parent_id}


def _schedule(coro) -> None:
    """Fire-and-forget a coroutine on a running loop, else drain synchronously."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # No running loop — execute synchronously so tests using monkeypatched
        # broadcast_to_room can still observe side-effects.
        try:
            asyncio.run(coro)
        except RuntimeError:
            coro.close()
