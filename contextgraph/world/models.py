"""Game-specific data models for ContextGraph World."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Expression(StrEnum):
    HAPPY = "happy"
    THINKING = "thinking"
    WORRIED = "worried"
    FOCUSED = "focused"
    SOCIAL = "social"
    SLEEPY = "sleepy"


class Accessory(StrEnum):
    HARD_HAT = "hard_hat"
    SIREN = "siren"
    BOOK = "book"
    MAGNIFYING_GLASS = "magnifying_glass"
    CLIPBOARD = "clipboard"
    SLEEP_BUBBLE = "sleep_bubble"
    NONE = "none"


class GlowColor(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    GRAY = "gray"
    BLUE = "blue"


class ZoneType(StrEnum):
    CODE_DESK = "code_desk"
    MEMORY_LIBRARY = "memory_library"
    REVIEW_STATION = "review_station"
    DEBUG_LAB = "debug_lab"


class Activity(StrEnum):
    IDLE = "idle"
    CODING = "coding"
    REVIEWING = "reviewing"
    DEBUGGING = "debugging"
    RESEARCHING = "researching"
    MEETING = "meeting"
    WALKING = "walking"


class Facing(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class AgentArchetype(StrEnum):
    ARCHMAGE = "archmage"  # main Claude session
    SCOUT = "scout"  # Explore
    ORACLE = "oracle"  # Plan
    SCRIBE = "scribe"  # code-reviewer
    APPRENTICE = "apprentice"  # general-purpose
    ARTIFICER = "artificer"  # statusline-setup
    SAGE = "sage"  # claude-code-guide
    USER = "user"  # human user avatar
    UNKNOWN = "unknown"


class AgentRank(StrEnum):
    NOVICE = "novice"
    ADEPT = "adept"
    MAGE = "mage"
    HIGH_MAGE = "high_mage"
    AVATAR = "avatar"


def rank_for_counts(tools_count: int, skills_count: int) -> AgentRank:
    total = max(0, tools_count) + max(0, skills_count)
    if total <= 5:
        return AgentRank.NOVICE
    if total <= 15:
        return AgentRank.ADEPT
    if total <= 30:
        return AgentRank.MAGE
    if total <= 60:
        return AgentRank.HIGH_MAGE
    return AgentRank.AVATAR


class MeetingPhase(StrEnum):
    GATHERING = "gathering"
    FACING = "facing"
    BUBBLE_A = "bubble_a"
    BUBBLE_B = "bubble_b"
    ORB_EXCHANGE = "orb_exchange"
    LINGERING = "lingering"
    DISPERSING = "dispersing"


class GameEventType(StrEnum):
    AGENT_MOVE = "agent_move"
    AGENT_STATE = "agent_state"
    AGENT_INTERACT = "agent_interact"
    AGENT_SPAWN = "agent_spawn"
    AGENT_DESPAWN = "agent_despawn"
    AGENT_PATH = "agent_path"
    AGENT_UPGRADE = "agent_upgrade"
    HANDOFF_ORB = "handoff_orb"
    MEETING_STARTED = "meeting_started"
    MEETING_UPDATED = "meeting_updated"
    MEETING_ENDED = "meeting_ended"
    WORLD_SNAPSHOT = "world_snapshot"
    ROOM_SNAPSHOT = "room_snapshot"


class MeetingTrigger(StrEnum):
    CLAIM_REVIEW = "claim_review"
    BLOCKER_ASSIST = "blocker_assist"


# ── Anchor & Layout ──────────────────────────────────────────────────


@dataclass
class Anchor:
    """A named position in a room that agents can walk to."""

    anchor_id: str
    x: float
    y: float
    zone: ZoneType | None = None
    wander_radius: float = 40.0

    def to_dict(self) -> dict:
        return {
            "anchor_id": self.anchor_id,
            "x": self.x,
            "y": self.y,
            "zone": self.zone.value if self.zone else None,
            "wander_radius": self.wander_radius,
        }


@dataclass
class MeetingCircle:
    """A fixed meeting spot with two seat anchors."""

    circle_id: str
    x: float
    y: float
    radius: float = 40.0
    seat_a: str = ""  # anchor_id for seat A
    seat_b: str = ""  # anchor_id for seat B

    def to_dict(self) -> dict:
        return {
            "circle_id": self.circle_id,
            "x": self.x,
            "y": self.y,
            "radius": self.radius,
            "seat_a": self.seat_a,
            "seat_b": self.seat_b,
        }


@dataclass
class RoomLayout:
    """Complete spatial layout for a room."""

    room_id: str
    anchors: dict[str, Anchor] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)
    meeting_circle: MeetingCircle | None = None

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "anchors": {k: v.to_dict() for k, v in self.anchors.items()},
            "edges": self.edges,
            "meeting_circle": self.meeting_circle.to_dict() if self.meeting_circle else None,
        }

    def neighbors(self, anchor_id: str) -> list[str]:
        """Return adjacent anchor IDs in the waypoint graph."""
        result = []
        for a, b in self.edges:
            if a == anchor_id:
                result.append(b)
            elif b == anchor_id:
                result.append(a)
        return result

    def shortest_path(self, start: str, end: str) -> list[str]:
        """Dijkstra on anchor graph. Returns list of anchor_ids from start to end inclusive."""
        if start == end:
            return [start]
        if start not in self.anchors or end not in self.anchors:
            return [start, end]

        import heapq

        dist: dict[str, float] = {aid: float("inf") for aid in self.anchors}
        prev: dict[str, str | None] = {aid: None for aid in self.anchors}
        dist[start] = 0.0
        heap = [(0.0, start)]

        while heap:
            d, u = heapq.heappop(heap)
            if u == end:
                break
            if d > dist[u]:
                continue
            for nb in self.neighbors(u):
                a_u = self.anchors[u]
                a_nb = self.anchors[nb]
                w = ((a_u.x - a_nb.x) ** 2 + (a_u.y - a_nb.y) ** 2) ** 0.5
                nd = d + w
                if nd < dist[nb]:
                    dist[nb] = nd
                    prev[nb] = u
                    heapq.heappush(heap, (nd, nb))

        # Reconstruct
        if prev[end] is None and start != end:
            return [start, end]  # no path found, direct jump
        path = []
        cur: str | None = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path


# ── Meeting ──────────────────────────────────────────────────────────


@dataclass
class Meeting:
    """An active two-agent meeting."""

    meeting_id: str
    room_id: str
    circle_id: str
    trigger: MeetingTrigger
    agent_a: str
    agent_b: str
    phase: MeetingPhase = MeetingPhase.GATHERING
    bubble_a: str = ""
    bubble_b: str = ""

    def to_dict(self) -> dict:
        return {
            "meeting_id": self.meeting_id,
            "room_id": self.room_id,
            "circle_id": self.circle_id,
            "trigger": self.trigger.value,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "phase": self.phase.value,
            "bubble_a": self.bubble_a,
            "bubble_b": self.bubble_b,
        }


# ── Agent ────────────────────────────────────────────────────────────


@dataclass
class AgentVisual:
    agent_id: str
    name: str
    color_index: int
    expression: Expression = Expression.HAPPY
    accessory: Accessory = Accessory.NONE
    glow: GlowColor = GlowColor.GRAY
    bubble: str | None = None
    x: float = 0.0
    y: float = 0.0
    room: str = "lobby"
    zone: ZoneType | None = None
    anchor_id: str | None = None
    home_anchor_id: str | None = None
    meeting_id: str | None = None
    activity: Activity = Activity.IDLE
    facing: Facing = Facing.RIGHT
    archetype: AgentArchetype = AgentArchetype.UNKNOWN
    rank: AgentRank = AgentRank.NOVICE
    parent_agent_id: str | None = None
    tools_count: int = 0
    skills_count: int = 0

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "color_index": self.color_index,
            "expression": self.expression.value,
            "accessory": self.accessory.value,
            "glow": self.glow.value,
            "bubble": self.bubble,
            "x": self.x,
            "y": self.y,
            "room": self.room,
            "zone": self.zone.value if self.zone else None,
            "anchor_id": self.anchor_id,
            "home_anchor_id": self.home_anchor_id,
            "meeting_id": self.meeting_id,
            "activity": self.activity.value,
            "facing": self.facing.value,
            "archetype": self.archetype.value,
            "rank": self.rank.value,
            "parent_agent_id": self.parent_agent_id,
            "tools_count": self.tools_count,
            "skills_count": self.skills_count,
        }


@dataclass
class GameEvent:
    type: GameEventType
    agent_id: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type.value, "agent_id": self.agent_id, "data": self.data}


@dataclass
class RoomInfo:
    room_id: str
    name: str
    agent_count: int = 0
    theme_key: str | None = None

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "name": self.name,
            "agent_count": self.agent_count,
            "theme_key": self.theme_key,
        }
