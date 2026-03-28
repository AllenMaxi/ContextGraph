from __future__ import annotations

from threading import RLock

from .models import (
    Agent,
    AuditEntry,
    Claim,
    ClaimSearchResult,
    ContextPack,
    Entity,
    Memory,
    MemoryCurationStatus,
    Notification,
    ReviewTask,
    SentinelVerdict,
    StandingQuery,
    Subscription,
    SubscriptionTarget,
)
from .permissions import can_access_claim
from .scoring import BM25Scorer
from .utils import tokenize


class InMemoryRepository:
    def __init__(self) -> None:
        self._lock = RLock()
        self._agents: dict[str, Agent] = {}
        self._agents_by_key: dict[str, str] = {}
        self._entities: dict[str, Entity] = {}
        self._entities_by_alias: dict[str, str] = {}
        self._memories: dict[str, Memory] = {}
        self._claims: dict[str, Claim] = {}
        self._claims_by_memory: dict[str, set[str]] = {}
        self._queries: dict[str, StandingQuery] = {}
        self._notifications: dict[str, Notification] = {}
        self._reviews: dict[str, ReviewTask] = {}
        self._audit_entries: dict[str, AuditEntry] = {}
        self._subscriptions: dict[str, Subscription] = {}
        self._sentinel_verdicts: dict[str, SentinelVerdict] = {}
        self._context_packs: dict[str, ContextPack] = {}
        self._claim_search = BM25Scorer(k1=1.5, b=0.75)

    def save_agent(self, agent: Agent) -> Agent:
        with self._lock:
            self._agents[agent.agent_id] = agent
            self._agents_by_key[agent.api_key] = agent.agent_id
            return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        with self._lock:
            return self._agents.get(agent_id)

    def find_agent_by_key(self, api_key: str) -> Agent | None:
        with self._lock:
            agent_id = self._agents_by_key.get(api_key)
            if agent_id is None:
                return None
            return self._agents.get(agent_id)

    def list_agents(self) -> list[Agent]:
        with self._lock:
            return list(self._agents.values())

    def save_memory(self, memory: Memory) -> Memory:
        with self._lock:
            self._memories[memory.memory_id] = memory
            return memory

    def update_memory(self, memory: Memory) -> Memory:
        with self._lock:
            self._memories[memory.memory_id] = memory
            return memory

    def get_memory(self, memory_id: str) -> Memory | None:
        with self._lock:
            return self._memories.get(memory_id)

    def upsert_entity(self, entity: Entity) -> Entity:
        with self._lock:
            existing_id = self._entities_by_alias.get(entity.alias_key)
            if existing_id is not None:
                existing = self._entities[existing_id]
                existing.updated_at = entity.updated_at
                return existing
            self._entities[entity.entity_id] = entity
            self._entities_by_alias[entity.alias_key] = entity.entity_id
            return entity

    def get_entity(self, entity_id: str) -> Entity | None:
        with self._lock:
            return self._entities.get(entity_id)

    def find_entity_by_alias(self, alias_key: str) -> Entity | None:
        with self._lock:
            entity_id = self._entities_by_alias.get(alias_key)
            if entity_id is None:
                return None
            return self._entities.get(entity_id)

    def save_claim(self, claim: Claim) -> Claim:
        with self._lock:
            existing = self._claims.get(claim.claim_id)
            if existing is not None and existing.memory_id != claim.memory_id:
                previous_ids = self._claims_by_memory.get(existing.memory_id)
                if previous_ids is not None:
                    previous_ids.discard(existing.claim_id)
                    if not previous_ids:
                        self._claims_by_memory.pop(existing.memory_id, None)
            self._claims[claim.claim_id] = claim
            self._claims_by_memory.setdefault(claim.memory_id, set()).add(claim.claim_id)
            self._claim_search.add_document(claim.claim_id, claim.statement)
            return claim

    def update_claim(self, claim: Claim) -> Claim:
        with self._lock:
            existing = self._claims.get(claim.claim_id)
            if existing is not None and existing.memory_id != claim.memory_id:
                previous_ids = self._claims_by_memory.get(existing.memory_id)
                if previous_ids is not None:
                    previous_ids.discard(existing.claim_id)
                    if not previous_ids:
                        self._claims_by_memory.pop(existing.memory_id, None)
            self._claims[claim.claim_id] = claim
            self._claims_by_memory.setdefault(claim.memory_id, set()).add(claim.claim_id)
            self._claim_search.add_document(claim.claim_id, claim.statement)
            return claim

    def get_claim(self, claim_id: str) -> Claim | None:
        with self._lock:
            return self._claims.get(claim_id)

    def list_claims(self) -> list[Claim]:
        with self._lock:
            return list(self._claims.values())

    def list_claims_for_memory(self, memory_id: str) -> list[Claim]:
        with self._lock:
            claim_ids = self._claims_by_memory.get(memory_id, set())
            return [self._claims[claim_id] for claim_id in claim_ids if claim_id in self._claims]

    def search_claims(
        self,
        query: str,
        limit: int = 100,
        requester_agent_id: str | None = None,
        requester_org_id: str | None = None,
        exclude_priced_cross_org: bool = False,
    ) -> list[ClaimSearchResult]:
        with self._lock:
            if not tokenize(query):
                return []
            results = self._claim_search.search(query, limit=limit)
            filtered: list[ClaimSearchResult] = []
            for claim_id, score in results:
                claim = self._claims.get(claim_id)
                if claim is None:
                    continue
                memory = self._memories.get(claim.memory_id)
                if memory is None or memory.curation_status != MemoryCurationStatus.ACTIVE:
                    continue
                if (
                    requester_agent_id is not None
                    and requester_org_id is not None
                    and not can_access_claim(requester_agent_id, requester_org_id, claim)
                ):
                    continue
                if (
                    exclude_priced_cross_org
                    and claim.price > 0
                    and requester_agent_id is not None
                    and requester_org_id is not None
                    and claim.source_agent_id != requester_agent_id
                    and claim.source_org_id != requester_org_id
                ):
                    continue
                filtered.append(ClaimSearchResult(claim=claim, text_score_raw=round(score, 4)))
            if requester_agent_id is not None and requester_org_id is not None:
                filtered.sort(
                    key=lambda item: (
                        item.claim.price > 0
                        and item.claim.source_agent_id != requester_agent_id
                        and item.claim.source_org_id != requester_org_id,
                        -item.text_score_raw,
                    )
                )
            return filtered

    def save_query(self, query: StandingQuery) -> StandingQuery:
        with self._lock:
            self._queries[query.query_id] = query
            return query

    def get_query(self, query_id: str) -> StandingQuery | None:
        with self._lock:
            return self._queries.get(query_id)

    def list_queries(self) -> list[StandingQuery]:
        with self._lock:
            return list(self._queries.values())

    def list_queries_for_agent(self, agent_id: str) -> list[StandingQuery]:
        with self._lock:
            return [query for query in self._queries.values() if query.agent_id == agent_id]

    def save_notification(self, notification: Notification) -> Notification:
        with self._lock:
            self._notifications[notification.notification_id] = notification
            return notification

    def get_notification(self, notification_id: str) -> Notification | None:
        with self._lock:
            return self._notifications.get(notification_id)

    def list_notifications_for_agent(self, agent_id: str) -> list[Notification]:
        with self._lock:
            return [notification for notification in self._notifications.values() if notification.agent_id == agent_id]

    def mark_notification_delivered(self, notification_id: str) -> Notification | None:
        with self._lock:
            notification = self._notifications.get(notification_id)
            if notification is None:
                return None
            notification.delivered = True
            return notification

    def save_review_task(self, review: ReviewTask) -> ReviewTask:
        with self._lock:
            self._reviews[review.task_id] = review
            return review

    def update_review_task(self, review: ReviewTask) -> ReviewTask:
        with self._lock:
            self._reviews[review.task_id] = review
            return review

    def get_review_task(self, task_id: str) -> ReviewTask | None:
        with self._lock:
            return self._reviews.get(task_id)

    def list_review_tasks(self) -> list[ReviewTask]:
        with self._lock:
            return list(self._reviews.values())

    def save_audit_entry(self, entry: AuditEntry) -> AuditEntry:
        with self._lock:
            self._audit_entries[entry.audit_id] = entry
            return entry

    def list_audit_entries(self) -> list[AuditEntry]:
        with self._lock:
            return list(self._audit_entries.values())

    def save_subscription(self, subscription: Subscription) -> Subscription:
        with self._lock:
            self._subscriptions[subscription.subscription_id] = subscription
            return subscription

    def get_subscription(self, subscription_id: str) -> Subscription | None:
        with self._lock:
            return self._subscriptions.get(subscription_id)

    def get_subscriptions_by_follower(self, agent_id: str) -> list[Subscription]:
        with self._lock:
            return [s for s in self._subscriptions.values() if s.follower_agent_id == agent_id and s.active]

    def get_followers_of_agent(self, agent_id: str) -> list[Subscription]:
        with self._lock:
            return [
                s
                for s in self._subscriptions.values()
                if s.target_type == SubscriptionTarget.AGENT and s.target_id == agent_id and s.active
            ]

    def save_sentinel_verdict(self, verdict: SentinelVerdict) -> SentinelVerdict:
        with self._lock:
            self._sentinel_verdicts[verdict.verdict_id] = verdict
            return verdict

    def list_verdicts_for_claim(self, claim_id: str) -> list[SentinelVerdict]:
        with self._lock:
            return [v for v in self._sentinel_verdicts.values() if v.claim_id == claim_id]

    def list_verdicts(self, limit: int = 100, decision: str | None = None) -> list[SentinelVerdict]:
        with self._lock:
            results = list(self._sentinel_verdicts.values())
            if decision:
                results = [v for v in results if v.decision == decision]
            results.sort(key=lambda v: v.timestamp, reverse=True)
            return results[:limit]

    def delete_subscription(self, subscription_id: str) -> None:
        with self._lock:
            self._subscriptions.pop(subscription_id, None)

    def save_context_pack(self, pack: ContextPack) -> ContextPack:
        with self._lock:
            self._context_packs[pack.pack_id] = pack
            return pack

    def get_context_pack(self, pack_id: str) -> ContextPack | None:
        with self._lock:
            return self._context_packs.get(pack_id)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "agents": len(self._agents),
                "entities": len(self._entities),
                "memories": len(self._memories),
                "claims": len(self._claims),
                "queries": len(self._queries),
                "notifications": len(self._notifications),
                "review_tasks": len(self._reviews),
                "audit_entries": len(self._audit_entries),
                "subscriptions": len(self._subscriptions),
                "sentinel_verdicts": len(self._sentinel_verdicts),
                "context_packs": len(self._context_packs),
            }

    def close(self) -> None:
        return None
