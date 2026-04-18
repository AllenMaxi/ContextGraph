"""Room templates, zone definitions, anchor layouts, and position helpers."""
from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence

from .models import Anchor, MeetingCircle, RoomLayout, ZoneType

AGENT_COLORS = [
    "#6366f1", "#f97316", "#06b6d4", "#ec4899", "#10b981", "#f59e0b",
    "#f43f5e", "#0ea5e9", "#8b5cf6", "#14b8a6", "#84cc16", "#d946ef",
]

ROOM_THEME_KEYS = ("library", "observatory", "alchemy", "workshop")
DEMO_ROOM_SPECS: dict[str, dict[str, str]] = {
    "ancient_library": {"name": "Ancient Library", "theme_key": "library"},
    "star_observatory": {"name": "Star Observatory", "theme_key": "observatory"},
    "alchemy_atelier": {"name": "Alchemy Atelier", "theme_key": "alchemy"},
    "rune_workshop": {"name": "Rune Workshop", "theme_key": "workshop"},
}

# Legacy zone rectangles — kept for backward-compat with existing tests
ROOM_ZONES: dict[ZoneType, dict[str, float]] = {
    ZoneType.CODE_DESK:       {"x": 80,  "y": 120, "w": 300, "h": 200},
    ZoneType.MEMORY_LIBRARY:  {"x": 640, "y": 120, "w": 300, "h": 200},
    ZoneType.REVIEW_STATION:  {"x": 80,  "y": 440, "w": 300, "h": 200},
    ZoneType.DEBUG_LAB:       {"x": 640, "y": 440, "w": 300, "h": 200},
}

LOBBY_ZONES: dict[str, dict[str, float]] = {
    "idle": {"x": 220, "y": 190, "w": 580, "h": 300},
}


def color_index_for_agent(agent_id: str) -> int:
    return int(hashlib.md5(agent_id.encode()).hexdigest()[:8], 16) % len(AGENT_COLORS)


def get_room_theme_key(room_id: str) -> str:
    """Return a deterministic theme key for a project room."""
    if room_id in DEMO_ROOM_SPECS:
        return DEMO_ROOM_SPECS[room_id]["theme_key"]
    digest = hashlib.sha256(room_id.encode()).hexdigest()
    return ROOM_THEME_KEYS[int(digest[:8], 16) % len(ROOM_THEME_KEYS)]


def get_room_display_name(room_id: str) -> str:
    """Return the user-facing room name."""
    if room_id in DEMO_ROOM_SPECS:
        return DEMO_ROOM_SPECS[room_id]["name"]
    return room_id.replace("_", " ").title()


def get_demo_room_info() -> list[dict[str, str]]:
    """Return the always-visible demo room catalog for world navigation."""
    return [
        {"room_id": room_id, **spec}
        for room_id, spec in DEMO_ROOM_SPECS.items()
    ]


# ── Legacy position helpers (kept for backward compat) ───────────────

def get_zone_position(
    zone: ZoneType,
    exclude: Sequence[tuple[float, float]] = (),
    min_distance: float = 40.0,
) -> tuple[float, float]:
    rect = ROOM_ZONES[zone]
    for _ in range(50):
        x = random.uniform(rect["x"], rect["x"] + rect["w"])
        y = random.uniform(rect["y"], rect["y"] + rect["h"])
        if all(((x - ex) ** 2 + (y - ey) ** 2) ** 0.5 >= min_distance for ex, ey in exclude):
            return (x, y)
    return (rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] / 2)


def get_lobby_idle_position(exclude: Sequence[tuple[float, float]] = ()) -> tuple[float, float]:
    rect = LOBBY_ZONES["idle"]
    for _ in range(50):
        x = random.uniform(rect["x"], rect["x"] + rect["w"])
        y = random.uniform(rect["y"], rect["y"] + rect["h"])
        if all(((x - ex) ** 2 + (y - ey) ** 2) ** 0.5 >= 40.0 for ex, ey in exclude):
            return (x, y)
    return (rect["x"] + rect["w"] / 2, rect["y"] + rect["h"] / 2)


def get_lobby_door_position(door_index: int) -> tuple[float, float]:
    return (160.0 + door_index * 160, 112.0)


# ══════════════════════════════════════════════════════════════════════
# Authored Room Layouts — anchors, waypoints, meeting circles
# ══════════════════════════════════════════════════════════════════════

# Canvas is 1024 x 576.
# Top 50px reserved for HUD. Usable: y=50..560.
# Each room has a theme-specific staged layout, plus a central meeting circle.

def _build_project_room_layout(room_id: str) -> RoomLayout:
    """Build the canonical layout for any project room.

    Rooms keep the same 4 logical zones for agent behavior, but anchors are
    staged around one coherent themed room instead of a uniform 2x2 grid.
    """
    theme_key = get_room_theme_key(room_id)

    themed_positions: dict[str, dict[ZoneType | str, tuple[float, float] | tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]] = {
        "library": {
            "center": (512.0, 326.0),
            "meeting_a": (476.0, 326.0),
            "meeting_b": (548.0, 326.0),
            "idle_left": (430.0, 452.0),
            "idle_right": (594.0, 452.0),
            ZoneType.MEMORY_LIBRARY: ((216.0, 236.0), (290.0, 262.0), (382.0, 274.0)),
            ZoneType.CODE_DESK: ((694.0, 226.0), (770.0, 248.0), (628.0, 264.0)),
            ZoneType.REVIEW_STATION: ((690.0, 386.0), (772.0, 410.0), (640.0, 382.0)),
            ZoneType.DEBUG_LAB: ((244.0, 386.0), (324.0, 412.0), (388.0, 388.0)),
        },
        "observatory": {
            "center": (512.0, 318.0),
            "meeting_a": (476.0, 318.0),
            "meeting_b": (548.0, 318.0),
            "idle_left": (418.0, 452.0),
            "idle_right": (606.0, 452.0),
            ZoneType.REVIEW_STATION: ((452.0, 206.0), (572.0, 208.0), (512.0, 258.0)),
            ZoneType.MEMORY_LIBRARY: ((206.0, 356.0), (286.0, 388.0), (380.0, 362.0)),
            ZoneType.CODE_DESK: ((742.0, 350.0), (820.0, 384.0), (646.0, 360.0)),
            ZoneType.DEBUG_LAB: ((216.0, 220.0), (298.0, 252.0), (386.0, 270.0)),
        },
        "alchemy": {
            "center": (512.0, 322.0),
            "meeting_a": (476.0, 322.0),
            "meeting_b": (548.0, 322.0),
            "idle_left": (420.0, 454.0),
            "idle_right": (604.0, 454.0),
            ZoneType.DEBUG_LAB: ((454.0, 220.0), (580.0, 224.0), (520.0, 274.0)),
            ZoneType.MEMORY_LIBRARY: ((208.0, 360.0), (286.0, 392.0), (378.0, 366.0)),
            ZoneType.CODE_DESK: ((736.0, 346.0), (814.0, 378.0), (646.0, 360.0)),
            ZoneType.REVIEW_STATION: ((734.0, 214.0), (808.0, 246.0), (646.0, 264.0)),
        },
        "workshop": {
            "center": (512.0, 322.0),
            "meeting_a": (476.0, 322.0),
            "meeting_b": (548.0, 322.0),
            "idle_left": (424.0, 450.0),
            "idle_right": (600.0, 450.0),
            ZoneType.CODE_DESK: ((450.0, 214.0), (574.0, 220.0), (514.0, 274.0)),
            ZoneType.MEMORY_LIBRARY: ((208.0, 350.0), (286.0, 386.0), (378.0, 360.0)),
            ZoneType.REVIEW_STATION: ((740.0, 214.0), (816.0, 244.0), (648.0, 266.0)),
            ZoneType.DEBUG_LAB: ((734.0, 360.0), (808.0, 396.0), (648.0, 364.0)),
        },
    }

    themed = themed_positions[theme_key]

    anchors: dict[str, Anchor] = {}
    edges: list[tuple[str, str]] = []

    # Center anchor (hub for pathfinding)
    cx, cy = themed["center"]
    anchors["center"] = Anchor(anchor_id="center", x=cx, y=cy)

    for zone_type in ZoneType:
        (a1x, a1y), (a2x, a2y), (door_x, door_y) = themed[zone_type]
        zone_name = zone_type.value  # e.g. "code_desk"

        a1_id = f"{zone_name}_a"
        a2_id = f"{zone_name}_b"
        anchors[a1_id] = Anchor(
            anchor_id=a1_id, x=a1x, y=a1y,
            zone=zone_type, wander_radius=40.0,
        )
        anchors[a2_id] = Anchor(
            anchor_id=a2_id, x=a2x, y=a2y,
            zone=zone_type, wander_radius=40.0,
        )

        door_id = f"{zone_name}_door"
        anchors[door_id] = Anchor(anchor_id=door_id, x=door_x, y=door_y)

        edges.append((a1_id, door_id))
        edges.append((a2_id, door_id))
        edges.append((door_id, "center"))

    anchors["idle_left"] = Anchor(anchor_id="idle_left", x=themed["idle_left"][0], y=themed["idle_left"][1], wander_radius=32.0)
    anchors["idle_right"] = Anchor(anchor_id="idle_right", x=themed["idle_right"][0], y=themed["idle_right"][1], wander_radius=32.0)
    edges.append(("idle_left", "center"))
    edges.append(("idle_right", "center"))

    # Meeting circle at center
    seat_a_id = "meeting_seat_a"
    seat_b_id = "meeting_seat_b"
    seat_a_x, seat_a_y = themed["meeting_a"]
    seat_b_x, seat_b_y = themed["meeting_b"]
    anchors[seat_a_id] = Anchor(anchor_id=seat_a_id, x=seat_a_x, y=seat_a_y)
    anchors[seat_b_id] = Anchor(anchor_id=seat_b_id, x=seat_b_x, y=seat_b_y)
    edges.append((seat_a_id, "center"))
    edges.append((seat_b_id, "center"))

    meeting = MeetingCircle(
        circle_id=f"{room_id}_circle",
        x=cx, y=cy, radius=44.0,
        seat_a=seat_a_id, seat_b=seat_b_id,
    )

    return RoomLayout(
        room_id=room_id,
        anchors=anchors,
        edges=edges,
        meeting_circle=meeting,
    )


def _build_lobby_layout() -> RoomLayout:
    """Build the lobby layout.

    Wide floor with scattered idle anchors and a central summoning circle.
    Canvas: 1024x576. Usable: x=60..964, y=160..540 (below doors/title).
    """
    anchors: dict[str, Anchor] = {}
    edges: list[tuple[str, str]] = []

    # Central hub
    cx, cy = 512.0, 336.0
    anchors["center"] = Anchor(anchor_id="center", x=cx, y=cy)

    # Scattered idle anchors
    idle_positions = [
        ("idle_1", 248, 246), ("idle_2", 392, 224), ("idle_3", 632, 224),
        ("idle_4", 776, 246), ("idle_5", 308, 390), ("idle_6", 432, 430),
        ("idle_7", 592, 430), ("idle_8", 716, 390), ("idle_9", 512, 196),
        ("idle_10", 512, 458),
    ]
    for aid, ax, ay in idle_positions:
        anchors[aid] = Anchor(anchor_id=aid, x=float(ax), y=float(ay), wander_radius=40.0)
        edges.append((aid, "center"))

    # Connect nearby anchors for smoother paths
    neighbor_pairs = [
        ("idle_1", "idle_2"), ("idle_2", "idle_9"), ("idle_9", "idle_3"),
        ("idle_3", "idle_4"), ("idle_1", "idle_5"), ("idle_5", "idle_6"),
        ("idle_6", "idle_10"), ("idle_10", "idle_7"), ("idle_7", "idle_8"),
        ("idle_4", "idle_8"), ("idle_2", "idle_6"), ("idle_3", "idle_7"),
    ]
    edges.extend(neighbor_pairs)

    # Meeting circle at center (for cross-room fallback if ever needed)
    seat_a_id = "meeting_seat_a"
    seat_b_id = "meeting_seat_b"
    anchors[seat_a_id] = Anchor(anchor_id=seat_a_id, x=476.0, y=336.0)
    anchors[seat_b_id] = Anchor(anchor_id=seat_b_id, x=548.0, y=336.0)
    edges.append((seat_a_id, "center"))
    edges.append((seat_b_id, "center"))

    meeting = MeetingCircle(
        circle_id="lobby_circle",
        x=512.0, y=336.0, radius=52.0,
        seat_a=seat_a_id, seat_b=seat_b_id,
    )

    return RoomLayout(
        room_id="lobby",
        anchors=anchors,
        edges=edges,
        meeting_circle=meeting,
    )


# Cached layouts
_LOBBY_LAYOUT: RoomLayout | None = None
_ROOM_LAYOUTS: dict[str, RoomLayout] = {}


def get_lobby_layout() -> RoomLayout:
    """Return the lobby layout (singleton)."""
    global _LOBBY_LAYOUT
    if _LOBBY_LAYOUT is None:
        _LOBBY_LAYOUT = _build_lobby_layout()
    return _LOBBY_LAYOUT


def get_room_layout(room_id: str) -> RoomLayout:
    """Return a project room layout (cached per room_id)."""
    if room_id not in _ROOM_LAYOUTS:
        _ROOM_LAYOUTS[room_id] = _build_project_room_layout(room_id)
    return _ROOM_LAYOUTS[room_id]


def get_layout(room_id: str) -> RoomLayout:
    """Get layout for any room (lobby or project)."""
    if room_id == "lobby":
        return get_lobby_layout()
    return get_room_layout(room_id)


def get_home_anchors_for_zone(layout: RoomLayout, zone: ZoneType) -> list[str]:
    """Return anchor IDs that belong to a specific zone."""
    return [
        aid for aid, a in layout.anchors.items()
        if a.zone == zone
    ]


def get_idle_anchors(layout: RoomLayout) -> list[str]:
    """Return anchor IDs suitable for idle placement (no zone, not seats/center)."""
    exclude_prefixes = ("meeting_seat_", "center")
    return [
        aid for aid, a in layout.anchors.items()
        if a.zone is None and not aid.startswith(exclude_prefixes) and not aid.endswith("_door")
    ]


def assign_home_anchor(
    layout: RoomLayout,
    zone: ZoneType | None,
    occupied: set[str],
) -> str | None:
    """Pick a free home anchor in the given zone, or any idle anchor if zone is None."""
    if zone is not None:
        candidates = get_home_anchors_for_zone(layout, zone)
    else:
        candidates = get_idle_anchors(layout)

    free = [a for a in candidates if a not in occupied]
    if free:
        return random.choice(free)
    # Fall back to any candidate even if occupied
    if candidates:
        return random.choice(candidates)
    return None


def get_wander_position(anchor: Anchor) -> tuple[float, float]:
    """Get a random position within the anchor's wander radius."""
    angle = random.uniform(0, 2 * 3.14159265)
    dist = random.uniform(0, anchor.wander_radius)
    return (
        anchor.x + dist * __import__("math").cos(angle),
        anchor.y + dist * __import__("math").sin(angle),
    )
