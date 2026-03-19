"""In-process event bus for real-time streaming."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)


class EventType(StrEnum):
    CLAIM_CREATED = "CLAIM_CREATED"
    CLAIM_REVIEWED = "CLAIM_REVIEWED"
    QUORUM_MET = "QUORUM_MET"
    MEMORY_STORED = "MEMORY_STORED"
    FEED_UPDATE = "FEED_UPDATE"
    NOTIFICATION = "NOTIFICATION"
    AGENT_REGISTERED = "AGENT_REGISTERED"
    HEARTBEAT = "HEARTBEAT"


@dataclass(slots=True)
class Event:
    event_id: str
    event_type: EventType
    data: dict[str, Any]
    timestamp: datetime
    agent_id: str = ""
    org_id: str = ""


class EventBus:
    """Thread-safe event bus with async subscriber support."""

    def __init__(self, max_history: int = 1000) -> None:
        self._lock = RLock()
        self._history: deque[Event] = deque(maxlen=max_history)
        self._async_queues: list[asyncio.Queue[Event]] = []
        self._event_counter = 0

    def publish(self, event: Event) -> None:
        with self._lock:
            self._event_counter += 1
            self._history.append(event)
            # Fan out to async subscribers
            dead_queues: list[asyncio.Queue[Event]] = []
            for queue in self._async_queues:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    dead_queues.append(queue)
            for dq in dead_queues:
                self._async_queues.remove(dq)

    def subscribe(self) -> asyncio.Queue[Event]:
        with self._lock:
            queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)
            self._async_queues.append(queue)
            return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        with self._lock:
            if queue in self._async_queues:
                self._async_queues.remove(queue)

    def recent(self, limit: int = 50) -> list[Event]:
        with self._lock:
            items = list(self._history)
            return items[-limit:]

    @property
    def total_events(self) -> int:
        return self._event_counter
