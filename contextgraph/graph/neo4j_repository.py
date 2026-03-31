from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from ..models import (
    Agent,
    AgentDiscoverability,
    AuditEntry,
    Claim,
    ClaimImpact,
    ClaimSearchResult,
    CompactionCheckpoint,
    ContextPack,
    ContextPackClaim,
    ContextPackExplanation,
    ContextPackSource,
    DeliveryMode,
    DeltaPack,
    DeltaPackDiff,
    Entity,
    Memory,
    MemoryCurationStatus,
    Notification,
    PatternFilter,
    ProvenanceEntry,
    ReviewStatus,
    ReviewTask,
    SentinelDecision,
    SentinelVerdict,
    Session,
    SessionEvent,
    SessionStateEntry,
    StandingQuery,
    Subscription,
    SubscriptionTarget,
    ValidationStatus,
    Visibility,
)
from ..utils import tokenize

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
            "CREATE CONSTRAINT subscription_id_unique IF NOT EXISTS FOR (s:Subscription) REQUIRE s.subscription_id IS UNIQUE",
            "CREATE CONSTRAINT context_pack_id_unique IF NOT EXISTS FOR (p:ContextPack) REQUIRE p.pack_id IS UNIQUE",
            "CREATE CONSTRAINT session_id_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.session_id IS UNIQUE",
            "CREATE CONSTRAINT session_event_id_unique IF NOT EXISTS FOR (e:SessionEvent) REQUIRE e.event_id IS UNIQUE",
            "CREATE CONSTRAINT checkpoint_id_unique IF NOT EXISTS FOR (c:CompactionCheckpoint) REQUIRE c.checkpoint_id IS UNIQUE",
            "CREATE CONSTRAINT delta_pack_id_unique IF NOT EXISTS FOR (d:DeltaPack) REQUIRE d.delta_pack_id IS UNIQUE",
            "CREATE INDEX claim_source_idx IF NOT EXISTS FOR (c:Claim) ON (c.source_agent_id)",
            "CREATE INDEX claim_visibility_idx IF NOT EXISTS FOR (c:Claim) ON (c.visibility)",
            "CREATE INDEX session_agent_idx IF NOT EXISTS FOR (s:Session) ON (s.agent_id)",
            "CREATE INDEX delta_pack_session_idx IF NOT EXISTS FOR (d:DeltaPack) ON (d.session_id)",
            "CREATE INDEX checkpoint_session_idx IF NOT EXISTS FOR (c:CompactionCheckpoint) ON (c.session_id)",
            "CREATE FULLTEXT INDEX claim_statement_fulltext IF NOT EXISTS FOR (c:Claim) ON EACH [c.statement]",
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

    def update_memory(self, memory: Memory) -> Memory:
        query = """
        MATCH (m:Memory {memory_id: $memory_id})
        SET m += $props
        RETURN m
        """
        self._write(query, {"memory_id": memory.memory_id, "props": self._serialize(memory)})
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

    def list_claims_for_memory(self, memory_id: str) -> list[Claim]:
        query = """
        MATCH (:Memory {memory_id: $memory_id})-[:EMITS]->(c:Claim)
        OPTIONAL MATCH (c)-[:SUBJECT]->(e:Entity)
        RETURN c, collect(e.entity_id) AS entity_ids
        ORDER BY c.created_at ASC
        """
        records = self._fetch_all(query, {"memory_id": memory_id})
        return [self._claim_from_record(record) for record in records]

    def search_claims(
        self,
        query: str,
        limit: int = 100,
        requester_agent_id: str | None = None,
        requester_org_id: str | None = None,
        exclude_priced_cross_org: bool = False,
    ) -> list[ClaimSearchResult]:
        terms = tokenize(query)
        if not terms:
            return []

        def _build_params() -> dict[str, Any]:
            return {
                "query": " ".join(terms),
                "terms": terms,
                "limit": limit,
                "requester_agent_id": requester_agent_id,
                "requester_org_id": requester_org_id,
                "apply_access_filter": requester_agent_id is not None and requester_org_id is not None,
                "exclude_priced_cross_org": exclude_priced_cross_org,
            }

        try:
            records = self._fetch_all(
                """
                CALL db.index.fulltext.queryNodes('claim_statement_fulltext', $query) YIELD node, score
                MATCH (m:Memory)-[:EMITS]->(node)
                WHERE coalesce(m.curation_status, 'active') = 'active'
                  AND (
                    NOT $apply_access_filter
                    OR node.source_agent_id = $requester_agent_id
                    OR (node.visibility = 'org' AND node.source_org_id = $requester_org_id)
                    OR (
                        node.visibility = 'shared'
                        AND any(item IN coalesce(node.access_list, []) WHERE item IN [$requester_agent_id, $requester_org_id])
                    )
                    OR node.visibility = 'published'
                  )
                  AND (
                    NOT $exclude_priced_cross_org
                    OR coalesce(node.price, 0.0) <= 0.0
                    OR node.source_agent_id = $requester_agent_id
                    OR coalesce(node.source_org_id, '') = $requester_org_id
                  )
                OPTIONAL MATCH (node)-[:SUBJECT]->(e:Entity)
                RETURN node AS c,
                       collect(e.entity_id) AS entity_ids,
                       score,
                       CASE
                         WHEN $apply_access_filter
                           AND coalesce(node.price, 0.0) > 0.0
                           AND node.source_agent_id <> $requester_agent_id
                           AND coalesce(node.source_org_id, '') <> $requester_org_id
                         THEN 1
                         ELSE 0
                       END AS locked_rank
                ORDER BY locked_rank ASC, score DESC, c.created_at DESC
                LIMIT $limit
                """,
                _build_params(),
            )
            if records:
                return [
                    ClaimSearchResult(
                        claim=self._claim_from_record(record),
                        text_score_raw=round(float(record["score"]), 4),
                    )
                    for record in records
                    if float(record["score"]) > 0
                ]
        except Exception:
            pass

        records = self._fetch_all(
            """
            MATCH (c:Claim)
            MATCH (m:Memory)-[:EMITS]->(c)
            WITH c, [term IN $terms WHERE toLower(c.statement) CONTAINS term] AS matched_terms
            WHERE size(matched_terms) > 0
              AND coalesce(m.curation_status, 'active') = 'active'
              AND (
                NOT $apply_access_filter
                OR c.source_agent_id = $requester_agent_id
                OR (c.visibility = 'org' AND c.source_org_id = $requester_org_id)
                OR (
                    c.visibility = 'shared'
                    AND any(item IN coalesce(c.access_list, []) WHERE item IN [$requester_agent_id, $requester_org_id])
                )
                OR c.visibility = 'published'
              )
              AND (
                NOT $exclude_priced_cross_org
                OR coalesce(c.price, 0.0) <= 0.0
                OR c.source_agent_id = $requester_agent_id
                OR coalesce(c.source_org_id, '') = $requester_org_id
              )
            OPTIONAL MATCH (c)-[:SUBJECT]->(e:Entity)
            RETURN c,
                   collect(e.entity_id) AS entity_ids,
                   toFloat(size(matched_terms)) AS score,
                   CASE
                     WHEN $apply_access_filter
                       AND coalesce(c.price, 0.0) > 0.0
                       AND c.source_agent_id <> $requester_agent_id
                       AND coalesce(c.source_org_id, '') <> $requester_org_id
                     THEN 1
                     ELSE 0
                   END AS locked_rank
            ORDER BY locked_rank ASC, score DESC, c.created_at DESC
            LIMIT $limit
            """,
            _build_params(),
        )
        return [
            ClaimSearchResult(
                claim=self._claim_from_record(record),
                text_score_raw=round(float(record["score"]), 4),
            )
            for record in records
            if float(record["score"]) > 0
        ]

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

    def save_sentinel_verdict(self, verdict: SentinelVerdict) -> SentinelVerdict:
        query = """
        MATCH (c:Claim {claim_id: $claim_id})
        MERGE (v:SentinelVerdict {verdict_id: $verdict_id})
        SET v += $props
        MERGE (v)-[:JUDGES]->(c)
        RETURN v
        """
        self._write(
            query,
            {
                "claim_id": verdict.claim_id,
                "verdict_id": verdict.verdict_id,
                "props": self._serialize(verdict),
            },
        )
        return verdict

    def list_verdicts_for_claim(self, claim_id: str) -> list[SentinelVerdict]:
        records = self._fetch_all(
            """
            MATCH (v:SentinelVerdict {claim_id: $claim_id})
            RETURN v ORDER BY v.timestamp DESC
            """,
            {"claim_id": claim_id},
        )
        return [self._verdict_from_node(record["v"]) for record in records]

    def list_verdicts(self, limit: int = 100, decision: str | None = None) -> list[SentinelVerdict]:
        if decision:
            records = self._fetch_all(
                """
                MATCH (v:SentinelVerdict {decision: $decision})
                RETURN v ORDER BY v.timestamp DESC LIMIT $limit
                """,
                {"decision": decision, "limit": limit},
            )
        else:
            records = self._fetch_all(
                """
                MATCH (v:SentinelVerdict)
                RETURN v ORDER BY v.timestamp DESC LIMIT $limit
                """,
                {"limit": limit},
            )
        return [self._verdict_from_node(record["v"]) for record in records]

    def save_subscription(self, subscription: Subscription) -> Subscription:
        query = """
        MERGE (s:Subscription {subscription_id: $subscription_id})
        SET s += $props
        RETURN s
        """
        self._write(
            query,
            {
                "subscription_id": subscription.subscription_id,
                "props": self._serialize(subscription),
            },
        )
        return subscription

    def get_subscription(self, subscription_id: str) -> Subscription | None:
        record = self._fetch_one(
            "MATCH (s:Subscription {subscription_id: $subscription_id}) RETURN s",
            {"subscription_id": subscription_id},
        )
        if record is None:
            return None
        return self._subscription_from_node(record["s"])

    def get_subscriptions_by_follower(self, agent_id: str) -> list[Subscription]:
        records = self._fetch_all(
            """
            MATCH (s:Subscription {follower_agent_id: $agent_id})
            WHERE coalesce(s.active, true) = true
            RETURN s ORDER BY s.created_at ASC
            """,
            {"agent_id": agent_id},
        )
        return [self._subscription_from_node(record["s"]) for record in records]

    def get_followers_of_agent(self, agent_id: str) -> list[Subscription]:
        records = self._fetch_all(
            """
            MATCH (s:Subscription {target_type: $target_type, target_id: $agent_id})
            WHERE coalesce(s.active, true) = true
            RETURN s ORDER BY s.created_at ASC
            """,
            {"target_type": SubscriptionTarget.AGENT.value, "agent_id": agent_id},
        )
        return [self._subscription_from_node(record["s"]) for record in records]

    def delete_subscription(self, subscription_id: str) -> None:
        self._write(
            """
            MATCH (s:Subscription {subscription_id: $subscription_id})
            DETACH DELETE s
            """,
            {"subscription_id": subscription_id},
        )

    def save_context_pack(self, pack: ContextPack) -> ContextPack:
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        MERGE (p:ContextPack {pack_id: $pack_id})
        SET p += $props
        MERGE (a)-[:COMPILED_CONTEXT]->(p)
        RETURN p
        """
        self._write(
            query,
            {
                "agent_id": pack.agent_id,
                "pack_id": pack.pack_id,
                "props": self._serialize(pack),
            },
        )
        return pack

    def get_context_pack(self, pack_id: str) -> ContextPack | None:
        record = self._fetch_one("MATCH (p:ContextPack {pack_id: $pack_id}) RETURN p", {"pack_id": pack_id})
        if record is None:
            return None
        return self._context_pack_from_node(record["p"])

    def save_session(self, session_obj: Session) -> Session:
        query = """
        MATCH (a:Agent {agent_id: $agent_id})
        MERGE (s:Session {session_id: $session_id})
        SET s += $props
        MERGE (a)-[:OWNS_SESSION]->(s)
        RETURN s
        """
        self._write(
            query,
            {
                "agent_id": session_obj.agent_id,
                "session_id": session_obj.session_id,
                "props": self._serialize(session_obj),
            },
        )
        return session_obj

    def update_session(self, session_obj: Session) -> Session:
        query = """
        MATCH (s:Session {session_id: $session_id})
        SET s += $props
        RETURN s
        """
        self._write(query, {"session_id": session_obj.session_id, "props": self._serialize(session_obj)})
        return session_obj

    def get_session(self, session_id: str) -> Session | None:
        record = self._fetch_one("MATCH (s:Session {session_id: $session_id}) RETURN s", {"session_id": session_id})
        if record is None:
            return None
        return self._session_from_node(record["s"])

    def list_sessions_for_agent(self, agent_id: str) -> list[Session]:
        records = self._fetch_all(
            """
            MATCH (:Agent {agent_id: $agent_id})-[:OWNS_SESSION]->(s:Session)
            RETURN s ORDER BY s.updated_at DESC, s.created_at DESC
            """,
            {"agent_id": agent_id},
        )
        return [self._session_from_node(record["s"]) for record in records]

    def save_session_event(self, event: SessionEvent) -> SessionEvent:
        query = """
        MATCH (s:Session {session_id: $session_id})
        MERGE (e:SessionEvent {event_id: $event_id})
        SET e += $props
        MERGE (s)-[:HAS_EVENT]->(e)
        RETURN e
        """
        self._write(
            query,
            {
                "session_id": event.session_id,
                "event_id": event.event_id,
                "props": self._serialize(event),
            },
        )
        return event

    def list_session_events(self, session_id: str) -> list[SessionEvent]:
        records = self._fetch_all(
            """
            MATCH (:Session {session_id: $session_id})-[:HAS_EVENT]->(e:SessionEvent)
            RETURN e ORDER BY e.sequence ASC, e.created_at ASC
            """,
            {"session_id": session_id},
        )
        return [self._session_event_from_node(record["e"]) for record in records]

    def save_compaction_checkpoint(self, checkpoint: CompactionCheckpoint) -> CompactionCheckpoint:
        query = """
        MATCH (s:Session {session_id: $session_id})
        MATCH (d:DeltaPack {delta_pack_id: $delta_pack_id})
        MERGE (c:CompactionCheckpoint {checkpoint_id: $checkpoint_id})
        SET c += $props
        MERGE (s)-[:HAS_CHECKPOINT]->(c)
        MERGE (c)-[:USES_DELTA_PACK]->(d)
        RETURN c
        """
        self._write(
            query,
            {
                "session_id": checkpoint.session_id,
                "delta_pack_id": checkpoint.delta_pack_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "props": self._serialize(checkpoint),
            },
        )
        return checkpoint

    def get_compaction_checkpoint(self, checkpoint_id: str) -> CompactionCheckpoint | None:
        record = self._fetch_one(
            "MATCH (c:CompactionCheckpoint {checkpoint_id: $checkpoint_id}) RETURN c",
            {"checkpoint_id": checkpoint_id},
        )
        if record is None:
            return None
        return self._compaction_checkpoint_from_node(record["c"])

    def list_compaction_checkpoints(self, session_id: str) -> list[CompactionCheckpoint]:
        records = self._fetch_all(
            """
            MATCH (:Session {session_id: $session_id})-[:HAS_CHECKPOINT]->(c:CompactionCheckpoint)
            RETURN c ORDER BY c.sequence ASC, c.created_at ASC
            """,
            {"session_id": session_id},
        )
        return [self._compaction_checkpoint_from_node(record["c"]) for record in records]

    def save_delta_pack(self, pack: DeltaPack) -> DeltaPack:
        query = """
        MATCH (s:Session {session_id: $session_id})
        MATCH (a:Agent {agent_id: $agent_id})
        MERGE (d:DeltaPack {delta_pack_id: $delta_pack_id})
        SET d += $props
        MERGE (s)-[:HAS_DELTA_PACK]->(d)
        MERGE (a)-[:COMPILED_DELTA]->(d)
        RETURN d
        """
        self._write(
            query,
            {
                "session_id": pack.session_id,
                "agent_id": pack.agent_id,
                "delta_pack_id": pack.delta_pack_id,
                "props": self._serialize(pack),
            },
        )
        return pack

    def get_delta_pack(self, delta_pack_id: str) -> DeltaPack | None:
        record = self._fetch_one(
            "MATCH (d:DeltaPack {delta_pack_id: $delta_pack_id}) RETURN d",
            {"delta_pack_id": delta_pack_id},
        )
        if record is None:
            return None
        return self._delta_pack_from_node(record["d"])

    def list_delta_packs(self, session_id: str) -> list[DeltaPack]:
        records = self._fetch_all(
            """
            MATCH (:Session {session_id: $session_id})-[:HAS_DELTA_PACK]->(d:DeltaPack)
            RETURN d ORDER BY d.sequence ASC, d.generated_at ASC
            """,
            {"session_id": session_id},
        )
        return [self._delta_pack_from_node(record["d"]) for record in records]

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
            "subscriptions": "Subscription",
            "sentinel_verdicts": "SentinelVerdict",
            "context_packs": "ContextPack",
            "sessions": "Session",
            "session_events": "SessionEvent",
            "compaction_checkpoints": "CompactionCheckpoint",
            "delta_packs": "DeltaPack",
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
        if isinstance(value, tuple):
            value = list(value)
        if isinstance(value, dict):
            return json.dumps(self._json_safe(value), sort_keys=True)
        if isinstance(value, list):
            serialized = [self._json_safe(item) for item in value]
            if self._list_is_neo4j_safe(serialized):
                return serialized
            return json.dumps(serialized, sort_keys=True)
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "value"):
            return value.value
        return value

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, tuple):
            value = list(value)
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        return value

    def _list_is_neo4j_safe(self, value: list[Any]) -> bool:
        return all(item is not None and isinstance(item, (str, int, float, bool)) for item in value)

    def _parse_dt(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    def _parse_json_if_needed(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped or stripped[0] not in "[{":
            return value
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return value

    def _parse_bool(self, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        return bool(value)

    def _parse_string_map(self, value: Any) -> dict[str, str]:
        parsed = self._parse_json_if_needed(value)
        if not isinstance(parsed, dict):
            return {}
        return {str(key): "" if item is None else str(item) for key, item in parsed.items()}

    def _parse_string_list(self, value: Any) -> list[str]:
        parsed = self._parse_json_if_needed(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if item is not None]
        if isinstance(parsed, tuple):
            return [str(item) for item in parsed if item is not None]
        if isinstance(parsed, str) and parsed.strip():
            return [parsed]
        return []

    def _parse_conflict_pairs(self, value: Any) -> list[tuple[str, str]]:
        parsed = self._parse_json_if_needed(value)
        if not isinstance(parsed, list):
            return []
        pairs: list[tuple[str, str]] = []
        for item in parsed:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                pairs.append((str(item[0]), str(item[1])))
        return pairs

    def _parse_pattern_filter(self, value: Any) -> PatternFilter | None:
        parsed = self._parse_json_if_needed(value)
        if not isinstance(parsed, dict) or not parsed:
            return None
        return PatternFilter(
            entities=self._parse_string_list(parsed.get("entities", [])),
            entity_types=self._parse_string_list(parsed.get("entity_types", [])),
            relation_types=self._parse_string_list(parsed.get("relation_types", [])),
            min_confidence=float(parsed.get("min_confidence", 0.0) or 0.0),
            source_org_ids=self._parse_string_list(parsed.get("source_org_ids", [])),
            visibility_levels=self._parse_string_list(parsed.get("visibility_levels", [])),
        )

    def _parse_provenance(self, value: Any) -> list[ProvenanceEntry]:
        parsed = self._parse_json_if_needed(value)
        if not isinstance(parsed, list):
            return []
        entries: list[ProvenanceEntry] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            timestamp = self._parse_dt(item.get("timestamp"))
            if timestamp is None:
                continue
            entries.append(
                ProvenanceEntry(
                    agent_id=str(item.get("agent_id", "")),
                    action=str(item.get("action", "")),
                    timestamp=timestamp,
                    confidence_at_action=float(item.get("confidence_at_action", 0.0) or 0.0),
                    detail=str(item.get("detail", "")),
                )
            )
        return entries

    def _context_pack_claim_from_data(self, value: Any) -> ContextPackClaim:
        data = value if isinstance(value, dict) else {}
        return ContextPackClaim(
            claim_id=str(data.get("claim_id", "")),
            statement=str(data.get("statement", "")),
            source_memory_id=str(data.get("source_memory_id", "")),
            source_agent_id=str(data.get("source_agent_id", "")),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            freshness_score=float(data.get("freshness_score", 0.0) or 0.0),
            validation_status=str(data.get("validation_status", ValidationStatus.UNREVIEWED.value)),
            score=float(data.get("score", 0.0) or 0.0),
            source_memory_section=str(data.get("source_memory_section", "")),
            source_label=str(data.get("source_label", "")),
            locked=self._parse_bool(data.get("locked", False)),
        )

    def _context_pack_source_from_data(self, value: Any) -> ContextPackSource:
        data = value if isinstance(value, dict) else {}
        return ContextPackSource(
            memory_id=str(data.get("memory_id", "")),
            agent_id=str(data.get("agent_id", "")),
            source_type=str(data.get("source_type", "")),
            source_label=str(data.get("source_label", "")),
            source_uri=str(data.get("source_uri", "")),
            claim_count=int(data.get("claim_count", 0) or 0),
        )

    def _context_pack_explanation_from_value(self, value: Any) -> ContextPackExplanation | None:
        parsed = self._parse_json_if_needed(value)
        if parsed is None:
            return None
        data = parsed if isinstance(parsed, dict) else {}
        return ContextPackExplanation(
            included_reasons={
                str(key): self._parse_string_list(item) for key, item in dict(data.get("included_reasons", {})).items()
            },
            excluded_reasons={
                str(key): self._parse_string_list(item) for key, item in dict(data.get("excluded_reasons", {})).items()
            },
            conflict_pairs=self._parse_conflict_pairs(data.get("conflict_pairs", [])),
            filter_counts={str(key): int(item or 0) for key, item in dict(data.get("filter_counts", {})).items()},
        )

    def _delta_pack_diff_from_value(self, value: Any) -> DeltaPackDiff | None:
        parsed = self._parse_json_if_needed(value)
        if parsed is None:
            return None
        data = parsed if isinstance(parsed, dict) else {}
        return DeltaPackDiff(
            added={str(key): self._parse_string_list(item) for key, item in dict(data.get("added", {})).items()},
            dropped={str(key): self._parse_string_list(item) for key, item in dict(data.get("dropped", {})).items()},
        )

    def _parse_state_snapshot(self, value: Any) -> dict[str, list[SessionStateEntry]]:
        parsed = self._parse_json_if_needed(value)
        if not isinstance(parsed, dict):
            return {}
        snapshot: dict[str, list[SessionStateEntry]] = {}
        for bucket, items in parsed.items():
            if not isinstance(items, list):
                continue
            entries: list[SessionStateEntry] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                observed_at = self._parse_dt(item.get("observed_at"))
                if observed_at is None:
                    continue
                entries.append(
                    SessionStateEntry(
                        value=str(item.get("value", "")),
                        observed_at=observed_at,
                    )
                )
            snapshot[str(bucket)] = entries
        return snapshot

    def _agent_from_node(self, node: Any) -> Agent:
        props = dict(node)
        return Agent(
            agent_id=props["agent_id"],
            name=props["name"],
            org_id=props["org_id"],
            capabilities=self._parse_string_list(props.get("capabilities", [])),
            api_key=props["api_key"],
            status=props["status"],
            created_at=self._parse_dt(props["created_at"]),
            updated_at=self._parse_dt(props["updated_at"]),
            erc8004_address=props.get("erc8004_address", ""),
            identity_verified=self._parse_bool(props.get("identity_verified", False)),
            reputation_score=float(props.get("reputation_score", 0.0)),
            followers_count=int(props.get("followers_count", 0)),
            default_visibility=Visibility(props.get("default_visibility", Visibility.PRIVATE.value)),
            default_access_list=self._parse_string_list(props.get("default_access_list", [])),
            default_price=float(props.get("default_price", 0.0)),
            profile_visibility=AgentDiscoverability(props.get("profile_visibility", AgentDiscoverability.ORG.value)),
            profile_access_list=self._parse_string_list(props.get("profile_access_list", [])),
            profile_summary=props.get("profile_summary", ""),
            profile_links=self._parse_string_map(props.get("profile_links", {})),
            last_activity_at=self._parse_dt(props.get("last_activity_at")),
            suspension_reason=props.get("suspension_reason"),
            suspended_at=self._parse_dt(props.get("suspended_at")),
            role=props.get("role", "agent"),
        )

    def _memory_from_node(self, node: Any) -> Memory:
        props = dict(node)
        return Memory(
            memory_id=props["memory_id"],
            agent_id=props["agent_id"],
            content=props["content"],
            visibility=Visibility(props["visibility"]),
            validation_status=ValidationStatus(props.get("validation_status", ValidationStatus.UNREVIEWED.value)),
            license=props["license"],
            metadata=self._parse_string_map(props.get("metadata", {})),
            created_at=self._parse_dt(props["created_at"]),
            updated_at=self._parse_dt(props["updated_at"]),
            access_list=self._parse_string_list(props.get("access_list", [])),
            price=float(props.get("price", 0.0)),
            evidence=self._parse_string_list(props.get("evidence", [])),
            citations=self._parse_string_list(props.get("citations", [])),
            validated_at=self._parse_dt(props.get("validated_at")),
            expires_at=self._parse_dt(props.get("expires_at")),
            curation_status=MemoryCurationStatus(props.get("curation_status", MemoryCurationStatus.ACTIVE.value)),
            curation_reason=props.get("curation_reason", ""),
            curated_at=self._parse_dt(props.get("curated_at")),
            source_type=props.get("source_type", ""),
            source_uri=props.get("source_uri", ""),
            source_label=props.get("source_label", ""),
            section_refs=self._parse_string_list(props.get("section_refs", [])),
            ingest_metadata=self._parse_string_map(props.get("ingest_metadata", {})),
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
        entity_ids = self._parse_string_list(record.get("entity_ids", props.get("entity_ids", [])))
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
            review_reasons=self._parse_string_list(props.get("review_reasons", [])),
            source_org_id=props.get("source_org_id", ""),
            access_list=self._parse_string_list(props.get("access_list", [])),
            price=float(props.get("price", 0.0)),
            evidence=self._parse_string_list(props.get("evidence", [])),
            citations=self._parse_string_list(props.get("citations", [])),
            validated_at=self._parse_dt(props.get("validated_at")),
            provenance=self._parse_provenance(props.get("provenance", [])),
            derived_from=self._parse_string_list(props.get("derived_from", [])),
            source_memory_section=props.get("source_memory_section", ""),
            impact=ClaimImpact(props.get("impact", ClaimImpact.LOW.value)),
            quorum_required=int(props.get("quorum_required", 0) or 0),
            quorum_met=self._parse_bool(props.get("quorum_met", True), default=True),
            attestation_count=int(props.get("attestation_count", 0) or 0),
            challenge_count=int(props.get("challenge_count", 0) or 0),
        )

    def _query_from_node(self, node: Any) -> StandingQuery:
        props = dict(node)
        return StandingQuery(
            query_id=props["query_id"],
            agent_id=props["agent_id"],
            name=props["name"],
            query=props["query"],
            filters=self._parse_string_map(props.get("filters", {})),
            delivery_mode=DeliveryMode(props["delivery_mode"]),
            status=props["status"],
            created_at=self._parse_dt(props["created_at"]),
            updated_at=self._parse_dt(props["updated_at"]),
            pattern=self._parse_pattern_filter(props.get("pattern")),
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
            delivered=self._parse_bool(props.get("delivered", False)),
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
            details=self._parse_string_map(props.get("details", {})),
            timestamp=self._parse_dt(props["timestamp"]),
        )

    def _verdict_from_node(self, node: Any) -> SentinelVerdict:
        props = dict(node)
        return SentinelVerdict(
            verdict_id=props["verdict_id"],
            sentinel_agent_id=props["sentinel_agent_id"],
            claim_id=props["claim_id"],
            memory_id=props["memory_id"],
            decision=SentinelDecision(props["decision"]),
            confidence=float(props["confidence"]),
            reason=props["reason"],
            conflicting_claim_id=props.get("conflicting_claim_id"),
            details=self._parse_string_map(props.get("details", {})),
            timestamp=self._parse_dt(props["timestamp"]),
        )

    def _subscription_from_node(self, node: Any) -> Subscription:
        props = dict(node)
        return Subscription(
            subscription_id=props["subscription_id"],
            follower_agent_id=props["follower_agent_id"],
            target_type=SubscriptionTarget(props["target_type"]),
            target_id=props["target_id"],
            created_at=self._parse_dt(props["created_at"]),
            active=self._parse_bool(props.get("active", True), default=True),
        )

    def _context_pack_from_node(self, node: Any) -> ContextPack:
        props = dict(node)
        included_claims = [
            self._context_pack_claim_from_data(item)
            for item in self._parse_json_if_needed(props.get("included_claims", []))
            if isinstance(item, dict)
        ]
        excluded_claims = [
            self._context_pack_claim_from_data(item)
            for item in self._parse_json_if_needed(props.get("excluded_claims", []))
            if isinstance(item, dict)
        ]
        conflicting_claims = [
            self._context_pack_claim_from_data(item)
            for item in self._parse_json_if_needed(props.get("conflicting_claims", []))
            if isinstance(item, dict)
        ]
        sources = [
            self._context_pack_source_from_data(item)
            for item in self._parse_json_if_needed(props.get("sources", []))
            if isinstance(item, dict)
        ]
        return ContextPack(
            pack_id=props["pack_id"],
            agent_id=props["agent_id"],
            query=props["query"],
            included_claims=included_claims,
            sources=sources,
            token_budget=int(props["token_budget"]),
            tokens_used=int(props["tokens_used"]),
            generated_at=self._parse_dt(props["generated_at"]),
            summary=props.get("summary", ""),
            session_id=props.get("session_id", ""),
            base_pack_id=props.get("base_pack_id", ""),
            delta_from_pack_id=props.get("delta_from_pack_id", ""),
            checkpoint_reason=props.get("checkpoint_reason", ""),
            restoration_prompt=props.get("restoration_prompt", ""),
            restoration_instructions=self._parse_string_list(props.get("restoration_instructions", [])),
            excluded_claims=excluded_claims,
            conflicting_claims=conflicting_claims,
            explanation=self._context_pack_explanation_from_value(props.get("explanation")),
        )

    def _session_from_node(self, node: Any) -> Session:
        props = dict(node)
        return Session(
            session_id=props["session_id"],
            agent_id=props["agent_id"],
            title=props["title"],
            source=props["source"],
            status=props["status"],
            metadata=self._parse_string_map(props.get("metadata", {})),
            created_at=self._parse_dt(props["created_at"]),
            updated_at=self._parse_dt(props["updated_at"]),
            parent_session_id=props.get("parent_session_id", ""),
            forked_from_checkpoint_id=props.get("forked_from_checkpoint_id", ""),
            latest_checkpoint_id=props.get("latest_checkpoint_id", ""),
            latest_delta_pack_id=props.get("latest_delta_pack_id", ""),
            checkpoint_count=int(props.get("checkpoint_count", 0) or 0),
            event_count=int(props.get("event_count", 0) or 0),
        )

    def _session_event_from_node(self, node: Any) -> SessionEvent:
        props = dict(node)
        return SessionEvent(
            event_id=props["event_id"],
            session_id=props["session_id"],
            agent_id=props["agent_id"],
            event_type=props["event_type"],
            content=props["content"],
            created_at=self._parse_dt(props["created_at"]),
            metadata=self._parse_string_map(props.get("metadata", {})),
            sequence=int(props.get("sequence", 0) or 0),
            important=self._parse_bool(props.get("important", False)),
        )

    def _delta_pack_from_node(self, node: Any) -> DeltaPack:
        props = dict(node)
        return DeltaPack(
            delta_pack_id=props["delta_pack_id"],
            checkpoint_id=props["checkpoint_id"],
            session_id=props["session_id"],
            agent_id=props["agent_id"],
            sequence=int(props.get("sequence", 0) or 0),
            checkpoint_reason=props["checkpoint_reason"],
            generated_at=self._parse_dt(props["generated_at"]),
            token_budget=int(props.get("token_budget", 0) or 0),
            tokens_used=int(props.get("tokens_used", 0) or 0),
            summary=props.get("summary", ""),
            base_pack_id=props.get("base_pack_id", ""),
            delta_from_pack_id=props.get("delta_from_pack_id", ""),
            decisions=self._parse_string_list(props.get("decisions", [])),
            constraints=self._parse_string_list(props.get("constraints", [])),
            open_tasks=self._parse_string_list(props.get("open_tasks", [])),
            failures=self._parse_string_list(props.get("failures", [])),
            resolved_items=self._parse_string_list(props.get("resolved_items", [])),
            important_artifacts=self._parse_string_list(props.get("important_artifacts", [])),
            external_references=self._parse_string_list(props.get("external_references", [])),
            changed_files=self._parse_string_list(props.get("changed_files", [])),
            commands=self._parse_string_list(props.get("commands", [])),
            notes=self._parse_string_list(props.get("notes", [])),
            stale_items=self._parse_string_list(props.get("stale_items", [])),
            untrusted_items=self._parse_string_list(props.get("untrusted_items", [])),
            dropped_items=self._parse_string_list(props.get("dropped_items", [])),
            restoration_prompt=props.get("restoration_prompt", ""),
            restoration_instructions=self._parse_string_list(props.get("restoration_instructions", [])),
            included_event_ids=self._parse_string_list(props.get("included_event_ids", [])),
            event_count=int(props.get("event_count", 0) or 0),
            cache_status=props.get("cache_status", "miss"),
            cache_base_checkpoint_id=props.get("cache_base_checkpoint_id", ""),
            reused_event_count=int(props.get("reused_event_count", 0) or 0),
            recomputed_event_count=int(props.get("recomputed_event_count", 0) or 0),
            invalidated_reasons=self._parse_string_list(props.get("invalidated_reasons", [])),
            state_snapshot=self._parse_state_snapshot(props.get("state_snapshot")),
            state_snapshot_version=props.get("state_snapshot_version", ""),
            state_snapshot_event_count=int(props.get("state_snapshot_event_count", 0) or 0),
            diff=self._delta_pack_diff_from_value(props.get("diff")),
        )

    def _compaction_checkpoint_from_node(self, node: Any) -> CompactionCheckpoint:
        props = dict(node)
        return CompactionCheckpoint(
            checkpoint_id=props["checkpoint_id"],
            session_id=props["session_id"],
            agent_id=props["agent_id"],
            sequence=int(props.get("sequence", 0) or 0),
            reason=props["reason"],
            created_at=self._parse_dt(props["created_at"]),
            delta_pack_id=props["delta_pack_id"],
            base_checkpoint_id=props.get("base_checkpoint_id", ""),
            event_count=int(props.get("event_count", 0) or 0),
            restoration_prompt=props.get("restoration_prompt", ""),
            restoration_instructions=self._parse_string_list(props.get("restoration_instructions", [])),
            summary=props.get("summary", ""),
        )
