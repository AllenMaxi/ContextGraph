from __future__ import annotations

from typing import Any

from ..service import ContextGraphService
from ..utils import to_jsonable


class ContextGraphMCPServer:
    """Minimal MCP-compatible facade.

    This keeps the tool contract explicit now and can be swapped with the real
    MCP SDK server once the dependency is added.
    """

    def __init__(self, service: ContextGraphService | None = None) -> None:
        self.service = service or ContextGraphService()

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "contextgraph_store",
                "description": "Store a memory and emit governed claims.",
                "input_schema": {
                    "type": "object",
                    "required": ["agent_id", "content"],
                    "properties": {
                        "agent_id": {"type": "string"},
                        "content": {"type": "string"},
                        "visibility": {"type": "string"},
                        "license": {"type": "string"},
                    },
                },
            },
            {
                "name": "contextgraph_recall",
                "description": "Recall claims for a query.",
                "input_schema": {
                    "type": "object",
                    "required": ["agent_id", "query"],
                    "properties": {
                        "agent_id": {"type": "string"},
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                },
            },
            {
                "name": "contextgraph_relate",
                "description": "Find a path between two entities.",
                "input_schema": {
                    "type": "object",
                    "required": ["agent_id", "entity_a", "entity_b"],
                    "properties": {
                        "agent_id": {"type": "string"},
                        "entity_a": {"type": "string"},
                        "entity_b": {"type": "string"},
                        "max_depth": {"type": "integer"},
                    },
                },
            },
            {
                "name": "contextgraph_watch",
                "description": "Create a standing query for matching claims.",
                "input_schema": {
                    "type": "object",
                    "required": ["agent_id", "query"],
                    "properties": {
                        "agent_id": {"type": "string"},
                        "query": {"type": "string"},
                        "name": {"type": "string"},
                        "delivery_mode": {"type": "string"},
                    },
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "contextgraph_store":
            return {"result": to_jsonable(self.service.store_memory(**arguments))}
        if name == "contextgraph_recall":
            return {"result": to_jsonable(self.service.recall(**arguments))}
        if name == "contextgraph_relate":
            return {"result": to_jsonable(self.service.relate(**arguments))}
        if name == "contextgraph_watch":
            return {"result": to_jsonable(self.service.watch(**arguments))}
        raise ValueError(f"Unknown tool '{name}'.")
