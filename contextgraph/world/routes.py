"""Route registration for ContextGraph World visualization."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from contextgraph.events import EventBus
from contextgraph.service import ContextGraphService

from .gateway import WorldGateway

from starlette.responses import FileResponse, HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


def register_world_routes(app, event_bus: EventBus, graph_service: ContextGraphService) -> None:
    """Mount all World visualization routes onto *app*."""

    gateway = WorldGateway(max_viewers=_get_max_viewers(graph_service))

    # Seed spatial state with existing agents
    try:
        agents = graph_service.repository.list_agents()
        gateway.seed_agents(agents)
        logger.info("World: seeded %d agents", len(agents))
    except Exception:
        logger.warning("World: failed to seed agents from repository", exc_info=True)

    # Background task: subscribe to EventBus and process events
    async def _event_loop() -> None:
        queue = event_bus.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=5.0)
                    await gateway.process_event(event)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    logger.exception("World: error processing event")
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(queue)

    @app.on_event("startup")
    async def _start_event_loop() -> None:
        asyncio.create_task(_event_loop())

    # Static files (may not exist yet — created by frontend tasks)
    if _STATIC_DIR.exists():
        app.mount("/world/static", StaticFiles(directory=str(_STATIC_DIR)), name="world_static")
    else:
        logger.info("World: static dir not found at %s — skipping static mount", _STATIC_DIR)

    # Serve index.html at GET /world
    @app.get("/world")
    async def world_index():
        index = _STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return HTMLResponse(
            "<html><body><h1>ContextGraph World</h1>"
            "<p>Frontend not built yet. Static assets missing.</p></body></html>",
            status_code=200,
        )

    # WebSocket endpoint
    @app.websocket("/ws/world")
    async def world_websocket(websocket: WebSocket):
        # Optionally validate API key from ?key= query param
        api_key = websocket.query_params.get("key")
        if api_key is not None:
            expected = getattr(graph_service.settings, "admin_key", "")
            if expected and api_key != expected:
                await websocket.close(code=4001)
                return

        await websocket.accept()

        viewer = await gateway.add_viewer(websocket)
        if viewer is None:
            await websocket.close(code=4008)  # capacity exceeded
            return

        # Send initial world snapshot
        try:
            await websocket.send_text(json.dumps(gateway.get_world_snapshot()))
        except Exception:
            await gateway.remove_viewer(viewer)
            return

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                action = msg.get("action")

                if action == "join_room":
                    room = msg.get("room")
                    await gateway.set_viewer_room(viewer, room)
                    if room:
                        await websocket.send_text(json.dumps(gateway.get_room_snapshot(room)))

                elif action == "leave_room":
                    await gateway.set_viewer_room(viewer, None)
                    await websocket.send_text(json.dumps(gateway.get_world_snapshot()))

                elif action == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("World: WebSocket error")
        finally:
            await gateway.remove_viewer(viewer)


def _get_max_viewers(graph_service: ContextGraphService) -> int:
    try:
        return graph_service.settings.world_max_viewers
    except AttributeError:
        return 50
