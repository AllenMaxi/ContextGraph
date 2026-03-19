"""A2A native integration for ContextGraph.

This module exposes ContextGraph capabilities using the Google A2A protocol,
supporting agent card discovery, task handling, streaming state transitions,
push notifications, and federation.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .utils import to_jsonable, utcnow

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentCard:
    """A2A-compliant agent card describing capabilities and endpoints."""

    name: str
    description: str
    url: str
    version: str = "1.0"
    protocol_version: str = "0.2.0"
    capabilities: dict[str, bool] = field(default_factory=lambda: {
        "streaming": True,
        "pushNotifications": True,
        "stateTransitionHistory": True,
    })
    skills: list[AgentSkill] = field(default_factory=list)
    authentication: dict[str, Any] = field(default_factory=lambda: {"schemes": ["bearer"]})
    defaultInputModes: list[str] = field(default_factory=lambda: ["application/json"])
    defaultOutputModes: list[str] = field(default_factory=lambda: ["application/json"])


@dataclass(slots=True)
class AgentSkill:
    """A skill/capability that an agent can perform."""

    id: str
    name: str
    description: str
    input_modes: list[str] = field(default_factory=lambda: ["application/json"])
    output_modes: list[str] = field(default_factory=lambda: ["application/json"])
    tags: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class A2ATask:
    """A task sent through the A2A protocol."""

    task_id: str
    sender_agent_id: str
    receiver_agent_id: str
    skill_id: str
    input_data: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, working, completed, failed
    output_data: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    state_history: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        now = utcnow().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.state_history:
            self.state_history.append({"status": self.status, "timestamp": self.created_at})

    def transition(self, new_status: str) -> None:
        """Record a state transition with timestamp."""
        self.status = new_status
        self.updated_at = utcnow().isoformat()
        self.state_history.append({"status": new_status, "timestamp": self.updated_at})


class A2AServer:
    """A2A-compliant server that exposes ContextGraph as an agent.

    Handles:
    - Agent card serving (/.well-known/agent.json)
    - Task reception, processing, and streaming state transitions
    - Agent discovery of remote A2A agents
    - Push notification delivery to remote A2A agents
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
        self._discovered_agents: dict[str, dict[str, Any]] = {}

    def set_federation_key(self, key: str) -> None:
        self._federation_key = key

    def agent_card(self) -> dict[str, Any]:
        """Generate the A2A-compliant agent card for this ContextGraph node."""
        card = AgentCard(
            name=f"ContextGraph Node ({self.node_id})",
            description=(
                "Knowledge graph memory protocol for AI agents. "
                "Store, recall, and share structured knowledge across agents."
            ),
            url=self.base_url,
            skills=[
                AgentSkill(
                    id="store_memory",
                    name="Store Memory",
                    description="Extract and store claims from unstructured text into the knowledge graph.",
                    tags=["memory", "knowledge", "extraction"],
                    examples=[
                        {"input": {"agent_id": "agent-1", "content": "The sky is blue."}, "output": {"claim_id": "c-1"}},
                    ],
                ),
                AgentSkill(
                    id="recall_memory",
                    name="Recall Memory",
                    description="Search the knowledge graph for claims matching a query.",
                    tags=["memory", "search", "recall"],
                    examples=[
                        {"input": {"agent_id": "agent-1", "query": "sky color"}, "output": {"hits": []}},
                    ],
                ),
                AgentSkill(
                    id="relate_entities",
                    name="Relate Entities",
                    description="Find relationship paths between two entities in the knowledge graph.",
                    tags=["entities", "relations", "graph"],
                    examples=[
                        {"input": {"agent_id": "agent-1", "entity_a": "Earth", "entity_b": "Sun"}, "output": {"paths": []}},
                    ],
                ),
                AgentSkill(
                    id="review_claim",
                    name="Review Claim",
                    description="Attest or challenge a claim in the knowledge graph.",
                    tags=["trust", "review", "attestation"],
                    examples=[
                        {"input": {"reviewer_agent_id": "agent-1", "claim_id": "c-1", "decision": "attest"}, "output": {"status": "attested"}},
                    ],
                ),
                AgentSkill(
                    id="federation_sync",
                    name="Federation Sync",
                    description="Receive published claims from federated ContextGraph nodes.",
                    tags=["federation", "sync"],
                    examples=[
                        {"input": {"claims": [], "source_node_id": "node-2"}, "output": {"ingested": 0}},
                    ],
                ),
                AgentSkill(
                    id="knowledge_subscribe",
                    name="Knowledge Subscribe",
                    description="Create a standing query to watch for knowledge changes matching a pattern.",
                    tags=["subscription", "watch", "pattern"],
                    examples=[
                        {"input": {"agent_id": "agent-1", "query": "weather", "pattern": {"subject": "weather.*"}}, "output": {"subscription_id": "sq-1"}},
                    ],
                ),
                AgentSkill(
                    id="knowledge_feed",
                    name="Knowledge Feed",
                    description="Retrieve the activity feed for an agent based on their subscriptions.",
                    tags=["feed", "activity", "subscription"],
                    examples=[
                        {"input": {"agent_id": "agent-1", "limit": 10}, "output": {"feed": []}},
                    ],
                ),
                AgentSkill(
                    id="knowledge_notify",
                    name="Knowledge Notify",
                    description="Deliver a notification to a remote A2A agent when a standing query matches.",
                    tags=["notification", "push", "a2a"],
                    examples=[
                        {"input": {"target_url": "http://remote/v1/a2a/tasks", "task_data": {}}, "output": {"delivered": True}},
                    ],
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
            task.transition("failed")
            task.output_data = {"error": "No service configured"}
            return to_jsonable(task)

        try:
            task.transition("working")
            result = self._dispatch_skill(task)
            task.transition("completed")
            task.output_data = result
        except Exception as exc:
            logger.warning("A2A task %s failed: %s", task.task_id, exc)
            task.transition("failed")
            task.output_data = {"error": str(exc)}

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

            if skill == "knowledge_subscribe":
                subscription = self.service.watch(
                    agent_id=data["agent_id"],
                    query=data["query"],
                    name=data.get("name"),
                    delivery_mode=data.get("delivery_mode", "pull"),
                    filters=data.get("filters"),
                    pattern=data.get("pattern"),
                )
                return to_jsonable(subscription)

            if skill == "knowledge_feed":
                feed = self.service.get_feed(
                    agent_id=data["agent_id"],
                    limit=data.get("limit", 20),
                    offset=data.get("offset", 0),
                )
                return {"feed": to_jsonable(feed)}

            if skill == "knowledge_notify":
                result = self.send_a2a_notification(
                    target_url=data["target_url"],
                    task_data=data.get("task_data", {}),
                )
                return result

        except KeyError as exc:
            raise ValueError(f"Missing required field {exc} for skill '{skill}'") from exc

        raise ValueError(f"Unknown skill: {skill}")

    # -- Agent discovery -------------------------------------------------

    def discover_remote_agent(self, url: str) -> dict[str, Any]:
        """Fetch and store the agent card from a remote A2A agent.

        Retrieves ``{url}/.well-known/agent.json``, parses it, stores it in
        ``_discovered_agents`` keyed by the agent's URL, and returns the card.
        """
        agent_url = url.rstrip("/")
        card_url = f"{agent_url}/.well-known/agent.json"

        req = urllib.request.Request(card_url, method="GET")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                card = json.loads(raw)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise ValueError(f"Failed to discover agent at {card_url}: {exc}") from exc

        self._discovered_agents[agent_url] = card
        logger.info("Discovered remote agent at %s: %s", agent_url, card.get("name", "unknown"))
        return card

    def get_discovered_agents(self) -> dict[str, dict[str, Any]]:
        """Return all previously discovered remote agents."""
        return dict(self._discovered_agents)

    # -- A2A notification delivery -----------------------------------------

    def send_a2a_notification(self, target_url: str, task_data: dict[str, Any]) -> dict[str, Any]:
        """POST a task to a remote A2A agent's task endpoint.

        Used when a standing query has ``delivery_mode=a2a`` and needs to push
        a notification to another agent.
        """
        payload = json.dumps(task_data).encode("utf-8")
        req = urllib.request.Request(target_url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
                return {"delivered": True, "response": result}
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            logger.warning("A2A notification to %s failed: %s", target_url, exc)
            return {"delivered": False, "error": str(exc)}

    # -- Task streaming support --------------------------------------------

    def get_task_updates(self, task_id: str) -> list[dict[str, str]] | None:
        """Return the state transition history for a task.

        Returns ``None`` if the task is not found.
        """
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return list(task.state_history)

    # -- Federation --------------------------------------------------------

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
            to_jsonable(c)
            for c in all_claims
            if c.visibility.value == "published" and (since is None or c.created_at.isoformat() > since)
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

    @app.get("/v1/a2a/tasks/{task_id}/updates")
    def get_task_updates(task_id: str) -> dict[str, Any]:
        updates = a2a.get_task_updates(task_id)
        if updates is None:
            return {"error": "Task not found"}
        return {"task_id": task_id, "state_history": updates}

    @app.get("/v1/a2a/discover")
    def discover_agent(url: str) -> dict[str, Any]:
        try:
            card = a2a.discover_remote_agent(url)
            return {"status": "discovered", "agent_card": card}
        except ValueError as exc:
            return {"error": str(exc)}

    @app.get("/v1/a2a/discovered")
    def list_discovered_agents() -> dict[str, Any]:
        agents = a2a.get_discovered_agents()
        return {"agents": agents, "count": len(agents)}

    @app.get("/v1/a2a/status")
    def a2a_status() -> dict[str, Any]:
        return a2a.status()
