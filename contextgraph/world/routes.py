"""Route registration for ContextGraph World visualization."""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from contextgraph.events import EventBus
from contextgraph.service import ContextGraphService

from .gateway import WorldGateway

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


def register_world_routes(app: Any, event_bus: EventBus, graph_service: ContextGraphService) -> None:
    """Mount all World visualization routes onto *app*."""
    from starlette.responses import FileResponse, HTMLResponse
    from starlette.staticfiles import StaticFiles
    from starlette.websockets import WebSocket, WebSocketDisconnect

    gateway = WorldGateway(event_bus=event_bus, graph_service=graph_service)

    # Seed spatial state with existing agents
    try:
        agents = graph_service.repository.list_agents()
        for agent in agents:
            gateway.spatial.register_agent(agent.agent_id, agent.name)
        logger.info("World: seeded %d agents", len(agents))
    except Exception:
        logger.warning("World: could not seed agents from repository")

    # Background task: subscribe to EventBus and forward to gateway
    async def _event_loop() -> None:
        queue = event_bus.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=5.0)
                    await gateway.process_bus_event(event)
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

    # Static files
    if _STATIC_DIR.exists():
        app.mount("/world/static", StaticFiles(directory=str(_STATIC_DIR)), name="world_static")

    @app.get("/world")
    async def world_index() -> Any:
        index = _STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index), media_type="text/html")
        return HTMLResponse("<h1>ContextGraph World</h1><p>Static files not found.</p>")

    @app.websocket("/ws/world")
    async def world_websocket(websocket: WebSocket):
        await websocket.accept()

        # Optional API key validation
        api_key = websocket.query_params.get("key", "")
        if api_key:
            try:
                graph_service.authenticate_agent(api_key)
            except Exception:
                await websocket.close(code=4003, reason="Invalid API key")
                return

        room = "lobby"
        await gateway.add_viewer(websocket, room=room)

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "join_room":
                    room = msg.get("room", "lobby")
                    gateway.switch_viewer_room(websocket, room)
                    snapshot = gateway._build_snapshot(room)
                    await websocket.send_text(json.dumps(snapshot))

                elif msg_type == "leave_room":
                    room = "lobby"
                    gateway.switch_viewer_room(websocket, "lobby")
                    snapshot = gateway._build_snapshot("lobby")
                    await websocket.send_text(json.dumps(snapshot))

                elif msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

        except WebSocketDisconnect:
            gateway.remove_viewer(websocket)
        except Exception:
            gateway.remove_viewer(websocket)
