from __future__ import annotations

from typing import Any

from .api._compat import JSONResponse, Request
from .errors import AuthenticationError
from .mcp_server import TOOLS, _dispatch_tool
from .service import ContextGraphService

MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {
    "name": "contextgraph",
    "version": "0.2.1",
}


def register_remote_mcp_routes(app: Any, graph: ContextGraphService, *, path: str = "/mcp") -> None:
    @app.api_route(path, methods=["GET", "POST"])
    async def remote_mcp(request: Request) -> Any:
        if request.method == "GET":
            return JSONResponse(_server_overview(request, path))

        payload = await request.json()
        if isinstance(payload, list):
            return JSONResponse(
                status_code=400,
                content={"detail": "Batch JSON-RPC requests are not supported by this server."},
            )

        response, status_code = _handle_jsonrpc_request(graph, request, payload)
        if response is None:
            return JSONResponse(status_code=202, content={})
        return JSONResponse(status_code=status_code, content=response)

    @app.get("/.well-known/mcp/server-card.json")
    async def server_card(request: Request) -> Any:
        return JSONResponse(_server_card(request, path))


def _server_overview(request: Request, path: str) -> dict[str, Any]:
    return {
        "name": SERVER_INFO["name"],
        "version": SERVER_INFO["version"],
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "transport": "streamable-http",
        "endpoint": str(request.base_url).rstrip("/") + path,
        "auth": {
            "headers": ["Authorization: Bearer <agent_api_key>", "X-Agent-Key: <agent_api_key>"],
            "requiredFor": ["tools/call"],
        },
        "capabilities": {"tools": {"listChanged": False}},
        "tools": [tool["name"] for tool in TOOLS],
    }


def _server_card(request: Request, path: str) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    return {
        "name": "ContextGraph",
        "description": "Shared memory bus for MCP-compatible agents with permissions, provenance, and optional payments.",
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "version": SERVER_INFO["version"],
        "remotes": [
            {
                "type": "streamable-http",
                "url": f"{base_url}{path}",
            }
        ],
        "auth": {
            "type": "api-key",
            "headers": ["Authorization", "X-Agent-Key"],
        },
        "capabilities": {"tools": {"listChanged": False}},
        "tools": TOOLS,
    }


def _jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _extract_api_key(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token
    header_key = request.headers.get("x-agent-key", "").strip()
    return header_key or None


def _authenticated_agent_id(graph: ContextGraphService, request: Request) -> str | None:
    api_key = _extract_api_key(request)
    if not api_key:
        return None
    agent = graph.authenticate_agent(api_key)
    return agent.agent_id


def _handle_jsonrpc_request(
    graph: ContextGraphService,
    request: Request,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, int]:
    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params", {}) or {}

    if method == "initialize":
        return (
            _jsonrpc_result(
                request_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "serverInfo": SERVER_INFO,
                    "capabilities": {"tools": {"listChanged": False}},
                },
            ),
            200,
        )
    if method in {"initialized", "notifications/initialized"}:
        return (None if request_id is None else _jsonrpc_result(request_id, {}), 202 if request_id is None else 200)
    if method == "ping":
        return (_jsonrpc_result(request_id, {}), 200)
    if method == "tools/list":
        return (_jsonrpc_result(request_id, {"tools": TOOLS}), 200)
    if method == "resources/list":
        return (_jsonrpc_result(request_id, {"resources": []}), 200)
    if method == "prompts/list":
        return (_jsonrpc_result(request_id, {"prompts": []}), 200)
    if method == "tools/call":
        try:
            agent_id = _authenticated_agent_id(graph, request)
        except AuthenticationError as exc:
            return (_jsonrpc_error(request_id, -32001, str(exc)), 401)
        if not agent_id:
            return (_jsonrpc_error(request_id, -32001, "Authentication required for tools/call."), 401)
        name = params.get("name", "")
        arguments = params.get("arguments", {}) or {}
        try:
            result = _dispatch_tool(graph, agent_id, name, arguments)
        except Exception as exc:
            return (
                _jsonrpc_result(request_id, {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True}),
                200,
            )
        return (
            _jsonrpc_result(
                request_id,
                {
                    "content": [{"type": "text", "text": _to_json_text(result)}],
                    "isError": False,
                },
            ),
            200,
        )
    if request_id is None:
        return (None, 202)
    return (_jsonrpc_error(request_id, -32601, f"Method not found: {method}"), 404)


def _to_json_text(value: Any) -> str:
    import json

    return json.dumps(value, indent=2, default=str)
