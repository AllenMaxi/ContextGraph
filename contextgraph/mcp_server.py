"""ContextGraph MCP Server.

Exposes ContextGraph as MCP (Model Context Protocol) tools so that
Claude, GPT, and other MCP-aware agents can store, recall, relate,
watch, and review knowledge-graph memories over stdio JSON-RPC.

Usage:
    python -m contextgraph.mcp_server

Environment variables:
    CG_AGENT_ID    – agent identity for all tool calls (required)
    CG_AGENT_NAME  – display name when auto-registering (default: "mcp-agent")
    CG_AGENT_ORG   – org id when auto-registering   (default: "default")
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime
from typing import Any

from .bootstrap import create_service
from .errors import ContextGraphError, NotFoundError
from .service import ContextGraphService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (MCP tools/list schema)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "contextgraph_store",
        "description": (
            "Store a memory in the ContextGraph knowledge graph. "
            "The content is parsed into claims, entities, and relations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The natural-language content to store as a memory.",
                },
                "visibility": {
                    "type": "string",
                    "enum": ["private", "org", "shared", "published"],
                    "description": "Visibility level for the stored claims.",
                    "default": "private",
                },
                "license": {
                    "type": "string",
                    "description": "License identifier for the stored data.",
                    "default": "internal",
                },
                "metadata": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Arbitrary key/value metadata attached to the memory.",
                    "default": {},
                },
                "access_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of agent IDs allowed to access the memory (for shared visibility).",
                    "default": [],
                },
                "price": {
                    "type": "number",
                    "description": "Price in credits for cross-org access.",
                    "default": 0.0,
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "contextgraph_recall",
        "description": (
            "Recall memories from the ContextGraph by semantic query. "
            "Returns matching claims with confidence scores and related entities."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query string to search for relevant claims.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "contextgraph_relate",
        "description": (
            "Find relation paths between two entities in the knowledge graph. "
            "Returns chains of claims that connect entity_a to entity_b."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_a": {
                    "type": "string",
                    "description": "Name of the first entity.",
                },
                "entity_b": {
                    "type": "string",
                    "description": "Name of the second entity.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum path depth to search.",
                    "default": 2,
                },
            },
            "required": ["entity_a", "entity_b"],
        },
    },
    {
        "name": "contextgraph_watch",
        "description": (
            "Create a standing query (subscription) that triggers notifications when new claims match the query."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query pattern to watch for.",
                },
                "name": {
                    "type": "string",
                    "description": "Human-readable name for this subscription.",
                },
                "delivery_mode": {
                    "type": "string",
                    "enum": ["pull", "websocket", "webhook", "a2a"],
                    "description": "How notifications should be delivered.",
                    "default": "pull",
                },
                "filters": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Optional filters (e.g. webhook_url for webhook delivery).",
                    "default": {},
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "contextgraph_notifications",
        "description": (
            "Get pending notifications for the current agent. Returns undelivered notifications from standing queries."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "contextgraph_review",
        "description": (
            "Review (attest or challenge) a claim in the knowledge graph. "
            "Attesting increases trust; challenging flags it for removal."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "ID of the claim to review.",
                },
                "decision": {
                    "type": "string",
                    "enum": ["attested", "challenged"],
                    "description": "Review decision: attest or challenge the claim.",
                },
                "reason": {
                    "type": "string",
                    "description": "Free-text reason for the review decision.",
                    "default": "",
                },
            },
            "required": ["claim_id", "decision"],
        },
    },
]


# ---------------------------------------------------------------------------
# Dataclass serialization helper
# ---------------------------------------------------------------------------


def _serialize(obj: Any) -> Any:
    """Recursively convert dataclass trees to JSON-safe dicts."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def _dispatch_tool(
    service: ContextGraphService,
    agent_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Execute a tool call and return a JSON-serializable result."""

    if tool_name == "contextgraph_store":
        result = service.store_memory(
            agent_id=agent_id,
            content=arguments["content"],
            visibility=arguments.get("visibility", "private"),
            license=arguments.get("license", "internal"),
            metadata=arguments.get("metadata"),
            access_list=arguments.get("access_list"),
            price=arguments.get("price", 0.0),
        )
        return {
            "memory_id": result.memory.memory_id,
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "statement": c.statement,
                    "confidence": c.confidence,
                }
                for c in result.claims
            ],
            "entities": [{"entity_id": e.entity_id, "name": e.name, "type": e.entity_type} for e in result.entities],
            "review_tasks": [
                {"task_id": rt.task_id, "claim_id": rt.claim_id, "reason": rt.reason} for rt in result.review_tasks
            ],
        }

    if tool_name == "contextgraph_recall":
        hits = service.recall(
            agent_id=agent_id,
            query=arguments["query"],
            limit=arguments.get("limit", 10),
        )
        return [
            {
                "claim_id": h.claim.claim_id,
                "statement": h.claim.statement,
                "confidence": h.claim.confidence,
                "score": h.score,
                "validation_status": h.claim.validation_status,
                "entities": [{"entity_id": e.entity_id, "name": e.name, "type": e.entity_type} for e in h.entities],
            }
            for h in hits
        ]

    if tool_name == "contextgraph_relate":
        paths = service.relate(
            agent_id=agent_id,
            entity_a=arguments["entity_a"],
            entity_b=arguments["entity_b"],
            max_depth=arguments.get("max_depth", 2),
        )
        return [_serialize(p) for p in paths]

    if tool_name == "contextgraph_watch":
        sq = service.watch(
            agent_id=agent_id,
            query=arguments["query"],
            name=arguments.get("name"),
            delivery_mode=arguments.get("delivery_mode", "pull"),
            filters=arguments.get("filters"),
        )
        return _serialize(sq)

    if tool_name == "contextgraph_notifications":
        notifications = service.get_notifications(
            agent_id=agent_id,
            mark_delivered=True,
        )
        return [_serialize(n) for n in notifications]

    if tool_name == "contextgraph_review":
        claim = service.review_claim(
            reviewer_agent_id=agent_id,
            claim_id=arguments["claim_id"],
            decision=arguments["decision"],
            reason=arguments.get("reason", ""),
        )
        return _serialize(claim)

    raise ValueError(f"Unknown tool: {tool_name}")


# ---------------------------------------------------------------------------
# Ensure agent exists (auto-register if needed)
# ---------------------------------------------------------------------------


def _ensure_agent(service: ContextGraphService, agent_id: str) -> str:
    """Return *agent_id*, creating the agent if it doesn't already exist."""
    try:
        service.get_agent(agent_id)
        return agent_id
    except (NotFoundError, KeyError):
        agent_name = os.environ.get("CG_AGENT_NAME", "mcp-agent")
        org_id = os.environ.get("CG_AGENT_ORG", "default")
        agent = service.register_agent(name=agent_name, org_id=org_id)
        return agent.agent_id


# ---------------------------------------------------------------------------
# MCP SDK server (preferred when the `mcp` package is available)
# ---------------------------------------------------------------------------


def _try_run_mcp_sdk(service: ContextGraphService, agent_id: str) -> bool:
    """Attempt to start the server via the ``mcp`` PyPI package.

    Returns True if the server ran (and exited), False if the package
    is not importable so the caller should fall back.
    """
    try:
        import mcp.types as mcp_types  # type: ignore[import-untyped]
        from mcp.server import Server  # type: ignore[import-untyped]
        from mcp.server.stdio import stdio_server  # type: ignore[import-untyped]
    except ImportError:
        return False

    import asyncio

    server = Server("contextgraph")

    @server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOLS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[mcp_types.TextContent]:
        try:
            result = _dispatch_tool(service, agent_id, name, arguments or {})
            text = json.dumps(result, indent=2, default=str)
            return [mcp_types.TextContent(type="text", text=text)]
        except ContextGraphError as exc:
            return [mcp_types.TextContent(type="text", text=f"Error: {exc}")]
        except Exception as exc:
            logger.exception("Tool call failed: %s", name)
            return [mcp_types.TextContent(type="text", text=f"Internal error: {exc}")]

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream)

    asyncio.run(_run())
    return True


# ---------------------------------------------------------------------------
# Fallback: standalone JSON-RPC 2.0 stdio server (no dependencies)
# ---------------------------------------------------------------------------


class _JsonRpcServer:
    """Minimal JSON-RPC 2.0 server over stdin/stdout implementing the
    MCP ``initialize``, ``tools/list``, and ``tools/call`` methods."""

    SERVER_INFO = {
        "name": "contextgraph",
        "version": "0.1.0",
    }
    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, service: ContextGraphService, agent_id: str) -> None:
        self._service = service
        self._agent_id = agent_id

    # -- public entry point --------------------------------------------------

    def run(self) -> None:
        """Read JSON-RPC messages from stdin, write responses to stdout."""
        logger.info("Starting ContextGraph MCP JSON-RPC server (stdio fallback)")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._write_error(None, -32700, "Parse error")
                continue
            self._handle(request)

    # -- routing -------------------------------------------------------------

    def _handle(self, request: dict[str, Any]) -> None:
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        handler = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "ping": self._handle_ping,
        }.get(method)

        if handler is None:
            # Notifications (no id) are silently ignored per JSON-RPC spec
            if req_id is not None:
                self._write_error(req_id, -32601, f"Method not found: {method}")
            return

        try:
            result = handler(params)
            if req_id is not None:
                self._write_result(req_id, result)
        except ContextGraphError as exc:
            self._write_error(req_id, -32000, str(exc))
        except Exception as exc:
            logger.exception("Unhandled error in %s", method)
            self._write_error(req_id, -32603, f"Internal error: {exc}")

    # -- method handlers -----------------------------------------------------

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "serverInfo": self.SERVER_INFO,
            "capabilities": {
                "tools": {"listChanged": False},
            },
        }

    def _handle_initialized(self, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"tools": TOOLS}

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = _dispatch_tool(self._service, self._agent_id, tool_name, arguments)
            text = json.dumps(result, indent=2, default=str)
            return {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }
        except ContextGraphError as exc:
            return {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            }
        except Exception as exc:
            logger.exception("Tool call failed: %s", tool_name)
            return {
                "content": [{"type": "text", "text": f"Internal error: {exc}"}],
                "isError": True,
            }

    # -- I/O helpers ---------------------------------------------------------

    def _write_result(self, req_id: Any, result: Any) -> None:
        self._write({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _write_error(self, req_id: Any, code: int, message: str) -> None:
        self._write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": code, "message": message},
            }
        )

    def _write(self, msg: dict[str, Any]) -> None:
        line = json.dumps(msg)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(agent_id: str | None = None) -> None:
    """Start the ContextGraph MCP server.

    Parameters
    ----------
    agent_id:
        Explicit agent identity.  Falls back to the ``CG_AGENT_ID``
        environment variable.  If neither is set the server will
        auto-register a new agent on startup.
    """
    logging.basicConfig(
        level=os.environ.get("CG_LOG_LEVEL", "WARNING").upper(),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,  # keep stdout clean for JSON-RPC
    )

    service = create_service()

    resolved_agent_id = agent_id or os.environ.get("CG_AGENT_ID", "")
    if resolved_agent_id:
        resolved_agent_id = _ensure_agent(service, resolved_agent_id)
    else:
        # Auto-register when no agent id is provided
        agent_name = os.environ.get("CG_AGENT_NAME", "mcp-agent")
        org_id = os.environ.get("CG_AGENT_ORG", "default")
        agent = service.register_agent(name=agent_name, org_id=org_id)
        resolved_agent_id = agent.agent_id
        logger.info("Auto-registered agent %s", resolved_agent_id)

    # Try the mcp SDK first; fall back to built-in JSON-RPC server
    if not _try_run_mcp_sdk(service, resolved_agent_id):
        logger.info("mcp package not found – using built-in JSON-RPC server")
        server = _JsonRpcServer(service, resolved_agent_id)
        server.run()


if __name__ == "__main__":
    main()
