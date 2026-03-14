from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from ..models import (
    Agent,
    AuditEntry,
    Claim,
    DeliveryMode,
    Entity,
    Memory,
    Notification,
    ReviewStatus,
    ReviewTask,
    StandingQuery,
    ValidationStatus,
    Visibility,
)

try:
    from neo4j import GraphDatabase
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    GraphDatabase = None


class Neo4jRepository:
    """Simple persistence adapter.

    This favors correctness and interface compatibility over query optimization.
    It can be replaced later with claim-native Cypher tuned for ranking and ACLs.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        if GraphDatabase is None:  # pragma: no cover - optional dependency
            raise RuntimeError('neo4j is not installed. Install with `pip install -e ".[server,neo4j]"`.')
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._ensure_schema()

    def close(self) -> None:
        self._driver.close()

    def _ensure_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT agent_id_unique IF NOT EXISTS FOR (a:Agent) REQUIRE a.agent_id IS UNIQUE",
            "CREATE CONSTRAINT memory_id_unique IF NOT EXISTS FOR (m:Memory) REQUIRE m.memory_id IS UNIQUE",
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
            "CREATE CONSTRAINT entity_alias_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.alias_key IS UNIQUE",
            "CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE",
            "CREATE CONSTRAINT query_id_unique IF NOT EXISTS FOR (q:StandingQuery) REQUIRE q.query_id IS UNIQUE",
            "CREATE CONSTRAINT review_id_unique IF NOT EXISTS FOR (r:ReviewTask) REQUIRE r.task_id IS UNIQUE",
            "CREATE CONSTRAINT notification_id_unique IF NOT EXISTS FOR (n:Notification) REQUIRE n.notification_id IS UNIQUE",
            "CREATE CONSTRAINT audit_id_unique IF NOT EXISTS FOR (a:AuditEntry) REQUIRE a.audit_id IS UNIQUE",
            "CREATE INDEX claim_source_idx IF NOT EXISTS FOR (c:Claim) ON (c.source_agent_id)",
            "CREATE INDEX claim_visibility_idx IF NOT EXISTS FOR (c:Claim) ON (c.visibility)",
        ]
        with self._driver.session() as session:
            for statement in statements:
                session.run(statement)

    def save_agent(self, agent: Agent) -> Agent:
        query = """
        MERGE (a:Agent {agent_id: $agent_id})
        SET a += $props
        RETURN a
        """
        self._write(query, {"agent_id": agent.agent_id, "props": self._serialize(agent)})
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        record = self._fetch_one("MATCH (a:Agent {agent_id: $agent_id}) RETURN a", {"agent_id": agent_id})
        if record is None:
            return None
        return self._agent_from_node(record["a"])

    def find_agent_by_key(self, api_key: str) -> Agent | None:
        record = self._fetch_one("MATCH (a:Agent {api_key: $api_key}) RETURN a", {"api_key": api_key})
        if record is None:
            return None
        return self._agent_from_node(record["a"])

    def list_agents(self) -> list[Agent]:
        records = self._fetch_all("MATCH (a:Agent) RETURN a ORDER BY a.created_at ASC")
        return [self._agent_from_node(record["a"]) for record in records]

    def save_memory(self, memory: Memory) -> Memory:
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        MERGE (m:Memory {memory_id: $memory_id})
        SET m += $props
        MERGE (a)-[:STORED]->(m)
        RETURN m
        """
        params = {
            "agent_id": memory.agent_id,
            "memory_id": memory.memory_id,
            "props": self._serialize(memory),
        }
        self._write(query, params)
        return memory

    def get_memory(self, memory_id: str) -> Memory | None:
        record = self._fetch_one("MATCH (m:Memory {memory_id: $memory_id}) RETURN m", {"memory_id": memory_id})
        if record is None:
            return None
        return self._memory_from_node(record["m"])

    def upsert_entity(self, entity: Entity) -> Entity:
        query = """
        MERGE (e:Entity {alias_key: $alias_key})
        ON CREATE SET e += $props
        ON MATCH SET e.updated_at = $updated_at
        RETURN e
        """
        record = self._fetch_one(
            query,
            {
                "alias_key": entity.alias_key,
                "props": self._serialize(entity),
                "updated_at": self._serialize_value(entity.updated_at),
            },
        )
        return self._entity_from_node(record["e"])

    def get_entity(self, entity_id: str) -> Entity | None:
        record = self._fetch_one("MATCH (e:Entity {entity_id: $entity_id}) RETURN e", {"entity_id": entity_id})
        if record is None:
            return None
        return self._entity_from_node(record["e"])

    def find_entity_by_alias(self, alias_key: str) -> Entity | None:
        record = self._fetch_one("MATCH (e:Entity {alias_key: $alias_key}) RETURN e", {"alias_key": alias_key})
        if record is None:
            return None
        return self._entity_from_node(record["e"])

    def save_claim(self, claim: Claim) -> Claim:
        query = """
        MATCH (a:Agent {agent_id: $source_agent_id})
        MATCH (m:Memory {memory_id: $memory_id})
        MERGE (c:Claim {claim_id: $claim_id})
        SET c += $props
        MERGE (m)-[:EMITS]->(c)
        MERGE (a)-[:ASSERTED]->(c)
        WITH c
        UNWIND $entity_ids AS entity_id
        MATCH (e:Entity {entity_id: entity_id})
        MERGE (c)-[:SUBJECT]->(e)
        RETURN c
        """
        self._write(
            query,
            {
                "claim_id": claim.claim_id,
                "source_agent_id": claim.source_agent_id,
                "memory_id": claim.memory_id,
                "props": self._serialize(claim),
                "entity_ids": claim.entity_ids,
            },
        )
        return claim

    def update_claim(self, claim: Claim) -> Claim:
        query = """
        MATCH (c:Claim {claim_id: $claim_id})
        SET c += $props
        RETURN c
        """
        self._write(query, {"claim_id": claim.claim_id, "props": self._serialize(claim)})
        return claim

    def get_claim(self, claim_id: str) -> Claim | None:
        record = self._fetch_one(
            """
            MATCH (c:Claim {claim_id: $claim_id})
            OPTIONAL MATCH (c)-[:SUBJECT]->(e:Entity)
            RETURN c, collect(e.entity_id) AS entity_ids
            """,
            {"claim_id": claim_id},
        )
        if record is None:
            return None
        return self._claim_from_record(record)

    def list_claims(self) -> list[Claim]:
        query = """
        MATCH (c:Claim)
        OPTIONAL MATCH (c)-[:SUBJECT]->(e:Entity)
        RETURN c, collect(e.entity_id) AS entity_ids
        ORDER BY c.created_at ASC
        """
        records = self._fetch_all(query)
        return [self._claim_from_record(record) for record in records]

    def save_query(self, query_obj: StandingQuery) -> StandingQuery:
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        MERGE (q:StandingQuery {query_id: $query_id})
        SET q += $props
        MERGE (a)-[:SUBSCRIBES_TO]->(q)
        RETURN q
        """
        self._write(
            query,
            {
                "agent_id": query_obj.agent_id,
                "query_id": query_obj.query_id,
                "props": self._serialize(query_obj),
            },
        )
        return query_obj

    def get_query(self, query_id: str) -> StandingQuery | None:
        record = self._fetch_one(
            "MATCH (q:StandingQuery {query_id: $query_id}) RETURN q",
            {"query_id": query_id},
        )
        if record is None:
            return None
        return self._query_from_node(record["q"])

    def list_queries(self) -> list[StandingQuery]:
        records = self._fetch_all("MATCH (q:StandingQuery) RETURN q ORDER BY q.created_at ASC")
        return [self._query_from_node(record["q"]) for record in records]

    def list_queries_for_agent(self, agent_id: str) -> list[StandingQuery]:
        records = self._fetch_all(
            """
            MATCH (:Agent {agent_id: $agent_id})-[:SUBSCRIBES_TO]->(q:StandingQuery)
            RETURN q ORDER BY q.created_at ASC
            """,
            {"agent_id": agent_id},
        )
        return [self._query_from_node(record["q"]) for record in records]

    def save_notification(self, notification: Notification) -> Notification:
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        MATCH (q:StandingQuery {query_id: $query_id})
        MATCH (c:Claim {claim_id: $claim_id})
        MERGE (n:Notification {notification_id: $notification_id})
        SET n += $props
        MERGE (q)-[:TRIGGERED]->(n)
        MERGE (a)-[:OWNS_NOTIFICATION]->(n)
        MERGE (n)-[:MATCHED_CLAIM]->(c)
        RETURN n
        """
        self._write(
            query,
            {
                "agent_id": notification.agent_id,
                "query_id": notification.query_id,
                "claim_id": notification.claim_id,
                "notification_id": notification.notification_id,
                "props": self._serialize(notification),
            },
        )
        return notification

    def get_notification(self, notification_id: str) -> Notification | None:
        record = self._fetch_one(
            "MATCH (n:Notification {notification_id: $notification_id}) RETURN n",
            {"notification_id": notification_id},
        )
        if record is None:
            return None
        return self._notification_from_node(record["n"])

    def list_notifications_for_agent(self, agent_id: str) -> list[Notification]:
        records = self._fetch_all(
            """
            MATCH (:Agent {agent_id: $agent_id})-[:OWNS_NOTIFICATION]->(n:Notification)
            RETURN n ORDER BY n.created_at DESC
            """,
            {"agent_id": agent_id},
        )
        return [self._notification_from_node(record["n"]) for record in records]

    def mark_notification_delivered(self, notification_id: str) -> Notification | None:
        record = self._fetch_one(
            """
            MATCH (n:Notification {notification_id: $notification_id})
            SET n.delivered = true
            RETURN n
            """,
            {"notification_id": notification_id},
        )
        if record is None:
            return None
        return self._notification_from_node(record["n"])

    def save_review_task(self, review: ReviewTask) -> ReviewTask:
        query = """
        MATCH (c:Claim {claim_id: $claim_id})
        MERGE (r:ReviewTask {task_id: $task_id})
        SET r += $props
        MERGE (r)-[:REVIEWS]->(c)
        RETURN r
        """
        self._write(
            query,
            {
                "claim_id": review.claim_id,
                "task_id": review.task_id,
                "props": self._serialize(review),
            },
        )
        return review

    def update_review_task(self, review: ReviewTask) -> ReviewTask:
        query = """
        MATCH (r:ReviewTask {task_id: $task_id})
        SET r += $props
        RETURN r
        """
        self._write(query, {"task_id": review.task_id, "props": self._serialize(review)})
        return review

    def get_review_task(self, task_id: str) -> ReviewTask | None:
        record = self._fetch_one("MATCH (r:ReviewTask {task_id: $task_id}) RETURN r", {"task_id": task_id})
        if record is None:
            return None
        return self._review_from_node(record["r"])

    def list_review_tasks(self) -> list[ReviewTask]:
        records = self._fetch_all("MATCH (r:ReviewTask) RETURN r ORDER BY r.created_at ASC")
        return [self._review_from_node(record["r"]) for record in records]

    def save_audit_entry(self, entry: AuditEntry) -> AuditEntry:
        query = """
        MERGE (a:AuditEntry {audit_id: $audit_id})
        SET a += $props
        RETURN a
        """
        self._write(query, {"audit_id": entry.audit_id, "props": self._serialize(entry)})
        return entry

    def list_audit_entries(self) -> list[AuditEntry]:
        records = self._fetch_all("MATCH (a:AuditEntry) RETURN a ORDER BY a.timestamp DESC")
        return [self._audit_from_node(record["a"]) for record in records]

    def snapshot(self) -> dict[str, int]:
        labels = {
            "agents": "Agent",
            "entities": "Entity",
            "memories": "Memory",
            "claims": "Claim",
            "queries": "StandingQuery",
            "notifications": "Notification",
            "review_tasks": "ReviewTask",
            "audit_entries": "AuditEntry",
        }
        counts: dict[str, int] = {}
        with self._driver.session() as session:
            for key, label in labels.items():
                record = session.run(f"MATCH (n:{label}) RETURN count(n) AS total").single()
                counts[key] = int(record["total"]) if record else 0
        return counts

    def _write(self, query: str, params: dict[str, Any]) -> None:
        with self._driver.session() as session:
            session.run(query, params)

    def _fetch_one(self, query: str, params: dict[str, Any] | None = None) -> Any:
        with self._driver.session() as session:
            return session.run(query, params or {}).single()

    def _fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[Any]:
        with self._driver.session() as session:
            return list(session.run(query, params or {}))

    def _serialize(self, value: Any) -> dict[str, Any]:
        return {key: self._serialize_value(item) for key, item in asdict(value).items()}

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, dict):
            return value
        return value

    def _parse_dt(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    def _agent_from_node(self, node: Any) -> Agent:
        props = dict(node)
        return Agent(
            agent_id=props["agent_id"],
            name=props["name"],
            org_id=props["org_id"],
            capabilities=list(props.get("capabilities", [])),
            api_key=props["api_key"],
            status=props["status"],
            created_at=self._parse_dt(props["created_at"]),
            updated_at=self._parse_dt(props["updated_at"]),
        )

    def _memory_from_node(self, node: Any) -> Memory:
        props = dict(node)
        return Memory(
            memory_id=props["memory_id"],
            agent_id=props["agent_id"],
            content=props["content"],
            visibility=Visibility(props["visibility"]),
            license=props["license"],
            metadata=dict(props.get("metadata", {})),
            created_at=self._parse_dt(props["created_at"]),
            updated_at=self._parse_dt(props["updated_at"]),
        )

    def _entity_from_node(self, node: Any) -> Entity:
        props = dict(node)
        return Entity(
            entity_id=props["entity_id"],
            name=props["name"],
            entity_type=props["entity_type"],
            alias_key=props["alias_key"],
            created_at=self._parse_dt(props["created_at"]),
            updated_at=self._parse_dt(props["updated_at"]),
        )

    def _claim_from_record(self, record: Any) -> Claim:
        props = dict(record["c"])
        entity_ids = list(record.get("entity_ids", props.get("entity_ids", [])))
        return Claim(
            claim_id=props["claim_id"],
            memory_id=props["memory_id"],
            source_agent_id=props["source_agent_id"],
            statement=props["statement"],
            claim_type=props["claim_type"],
            relation_type=props.get("relation_type"),
            confidence=float(props["confidence"]),
            freshness_score=float(props["freshness_score"]),
            validation_status=ValidationStatus(props["validation_status"]),
            visibility=Visibility(props["visibility"]),
            license=props["license"],
            entity_ids=entity_ids,
            created_at=self._parse_dt(props["created_at"]),
            expires_at=self._parse_dt(props.get("expires_at")),
            updated_at=self._parse_dt(props["updated_at"]),
            review_reasons=list(props.get("review_reasons", [])),
        )

    def _query_from_node(self, node: Any) -> StandingQuery:
        props = dict(node)
        return StandingQuery(
            query_id=props["query_id"],
            agent_id=props["agent_id"],
            name=props["name"],
            query=props["query"],
            filters=dict(props.get("filters", {})),
            delivery_mode=DeliveryMode(props["delivery_mode"]),
            status=props["status"],
            created_at=self._parse_dt(props["created_at"]),
            updated_at=self._parse_dt(props["updated_at"]),
        )

    def _notification_from_node(self, node: Any) -> Notification:
        props = dict(node)
        return Notification(
            notification_id=props["notification_id"],
            query_id=props["query_id"],
            agent_id=props["agent_id"],
            claim_id=props["claim_id"],
            event_type=props["event_type"],
            created_at=self._parse_dt(props["created_at"]),
            delivered=bool(props.get("delivered", False)),
        )

    def _review_from_node(self, node: Any) -> ReviewTask:
        props = dict(node)
        resolved_at = self._parse_dt(props.get("resolved_at"))
        return ReviewTask(
            task_id=props["task_id"],
            claim_id=props["claim_id"],
            reason=props["reason"],
            status=ReviewStatus(props["status"]),
            created_at=self._parse_dt(props["created_at"]),
            resolved_at=resolved_at,
        )

    def _audit_from_node(self, node: Any) -> AuditEntry:
        props = dict(node)
        return AuditEntry(
            audit_id=props["audit_id"],
            action=props["action"],
            actor_agent_id=props["actor_agent_id"],
            target_agent_id=props.get("target_agent_id"),
            details=dict(props.get("details", {})),
            timestamp=self._parse_dt(props["timestamp"]),
        )
