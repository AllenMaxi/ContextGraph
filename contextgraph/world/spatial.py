"""Spatial state tracker — manages agent positions, rooms, and zones."""
from __future__ import annotations

from .models import (
    Accessory,
    AgentVisual,
    Expression,
    GlowColor,
    RoomInfo,
    ZoneType,
)
from .rooms import (
    color_index_for_agent,
    get_lobby_idle_position,
    get_zone_position,
)


class SpatialState:
    """Tracks every agent's visual / spatial state in the world."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentVisual] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_agent(self, agent_id: str, name: str) -> AgentVisual:
        """Create an agent in the lobby.  Idempotent — returns existing entry."""
        if agent_id in self._agents:
            return self._agents[agent_id]

        exclude = [(a.x, a.y) for a in self._agents.values() if a.room == "lobby"]
        x, y = get_lobby_idle_position(exclude=exclude)

        agent = AgentVisual(
            agent_id=agent_id,
            name=name,
            color_index=color_index_for_agent(agent_id),
            expression=Expression.SLEEPY,
            accessory=Accessory.SLEEP_BUBBLE,
            glow=GlowColor.GRAY,
            bubble=None,
            x=x,
            y=y,
            room="lobby",
            zone=None,
        )
        self._agents[agent_id] = agent
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
        """Return RoomInfo for every non-lobby room that has at least one agent."""
        counts: dict[str, int] = {}
        for agent in self._agents.values():
            if agent.room != "lobby":
                counts[agent.room] = counts.get(agent.room, 0) + 1

        return [
            RoomInfo(room_id=room_id, name=room_id.replace("_", " ").title(), agent_count=count)
            for room_id, count in counts.items()
        ]

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def move_agent_to_room(self, agent_id: str, room: str) -> None:
        """Move agent to a room, resetting zone.

        Lobby → SLEEPY, SLEEP_BUBBLE, GRAY.
        Any other room → HAPPY, GREEN.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            return

        agent.room = room
        agent.zone = None

        if room == "lobby":
            agent.expression = Expression.SLEEPY
            agent.accessory = Accessory.SLEEP_BUBBLE
            agent.glow = GlowColor.GRAY
            exclude = [(a.x, a.y) for a in self._agents.values() if a.room == "lobby" and a.agent_id != agent_id]
            agent.x, agent.y = get_lobby_idle_position(exclude=exclude)
        else:
            agent.expression = Expression.HAPPY
            agent.glow = GlowColor.GREEN
            # Position will be refined once a zone is assigned; park at room centre.
            agent.x, agent.y = 500.0, 300.0

    def move_agent_to_zone(self, agent_id: str, zone: ZoneType) -> None:
        """Assign a zone and pick a non-overlapping position within it."""
        agent = self._agents.get(agent_id)
        if agent is None:
            return

        agent.zone = zone
        exclude = [
            (a.x, a.y)
            for a in self._agents.values()
            if a.zone == zone and a.agent_id != agent_id
        ]
        agent.x, agent.y = get_zone_position(zone, exclude=exclude)

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

    def remove_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
