from __future__ import annotations

import unittest

from contextgraph.world.models import (
    Accessory,
    Activity,
    AgentVisual,
    Expression,
    Facing,
    GameEvent,
    GameEventType,
    GlowColor,
    RoomInfo,
    ZoneType,
)


class ExpressionEnumTest(unittest.TestCase):
    def test_members(self) -> None:
        self.assertEqual(Expression.HAPPY, "happy")
        self.assertEqual(Expression.THINKING, "thinking")
        self.assertEqual(Expression.WORRIED, "worried")
        self.assertEqual(Expression.FOCUSED, "focused")
        self.assertEqual(Expression.SOCIAL, "social")
        self.assertEqual(Expression.SLEEPY, "sleepy")

    def test_count(self) -> None:
        self.assertEqual(len(Expression), 6)


class AccessoryEnumTest(unittest.TestCase):
    def test_members(self) -> None:
        self.assertEqual(Accessory.HARD_HAT, "hard_hat")
        self.assertEqual(Accessory.SIREN, "siren")
        self.assertEqual(Accessory.BOOK, "book")
        self.assertEqual(Accessory.MAGNIFYING_GLASS, "magnifying_glass")
        self.assertEqual(Accessory.CLIPBOARD, "clipboard")
        self.assertEqual(Accessory.SLEEP_BUBBLE, "sleep_bubble")
        self.assertEqual(Accessory.NONE, "none")

    def test_count(self) -> None:
        self.assertEqual(len(Accessory), 7)


class GlowColorEnumTest(unittest.TestCase):
    def test_members(self) -> None:
        self.assertEqual(GlowColor.GREEN, "green")
        self.assertEqual(GlowColor.YELLOW, "yellow")
        self.assertEqual(GlowColor.RED, "red")
        self.assertEqual(GlowColor.GRAY, "gray")
        self.assertEqual(GlowColor.BLUE, "blue")

    def test_count(self) -> None:
        self.assertEqual(len(GlowColor), 5)


class ZoneTypeEnumTest(unittest.TestCase):
    def test_members(self) -> None:
        self.assertEqual(ZoneType.CODE_DESK, "code_desk")
        self.assertEqual(ZoneType.MEMORY_LIBRARY, "memory_library")
        self.assertEqual(ZoneType.REVIEW_STATION, "review_station")
        self.assertEqual(ZoneType.DEBUG_LAB, "debug_lab")

    def test_count(self) -> None:
        self.assertEqual(len(ZoneType), 4)


class GameEventTypeEnumTest(unittest.TestCase):
    def test_members(self) -> None:
        self.assertEqual(GameEventType.AGENT_MOVE, "agent_move")
        self.assertEqual(GameEventType.AGENT_STATE, "agent_state")
        self.assertEqual(GameEventType.AGENT_INTERACT, "agent_interact")
        self.assertEqual(GameEventType.AGENT_SPAWN, "agent_spawn")
        self.assertEqual(GameEventType.AGENT_DESPAWN, "agent_despawn")
        self.assertEqual(GameEventType.WORLD_SNAPSHOT, "world_snapshot")
        self.assertEqual(GameEventType.ROOM_SNAPSHOT, "room_snapshot")

    def test_count(self) -> None:
        self.assertEqual(len(GameEventType), 13)


class AgentVisualTest(unittest.TestCase):
    def test_defaults(self) -> None:
        av = AgentVisual(agent_id="agt_1", name="Alice", color_index=0)
        self.assertEqual(av.expression, Expression.HAPPY)
        self.assertEqual(av.accessory, Accessory.NONE)
        self.assertEqual(av.glow, GlowColor.GRAY)
        self.assertIsNone(av.bubble)
        self.assertEqual(av.x, 0.0)
        self.assertEqual(av.y, 0.0)
        self.assertEqual(av.room, "lobby")
        self.assertIsNone(av.zone)
        self.assertIsNone(av.anchor_id)
        self.assertIsNone(av.home_anchor_id)
        self.assertIsNone(av.meeting_id)
        self.assertEqual(av.activity.value, "idle")
        self.assertEqual(av.facing.value, "right")

    def test_to_dict_required_fields(self) -> None:
        av = AgentVisual(agent_id="agt_1", name="Alice", color_index=2)
        d = av.to_dict()
        self.assertEqual(d["agent_id"], "agt_1")
        self.assertEqual(d["name"], "Alice")
        self.assertEqual(d["color_index"], 2)

    def test_to_dict_defaults(self) -> None:
        av = AgentVisual(agent_id="agt_1", name="Bob", color_index=1)
        d = av.to_dict()
        self.assertEqual(d["expression"], "happy")
        self.assertEqual(d["accessory"], "none")
        self.assertEqual(d["glow"], "gray")
        self.assertIsNone(d["bubble"])
        self.assertEqual(d["x"], 0.0)
        self.assertEqual(d["y"], 0.0)
        self.assertEqual(d["room"], "lobby")
        self.assertIsNone(d["zone"])
        self.assertIsNone(d["anchor_id"])
        self.assertIsNone(d["home_anchor_id"])
        self.assertIsNone(d["meeting_id"])
        self.assertEqual(d["activity"], "idle")
        self.assertEqual(d["facing"], "right")

    def test_to_dict_custom_values(self) -> None:
        av = AgentVisual(
            agent_id="agt_2",
            name="Carol",
            color_index=3,
            expression=Expression.THINKING,
            accessory=Accessory.BOOK,
            glow=GlowColor.GREEN,
            bubble="Hello!",
            x=10.5,
            y=20.0,
            room="code_room",
            zone=ZoneType.CODE_DESK,
        )
        d = av.to_dict()
        self.assertEqual(d["expression"], "thinking")
        self.assertEqual(d["accessory"], "book")
        self.assertEqual(d["glow"], "green")
        self.assertEqual(d["bubble"], "Hello!")
        self.assertEqual(d["x"], 10.5)
        self.assertEqual(d["y"], 20.0)
        self.assertEqual(d["room"], "code_room")
        self.assertEqual(d["zone"], "code_desk")


class GameEventTest(unittest.TestCase):
    def test_defaults(self) -> None:
        ev = GameEvent(type=GameEventType.AGENT_SPAWN, agent_id="agt_1")
        self.assertEqual(ev.data, {})

    def test_to_dict(self) -> None:
        ev = GameEvent(
            type=GameEventType.AGENT_MOVE,
            agent_id="agt_1",
            data={"x": 5.0, "y": 3.0},
        )
        d = ev.to_dict()
        self.assertEqual(d["type"], "agent_move")
        self.assertEqual(d["agent_id"], "agt_1")
        self.assertEqual(d["data"], {"x": 5.0, "y": 3.0})

    def test_to_dict_default_data(self) -> None:
        ev = GameEvent(type=GameEventType.AGENT_DESPAWN, agent_id="agt_2")
        d = ev.to_dict()
        self.assertEqual(d["data"], {})

    def test_data_not_shared_between_instances(self) -> None:
        ev1 = GameEvent(type=GameEventType.AGENT_STATE, agent_id="agt_1")
        ev2 = GameEvent(type=GameEventType.AGENT_STATE, agent_id="agt_2")
        ev1.data["key"] = "value"
        self.assertNotIn("key", ev2.data)


class RoomInfoTest(unittest.TestCase):
    def test_defaults(self) -> None:
        ri = RoomInfo(room_id="room_1", name="Lobby")
        self.assertEqual(ri.agent_count, 0)
        self.assertIsNone(ri.theme_key)

    def test_to_dict(self) -> None:
        ri = RoomInfo(room_id="room_1", name="Lobby", agent_count=3, theme_key="library")
        d = ri.to_dict()
        self.assertEqual(d["room_id"], "room_1")
        self.assertEqual(d["name"], "Lobby")
        self.assertEqual(d["agent_count"], 3)
        self.assertEqual(d["theme_key"], "library")

    def test_to_dict_default_count(self) -> None:
        ri = RoomInfo(room_id="room_2", name="Code Room")
        d = ri.to_dict()
        self.assertEqual(d["agent_count"], 0)
        self.assertIsNone(d["theme_key"])


if __name__ == "__main__":
    unittest.main()
