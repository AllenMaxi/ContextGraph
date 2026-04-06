"""Tests for contextgraph.world.translator."""
from __future__ import annotations

import unittest
from datetime import datetime

from contextgraph.events import Event, EventType
from contextgraph.models import SessionEvent
from contextgraph.world.models import Accessory, Expression, GlowColor, ZoneType
from contextgraph.world.translator import TranslationResult, translate_bus_event, translate_session_event


def _make_session_event(event_type: str, content: str = "test content") -> SessionEvent:
    return SessionEvent(
        event_id="evt_1",
        session_id="sess_1",
        agent_id="agt_1",
        event_type=event_type,
        content=content,
        created_at=datetime(2024, 1, 1),
    )


def _make_bus_event(event_type: EventType) -> Event:
    return Event(
        event_id="evt_1",
        event_type=event_type,
        data={},
        timestamp=datetime(2024, 1, 1),
        agent_id="agt_1",
    )


class TranslationResultDefaultsTest(unittest.TestCase):
    def test_defaults(self) -> None:
        result = TranslationResult()
        self.assertIsNone(result.zone)
        self.assertEqual(result.expression, Expression.HAPPY)
        self.assertEqual(result.accessory, Accessory.NONE)
        self.assertEqual(result.glow, GlowColor.GREEN)
        self.assertIsNone(result.bubble)
        self.assertIsNone(result.interact_with)
        self.assertFalse(result.is_spawn)
        self.assertFalse(result.is_despawn)


class TranslateSessionEventCodingTest(unittest.TestCase):
    """file_change, file_edit, diff, command, tool, bash → CODE_DESK, HARD_HAT, FOCUSED, GREEN"""

    def _assert_coding(self, result: TranslationResult) -> None:
        self.assertEqual(result.zone, ZoneType.CODE_DESK)
        self.assertEqual(result.accessory, Accessory.HARD_HAT)
        self.assertEqual(result.expression, Expression.FOCUSED)
        self.assertEqual(result.glow, GlowColor.GREEN)

    def test_file_change(self) -> None:
        self._assert_coding(translate_session_event(_make_session_event("file_change")))

    def test_file_edit(self) -> None:
        self._assert_coding(translate_session_event(_make_session_event("file_edit")))

    def test_diff(self) -> None:
        self._assert_coding(translate_session_event(_make_session_event("diff")))

    def test_command(self) -> None:
        self._assert_coding(translate_session_event(_make_session_event("command")))

    def test_tool(self) -> None:
        self._assert_coding(translate_session_event(_make_session_event("tool")))

    def test_bash(self) -> None:
        self._assert_coding(translate_session_event(_make_session_event("bash")))


class TranslateSessionEventErrorTest(unittest.TestCase):
    """failure, blocker, error → DEBUG_LAB, SIREN, WORRIED, RED"""

    def _assert_error(self, result: TranslationResult) -> None:
        self.assertEqual(result.zone, ZoneType.DEBUG_LAB)
        self.assertEqual(result.accessory, Accessory.SIREN)
        self.assertEqual(result.expression, Expression.WORRIED)
        self.assertEqual(result.glow, GlowColor.RED)

    def test_failure(self) -> None:
        self._assert_error(translate_session_event(_make_session_event("failure")))

    def test_blocker(self) -> None:
        self._assert_error(translate_session_event(_make_session_event("blocker")))

    def test_error(self) -> None:
        self._assert_error(translate_session_event(_make_session_event("error")))


class TranslateSessionEventResolvedTest(unittest.TestCase):
    """resolved, fix, done → no zone change, HAPPY, GREEN, bubble with content"""

    def _assert_resolved(self, result: TranslationResult, content: str) -> None:
        self.assertIsNone(result.zone)
        self.assertEqual(result.expression, Expression.HAPPY)
        self.assertEqual(result.glow, GlowColor.GREEN)
        self.assertEqual(result.bubble, content)

    def test_resolved(self) -> None:
        ev = _make_session_event("resolved", "All good!")
        self._assert_resolved(translate_session_event(ev), "All good!")

    def test_fix(self) -> None:
        ev = _make_session_event("fix", "Fixed bug")
        self._assert_resolved(translate_session_event(ev), "Fixed bug")

    def test_done(self) -> None:
        ev = _make_session_event("done", "Task complete")
        self._assert_resolved(translate_session_event(ev), "Task complete")


class TranslateSessionEventDecisionTest(unittest.TestCase):
    """decision → THINKING, GREEN, bubble with content"""

    def test_decision(self) -> None:
        ev = _make_session_event("decision", "Should I use X or Y?")
        result = translate_session_event(ev)
        self.assertEqual(result.expression, Expression.THINKING)
        self.assertEqual(result.glow, GlowColor.GREEN)
        self.assertEqual(result.bubble, "Should I use X or Y?")


class TranslateSessionEventContextPressureTest(unittest.TestCase):
    """context_pressure, compact → THINKING, YELLOW"""

    def _assert_pressure(self, result: TranslationResult) -> None:
        self.assertEqual(result.expression, Expression.THINKING)
        self.assertEqual(result.glow, GlowColor.YELLOW)

    def test_context_pressure(self) -> None:
        self._assert_pressure(translate_session_event(_make_session_event("context_pressure")))

    def test_compact(self) -> None:
        self._assert_pressure(translate_session_event(_make_session_event("compact")))


class TranslateSessionEventTodoTest(unittest.TestCase):
    """todo → THINKING, GREEN"""

    def test_todo(self) -> None:
        result = translate_session_event(_make_session_event("todo"))
        self.assertEqual(result.expression, Expression.THINKING)
        self.assertEqual(result.glow, GlowColor.GREEN)


class TranslateSessionEventArtifactTest(unittest.TestCase):
    """artifact, reference → MEMORY_LIBRARY, MAGNIFYING_GLASS, FOCUSED"""

    def _assert_artifact(self, result: TranslationResult) -> None:
        self.assertEqual(result.zone, ZoneType.MEMORY_LIBRARY)
        self.assertEqual(result.accessory, Accessory.MAGNIFYING_GLASS)
        self.assertEqual(result.expression, Expression.FOCUSED)

    def test_artifact(self) -> None:
        self._assert_artifact(translate_session_event(_make_session_event("artifact")))

    def test_reference(self) -> None:
        self._assert_artifact(translate_session_event(_make_session_event("reference")))


class TranslateSessionEventUnknownTest(unittest.TestCase):
    """unknown → HAPPY, GREEN, no zone change"""

    def test_unknown_type(self) -> None:
        result = translate_session_event(_make_session_event("something_random"))
        self.assertIsNone(result.zone)
        self.assertEqual(result.expression, Expression.HAPPY)
        self.assertEqual(result.glow, GlowColor.GREEN)

    def test_no_spawn_or_despawn_for_session_events(self) -> None:
        result = translate_session_event(_make_session_event("file_change"))
        self.assertFalse(result.is_spawn)
        self.assertFalse(result.is_despawn)


class TranslateBusEventMemoryStoredTest(unittest.TestCase):
    """MEMORY_STORED → MEMORY_LIBRARY, BOOK, FOCUSED"""

    def test_memory_stored(self) -> None:
        result = translate_bus_event(_make_bus_event(EventType.MEMORY_STORED))
        self.assertEqual(result.zone, ZoneType.MEMORY_LIBRARY)
        self.assertEqual(result.accessory, Accessory.BOOK)
        self.assertEqual(result.expression, Expression.FOCUSED)


class TranslateBusEventClaimReviewedTest(unittest.TestCase):
    """CLAIM_REVIEWED → REVIEW_STATION, CLIPBOARD, SOCIAL"""

    def test_claim_reviewed(self) -> None:
        result = translate_bus_event(_make_bus_event(EventType.CLAIM_REVIEWED))
        self.assertEqual(result.zone, ZoneType.REVIEW_STATION)
        self.assertEqual(result.accessory, Accessory.CLIPBOARD)
        self.assertEqual(result.expression, Expression.SOCIAL)


class TranslateBusEventClaimCreatedTest(unittest.TestCase):
    """CLAIM_CREATED → MEMORY_LIBRARY, BOOK, HAPPY"""

    def test_claim_created(self) -> None:
        result = translate_bus_event(_make_bus_event(EventType.CLAIM_CREATED))
        self.assertEqual(result.zone, ZoneType.MEMORY_LIBRARY)
        self.assertEqual(result.accessory, Accessory.BOOK)
        self.assertEqual(result.expression, Expression.HAPPY)


class TranslateBusEventAgentRegisteredTest(unittest.TestCase):
    """AGENT_REGISTERED → is_spawn=True"""

    def test_agent_registered(self) -> None:
        result = translate_bus_event(_make_bus_event(EventType.AGENT_REGISTERED))
        self.assertTrue(result.is_spawn)
        self.assertFalse(result.is_despawn)


class TranslateBusEventAgentDespawnTest(unittest.TestCase):
    """AGENT_DELETED, AGENT_SUSPENDED → is_despawn=True"""

    def test_agent_deleted(self) -> None:
        result = translate_bus_event(_make_bus_event(EventType.AGENT_DELETED))
        self.assertTrue(result.is_despawn)
        self.assertFalse(result.is_spawn)

    def test_agent_suspended(self) -> None:
        result = translate_bus_event(_make_bus_event(EventType.AGENT_SUSPENDED))
        self.assertTrue(result.is_despawn)
        self.assertFalse(result.is_spawn)


class TranslateBusEventUnknownTest(unittest.TestCase):
    """Other bus events return a default TranslationResult."""

    def test_heartbeat(self) -> None:
        result = translate_bus_event(_make_bus_event(EventType.HEARTBEAT))
        self.assertIsNone(result.zone)
        self.assertEqual(result.expression, Expression.HAPPY)
        self.assertFalse(result.is_spawn)
        self.assertFalse(result.is_despawn)


if __name__ == "__main__":
    unittest.main()
