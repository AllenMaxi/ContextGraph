"""Route registration for ContextGraph World visualization."""
import asyncio
import json
import logging
import os
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

    # FastAPI lifespan is set in web.py, so @app.on_event("startup") is ignored.
    # Start background tasks lazily the first time anything touches the world.
    _bg_started = {"value": False}

    def _ensure_background_started() -> None:
        if _bg_started["value"]:
            return
        _bg_started["value"] = True
        asyncio.create_task(_event_loop())
        if os.environ.get("CG_ENABLE_WORLD_DEMO", "").lower() in ("1", "true", "yes"):
            from .demo_runtime import DemoAgentRuntime
            runtime = DemoAgentRuntime(gateway=gateway, event_bus=event_bus)
            runtime.start()
            app.state.world_demo_runtime = runtime
            logger.info("World: demo runtime enabled")
        logger.info("World: background tasks started")

    # Static files
    if _STATIC_DIR.exists():
        app.mount("/world/static", StaticFiles(directory=str(_STATIC_DIR)), name="world_static")

    @app.get("/world")
    async def world_index() -> Any:
        index = _STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index), media_type="text/html")
        return HTMLResponse("<h1>ContextGraph World</h1><p>Static files not found.</p>")

    @app.post("/v1/world/activity")
    async def world_activity(payload: dict) -> dict:
        """Push real-time agent activity into the world.

        Payload shape:
          {
            "actor": "claude" | "<agent_id>",
            "name":  "Claude" (optional, first use),
            "action": "read" | "edit" | "write" | "bash" | "search" | "spawn" | "think" | "speak" | "review",
            "room":   "ancient_library" | "star_observatory" | ... (optional),
            "bubble": "...free text..." (optional),
            "detail": {...} (optional)
          }
        """
        from .activity_bridge import apply_activity
        _ensure_background_started()
        try:
            result = apply_activity(gateway, event_bus, payload or {})
            return {"ok": True, **result}
        except Exception as exc:
            logger.exception("World: activity bridge failed")
            return {"ok": False, "error": str(exc)}

    @app.post("/v1/world/identity")
    async def world_identity(payload: dict) -> dict:
        from .identity_bridge import register_identity
        from .models import AgentArchetype
        _ensure_background_started()
        try:
            actor = str(payload.get("actor", "")).strip()
            name = str(payload.get("name") or actor).strip()
            raw_arch = str(payload.get("archetype", "unknown")).strip().lower()
            try:
                archetype = AgentArchetype(raw_arch)
            except ValueError:
                archetype = AgentArchetype.UNKNOWN
            tools_count = int(payload.get("tools_count", 0) or 0)
            skills_count = int(payload.get("skills_count", 0) or 0)
            return register_identity(
                gateway, actor_id=actor, name=name, archetype=archetype,
                tools_count=tools_count, skills_count=skills_count,
            )
        except Exception as exc:
            logger.exception("World: /identity failed")
            return {"ok": False, "error": str(exc)}

    @app.post("/v1/world/identity/upgrade")
    async def world_identity_upgrade(payload: dict) -> dict:
        from .identity_bridge import upgrade_identity
        _ensure_background_started()
        try:
            actor = str(payload.get("actor", "")).strip()
            tools_count = int(payload.get("tools_count", 0) or 0)
            skills_count = int(payload.get("skills_count", 0) or 0)
            return upgrade_identity(
                gateway, actor_id=actor,
                tools_count=tools_count, skills_count=skills_count,
            )
        except Exception as exc:
            logger.exception("World: /identity/upgrade failed")
            return {"ok": False, "error": str(exc)}

    @app.post("/v1/world/spawn")
    async def world_spawn(payload: dict) -> dict:
        from .identity_bridge import spawn_subagent
        _ensure_background_started()
        try:
            parent = str(payload.get("parent", "")).strip()
            subagent_type = str(payload.get("subagent_type", "")).strip()
            description = str(payload.get("description") or "").strip()
            invocation_id = str(payload.get("invocation_id", "")).strip()
            if not invocation_id:
                import uuid
                invocation_id = uuid.uuid4().hex[:8]
            return spawn_subagent(
                gateway,
                parent_actor_id=parent,
                subagent_type=subagent_type,
                description=description,
                invocation_id=invocation_id,
            )
        except Exception as exc:
            logger.exception("World: /spawn failed")
            return {"ok": False, "error": str(exc)}

    @app.post("/v1/world/despawn")
    async def world_despawn(payload: dict) -> dict:
        from .identity_bridge import despawn_subagent
        _ensure_background_started()
        try:
            actor = str(payload.get("actor", "")).strip()
            summary = str(payload.get("result_summary") or "").strip()
            return despawn_subagent(
                gateway, actor_id=actor, result_summary=summary,
            )
        except Exception as exc:
            logger.exception("World: /despawn failed")
            return {"ok": False, "error": str(exc)}

    @app.post("/v1/world/message")
    async def world_message(payload: dict) -> dict:
        from .message_bridge import set_bubble
        _ensure_background_started()
        try:
            actor = str(payload.get("actor", "")).strip()
            role = str(payload.get("role", "")).strip().lower()
            text = str(payload.get("text") or "")
            return set_bubble(gateway, actor_id=actor, role=role, text=text)
        except Exception as exc:
            logger.exception("World: /message failed")
            return {"ok": False, "error": str(exc)}

    @app.websocket("/ws/world")
    async def world_websocket(websocket: WebSocket):
        await websocket.accept()
        _ensure_background_started()

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
                    logger.info("World: join_room → %s", room)
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
