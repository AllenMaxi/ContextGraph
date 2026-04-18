"""Spatial state tracker — manages agent positions, rooms, anchors, and meetings."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .models import (
    Accessory,
    Activity,
    AgentArchetype,
    AgentRank,
    AgentVisual,
    Expression,
    Facing,
    GlowColor,
    Meeting,
    RoomInfo,
    ZoneType,
    rank_for_counts,
)
from .rooms import (
    assign_home_anchor,
    color_index_for_agent,
    get_demo_room_info,
    get_layout,
    get_lobby_idle_position,
    get_room_display_name,
    get_room_theme_key,
    get_zone_position,
)

if TYPE_CHECKING:
    from .identity_store import IdentityStore


class SpatialState:
    """Tracks every agent's visual / spatial state in the world."""

    def __init__(self, identity_store: "IdentityStore | None" = None) -> None:
        self._agents: dict[str, AgentVisual] = {}
        self._meetings: dict[str, Meeting] = {}
        # Track which meeting circles are in use: room_id → meeting_id
        self._occupied_circles: dict[str, str] = {}
        # IdentityStore is optional — callers without persistence get an
        # ephemeral in-memory store rooted at a temp path.
        from .identity_store import IdentityStore as _IdentityStore
        if identity_store is None:
            identity_store = _IdentityStore(Path("/tmp/_cg_test_identities.json"))
        self._identity_store = identity_store

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_agent(
        self,
        agent_id: str,
        name: str,
        archetype: AgentArchetype | None = None,
        parent_agent_id: str | None = None,
    ) -> AgentVisual:
        """Create an agent in the lobby. Idempotent — returns existing entry.

        If the identity store has a record for ``agent_id`` its archetype,
        rank, and color_index are reused. Otherwise a new record is created
        from the supplied ``archetype`` (or UNKNOWN) and persisted.
        """
        if agent_id in self._agents:
            return self._agents[agent_id]

        from .identity_store import IdentityRecord

        rec = self._identity_store.get(agent_id)
        if rec is None:
            chosen_archetype = archetype or AgentArchetype.UNKNOWN
            rec = IdentityRecord(
                agent_id=agent_id,
                name=name,
                archetype=chosen_archetype,
                rank=AgentRank.NOVICE,
                color_index=color_index_for_agent(agent_id),
                tools_count=0,
                skills_count=0,
            )
            self._identity_store.upsert(rec)
            self._identity_store.save()

        layout = get_layout("lobby")
        occupied = {a.anchor_id for a in self._agents.values() if a.room == "lobby" and a.anchor_id}
        anchor_id = assign_home_anchor(layout, zone=None, occupied=occupied)

        if anchor_id and anchor_id in layout.anchors:
            anchor = layout.anchors[anchor_id]
            x, y = anchor.x, anchor.y
        else:
            exclude = [(a.x, a.y) for a in self._agents.values() if a.room == "lobby"]
            x, y = get_lobby_idle_position(exclude=exclude)

        agent = AgentVisual(
            agent_id=agent_id,
            name=name,
            color_index=rec.color_index,
            expression=Expression.SLEEPY,
            accessory=Accessory.SLEEP_BUBBLE,
            glow=GlowColor.GRAY,
            bubble=None,
            x=x,
            y=y,
            room="lobby",
            zone=None,
            anchor_id=anchor_id,
            home_anchor_id=anchor_id,
            activity=Activity.IDLE,
            facing=Facing.RIGHT,
            archetype=rec.archetype,
            rank=rec.rank,
            parent_agent_id=parent_agent_id,
            tools_count=rec.tools_count,
            skills_count=rec.skills_count,
        )
        self._agents[agent_id] = agent
        return agent

    # ------------------------------------------------------------------
    # Identity mutations — rank + parent
    # ------------------------------------------------------------------

    def update_rank(
        self,
        agent_id: str,
        tools_count: int,
        skills_count: int,
    ) -> tuple[AgentRank, AgentRank] | None:
        """Recompute rank from tool/skill counts.

        Returns ``(old_rank, new_rank)`` if rank changed, else ``None``.
        Counts are always persisted even when rank is unchanged.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            return None
        old_rank = agent.rank
        new_rank = rank_for_counts(tools_count, skills_count)
        agent.tools_count = tools_count
        agent.skills_count = skills_count
        agent.rank = new_rank

        rec = self._identity_store.get(agent_id)
        if rec is not None:
            rec.rank = new_rank
            rec.tools_count = tools_count
            rec.skills_count = skills_count
            self._identity_store.upsert(rec)
            self._identity_store.save()

        if old_rank == new_rank:
            return None
        return (old_rank, new_rank)

    def set_parent(
        self, agent_id: str, parent_agent_id: str | None
    ) -> AgentVisual | None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return None
        agent.parent_agent_id = parent_agent_id
        return agent

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_agent(self, agent_id: str) -> AgentVisual | None:
        return self._agents.get(agent_id)

    def get_all_agents(self) -> list[AgentVisual]:
        return list(self._agents.values())

    def get_agents_in_room(self, room: str) -> list[AgentVisual]:
        return [a for a in self._agents.values() if a.room == room]

    def get_room_list(self) -> list[RoomInfo]:
        """Return RoomInfo for visible project rooms plus any active custom rooms."""
        counts: dict[str, int] = {}
        for agent in self._agents.values():
            if agent.room != "lobby":
                counts[agent.room] = counts.get(agent.room, 0) + 1

        rooms: list[RoomInfo] = []

        for spec in get_demo_room_info():
            room_id = spec["room_id"]
            rooms.append(
                RoomInfo(
                    room_id=room_id,
                    name=spec["name"],
                    agent_count=counts.pop(room_id, 0),
                    theme_key=spec["theme_key"],
                )
            )

        for room_id in sorted(counts):
            rooms.append(
                RoomInfo(
                    room_id=room_id,
                    name=get_room_display_name(room_id),
                    agent_count=counts[room_id],
                    theme_key=get_room_theme_key(room_id),
                )
            )

        return rooms

    def get_meeting(self, meeting_id: str) -> Meeting | None:
        return self._meetings.get(meeting_id)

    def get_meetings_in_room(self, room_id: str) -> list[Meeting]:
        return [m for m in self._meetings.values() if m.room_id == room_id]

    def is_circle_occupied(self, room_id: str) -> bool:
        return room_id in self._occupied_circles

    def is_agent_in_meeting(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        return agent is not None and agent.meeting_id is not None

    # ------------------------------------------------------------------
    # Mutations — Room & Zone
    # ------------------------------------------------------------------

    def move_agent_to_room(self, agent_id: str, room: str) -> None:
        """Move agent to a room, assigning anchor-based position."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return

        agent.room = room
        agent.zone = None
        agent.meeting_id = None

        layout = get_layout(room)
        occupied = {a.anchor_id for a in self._agents.values() if a.room == room and a.agent_id != agent_id and a.anchor_id}

        if room == "lobby":
            agent.expression = Expression.SLEEPY
            agent.accessory = Accessory.SLEEP_BUBBLE
            agent.glow = GlowColor.GRAY
            agent.activity = Activity.IDLE
            anchor_id = assign_home_anchor(layout, zone=None, occupied=occupied)
        else:
            agent.expression = Expression.HAPPY
            agent.glow = GlowColor.GREEN
            agent.activity = Activity.IDLE
            anchor_id = assign_home_anchor(layout, zone=None, occupied=occupied)

        if anchor_id and anchor_id in layout.anchors:
            anchor = layout.anchors[anchor_id]
            agent.x, agent.y = anchor.x, anchor.y
            agent.anchor_id = anchor_id
            agent.home_anchor_id = anchor_id
        else:
            # Fallback
            if room == "lobby":
                exclude = [(a.x, a.y) for a in self._agents.values() if a.room == "lobby" and a.agent_id != agent_id]
                agent.x, agent.y = get_lobby_idle_position(exclude=exclude)
            else:
                agent.x, agent.y = 500.0, 300.0
            agent.anchor_id = None
            agent.home_anchor_id = None

    def move_agent_to_zone(self, agent_id: str, zone: ZoneType) -> None:
        """Assign a zone and pick anchor-based position within it."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return

        # Don't move an agent that's in a meeting
        if agent.meeting_id is not None:
            return

        agent.zone = zone
        layout = get_layout(agent.room)
        occupied = {
            a.anchor_id for a in self._agents.values()
            if a.zone == zone and a.agent_id != agent_id and a.anchor_id
        }
        anchor_id = assign_home_anchor(layout, zone=zone, occupied=occupied)

        if anchor_id and anchor_id in layout.anchors:
            anchor = layout.anchors[anchor_id]
            agent.x, agent.y = anchor.x, anchor.y
            agent.anchor_id = anchor_id
            agent.home_anchor_id = anchor_id
        else:
            # Fallback to legacy
            exclude = [
                (a.x, a.y)
                for a in self._agents.values()
                if a.zone == zone and a.agent_id != agent_id
            ]
            agent.x, agent.y = get_zone_position(zone, exclude=exclude)

    def move_agent_to_anchor(self, agent_id: str, anchor_id: str) -> None:
        """Move agent directly to a specific anchor."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        layout = get_layout(agent.room)
        if anchor_id in layout.anchors:
            anchor = layout.anchors[anchor_id]
            agent.x = anchor.x
            agent.y = anchor.y
            agent.anchor_id = anchor_id

    # ------------------------------------------------------------------
    # Mutations — Visuals
    # ------------------------------------------------------------------

    def update_visual(
        self,
        agent_id: str,
        expression: Expression | None = None,
        accessory: Accessory | None = None,
        glow: GlowColor | None = None,
        bubble: str | None = None,
    ) -> None:
        """Patch only the supplied (non-None) visual fields."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return

        if expression is not None:
            agent.expression = expression
        if accessory is not None:
            agent.accessory = accessory
        if glow is not None:
            agent.glow = glow
        if bubble is not None:
            agent.bubble = bubble

    def update_activity(self, agent_id: str, activity: Activity) -> None:
        agent = self._agents.get(agent_id)
        if agent is not None:
            agent.activity = activity

    def update_facing(self, agent_id: str, facing: Facing) -> None:
        agent = self._agents.get(agent_id)
        if agent is not None:
            agent.facing = facing

    # ------------------------------------------------------------------
    # Mutations — Meetings
    # ------------------------------------------------------------------

    def create_meeting(self, meeting: Meeting) -> bool:
        """Register a meeting. Returns False if the circle is already occupied."""
        if meeting.room_id in self._occupied_circles:
            return False

        self._meetings[meeting.meeting_id] = meeting
        self._occupied_circles[meeting.room_id] = meeting.meeting_id

        # Mark both agents
        for aid in (meeting.agent_a, meeting.agent_b):
            agent = self._agents.get(aid)
            if agent is not None:
                agent.meeting_id = meeting.meeting_id
                agent.activity = Activity.MEETING

        return True

    def update_meeting_phase(self, meeting_id: str, phase: "MeetingPhase") -> None:
        meeting = self._meetings.get(meeting_id)
        if meeting is not None:
            meeting.phase = phase

    def end_meeting(self, meeting_id: str) -> Meeting | None:
        """Remove a meeting and free the circle. Returns the ended meeting."""
        meeting = self._meetings.pop(meeting_id, None)
        if meeting is None:
            return None

        # Free circle
        if self._occupied_circles.get(meeting.room_id) == meeting_id:
            del self._occupied_circles[meeting.room_id]

        # Clear agent meeting state and return them to home anchors
        for aid in (meeting.agent_a, meeting.agent_b):
            agent = self._agents.get(aid)
            if agent is not None:
                agent.meeting_id = None
                agent.activity = Activity.IDLE
                # Return to home anchor position
                if agent.home_anchor_id:
                    layout = get_layout(agent.room)
                    if agent.home_anchor_id in layout.anchors:
                        home = layout.anchors[agent.home_anchor_id]
                        agent.x = home.x
                        agent.y = home.y
                        agent.anchor_id = agent.home_anchor_id

        return meeting

    # ------------------------------------------------------------------
    # Removal
    # ------------------------------------------------------------------

    def remove_agent(self, agent_id: str) -> None:
        agent = self._agents.pop(agent_id, None)
        if agent and agent.meeting_id:
            # End any meeting this agent was in
            self.end_meeting(agent.meeting_id)
