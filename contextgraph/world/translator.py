"""Event translation layer: maps ContextGraph events to game visual state changes."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from contextgraph.events import Event, EventType
from contextgraph.models import SessionEvent
from contextgraph.world.models import (
    Accessory,
    Activity,
    Expression,
    GlowColor,
    MeetingTrigger,
    ZoneType,
)

# Session event_type keyword sets
_CODING_TYPES = frozenset({"file_change", "file_edit", "diff", "command", "tool", "bash"})
_ERROR_TYPES = frozenset({"failure", "blocker", "error"})
_RESOLVED_TYPES = frozenset({"resolved", "fix", "done"})
_DECISION_TYPES = frozenset({"decision"})
_PRESSURE_TYPES = frozenset({"context_pressure", "compact"})
_TODO_TYPES = frozenset({"todo"})
_ARTIFACT_TYPES = frozenset({"artifact", "reference"})


@dataclass
class TranslationResult:
    zone: ZoneType | None = None
    expression: Expression = Expression.HAPPY
    accessory: Accessory = Accessory.NONE
    glow: GlowColor = GlowColor.GREEN
    bubble: str | None = None
    interact_with: str | None = None
    is_spawn: bool = False
    is_despawn: bool = False
    activity: Activity | None = None
    meeting_trigger: MeetingTrigger | None = None
    meeting_data: dict = field(default_factory=dict)


def translate_session_event(event: SessionEvent) -> TranslationResult:
    """Map a SessionEvent to a TranslationResult describing visual state."""
    t = event.event_type

    if t in _CODING_TYPES:
        return TranslationResult(
            zone=ZoneType.CODE_DESK,
            expression=Expression.FOCUSED,
            accessory=Accessory.HARD_HAT,
            glow=GlowColor.GREEN,
            activity=Activity.CODING,
        )

    if t in _ERROR_TYPES:
        return TranslationResult(
            zone=ZoneType.DEBUG_LAB,
            expression=Expression.WORRIED,
            accessory=Accessory.SIREN,
            glow=GlowColor.RED,
            activity=Activity.DEBUGGING,
        )

    if t in _RESOLVED_TYPES:
        return TranslationResult(
            expression=Expression.HAPPY,
            glow=GlowColor.GREEN,
            bubble=event.content,
        )

    if t in _DECISION_TYPES:
        return TranslationResult(
            expression=Expression.THINKING,
            glow=GlowColor.GREEN,
            bubble=event.content,
        )

    if t in _PRESSURE_TYPES:
        return TranslationResult(
            expression=Expression.THINKING,
            glow=GlowColor.YELLOW,
        )

    if t in _TODO_TYPES:
        return TranslationResult(
            expression=Expression.THINKING,
            glow=GlowColor.GREEN,
        )

    if t in _ARTIFACT_TYPES:
        return TranslationResult(
            zone=ZoneType.MEMORY_LIBRARY,
            expression=Expression.FOCUSED,
            accessory=Accessory.MAGNIFYING_GLASS,
            glow=GlowColor.GREEN,
            activity=Activity.RESEARCHING,
        )

    # unknown
    return TranslationResult(
        expression=Expression.HAPPY,
        glow=GlowColor.GREEN,
    )


def translate_bus_event(event: Event) -> TranslationResult:
    """Map an EventBus Event to a TranslationResult describing visual state."""
    et = event.event_type

    if et == EventType.MEMORY_STORED:
        return TranslationResult(
            zone=ZoneType.MEMORY_LIBRARY,
            expression=Expression.FOCUSED,
            accessory=Accessory.BOOK,
            glow=GlowColor.GREEN,
            activity=Activity.RESEARCHING,
        )

    if et == EventType.CLAIM_REVIEWED:
        reviewer = event.data.get("reviewer_agent_id", event.agent_id)
        source = event.data.get("source_agent_id", "")
        claim_id = event.data.get("claim_id", "")
        decision = event.data.get("decision", "")
        return TranslationResult(
            zone=ZoneType.REVIEW_STATION,
            expression=Expression.SOCIAL,
            accessory=Accessory.CLIPBOARD,
            glow=GlowColor.GREEN,
            activity=Activity.REVIEWING,
            meeting_trigger=MeetingTrigger.CLAIM_REVIEW,
            meeting_data={
                "reviewer_agent_id": reviewer,
                "source_agent_id": source,
                "claim_id": claim_id,
                "decision": decision,
            },
        )

    if et == EventType.CLAIM_CREATED:
        return TranslationResult(
            zone=ZoneType.MEMORY_LIBRARY,
            expression=Expression.HAPPY,
            accessory=Accessory.BOOK,
            glow=GlowColor.GREEN,
        )

    if et == EventType.AGENT_REGISTERED:
        return TranslationResult(is_spawn=True)

    if et in (EventType.AGENT_DELETED, EventType.AGENT_SUSPENDED):
        return TranslationResult(is_despawn=True)

    # All other bus events: default visual state
    return TranslationResult()


# ══════════════════════════════════════════════════════════════════════
# Blocker Assist Tracker
# ══════════════════════════════════════════════════════════════════════


class BlockerTracker:
    """Tracks failure/blocker/error events per agent to detect blocker assist scenarios.

    Triggers when an agent has 2+ failure events within a 120-second window.
    """

    WINDOW_SECONDS = 120
    THRESHOLD = 2

    def __init__(self) -> None:
        # agent_id → list of timestamps
        self._failures: dict[str, list[float]] = defaultdict(list)

    def record_failure(self, agent_id: str, timestamp: float | None = None) -> bool:
        """Record a failure event. Returns True if threshold is met (trigger blocker assist)."""
        ts = timestamp if timestamp is not None else time.time()
        events = self._failures[agent_id]
        events.append(ts)

        # Prune old events outside window
        cutoff = ts - self.WINDOW_SECONDS
        self._failures[agent_id] = [t for t in events if t >= cutoff]

        return len(self._failures[agent_id]) >= self.THRESHOLD

    def clear(self, agent_id: str) -> None:
        """Clear failure history for an agent (e.g. after a meeting is triggered)."""
        self._failures.pop(agent_id, None)
