"""Demo agent runtime — drives scripted agents in the world for visual QA.

Spawns a handful of personas, moves them between rooms + zones, emits
speech bubbles, and triggers meetings. Uses the same EventBus +
WorldGateway path as real agents so the visualization sees nothing
special about them.

Enable with env var CG_ENABLE_WORLD_DEMO=true.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from contextgraph.events import Event, EventBus, EventType

from .models import Accessory, Activity, Expression, GameEvent, GameEventType, GlowColor, ZoneType

if TYPE_CHECKING:
    from .gateway import WorldGateway

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Persona:
    agent_id: str
    name: str
    bubbles: tuple[str, ...]
    favorite_zone: ZoneType


PERSONAS: tuple[Persona, ...] = (
    Persona(
        agent_id="demo_researcher",
        name="Ada",
        bubbles=(
            "Reading the archive...",
            "Found a relevant memory.",
            "Cross-referencing sources.",
            "Adding to the library.",
        ),
        favorite_zone=ZoneType.MEMORY_LIBRARY,
    ),
    Persona(
        agent_id="demo_coder",
        name="Bjarne",
        bubbles=(
            "Compiling...",
            "Refactoring the renderer.",
            "Tests green.",
            "Pushing to main.",
        ),
        favorite_zone=ZoneType.CODE_DESK,
    ),
    Persona(
        agent_id="demo_reviewer",
        name="Grace",
        bubbles=(
            "Reviewing this claim.",
            "Looks good to me.",
            "One nit on line 42.",
            "Approved.",
        ),
        favorite_zone=ZoneType.REVIEW_STATION,
    ),
    Persona(
        agent_id="demo_debugger",
        name="Linus",
        bubbles=(
            "Strange. Reproducing...",
            "Caught the null deref.",
            "Logging the trace.",
            "Fix incoming.",
        ),
        favorite_zone=ZoneType.DEBUG_LAB,
    ),
)

ROOM_POOL: tuple[str, ...] = (
    "lobby",
    "ancient_library",
    "star_observatory",
    "alchemy_atelier",
    "rune_workshop",
)


class DemoAgentRuntime:
    """Scripted agent loop for visual QA of the world."""

    def __init__(self, gateway: WorldGateway, event_bus: EventBus) -> None:
        self._gateway = gateway
        self._event_bus = event_bus
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._tick = 0

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="world-demo-runtime")
        logger.info("DemoAgentRuntime: started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None
            logger.info("DemoAgentRuntime: stopped")

    async def _run(self) -> None:
        try:
            await asyncio.sleep(1.0)
            self._spawn_all()
            while not self._stop.is_set():
                self._tick += 1
                try:
                    await self._drive_tick()
                except Exception:
                    logger.exception("DemoAgentRuntime: tick failed")
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stop.wait(), timeout=4.0)
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # Spawn
    # ------------------------------------------------------------------

    def _spawn_all(self) -> None:
        for p in PERSONAS:
            self._event_bus.publish(
                Event(
                    event_id=f"demo-spawn-{p.agent_id}",
                    event_type=EventType.AGENT_REGISTERED,
                    data={"name": p.name},
                    timestamp=datetime.utcnow(),
                    agent_id=p.agent_id,
                )
            )

    # ------------------------------------------------------------------
    # Per-tick driver
    # ------------------------------------------------------------------

    async def _drive_tick(self) -> None:
        for persona in PERSONAS:
            agent = self._gateway.spatial.get_agent(persona.agent_id)
            if agent is None:
                continue
            if agent.meeting_id is not None:
                continue
            choice = random.random()
            if choice < 0.25:
                await self._speak(persona)
            elif choice < 0.55:
                await self._visit_zone(persona)
            elif choice < 0.80:
                await self._move_room(persona)
            else:
                await self._idle_shuffle(persona)

    async def _speak(self, persona: Persona) -> None:
        bubble = random.choice(persona.bubbles)
        self._gateway.spatial.update_visual(persona.agent_id, bubble=bubble)
        agent = self._gateway.spatial.get_agent(persona.agent_id)
        if agent is None:
            return
        await self._gateway.broadcast_to_room(
            agent.room,
            GameEvent(
                type=GameEventType.AGENT_STATE,
                agent_id=persona.agent_id,
                data=agent.to_dict(),
            ).to_dict(),
        )

    async def _visit_zone(self, persona: Persona) -> None:
        """Emit a bus event matching the persona's role → gateway moves them to zone."""
        agent = self._gateway.spatial.get_agent(persona.agent_id)
        if agent is None or agent.room == "lobby":
            return

        zone = persona.favorite_zone if random.random() < 0.7 else random.choice(list(ZoneType))
        if zone == ZoneType.MEMORY_LIBRARY:
            event_type = EventType.MEMORY_STORED
            data = {"memory_id": f"mem-{self._tick}"}
        elif zone == ZoneType.REVIEW_STATION:
            event_type = EventType.CLAIM_REVIEWED
            data = {
                "reviewer_agent_id": persona.agent_id,
                "source_agent_id": random.choice([p.agent_id for p in PERSONAS if p.agent_id != persona.agent_id]),
                "claim_id": f"claim-{self._tick}",
                "decision": random.choice(["validate", "dispute", "reject"]),
            }
        else:
            # For CODE_DESK / DEBUG_LAB we nudge via direct spatial + broadcast
            self._gateway.spatial.move_agent_to_zone(persona.agent_id, zone)
            self._gateway.spatial.update_visual(
                persona.agent_id,
                expression=Expression.FOCUSED if zone == ZoneType.CODE_DESK else Expression.WORRIED,
                accessory=Accessory.HARD_HAT if zone == ZoneType.CODE_DESK else Accessory.SIREN,
                glow=GlowColor.GREEN if zone == ZoneType.CODE_DESK else GlowColor.RED,
            )
            self._gateway.spatial.update_activity(
                persona.agent_id,
                Activity.CODING if zone == ZoneType.CODE_DESK else Activity.DEBUGGING,
            )
            updated = self._gateway.spatial.get_agent(persona.agent_id)
            if updated is not None:
                await self._gateway.broadcast_to_room(
                    updated.room,
                    GameEvent(
                        type=GameEventType.AGENT_STATE,
                        agent_id=persona.agent_id,
                        data=updated.to_dict(),
                    ).to_dict(),
                )
            return

        self._event_bus.publish(
            Event(
                event_id=f"demo-{event_type.value}-{self._tick}-{persona.agent_id}",
                event_type=event_type,
                data=data,
                timestamp=datetime.utcnow(),
                agent_id=persona.agent_id,
            )
        )

    async def _move_room(self, persona: Persona) -> None:
        """Move the agent directly between rooms (not expressible as a bus event)."""
        agent = self._gateway.spatial.get_agent(persona.agent_id)
        if agent is None:
            return

        target = random.choice([r for r in ROOM_POOL if r != agent.room])
        old_room = agent.room
        self._gateway.spatial.move_agent_to_room(persona.agent_id, target)
        updated = self._gateway.spatial.get_agent(persona.agent_id)
        if updated is None:
            return

        despawn = GameEvent(
            type=GameEventType.AGENT_DESPAWN,
            agent_id=persona.agent_id,
            data={},
        ).to_dict()
        spawn = GameEvent(
            type=GameEventType.AGENT_SPAWN,
            agent_id=persona.agent_id,
            data=updated.to_dict(),
        ).to_dict()
        await self._gateway.broadcast_to_room(old_room, despawn)
        await self._gateway.broadcast_to_room(target, spawn)

    async def _idle_shuffle(self, persona: Persona) -> None:
        """Tiny position nudge within the current anchor — wake the sprite up."""
        agent = self._gateway.spatial.get_agent(persona.agent_id)
        if agent is None:
            return
        self._gateway.spatial.update_visual(
            persona.agent_id,
            expression=random.choice([Expression.HAPPY, Expression.THINKING, Expression.SOCIAL]),
        )
        updated = self._gateway.spatial.get_agent(persona.agent_id)
        if updated is None:
            return
        await self._gateway.broadcast_to_room(
            updated.room,
            GameEvent(
                type=GameEventType.AGENT_STATE,
                agent_id=persona.agent_id,
                data=updated.to_dict(),
            ).to_dict(),
        )
