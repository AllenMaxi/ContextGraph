"""WorldGateway — manages WebSocket viewers and broadcasts game events."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from .models import GameEvent, GameEventType
from .spatial import SpatialState
from .translator import translate_bus_event

from contextgraph.events import Event, EventType

logger = logging.getLogger(__name__)


@dataclass
class _Viewer:
    websocket: object  # starlette WebSocket
    room: str | None = None


class WorldGateway:
    """Manages the spatial world state and broadcasts updates to WebSocket viewers."""

    def __init__(self, max_viewers: int = 50) -> None:
        self._spatial = SpatialState()
        self._viewers: list[_Viewer] = []
        self._max_viewers = max_viewers
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    def seed_agents(self, agents: list) -> None:
        """Pre-populate spatial state from existing agents (called at startup)."""
        for agent in agents:
            self._spatial.register_agent(agent.agent_id, agent.name)

    # ------------------------------------------------------------------
    # Viewer management
    # ------------------------------------------------------------------

    async def add_viewer(self, websocket: object) -> _Viewer | None:
        """Register a new WebSocket viewer. Returns None if capacity exceeded."""
        async with self._lock:
            if len(self._viewers) >= self._max_viewers:
                return None
            viewer = _Viewer(websocket=websocket)
            self._viewers.append(viewer)
            return viewer

    async def remove_viewer(self, viewer: _Viewer) -> None:
        async with self._lock:
            if viewer in self._viewers:
                self._viewers.remove(viewer)

    async def set_viewer_room(self, viewer: _Viewer, room: str | None) -> None:
        viewer.room = room

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    async def process_event(self, event: Event) -> None:
        """Translate a bus event into visual state changes and broadcast."""
        agent_id = event.data.get("agent_id", event.agent_id)
        if not agent_id:
            return

        result = translate_bus_event(event)

        if result.is_spawn:
            name = event.data.get("name", agent_id)
            self._spatial.register_agent(agent_id, name)
            game_event = GameEvent(
                type=GameEventType.AGENT_SPAWN,
                agent_id=agent_id,
                data={"agent": self._spatial.get_agent(agent_id).to_dict()},  # type: ignore[union-attr]
            )
            await self._broadcast(game_event)
            return

        if result.is_despawn:
            self._spatial.remove_agent(agent_id)
            game_event = GameEvent(
                type=GameEventType.AGENT_DESPAWN,
                agent_id=agent_id,
                data={},
            )
            await self._broadcast(game_event)
            return

        # Ensure agent is tracked
        if self._spatial.get_agent(agent_id) is None:
            name = event.data.get("name", agent_id)
            self._spatial.register_agent(agent_id, name)

        # Apply visual changes
        if result.zone is not None:
            room = event.data.get("room", agent_id)
            self._spatial.move_agent_to_room(agent_id, room)
            self._spatial.move_agent_to_zone(agent_id, result.zone)
        self._spatial.update_visual(
            agent_id,
            expression=result.expression,
            accessory=result.accessory,
            glow=result.glow,
            bubble=result.bubble,
        )

        agent = self._spatial.get_agent(agent_id)
        if agent is None:
            return

        game_event = GameEvent(
            type=GameEventType.AGENT_STATE,
            agent_id=agent_id,
            data={"agent": agent.to_dict()},
        )
        await self._broadcast(game_event)

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    def get_world_snapshot(self) -> dict:
        return {
            "type": GameEventType.WORLD_SNAPSHOT.value,
            "agents": [a.to_dict() for a in self._spatial.get_all_agents()],
            "rooms": [r.to_dict() for r in self._spatial.get_room_list()],
        }

    def get_room_snapshot(self, room: str) -> dict:
        return {
            "type": GameEventType.ROOM_SNAPSHOT.value,
            "room": room,
            "agents": [a.to_dict() for a in self._spatial.get_agents_in_room(room)],
        }

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def _broadcast(self, event: GameEvent) -> None:
        """Send a game event to all matching viewers."""
        async with self._lock:
            viewers = list(self._viewers)

        payload = json.dumps(event.to_dict())
        dead: list[_Viewer] = []

        for viewer in viewers:
            # Skip viewers scoped to a different room
            if viewer.room is not None and event.agent_id:
                agent = self._spatial.get_agent(event.agent_id)
                if agent and agent.room != viewer.room:
                    continue
            try:
                await viewer.websocket.send_text(payload)  # type: ignore[attr-defined]
            except Exception:
                dead.append(viewer)

        if dead:
            async with self._lock:
                for v in dead:
                    if v in self._viewers:
                        self._viewers.remove(v)
