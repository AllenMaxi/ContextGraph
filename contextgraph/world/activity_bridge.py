"""Activity bridge — translate external tool-use events to world visuals.

External drivers (Claude Code hooks, CLI wrappers, other processes) POST
to /v1/world/activity with a simple {actor, action, room, bubble, ...}
payload. This module maps each action to a zone + visual state and
pushes the change through the gateway.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from contextgraph.events import Event, EventBus, EventType

from .gateway import WorldGateway
from .models import (
    Accessory,
    Activity,
    Expression,
    GameEvent,
    GameEventType,
    GlowColor,
    ZoneType,
)

logger = logging.getLogger(__name__)


ACTION_MAP: dict[str, dict[str, Any]] = {
    "read": {
        "zone": ZoneType.MEMORY_LIBRARY,
        "expression": Expression.FOCUSED,
        "accessory": Accessory.BOOK,
        "glow": GlowColor.GREEN,
        "activity": Activity.RESEARCHING,
    },
    "search": {
        "zone": ZoneType.MEMORY_LIBRARY,
        "expression": Expression.FOCUSED,
        "accessory": Accessory.MAGNIFYING_GLASS,
        "glow": GlowColor.GREEN,
        "activity": Activity.RESEARCHING,
    },
    "edit": {
        "zone": ZoneType.CODE_DESK,
        "expression": Expression.FOCUSED,
        "accessory": Accessory.HARD_HAT,
        "glow": GlowColor.GREEN,
        "activity": Activity.CODING,
    },
    "write": {
        "zone": ZoneType.CODE_DESK,
        "expression": Expression.FOCUSED,
        "accessory": Accessory.HARD_HAT,
        "glow": GlowColor.GREEN,
        "activity": Activity.CODING,
    },
    "bash": {
        "zone": ZoneType.DEBUG_LAB,
        "expression": Expression.THINKING,
        "accessory": Accessory.CLIPBOARD,
        "glow": GlowColor.YELLOW,
        "activity": Activity.DEBUGGING,
    },
    "error": {
        "zone": ZoneType.DEBUG_LAB,
        "expression": Expression.WORRIED,
        "accessory": Accessory.SIREN,
        "glow": GlowColor.RED,
        "activity": Activity.DEBUGGING,
    },
    "think": {
        "zone": ZoneType.REVIEW_STATION,
        "expression": Expression.THINKING,
        "accessory": Accessory.CLIPBOARD,
        "glow": GlowColor.GREEN,
        "activity": Activity.REVIEWING,
    },
    "review": {
        "zone": ZoneType.REVIEW_STATION,
        "expression": Expression.SOCIAL,
        "accessory": Accessory.CLIPBOARD,
        "glow": GlowColor.GREEN,
        "activity": Activity.REVIEWING,
    },
    "speak": {
        "expression": Expression.SOCIAL,
    },
    "idle": {
        "expression": Expression.HAPPY,
        "activity": Activity.IDLE,
    },
}


def apply_activity(gateway: WorldGateway, event_bus: EventBus, payload: dict) -> dict:
    """Synchronous entry point used by the HTTP route."""
    actor = str(payload.get("actor") or "").strip()
    if not actor:
        raise ValueError("actor required")

    action = str(payload.get("action") or "idle").strip().lower()
    name = str(payload.get("name") or actor).strip()
    room = payload.get("room")
    bubble = payload.get("bubble")

    spatial = gateway.spatial

    # Spawn if new
    existing = spatial.get_agent(actor)
    spawned = False
    if existing is None:
        event_bus.publish(Event(
            event_id=f"activity-spawn-{actor}-{datetime.utcnow().timestamp()}",
            event_type=EventType.AGENT_REGISTERED,
            data={"name": name},
            timestamp=datetime.utcnow(),
            agent_id=actor,
        ))
        # Register directly too, in case loop hasn't drained yet
        spatial.register_agent(actor, name)
        spawned = True

    agent = spatial.get_agent(actor)
    if agent is None:
        return {"spawned": spawned, "moved": False}

    # Optional explicit room move
    moved_room = False
    if room and room != agent.room:
        old_room = agent.room
        spatial.move_agent_to_room(actor, room)
        updated = spatial.get_agent(actor)
        if updated is not None:
            _schedule(gateway.broadcast_to_room(old_room, GameEvent(
                type=GameEventType.AGENT_DESPAWN, agent_id=actor, data={},
            ).to_dict()))
            _schedule(gateway.broadcast_to_room(room, GameEvent(
                type=GameEventType.AGENT_SPAWN, agent_id=actor, data=updated.to_dict(),
            ).to_dict()))
        moved_room = True

    # Apply visual + zone based on action
    mapping = ACTION_MAP.get(action, ACTION_MAP["idle"])
    zone = mapping.get("zone")
    target_agent = spatial.get_agent(actor)
    if zone is not None and target_agent is not None and target_agent.room != "lobby":
        spatial.move_agent_to_zone(actor, zone)

    spatial.update_visual(
        actor,
        expression=mapping.get("expression"),
        accessory=mapping.get("accessory"),
        glow=mapping.get("glow"),
        bubble=bubble,
    )
    if mapping.get("activity") is not None:
        spatial.update_activity(actor, mapping["activity"])

    updated = spatial.get_agent(actor)
    if updated is not None:
        _schedule(gateway.broadcast_to_room(updated.room, GameEvent(
            type=GameEventType.AGENT_STATE, agent_id=actor, data=updated.to_dict(),
        ).to_dict()))
        if updated.anchor_id:
            _schedule(gateway.broadcast_to_room(updated.room, GameEvent(
                type=GameEventType.AGENT_MOVE, agent_id=actor,
                data={
                    "x": updated.x,
                    "y": updated.y,
                    "room": updated.room,
                    "zone": updated.zone.value if updated.zone else None,
                },
            ).to_dict()))

    return {
        "spawned": spawned,
        "moved_room": moved_room,
        "room": updated.room if updated else None,
        "zone": updated.zone.value if updated and updated.zone else None,
    }


def _schedule(coro) -> None:
    """Fire-and-forget a coroutine on the running loop."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # No running loop — drop
        coro.close()
