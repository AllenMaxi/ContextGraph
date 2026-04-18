"""WebSocket gateway — bridges ContextGraph events to game viewers."""
from __future__ import annotations

import json
import logging
from typing import Any

from contextgraph.events import Event, EventBus
from contextgraph.models import SessionEvent
from contextgraph.service import ContextGraphService

from .meeting import MeetingOrchestrator
from .models import Activity, GameEvent, GameEventType, MeetingTrigger
from .rooms import get_layout, get_room_theme_key
from .spatial import SpatialState
from .translator import BlockerTracker, translate_bus_event, translate_session_event

logger = logging.getLogger(__name__)


class WorldGateway:
    """Bridges ContextGraph events to connected WebSocket viewers."""

    def __init__(self, event_bus: EventBus, graph_service: ContextGraphService) -> None:
        self.event_bus = event_bus
        self.graph_service = graph_service
        self.spatial = SpatialState()
        self.meetings = MeetingOrchestrator(self.spatial)
        self.meetings.set_broadcast(self.broadcast_to_room)
        self.blocker_tracker = BlockerTracker()
        # id(ws) → {"ws": ws, "room": str}
        self._viewers: dict[int, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Viewer management
    # ------------------------------------------------------------------

    async def add_viewer(self, ws: Any, room: str = "lobby") -> None:
        """Register a new viewer and send it a snapshot of the current room state."""
        self._viewers[id(ws)] = {"ws": ws, "room": room}
        snapshot = self._build_snapshot(room)
        await ws.send_text(json.dumps(snapshot))

    def remove_viewer(self, ws: Any) -> None:
        """Remove a viewer from the registry."""
        self._viewers.pop(id(ws), None)

    def switch_viewer_room(self, ws: Any, room: str) -> None:
        """Move a viewer to a different room."""
        entry = self._viewers.get(id(ws))
        if entry is not None:
            entry["room"] = room

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    async def broadcast_to_room(self, room: str, message: dict) -> None:
        """Send a JSON-encoded message to all viewers in the given room.

        Viewers whose send raises are silently removed (dead connections).
        """
        dead: list[int] = []
        payload = json.dumps(message)
        for viewer_id, entry in list(self._viewers.items()):
            if entry["room"] != room:
                continue
            try:
                await entry["ws"].send_text(payload)
            except Exception:
                dead.append(viewer_id)

        for viewer_id in dead:
            self._viewers.pop(viewer_id, None)

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    async def process_session_event(self, event: SessionEvent) -> None:
        """Translate a SessionEvent, update spatial state, and broadcast."""
        agent_id = event.agent_id

        # Ensure agent exists
        if self.spatial.get_agent(agent_id) is None:
            self.spatial.register_agent(agent_id, agent_id)

        agent = self.spatial.get_agent(agent_id)
        if agent is None:
            return

        # Don't disrupt an agent that's in a meeting
        if agent.meeting_id is not None:
            return

        room = agent.room
        tr = translate_session_event(event)

        # Track failures for blocker assist
        if event.event_type in ("failure", "blocker", "error"):
            should_trigger = self.blocker_tracker.record_failure(agent_id)
            if should_trigger:
                self.blocker_tracker.clear(agent_id)
                await self.meetings.try_blocker_assist_meeting(agent_id)

        old_anchor = agent.anchor_id

        # Move agent to zone if specified
        if tr.zone is not None:
            self.spatial.move_agent_to_zone(agent_id, tr.zone)

        # Update visuals
        self.spatial.update_visual(
            agent_id,
            expression=tr.expression,
            accessory=tr.accessory,
            glow=tr.glow,
            bubble=tr.bubble,
        )

        # Update activity
        if tr.activity is not None:
            self.spatial.update_activity(agent_id, tr.activity)

        agent = self.spatial.get_agent(agent_id)
        if agent is None:
            return

        # Broadcast agent_path if anchor changed
        new_anchor = agent.anchor_id
        if old_anchor and new_anchor and old_anchor != new_anchor:
            path_event = GameEvent(
                type=GameEventType.AGENT_PATH,
                agent_id=agent_id,
                data={
                    "from_anchor_id": old_anchor,
                    "to_anchor_id": new_anchor,
                    "room_id": room,
                    "speed": 1.0,
                },
            )
            await self.broadcast_to_room(room, path_event.to_dict())

        # Broadcast agent_move (for legacy clients / position sync)
        move_event = GameEvent(
            type=GameEventType.AGENT_MOVE,
            agent_id=agent_id,
            data={
                "x": agent.x,
                "y": agent.y,
                "room": agent.room,
                "zone": agent.zone.value if agent.zone else None,
            },
        )
        await self.broadcast_to_room(room, move_event.to_dict())

        # Broadcast agent_state
        state_event = GameEvent(
            type=GameEventType.AGENT_STATE,
            agent_id=agent_id,
            data=agent.to_dict(),
        )
        await self.broadcast_to_room(room, state_event.to_dict())

    async def process_bus_event(self, event: Event) -> None:
        """Handle an EventBus Event: spawn/despawn, visual update, or meeting trigger."""
        agent_id = event.agent_id
        tr = translate_bus_event(event)

        if tr.is_spawn:
            name = event.data.get("name", agent_id)
            self.spatial.register_agent(agent_id, name)
            agent = self.spatial.get_agent(agent_id)
            if agent is None:
                return
            spawn_event = GameEvent(
                type=GameEventType.AGENT_SPAWN,
                agent_id=agent_id,
                data=agent.to_dict(),
            )
            await self.broadcast_to_room(agent.room, spawn_event.to_dict())
            return

        if tr.is_despawn:
            agent = self.spatial.get_agent(agent_id)
            room = agent.room if agent else "lobby"
            self.spatial.remove_agent(agent_id)
            despawn_event = GameEvent(
                type=GameEventType.AGENT_DESPAWN,
                agent_id=agent_id,
                data={},
            )
            await self.broadcast_to_room(room, despawn_event.to_dict())
            return

        # Normal bus event — only update if agent is already tracked
        if self.spatial.get_agent(agent_id) is None:
            return

        agent = self.spatial.get_agent(agent_id)
        if agent is None:
            return

        # Don't disrupt meetings
        if agent.meeting_id is not None:
            return

        room = agent.room
        old_anchor = agent.anchor_id

        if tr.zone is not None:
            self.spatial.move_agent_to_zone(agent_id, tr.zone)

        self.spatial.update_visual(
            agent_id,
            expression=tr.expression,
            accessory=tr.accessory,
            glow=tr.glow,
            bubble=tr.bubble,
        )

        if tr.activity is not None:
            self.spatial.update_activity(agent_id, tr.activity)

        agent = self.spatial.get_agent(agent_id)
        if agent is None:
            return

        # Broadcast agent_path if anchor changed
        new_anchor = agent.anchor_id
        if old_anchor and new_anchor and old_anchor != new_anchor:
            path_event = GameEvent(
                type=GameEventType.AGENT_PATH,
                agent_id=agent_id,
                data={
                    "from_anchor_id": old_anchor,
                    "to_anchor_id": new_anchor,
                    "room_id": room,
                    "speed": 1.0,
                },
            )
            await self.broadcast_to_room(room, path_event.to_dict())

        move_event = GameEvent(
            type=GameEventType.AGENT_MOVE,
            agent_id=agent_id,
            data={
                "x": agent.x,
                "y": agent.y,
                "room": agent.room,
                "zone": agent.zone.value if agent.zone else None,
            },
        )
        await self.broadcast_to_room(room, move_event.to_dict())

        state_event = GameEvent(
            type=GameEventType.AGENT_STATE,
            agent_id=agent_id,
            data=agent.to_dict(),
        )
        await self.broadcast_to_room(room, state_event.to_dict())

        # Check for meeting triggers
        if tr.meeting_trigger == MeetingTrigger.CLAIM_REVIEW:
            reviewer = tr.meeting_data.get("reviewer_agent_id", agent_id)
            source = tr.meeting_data.get("source_agent_id", "")
            claim_id = tr.meeting_data.get("claim_id", "")
            decision = tr.meeting_data.get("decision", "")
            if source:
                await self.meetings.try_claim_review_meeting(
                    reviewer_id=reviewer,
                    source_id=source,
                    claim_id=claim_id,
                    decision=decision,
                )

    # ------------------------------------------------------------------
    # Snapshot builder
    # ------------------------------------------------------------------

    def _build_snapshot(self, room: str) -> dict:
        """Build a world_snapshot (lobby) or room_snapshot (project room)."""
        layout = get_layout(room)

        if room == "lobby":
            agents = [a.to_dict() for a in self.spatial.get_all_agents()]
            rooms = [r.to_dict() for r in self.spatial.get_room_list()]
            meetings = [m.to_dict() for m in self.spatial.get_meetings_in_room(room)]
            return {
                "type": GameEventType.WORLD_SNAPSHOT,
                "agents": agents,
                "rooms": rooms,
                "meetings": meetings,
                "layout": layout.to_dict(),
            }
        else:
            agents = [a.to_dict() for a in self.spatial.get_agents_in_room(room)]
            rooms = [r.to_dict() for r in self.spatial.get_room_list()]
            meetings = [m.to_dict() for m in self.spatial.get_meetings_in_room(room)]
            return {
                "type": GameEventType.ROOM_SNAPSHOT,
                "room_id": room,
                "room": room,
                "theme_key": get_room_theme_key(room),
                "agents": agents,
                "rooms": rooms,
                "meetings": meetings,
                "layout": layout.to_dict(),
            }
