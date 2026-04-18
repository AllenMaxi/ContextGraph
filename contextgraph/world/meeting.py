"""Meeting orchestrator — manages the lifecycle of two-agent meetings."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

from .models import (
    Activity,
    Facing,
    GameEvent,
    GameEventType,
    Meeting,
    MeetingPhase,
    MeetingTrigger,
)
from .rooms import get_layout

if TYPE_CHECKING:
    from .spatial import SpatialState

logger = logging.getLogger(__name__)

# Meeting phase durations in seconds
PHASE_DURATIONS = {
    MeetingPhase.GATHERING: 2.0,  # time for agents to walk to seats
    MeetingPhase.FACING: 0.3,
    MeetingPhase.BUBBLE_A: 1.8,
    MeetingPhase.BUBBLE_B: 1.8,
    MeetingPhase.ORB_EXCHANGE: 0.9,
    MeetingPhase.LINGERING: 0.7,
    MeetingPhase.DISPERSING: 0.0,  # instant — agents start walking back
}

PHASE_ORDER = [
    MeetingPhase.GATHERING,
    MeetingPhase.FACING,
    MeetingPhase.BUBBLE_A,
    MeetingPhase.BUBBLE_B,
    MeetingPhase.ORB_EXCHANGE,
    MeetingPhase.LINGERING,
    MeetingPhase.DISPERSING,
]


class MeetingOrchestrator:
    """Manages the lifecycle of meetings in the world."""

    def __init__(self, spatial: SpatialState) -> None:
        self.spatial = spatial
        self._active_tasks: dict[str, asyncio.Task] = {}
        # Callback for broadcasting — set by gateway
        self._broadcast_fn = None

    def set_broadcast(self, fn) -> None:
        """Set the async broadcast function: fn(room, message_dict)."""
        self._broadcast_fn = fn

    async def _broadcast(self, room: str, message: dict) -> None:
        if self._broadcast_fn:
            await self._broadcast_fn(room, message)

    # ------------------------------------------------------------------
    # Meeting triggers
    # ------------------------------------------------------------------

    async def try_claim_review_meeting(
        self,
        reviewer_id: str,
        source_id: str,
        claim_id: str,
        decision: str,
    ) -> bool:
        """Attempt to start a meeting for a claim review.

        Only starts if both agents are in the same room and the circle is free.
        """
        reviewer = self.spatial.get_agent(reviewer_id)
        source = self.spatial.get_agent(source_id)

        if reviewer is None or source is None:
            return False
        if reviewer.room != source.room:
            return False
        if reviewer.room == "lobby":
            return False
        if self.spatial.is_agent_in_meeting(reviewer_id) or self.spatial.is_agent_in_meeting(source_id):
            return False
        if self.spatial.is_circle_occupied(reviewer.room):
            return False

        bubble_a = f"Reviewing claim: {decision}"
        bubble_b = f"Claim {claim_id[:8]}... reviewed"

        return await self._start_meeting(
            room_id=reviewer.room,
            trigger=MeetingTrigger.CLAIM_REVIEW,
            agent_a=reviewer_id,
            agent_b=source_id,
            bubble_a=bubble_a,
            bubble_b=bubble_b,
        )

    async def try_blocker_assist_meeting(
        self,
        blocked_agent_id: str,
    ) -> bool:
        """Attempt to start a blocker-assist meeting.

        Finds the nearest active same-room helper.
        """
        blocked = self.spatial.get_agent(blocked_agent_id)
        if blocked is None:
            return False
        if blocked.room == "lobby":
            return False
        if self.spatial.is_agent_in_meeting(blocked_agent_id):
            return False
        if self.spatial.is_circle_occupied(blocked.room):
            return False

        # Find nearest helper in same room
        candidates = [
            a
            for a in self.spatial.get_agents_in_room(blocked.room)
            if a.agent_id != blocked_agent_id and a.meeting_id is None and a.activity != Activity.MEETING
        ]
        if not candidates:
            return False

        # Pick nearest by distance
        def dist(a):
            return ((a.x - blocked.x) ** 2 + (a.y - blocked.y) ** 2) ** 0.5

        helper = min(candidates, key=dist)

        return await self._start_meeting(
            room_id=blocked.room,
            trigger=MeetingTrigger.BLOCKER_ASSIST,
            agent_a=blocked_agent_id,
            agent_b=helper.agent_id,
            bubble_a="I'm stuck, need help!",
            bubble_b="Let me take a look...",
        )

    # ------------------------------------------------------------------
    # Core lifecycle
    # ------------------------------------------------------------------

    async def _start_meeting(
        self,
        room_id: str,
        trigger: MeetingTrigger,
        agent_a: str,
        agent_b: str,
        bubble_a: str,
        bubble_b: str,
    ) -> bool:
        meeting_id = f"mtg_{uuid.uuid4().hex[:12]}"

        layout = get_layout(room_id)
        circle = layout.meeting_circle
        if circle is None:
            return False

        meeting = Meeting(
            meeting_id=meeting_id,
            room_id=room_id,
            circle_id=circle.circle_id,
            trigger=trigger,
            agent_a=agent_a,
            agent_b=agent_b,
            phase=MeetingPhase.GATHERING,
            bubble_a=bubble_a,
            bubble_b=bubble_b,
        )

        if not self.spatial.create_meeting(meeting):
            return False

        # Move agents to seat anchors
        self.spatial.move_agent_to_anchor(agent_a, circle.seat_a)
        self.spatial.move_agent_to_anchor(agent_b, circle.seat_b)

        # Broadcast meeting_started
        await self._broadcast(
            room_id,
            GameEvent(
                type=GameEventType.MEETING_STARTED,
                agent_id=agent_a,
                data=meeting.to_dict(),
            ).to_dict(),
        )

        # Broadcast agent paths to seats
        for aid, seat_id in [(agent_a, circle.seat_a), (agent_b, circle.seat_b)]:
            agent = self.spatial.get_agent(aid)
            if agent:
                await self._broadcast(
                    room_id,
                    GameEvent(
                        type=GameEventType.AGENT_PATH,
                        agent_id=aid,
                        data={
                            "from_anchor_id": agent.home_anchor_id,
                            "to_anchor_id": seat_id,
                            "room_id": room_id,
                            "speed": 1.0,
                        },
                    ).to_dict(),
                )

        # Run lifecycle in background
        task = asyncio.create_task(self._run_lifecycle(meeting))
        self._active_tasks[meeting_id] = task
        return True

    async def _run_lifecycle(self, meeting: Meeting) -> None:
        """Run through meeting phases with timed delays."""
        try:
            for phase in PHASE_ORDER:
                meeting.phase = phase
                self.spatial.update_meeting_phase(meeting.meeting_id, phase)

                # Broadcast phase update
                await self._broadcast(
                    meeting.room_id,
                    GameEvent(
                        type=GameEventType.MEETING_UPDATED,
                        agent_id=meeting.agent_a,
                        data=meeting.to_dict(),
                    ).to_dict(),
                )

                # Apply phase-specific effects
                if phase == MeetingPhase.FACING:
                    self.spatial.update_facing(meeting.agent_a, Facing.RIGHT)
                    self.spatial.update_facing(meeting.agent_b, Facing.LEFT)
                elif phase == MeetingPhase.BUBBLE_A:
                    self.spatial.update_visual(meeting.agent_a, bubble=meeting.bubble_a)
                    await self._broadcast_agent_state(meeting.agent_a, meeting.room_id)
                elif phase == MeetingPhase.BUBBLE_B:
                    self.spatial.update_visual(meeting.agent_b, bubble=meeting.bubble_b)
                    await self._broadcast_agent_state(meeting.agent_b, meeting.room_id)

                duration = PHASE_DURATIONS.get(phase, 0)
                if duration > 0:
                    await asyncio.sleep(duration)

            # End the meeting
            ended = self.spatial.end_meeting(meeting.meeting_id)
            if ended:
                await self._broadcast(
                    meeting.room_id,
                    GameEvent(
                        type=GameEventType.MEETING_ENDED,
                        agent_id=meeting.agent_a,
                        data=ended.to_dict(),
                    ).to_dict(),
                )

                # Broadcast agents returning to home anchors
                for aid in (meeting.agent_a, meeting.agent_b):
                    agent = self.spatial.get_agent(aid)
                    if agent and agent.home_anchor_id:
                        await self._broadcast(
                            meeting.room_id,
                            GameEvent(
                                type=GameEventType.AGENT_PATH,
                                agent_id=aid,
                                data={
                                    "from_anchor_id": agent.anchor_id,
                                    "to_anchor_id": agent.home_anchor_id,
                                    "room_id": meeting.room_id,
                                    "speed": 1.0,
                                },
                            ).to_dict(),
                        )
                        await self._broadcast_agent_state(aid, meeting.room_id)

        except asyncio.CancelledError:
            # Clean up on cancellation
            self.spatial.end_meeting(meeting.meeting_id)
        except Exception:
            logger.exception("Meeting lifecycle error: %s", meeting.meeting_id)
            self.spatial.end_meeting(meeting.meeting_id)
        finally:
            self._active_tasks.pop(meeting.meeting_id, None)

    async def _broadcast_agent_state(self, agent_id: str, room_id: str) -> None:
        agent = self.spatial.get_agent(agent_id)
        if agent:
            await self._broadcast(
                room_id,
                GameEvent(
                    type=GameEventType.AGENT_STATE,
                    agent_id=agent_id,
                    data=agent.to_dict(),
                ).to_dict(),
            )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def cancel_all(self) -> None:
        """Cancel all active meeting lifecycles."""
        for task in self._active_tasks.values():
            task.cancel()
        self._active_tasks.clear()
