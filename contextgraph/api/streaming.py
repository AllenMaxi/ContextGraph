"""SSE streaming endpoints for AG-UI event streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from starlette.responses import StreamingResponse

from ..events import Event, EventBus, EventType
from ..service import ContextGraphService
from ._compat import Depends, Request
from .dependencies import build_authenticated_agent_dependency

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event type filters per stream endpoint
# ---------------------------------------------------------------------------

_FEED_EVENT_TYPES: frozenset[EventType] = frozenset(
    {
        EventType.FEED_UPDATE,
        EventType.CLAIM_CREATED,
        EventType.CLAIM_REVIEWED,
        EventType.QUORUM_MET,
        EventType.MEMORY_STORED,
        EventType.AGENT_REGISTERED,
    }
)

_CLAIMS_EVENT_TYPES: frozenset[EventType] = frozenset(
    {
        EventType.CLAIM_CREATED,
        EventType.CLAIM_REVIEWED,
        EventType.QUORUM_MET,
    }
)

_NOTIFICATION_EVENT_TYPES: frozenset[EventType] = frozenset(
    {
        EventType.NOTIFICATION,
    }
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _serialize_event(event: Event) -> str:
    """Format a single event as an SSE text frame."""
    payload = json.dumps(event.data, default=str)
    return f"id: {event.event_id}\nevent: {event.event_type}\ndata: {payload}\n\n"


def _heartbeat_frame() -> str:
    payload = json.dumps({"timestamp": _utcnow().isoformat()})
    return f"event: HEARTBEAT\ndata: {payload}\n\n"


async def _event_generator(
    queue: asyncio.Queue[Event],
    event_types: frozenset[EventType],
    agent_id: str,
    heartbeat_seconds: float = 30.0,
    last_event_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames filtered by *event_types* for *agent_id*.

    If *last_event_id* is provided the generator skips until that id is seen
    (useful for reconnection via the ``Last-Event-ID`` header).
    """
    seen_last = last_event_id is None  # if no id requested, start immediately
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                yield _heartbeat_frame()
                continue

            # Skip until we pass the reconnection cursor
            if not seen_last:
                if event.event_id == last_event_id:
                    seen_last = True
                continue

            # Filter by type
            if event.event_type not in event_types:
                continue

            # Filter by agent visibility: events with an agent_id set are
            # private to that agent; empty agent_id means broadcast.
            if event.agent_id and event.agent_id != agent_id:
                continue

            yield _serialize_event(event)
    except asyncio.CancelledError:
        return


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_streaming_routes(
    app: Any,
    event_bus: EventBus,
    graph_service: ContextGraphService,
) -> None:
    """Mount SSE streaming endpoints on *app*."""

    authenticated_agent = build_authenticated_agent_dependency(graph_service)

    def _streaming_response(
        queue: asyncio.Queue[Event],
        event_types: frozenset[EventType],
        agent_id: str,
        heartbeat_seconds: float,
        last_event_id: str | None,
    ) -> StreamingResponse:
        return StreamingResponse(
            _event_generator(
                queue,
                event_types,
                agent_id,
                heartbeat_seconds=heartbeat_seconds,
                last_event_id=last_event_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ---- /v1/stream/feed ------------------------------------------------

    @app.get("/v1/stream/feed")
    async def stream_feed(
        request: Request,
        heartbeat: float = 30.0,
        authenticated: Any = Depends(authenticated_agent),
    ) -> StreamingResponse:
        last_event_id = request.headers.get("Last-Event-ID")
        queue = event_bus.subscribe()
        try:
            return _streaming_response(
                queue,
                _FEED_EVENT_TYPES,
                authenticated.agent_id,
                heartbeat_seconds=heartbeat,
                last_event_id=last_event_id,
            )
        except Exception:
            event_bus.unsubscribe(queue)
            raise

    # ---- /v1/stream/claims ----------------------------------------------

    @app.get("/v1/stream/claims")
    async def stream_claims(
        request: Request,
        heartbeat: float = 30.0,
        authenticated: Any = Depends(authenticated_agent),
    ) -> StreamingResponse:
        last_event_id = request.headers.get("Last-Event-ID")
        queue = event_bus.subscribe()
        try:
            return _streaming_response(
                queue,
                _CLAIMS_EVENT_TYPES,
                authenticated.agent_id,
                heartbeat_seconds=heartbeat,
                last_event_id=last_event_id,
            )
        except Exception:
            event_bus.unsubscribe(queue)
            raise

    # ---- /v1/stream/notifications ---------------------------------------

    @app.get("/v1/stream/notifications")
    async def stream_notifications(
        request: Request,
        heartbeat: float = 30.0,
        authenticated: Any = Depends(authenticated_agent),
    ) -> StreamingResponse:
        last_event_id = request.headers.get("Last-Event-ID")
        queue = event_bus.subscribe()
        try:
            return _streaming_response(
                queue,
                _NOTIFICATION_EVENT_TYPES,
                authenticated.agent_id,
                heartbeat_seconds=heartbeat,
                last_event_id=last_event_id,
            )
        except Exception:
            event_bus.unsubscribe(queue)
            raise
