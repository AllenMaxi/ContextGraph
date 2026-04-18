"""Message bridge — user prompts and assistant replies as speech bubbles."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .gateway import WorldGateway
from .models import AgentArchetype, GameEvent, GameEventType

logger = logging.getLogger(__name__)

MAX_BUBBLE_LEN = 180


def _truncate(text: str, limit: int = MAX_BUBBLE_LEN) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def set_bubble(
    gateway: WorldGateway,
    actor_id: str,
    role: str,
    text: str,
) -> dict[str, Any]:
    """Set a speech bubble on ``actor_id``. Role is 'user' or 'assistant'.

    If ``actor_id == 'user'`` and no agent exists yet, the user avatar is
    auto-spawned.
    """
    if not actor_id:
        raise ValueError("actor_id required")
    if role not in ("user", "assistant"):
        raise ValueError("role must be user or assistant")

    spatial = gateway.spatial

    if spatial.get_agent(actor_id) is None:
        if actor_id == "user":
            spatial.register_agent(
                "user", "User", archetype=AgentArchetype.USER,
            )
        else:
            return {"ok": False, "error": "unknown actor"}

    bubble = _truncate(text)
    tagged = f"[{role[0]}]{bubble}"
    spatial.update_visual(actor_id, bubble=tagged)
    agent = spatial.get_agent(actor_id)
    _schedule(gateway.broadcast_to_room(agent.room, GameEvent(
        type=GameEventType.AGENT_STATE,
        agent_id=actor_id,
        data=agent.to_dict(),
    ).to_dict()))
    return {"ok": True, "bubble": bubble}


def _schedule(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        try:
            asyncio.run(coro)
        except RuntimeError:
            coro.close()
