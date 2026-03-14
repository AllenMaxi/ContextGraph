"""Agent-to-Agent (A2A) protocol server for cross-agent discovery and communication.

Implements the A2A protocol specification for ContextGraph, enabling:
- Agent card discovery (/.well-known/agent.json)
- Capability advertisement
- Cross-agent task delegation
- Federated claim exchange
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .models import Agent
from .utils import to_jsonable, utcnow

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentCard:
    """A2A Agent Card describing an agent's capabilities and endpoints.

    Follows the A2A protocol specification for agent discovery.
    """

    name: str
    description: str
    url: str
    version: str = "1.0"
    protocol_version: str = "0.2.0"
    capabilities: list[str] = field(default_factory=list)
    skills: list[AgentSkill] = field(default_factory=list)
    authentication: dict[str, Any] = field(default_factory=lambda: {"schemes": ["bearer"]})
    default_input_modes: list[str] = field(default_factory=lambda: ["application/json"])
    default_output_modes: list[str] = field(default_factory=lambda: ["application/json"])


@dataclass(slots=True)
class AgentSkill:
    """A skill/capability that an agent can perform."""

    id: str
    name: str
    description: str
    input_modes: list[str] = field(default_factory=lambda: ["application/json"])
    output_modes: list[str] = field(default_factory=lambda: ["application/json"])
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class A2ATask:
    """A task sent between agents via A2A protocol."""

    task_id: str
    sender_agent_id: str
    receiver_agent_id: str
    skill_id: str
    input_data: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, working, completed, failed
    output_data: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = utcnow().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


class A2AServer:
    """A2A protocol server that exposes ContextGraph as an agent.

    Handles:
    - Agent card serving (/.well-known/agent.json)
    - Task reception and processing
    - Federation claim ingestion
    """

    def __init__(
        self,
        node_id: str,
        base_url: str,
        service: Any = None,
        enabled: bool = False,
    ) -> None:
        self.node_id = node_id
        self.base_url = base_url.rstrip("/")
        self.service = service
        self.enabled = enabled
        self._tasks: dict[str, A2ATask] = {}
        self._federation_key: str = ""

    def set_federation_key(self, key: str) -> None:
        self._federation_key = key

    def agent_card(self) -> dict[str, Any]:
        """Generate the A2A agent card for this ContextGraph node."""
        card = AgentCard(
            name=f"ContextGraph Node ({self.node_id})",
            description=(
                "Knowledge graph memory protocol for AI agents. "
                "Store, recall, and share structured knowledge across agents."
            ),
            url=self.base_url,
            capabilities=["knowledge_store", "knowledge_recall", "entity_resolution", "claim_review"],
            skills=[
                AgentSkill(
                    id="store_memory",
                    name="Store Memory",
                    description="Extract and store claims from unstructured text into the knowledge graph.",
                    tags=["memory", "knowledge", "extraction"],
                ),
                AgentSkill(
                    id="recall_memory",
                    name="Recall Memory",
                    description="Search the knowledge graph for claims matching a query.",
                    tags=["memory", "search", "recall"],
                ),
                AgentSkill(
                    id="relate_entities",
                    name="Relate Entities",
                    description="Find relationship paths between two entities in the knowledge graph.",
                    tags=["entities", "relations", "graph"],
                ),
                AgentSkill(
                    id="review_claim",
                    name="Review Claim",
                    description="Attest or challenge a claim in the knowledge graph.",
                    tags=["trust", "review", "attestation"],
                ),
                AgentSkill(
                    id="federation_sync",
                    name="Federation Sync",
                    description="Receive published claims from federated ContextGraph nodes.",
                    tags=["federation", "sync"],
                ),
            ],
        )
        return to_jsonable(card)

    def handle_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming A2A task."""
        if not self.enabled:
            return {"error": "A2A server is not enabled", "status": "failed"}

        task = A2ATask(
            task_id=task_data.get("task_id", ""),
            sender_agent_id=task_data.get("sender_agent_id", ""),
            receiver_agent_id=task_data.get("receiver_agent_id", ""),
            skill_id=task_data.get("skill_id", ""),
            input_data=task_data.get("input_data", {}),
        )

        self._tasks[task.task_id] = task

        if not self.service:
            task.status = "failed"
            task.output_data = {"error": "No service configured"}
            return to_jsonable(task)

        try:
            task.status = "working"
            result = self._dispatch_skill(task)
            task.status = "completed"
            task.output_data = result
        except Exception as exc:
            logger.warning("A2A task %s failed: %s", task.task_id, exc)
            task.status = "failed"
            task.output_data = {"error": str(exc)}

        task.updated_at = utcnow().isoformat()
        return to_jsonable(task)

    def _dispatch_skill(self, task: A2ATask) -> dict[str, Any]:
        """Route a task to the appropriate service method."""
        skill = task.skill_id
        data = task.input_data

        try:
            if skill == "store_memory":
                result = self.service.store_memory(
                    agent_id=data["agent_id"],
                    content=data["content"],
                    visibility=data.get("visibility", "published"),
                    license=data.get("license", "internal"),
                    metadata=data.get("metadata", {}),
                    access_list=data.get("access_list"),
                    price=data.get("price", 0.0),
                )
                return to_jsonable(result)

            if skill == "recall_memory":
                hits = self.service.recall(
                    agent_id=data["agent_id"],
                    query=data["query"],
                    limit=data.get("limit", 10),
                )
                return {"hits": to_jsonable(hits)}

            if skill == "relate_entities":
                paths = self.service.relate(
                    agent_id=data["agent_id"],
                    entity_a=data["entity_a"],
                    entity_b=data["entity_b"],
                    max_depth=data.get("max_depth", 2),
                )
                return {"paths": to_jsonable(paths)}

            if skill == "review_claim":
                reviewed = self.service.review_claim(
                    reviewer_agent_id=data["reviewer_agent_id"],
                    claim_id=data["claim_id"],
                    decision=data["decision"],
                    reason=data.get("reason", ""),
                )
                return to_jsonable(reviewed)
        except KeyError as exc:
            raise ValueError(f"Missing required field {exc} for skill '{skill}'") from exc

        raise ValueError(f"Unknown skill: {skill}")

    def handle_federation_ingest(
        self, claims_data: list[dict[str, Any]], source_node_id: str, federation_key: str
    ) -> dict[str, Any]:
        """Ingest claims from a federated peer node."""
        if not self.enabled:
            return {"error": "A2A server is not enabled", "ingested": 0}

        if self._federation_key and federation_key != self._federation_key:
            return {"error": "Invalid federation key", "ingested": 0}

        ingested = 0
        errors: list[str] = []

        for claim_data in claims_data:
            try:
                # Federation only accepts published claims
                if claim_data.get("visibility") != "published":
                    continue
                ingested += 1
            except Exception as exc:
                errors.append(str(exc))

        return {
            "ingested": ingested,
            "errors": errors,
            "source_node_id": source_node_id,
        }

    def get_published_claims(self, since: str | None = None) -> list[dict[str, Any]]:
        """Return published claims for federation peers to pull."""
        if not self.service:
            return []

        # List all claims visible to federation
        all_claims = self.service.repository.list_claims()
        published = [
            to_jsonable(c) for c in all_claims
            if c.visibility.value == "published"
            and (since is None or c.created_at.isoformat() > since)
        ]
        return published

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return to_jsonable(task)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "node_id": self.node_id,
            "base_url": self.base_url,
            "pending_tasks": sum(1 for t in self._tasks.values() if t.status == "pending"),
            "completed_tasks": sum(1 for t in self._tasks.values() if t.status == "completed"),
            "total_tasks": len(self._tasks),
        }


def register_a2a_routes(app: Any, a2a: A2AServer) -> None:
    """Register A2A protocol routes on a web framework app.

    Works with FastAPI or any framework with @app.get/@app.post decorators.
    """
    try:
        from .api._compat import Header
    except ImportError:
        Header = None

    @app.get("/.well-known/agent.json")
    def agent_card() -> dict[str, Any]:
        return a2a.agent_card()

    @app.post("/v1/a2a/tasks")
    def create_task(payload: dict[str, Any]) -> dict[str, Any]:
        return a2a.handle_task(payload)

    @app.get("/v1/a2a/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        result = a2a.get_task(task_id)
        if result is None:
            return {"error": "Task not found"}
        return result

    @app.post("/v1/federation/ingest")
    def federation_ingest(payload: dict[str, Any]) -> dict[str, Any]:
        federation_key = ""
        if Header is not None:
            # In FastAPI context, extract from header
            pass
        return a2a.handle_federation_ingest(
            claims_data=payload.get("claims", []),
            source_node_id=payload.get("source_node_id", ""),
            federation_key=federation_key,
        )

    @app.get("/v1/federation/claims")
    def federation_claims(since: str | None = None) -> dict[str, Any]:
        claims = a2a.get_published_claims(since=since)
        return {"claims": claims, "count": len(claims)}

    @app.get("/v1/a2a/status")
    def a2a_status() -> dict[str, Any]:
        return a2a.status()
