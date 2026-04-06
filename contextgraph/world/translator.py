"""Event translation layer: maps ContextGraph events to game visual state changes."""
from __future__ import annotations

from dataclasses import dataclass

from contextgraph.events import Event, EventType
from contextgraph.models import SessionEvent
from contextgraph.world.models import Accessory, Expression, GlowColor, ZoneType

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


def translate_session_event(event: SessionEvent) -> TranslationResult:
    """Map a SessionEvent to a TranslationResult describing visual state."""
    t = event.event_type

    if t in _CODING_TYPES:
        return TranslationResult(
            zone=ZoneType.CODE_DESK,
            expression=Expression.FOCUSED,
            accessory=Accessory.HARD_HAT,
            glow=GlowColor.GREEN,
        )

    if t in _ERROR_TYPES:
        return TranslationResult(
            zone=ZoneType.DEBUG_LAB,
            expression=Expression.WORRIED,
            accessory=Accessory.SIREN,
            glow=GlowColor.RED,
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
        )

    if et == EventType.CLAIM_REVIEWED:
        return TranslationResult(
            zone=ZoneType.REVIEW_STATION,
            expression=Expression.SOCIAL,
            accessory=Accessory.CLIPBOARD,
            glow=GlowColor.GREEN,
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
