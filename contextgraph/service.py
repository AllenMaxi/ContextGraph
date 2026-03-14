from __future__ import annotations

import logging
from collections import deque
from datetime import timedelta
from enum import StrEnum
from threading import RLock, Timer
from time import monotonic, sleep
from typing import Any

from .background import BackgroundWorker
from .config import Settings, settings
from .delivery import DeliveryRequest, NotificationDispatcher, WebhookNotificationDispatcher, validate_webhook_url
from .errors import AuthenticationError, NotFoundError, PermissionDeniedError
from .extraction import Extractor, RuleBasedExtractor
from .identity import AgentIdentity, IdentityVerifier
from .in_memory import InMemoryRepository
from .models import (
    Agent,
    AuditEntry,
    BackgroundJob,
    Claim,
    DeliveryMode,
    Entity,
    JobStatus,
    JobType,
    Memory,
    Notification,
    RecallHit,
    RelationPath,
    ReviewQueueItem,
    ReviewStatus,
    ReviewTask,
    StandingQuery,
    StoreResult,
    ValidationStatus,
    Visibility,
)
from .payment import PaymentGate
from .permissions import can_access_claim
from .repository import Repository
from .scoring import BM25Scorer
from .utils import jaccard_similarity, new_api_key, new_id, normalize_alias, pairwise, utcnow

logger = logging.getLogger(__name__)


class ReviewDecision(StrEnum):
    ATTEST = "attested"
    CHALLENGE = "challenged"


class ContextGraphService:
    def __init__(
        self,
        repository: Repository | None = None,
        extractor: Extractor | None = None,
        app_settings: Settings | None = None,
        notification_dispatcher: NotificationDispatcher | None = None,
    ) -> None:
        self.repository = repository or InMemoryRepository()
        self.extractor = extractor or RuleBasedExtractor()
        self.settings = app_settings or settings
        self._notification_dispatcher = notification_dispatcher or WebhookNotificationDispatcher(
            timeout_seconds=self.settings.webhook_timeout_seconds
        )
        self._job_lock = RLock()
        self._jobs: dict[str, BackgroundJob] = {}
        self._job_payloads: dict[str, dict[str, Any]] = {}
        self._timers: set[Timer] = set()
        self._closing = False
        self._last_claim_expiry_sweep_at = None
        self._last_claim_expiry_sweep_result: dict[str, int] = {}
        self._claim_expiry_sweep_runs = 0
        self._claims_expired_by_sweeps = 0
        self._delivery_retry_scheduled_total = 0
        self._delivery_dead_letter_total = 0
        self._bm25 = BM25Scorer(k1=1.5, b=0.75)
        self._bm25_indexed_claims: set[str] = set()
        self._background_worker = BackgroundWorker(
            name="contextgraph-worker",
            handler=self._process_job,
            poll_interval_seconds=self.settings.background_worker_poll_seconds,
        )
        if self.settings.enable_background_worker:
            self._background_worker.start()
            if self.settings.enable_claim_expiry_sweeps:
                self._schedule_claim_expiry_sweep(self.settings.claim_expiry_sweep_seconds)

    def register_agent(
        self,
        name: str,
        org_id: str,
        capabilities: list[str] | None = None,
        admin_key: str | None = None,
        erc8004_address: str = "",
    ) -> Agent:
        configured_admin_key = self.settings.admin_key
        if configured_admin_key and (not admin_key or admin_key != configured_admin_key):
            raise PermissionDeniedError("Agent registration requires a valid admin key when CG_ADMIN_KEY is set.")
        now = utcnow()
        agent = Agent(
            agent_id=new_id("agt"),
            name=name,
            org_id=org_id,
            capabilities=list(capabilities or []),
            api_key=new_api_key(),
            status="active",
            created_at=now,
            updated_at=now,
            erc8004_address=erc8004_address,
        )
        # Verify ERC-8004 identity if provided
        if erc8004_address:
            verifier = IdentityVerifier(
                enabled=self.settings.enable_identity_verification,
                registry_url=self.settings.erc8004_registry_url,
            )
            identity = AgentIdentity(agent_id=agent.agent_id, erc8004_address=erc8004_address)
            verified = verifier.verify(identity)
            agent.identity_verified = verified.is_verified
            agent.reputation_score = verified.reputation_score
        self.repository.save_agent(agent)
        logger.info("Agent registered: %s org=%s erc8004=%s", agent.agent_id, org_id, bool(erc8004_address))
        self._audit("register_agent", actor_agent_id=agent.agent_id, details={"org_id": org_id})
        return agent

    def get_agent(self, agent_id: str) -> Agent:
        agent = self.repository.get_agent(agent_id)
        if agent is None:
            raise NotFoundError(f"Agent '{agent_id}' was not found.")
        return agent

    def authenticate_agent(self, api_key: str) -> Agent:
        agent = self.repository.find_agent_by_key(api_key)
        if agent is None:
            raise AuthenticationError("Invalid API key.")
        if agent.status != "active":
            raise PermissionDeniedError(f"Agent '{agent.agent_id}' is not active.")
        return agent

    def store_memory(
        self,
        agent_id: str,
        content: str,
        visibility: str = "private",
        license: str = "internal",
        metadata: dict[str, str] | None = None,
        access_list: list[str] | None = None,
        price: float = 0.0,
    ) -> StoreResult:
        return self._store_memory_internal(
            agent_id=agent_id,
            content=content,
            visibility=visibility,
            license=license,
            metadata=metadata,
            access_list=access_list,
            price=price,
        )

    def enqueue_memory_store(
        self,
        agent_id: str,
        content: str,
        visibility: str = "private",
        license: str = "internal",
        metadata: dict[str, str] | None = None,
    ) -> BackgroundJob:
        agent = self.get_agent(agent_id)
        return self._create_job(
            job_type=JobType.STORE_MEMORY,
            owner_agent_id=agent.agent_id,
            owner_org_id=agent.org_id,
            requester_agent_id=agent.agent_id,
            payload_summary={
                "visibility": visibility,
                "license": license,
                "content_preview": content.strip()[:120],
            },
            payload={
                "agent_id": agent_id,
                "content": content,
                "visibility": visibility,
                "license": license,
                "metadata": dict(metadata or {}),
            },
            max_attempts=1,
            audit_action="enqueue_memory_store",
            audit_details={"visibility": visibility},
        )

    def enqueue_claim_expiry_sweep(
        self,
        requester_agent_id: str | None = None,
        recurring: bool = False,
    ) -> BackgroundJob:
        if requester_agent_id is None:
            return self._create_job(
                job_type=JobType.SWEEP_EXPIRED_CLAIMS,
                owner_agent_id="system",
                owner_org_id="system",
                requester_agent_id=None,
                payload_summary={"recurring": recurring},
                payload={"recurring": recurring},
                max_attempts=1,
            )

        agent = self.get_agent(requester_agent_id)
        return self._create_job(
            job_type=JobType.SWEEP_EXPIRED_CLAIMS,
            owner_agent_id=agent.agent_id,
            owner_org_id=agent.org_id,
            requester_agent_id=agent.agent_id,
            payload_summary={"recurring": recurring},
            payload={"recurring": recurring},
            max_attempts=1,
            audit_action="enqueue_claim_expiry_sweep",
        )

    def get_job(self, job_id: str, requester_agent_id: str) -> BackgroundJob:
        requester = self.get_agent(requester_agent_id)
        with self._job_lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"Job '{job_id}' was not found.")
        if requester.org_id != job.org_id and requester.agent_id != job.agent_id:
            raise PermissionDeniedError("Requester cannot access this job.")
        return job

    def list_jobs(self, requester_agent_id: str) -> list[BackgroundJob]:
        requester = self.get_agent(requester_agent_id)
        with self._job_lock:
            jobs = list(self._jobs.values())
        visible = [job for job in jobs if job.org_id == requester.org_id or job.agent_id == requester.agent_id]
        return sorted(visible, key=lambda item: item.created_at, reverse=True)

    def wait_for_job(self, job_id: str, requester_agent_id: str, timeout_seconds: float = 5.0) -> BackgroundJob:
        deadline = monotonic() + timeout_seconds
        while monotonic() < deadline:
            job = self.get_job(job_id, requester_agent_id=requester_agent_id)
            if self._is_terminal_job_status(job.status):
                return job
            sleep(0.01)
        return self.get_job(job_id, requester_agent_id=requester_agent_id)

    def start_background_worker(self) -> None:
        was_running = self._background_worker.is_running()
        self._closing = False
        self._background_worker.start()
        if self.settings.enable_claim_expiry_sweeps and not was_running:
            self._schedule_claim_expiry_sweep(self.settings.claim_expiry_sweep_seconds)

    def stop_background_worker(self) -> None:
        self._closing = True
        self._cancel_timers()
        self._background_worker.stop()

    def _store_memory_internal(
        self,
        agent_id: str,
        content: str,
        visibility: str = "private",
        license: str = "internal",
        metadata: dict[str, str] | None = None,
        access_list: list[str] | None = None,
        price: float = 0.0,
    ) -> StoreResult:
        agent = self.get_agent(agent_id)
        now = utcnow()
        visibility_enum = Visibility(visibility)
        memory = Memory(
            memory_id=new_id("mem"),
            agent_id=agent.agent_id,
            content=content.strip(),
            visibility=visibility_enum,
            license=license,
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        self.repository.save_memory(memory)

        created_entities: dict[str, Entity] = {}
        created_claims: list[Claim] = []
        review_tasks: list[ReviewTask] = []
        expires_at = now + timedelta(days=self.settings.default_claim_ttl_days)

        for extracted in self.extractor.extract(content):
            entity_ids: list[str] = []
            for raw_entity in extracted.entities:
                entity = self._upsert_entity(raw_entity.name, raw_entity.entity_type)
                created_entities[entity.entity_id] = entity
                entity_ids.append(entity.entity_id)

            claim = Claim(
                claim_id=new_id("clm"),
                memory_id=memory.memory_id,
                source_agent_id=agent.agent_id,
                statement=extracted.statement,
                claim_type=extracted.claim_type,
                relation_type=extracted.relation_type,
                confidence=extracted.confidence,
                freshness_score=1.0,
                validation_status=ValidationStatus.UNREVIEWED,
                visibility=visibility_enum,
                license=license,
                entity_ids=entity_ids,
                created_at=now,
                expires_at=expires_at,
                updated_at=now,
                source_org_id=agent.org_id,
                access_list=list(access_list or []),
                price=price,
            )
            self.repository.save_claim(claim)
            created_claims.append(claim)

            if claim.confidence < self.settings.trust_threshold or not claim.entity_ids:
                review = ReviewTask(
                    task_id=new_id("rev"),
                    claim_id=claim.claim_id,
                    reason="low_confidence" if claim.confidence < self.settings.trust_threshold else "missing_entities",
                    status=ReviewStatus.OPEN,
                    created_at=now,
                )
                self.repository.save_review_task(review)
                review_tasks.append(review)

        self._emit_notifications(created_claims)
        self._audit(
            "store_memory",
            actor_agent_id=agent.agent_id,
            details={"memory_id": memory.memory_id, "claim_count": str(len(created_claims))},
        )

        return StoreResult(
            memory=memory,
            claims=created_claims,
            entities=list(created_entities.values()),
            review_tasks=review_tasks,
        )

    def _sync_bm25_index(self, claims: list[Claim]) -> None:
        """Incrementally sync the BM25 index with the current claim set."""
        current_ids = {c.claim_id for c in claims}
        # Remove stale documents
        stale = self._bm25_indexed_claims - current_ids
        for cid in stale:
            self._bm25.remove_document(cid)
            self._bm25_indexed_claims.discard(cid)
        # Add new documents
        for claim in claims:
            if claim.claim_id not in self._bm25_indexed_claims:
                self._bm25.add_document(claim.claim_id, claim.statement)
                self._bm25_indexed_claims.add(claim.claim_id)

    def recall(
        self,
        agent_id: str,
        query: str,
        limit: int = 10,
        payment_token: str | None = None,
    ) -> list[RecallHit]:
        requester = self.get_agent(agent_id)
        payment_gate = PaymentGate(enabled=self.settings.enable_payments, currency=self.settings.payment_currency)
        all_claims = self.repository.list_claims()
        self._sync_bm25_index(all_claims)
        hits: list[RecallHit] = []
        for claim in all_claims:
            if not self._can_access(requester, claim):
                continue
            # x402 payment check for priced cross-org claims
            if claim.price > 0:
                payment_gate.check_access(
                    agent_id=agent_id,
                    claim_price=claim.price,
                    payment_token=payment_token,
                    requester_org=requester.org_id,
                    claim_org=claim.source_org_id,
                )
            score = self._score_claim(query, claim)
            if score <= 0:
                continue
            entities = [self.repository.get_entity(entity_id) for entity_id in claim.entity_ids]
            hits.append(
                RecallHit(
                    claim=claim,
                    score=round(score, 4),
                    entities=[entity for entity in entities if entity is not None],
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        self._audit("recall", actor_agent_id=agent_id, details={"query": query, "limit": str(limit)})
        return hits[:limit]

    def relate(self, agent_id: str, entity_a: str, entity_b: str, max_depth: int = 2) -> list[RelationPath]:
        requester = self.get_agent(agent_id)
        left = self.repository.find_entity_by_alias(normalize_alias(entity_a))
        right = self.repository.find_entity_by_alias(normalize_alias(entity_b))
        if left is None or right is None:
            return []

        accessible_claims = [claim for claim in self.repository.list_claims() if self._can_access(requester, claim)]

        direct_paths = [
            RelationPath(
                entities=[left.name, right.name],
                claim_ids=[claim.claim_id],
                statements=[claim.statement],
            )
            for claim in accessible_claims
            if left.entity_id in claim.entity_ids and right.entity_id in claim.entity_ids
        ]
        if direct_paths:
            self._audit("relate", actor_agent_id=agent_id, details={"entity_a": entity_a, "entity_b": entity_b})
            return direct_paths

        graph: dict[str, list[tuple[str, Claim]]] = {}
        for claim in accessible_claims:
            for source, target in pairwise(claim.entity_ids):
                graph.setdefault(source, []).append((target, claim))
                graph.setdefault(target, []).append((source, claim))

        queue: deque[tuple[str, list[str], list[Claim]]] = deque([(left.entity_id, [left.entity_id], [])])
        visited = {left.entity_id}
        found: list[RelationPath] = []

        while queue:
            current, path, claim_chain = queue.popleft()
            if len(path) - 1 > max_depth:
                continue
            if current == right.entity_id and claim_chain:
                names = [
                    self.repository.get_entity(entity_id).name
                    for entity_id in path
                    if self.repository.get_entity(entity_id)
                ]
                found.append(
                    RelationPath(
                        entities=names,
                        claim_ids=[claim.claim_id for claim in claim_chain],
                        statements=[claim.statement for claim in claim_chain],
                    )
                )
                continue
            for neighbor, claim in graph.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor], claim_chain + [claim]))

        self._audit("relate", actor_agent_id=agent_id, details={"entity_a": entity_a, "entity_b": entity_b})
        return found

    def watch(
        self,
        agent_id: str,
        query: str,
        name: str | None = None,
        delivery_mode: str = "pull",
        filters: dict[str, str] | None = None,
    ) -> StandingQuery:
        self.get_agent(agent_id)
        filters_dict = dict(filters or {})
        delivery_mode_enum = DeliveryMode(delivery_mode)
        if delivery_mode_enum == DeliveryMode.WEBHOOK:
            webhook_url = filters_dict.get("webhook_url", "").strip()
            if not webhook_url:
                raise ValueError("Webhook delivery requires filters.webhook_url.")
            if not webhook_url.startswith(("http://", "https://")):
                raise ValueError("Webhook delivery requires an http:// or https:// webhook_url.")
            validate_webhook_url(webhook_url)
        now = utcnow()
        standing_query = StandingQuery(
            query_id=new_id("qry"),
            agent_id=agent_id,
            name=name or query,
            query=query,
            filters=filters_dict,
            delivery_mode=delivery_mode_enum,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.repository.save_query(standing_query)
        self._audit("watch", actor_agent_id=agent_id, details={"query": query})
        return standing_query

    def get_notifications(self, agent_id: str, mark_delivered: bool = False) -> list[Notification]:
        self.get_agent(agent_id)
        notifications = sorted(
            self.repository.list_notifications_for_agent(agent_id),
            key=lambda item: item.created_at,
            reverse=True,
        )
        if mark_delivered:
            for notification in notifications:
                self.repository.mark_notification_delivered(notification.notification_id)
        return notifications

    def list_standing_queries(self, requester_agent_id: str, include_inactive: bool = False) -> list[StandingQuery]:
        self.get_agent(requester_agent_id)
        queries = self.repository.list_queries_for_agent(requester_agent_id)
        if include_inactive:
            return sorted(queries, key=lambda item: item.created_at, reverse=True)
        active = [query for query in queries if query.status == "active"]
        return sorted(active, key=lambda item: item.created_at, reverse=True)

    def deactivate_watch(self, requester_agent_id: str, query_id: str) -> StandingQuery:
        requester = self.get_agent(requester_agent_id)
        query = self.repository.get_query(query_id)
        if query is None:
            raise NotFoundError(f"Standing query '{query_id}' was not found.")
        if query.agent_id != requester.agent_id:
            raise PermissionDeniedError("Requester cannot deactivate this standing query.")
        query.status = "inactive"
        query.updated_at = utcnow()
        self.repository.save_query(query)
        self._audit(
            "deactivate_watch",
            actor_agent_id=requester.agent_id,
            details={"query_id": query_id},
        )
        return query

    def review_claim(
        self,
        reviewer_agent_id: str,
        claim_id: str,
        decision: str,
        reason: str = "",
    ) -> Claim:
        reviewer = self.get_agent(reviewer_agent_id)
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise NotFoundError(f"Claim '{claim_id}' was not found.")
        source_agent = self.get_agent(claim.source_agent_id)
        if reviewer.org_id != source_agent.org_id and reviewer.agent_id != claim.source_agent_id:
            raise PermissionDeniedError("Only the claim owner org may review the claim in v0.1.")

        if decision == ReviewDecision.ATTEST:
            claim.validation_status = ValidationStatus.ATTESTED
        elif decision == ReviewDecision.CHALLENGE:
            claim.validation_status = ValidationStatus.CHALLENGED
        else:
            raise ValueError(f"Unsupported review decision '{decision}'.")
        if reason:
            claim.review_reasons.append(reason)
        claim.updated_at = utcnow()
        self.repository.update_claim(claim)

        for review in self.repository.list_review_tasks():
            if review.claim_id == claim.claim_id and review.status == ReviewStatus.OPEN:
                review.status = ReviewStatus.RESOLVED
                review.resolved_at = claim.updated_at
                self.repository.update_review_task(review)

        self._audit(
            "review_claim",
            actor_agent_id=reviewer_agent_id,
            target_agent_id=claim.source_agent_id,
            details={"claim_id": claim_id, "decision": decision},
        )
        return claim

    def list_agents(self, requester_agent_id: str) -> list[Agent]:
        agents = self.repository.list_agents()
        requester = self.get_agent(requester_agent_id)
        return [agent for agent in agents if agent.org_id == requester.org_id]

    def list_review_tasks(self, requester_agent_id: str) -> list[ReviewTask]:
        reviews = self.repository.list_review_tasks()
        requester = self.get_agent(requester_agent_id)
        visible: list[ReviewTask] = []
        for review in reviews:
            claim = self.repository.get_claim(review.claim_id)
            if claim is None:
                continue
            source_agent = self.repository.get_agent(claim.source_agent_id)
            if source_agent is not None and source_agent.org_id == requester.org_id:
                visible.append(review)
        return visible

    def list_review_queue(self, requester_agent_id: str) -> list[ReviewQueueItem]:
        requester = self.get_agent(requester_agent_id)
        queue_items: list[ReviewQueueItem] = []
        for review in self.repository.list_review_tasks():
            if review.status != ReviewStatus.OPEN:
                continue
            claim = self.repository.get_claim(review.claim_id)
            if claim is None:
                continue
            source_agent = self.repository.get_agent(claim.source_agent_id)
            if source_agent is None or source_agent.org_id != requester.org_id:
                continue
            queue_items.append(
                ReviewQueueItem(
                    review=review,
                    claim=claim,
                    source_agent=source_agent,
                )
            )
        return sorted(queue_items, key=lambda item: item.review.created_at, reverse=True)

    def get_claim_for_agent(
        self,
        requester_agent_id: str,
        claim_id: str,
        include_private_same_org: bool = False,
    ) -> Claim:
        requester = self.get_agent(requester_agent_id)
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise NotFoundError(f"Claim '{claim_id}' was not found.")
        if self._can_access_claim(requester, claim, include_private_same_org=include_private_same_org):
            return claim
        raise PermissionDeniedError("Requester cannot access this claim.")

    def list_claims(
        self,
        requester_agent_id: str,
        validation_status: str | None = None,
        include_private_same_org: bool = False,
        only_needing_review: bool = False,
        limit: int = 100,
    ) -> list[Claim]:
        requester = self.get_agent(requester_agent_id)
        open_review_claim_ids = (
            {review.claim_id for review in self.repository.list_review_tasks() if review.status == ReviewStatus.OPEN}
            if only_needing_review
            else None
        )
        status_filter = ValidationStatus(validation_status) if validation_status is not None else None
        claims: list[Claim] = []
        for claim in self.repository.list_claims():
            if not self._can_access_claim(requester, claim, include_private_same_org=include_private_same_org):
                continue
            if status_filter is not None and claim.validation_status != status_filter:
                continue
            if open_review_claim_ids is not None and claim.claim_id not in open_review_claim_ids:
                continue
            claims.append(claim)
        claims.sort(key=lambda item: item.updated_at, reverse=True)
        return claims[:limit]

    def operator_snapshot(self, requester_agent_id: str) -> dict[str, object]:
        requester = self.get_agent(requester_agent_id)
        review_queue = self.list_review_queue(requester.agent_id)
        claims = self.list_claims(
            requester_agent_id=requester.agent_id,
            include_private_same_org=True,
            limit=10_000,
        )
        jobs = self.list_jobs(requester.agent_id)
        status_counts: dict[str, int] = {}
        for job in jobs:
            status_counts[job.status.value] = status_counts.get(job.status.value, 0) + 1
        return {
            "org_id": requester.org_id,
            "pending_review_count": len(review_queue),
            "claim_count": len(claims),
            "expired_claim_count": sum(1 for claim in claims if claim.validation_status == ValidationStatus.EXPIRED),
            "reviewed_claim_count": sum(
                1
                for claim in claims
                if claim.validation_status in {ValidationStatus.ATTESTED, ValidationStatus.CHALLENGED}
            ),
            "job_status_counts": status_counts,
            "health": self.health(),
        }

    def list_audit_entries(self, requester_agent_id: str) -> list[AuditEntry]:
        entries = self.repository.list_audit_entries()
        requester = self.get_agent(requester_agent_id)
        visible: list[AuditEntry] = []
        for entry in entries:
            actor = self.repository.get_agent(entry.actor_agent_id)
            target = self.repository.get_agent(entry.target_agent_id) if entry.target_agent_id else None
            if actor is not None and actor.org_id == requester.org_id:
                visible.append(entry)
                continue
            if target is not None and target.org_id == requester.org_id:
                visible.append(entry)
        return visible

    def health(self) -> dict[str, object]:
        with self._job_lock:
            jobs = list(self._jobs.values())
            scheduled_timers = len(self._timers)
        jobs_by_status: dict[str, int] = {}
        jobs_by_type: dict[str, int] = {}
        for job in jobs:
            jobs_by_status[job.status.value] = jobs_by_status.get(job.status.value, 0) + 1
            jobs_by_type[job.job_type.value] = jobs_by_type.get(job.job_type.value, 0) + 1
        expired_claims = sum(
            1 for claim in self.repository.list_claims() if claim.validation_status == ValidationStatus.EXPIRED
        )
        return {
            "status": "ok",
            "snapshot": self.repository.snapshot(),
            "federation_enabled": self.settings.enable_federation,
            "repository_backend": self.settings.repository_backend,
            "background_worker_enabled": self.settings.enable_background_worker,
            "background_worker_running": self._background_worker.is_running(),
            "queued_jobs": self._background_worker.queued_items(),
            "tracked_jobs": len(jobs),
            "scheduled_timers": scheduled_timers,
            "jobs_by_status": jobs_by_status,
            "jobs_by_type": jobs_by_type,
            "expired_claims": expired_claims,
            "last_claim_expiry_sweep_at": self._last_claim_expiry_sweep_at,
            "last_claim_expiry_sweep_result": dict(self._last_claim_expiry_sweep_result),
            "claim_expiry_sweep_runs": self._claim_expiry_sweep_runs,
            "claims_expired_by_sweeps": self._claims_expired_by_sweeps,
            "delivery_retry_scheduled_total": self._delivery_retry_scheduled_total,
            "delivery_dead_letter_total": self._delivery_dead_letter_total,
        }

    def close(self) -> None:
        self.stop_background_worker()
        self.repository.close()

    def _upsert_entity(self, name: str, entity_type: str) -> Entity:
        now = utcnow()
        entity = Entity(
            entity_id=new_id("ent"),
            name=name,
            entity_type=entity_type,
            alias_key=normalize_alias(name),
            created_at=now,
            updated_at=now,
        )
        return self.repository.upsert_entity(entity)

    def _can_access(self, requester: Agent, claim: Claim) -> bool:
        return self._can_access_claim(requester, claim)

    def _can_access_claim(
        self,
        requester: Agent,
        claim: Claim,
        include_private_same_org: bool = False,
    ) -> bool:
        # Use the granular permissions module
        if can_access_claim(requester.agent_id, requester.org_id, claim):
            return True
        # Legacy: allow same-org to see private claims when reviewing
        if include_private_same_org:
            source_org = claim.source_org_id
            if not source_org:
                source_agent = self.repository.get_agent(claim.source_agent_id)
                source_org = source_agent.org_id if source_agent else ""
            if source_org == requester.org_id:
                return True
        return False

    def _score_claim(self, query: str, claim: Claim) -> float:
        # Use BM25 if the claim is indexed; fall back to Jaccard otherwise
        if self._bm25.has_document(claim.claim_id):
            text_score = self._bm25.score(claim.claim_id, query)
        else:
            text_score = jaccard_similarity(query, claim.statement)

        if text_score == 0:
            return 0.0

        # Normalize BM25 score into roughly [0, 1] range for combination
        # with the other signals. Cap at 1.0.
        if self._bm25.has_document(claim.claim_id):
            text_score = min(text_score / (text_score + 1.0), 1.0)

        freshness = self._freshness_factor(claim)
        validation_bonus = 0.0
        if claim.validation_status == ValidationStatus.ATTESTED:
            validation_bonus = 0.15
        elif claim.validation_status == ValidationStatus.CHALLENGED:
            validation_bonus = -0.2
        elif claim.validation_status == ValidationStatus.EXPIRED:
            validation_bonus = -1.0

        confidence = claim.confidence * 0.2
        return text_score * 0.55 + freshness * 0.1 + confidence + validation_bonus

    def _freshness_factor(self, claim: Claim) -> float:
        now = utcnow()
        if claim.expires_at is None:
            return claim.freshness_score
        if claim.expires_at <= now:
            claim.validation_status = ValidationStatus.EXPIRED
            self.repository.update_claim(claim)
            return 0.0
        total = (claim.expires_at - claim.created_at).total_seconds()
        remaining = (claim.expires_at - now).total_seconds()
        if total <= 0:
            return 0.0
        return max(0.0, min(1.0, remaining / total))

    def _emit_notifications(self, claims: list[Claim]) -> None:
        for query in self.repository.list_queries():
            if query.status != "active":
                continue
            owner = self.repository.get_agent(query.agent_id)
            if owner is None:
                continue
            for claim in claims:
                if not self._matches_standing_query(owner, query, claim):
                    continue
                notification = Notification(
                    notification_id=new_id("ntf"),
                    query_id=query.query_id,
                    agent_id=query.agent_id,
                    claim_id=claim.claim_id,
                    event_type="claim.matched",
                    created_at=utcnow(),
                )
                self.repository.save_notification(notification)
                if query.delivery_mode == DeliveryMode.WEBHOOK:
                    self._enqueue_notification_delivery(
                        owner=owner, query=query, claim=claim, notification=notification
                    )

    def _matches_standing_query(self, owner: Agent, query: StandingQuery, claim: Claim) -> bool:
        if not self._can_access(owner, claim):
            return False
        filters = query.filters
        source_agent_id = filters.get("source_agent_id")
        if source_agent_id and claim.source_agent_id != source_agent_id:
            return False
        claim_type = filters.get("claim_type")
        if claim_type and claim.claim_type != claim_type:
            return False
        validation_status = filters.get("validation_status")
        if validation_status and claim.validation_status.value != validation_status:
            return False
        visibility = filters.get("visibility")
        if visibility and claim.visibility.value != visibility:
            return False
        entity_filter = filters.get("entity")
        if entity_filter:
            entity_alias = normalize_alias(entity_filter)
            claim_entities = [self.repository.get_entity(entity_id) for entity_id in claim.entity_ids]
            if all(entity is None or entity.alias_key != entity_alias for entity in claim_entities):
                return False
        if query.query.strip():
            return jaccard_similarity(query.query, claim.statement) > 0
        return True

    def _process_job(self, job_id: str) -> None:
        with self._job_lock:
            job = self._jobs.get(job_id)
            payload = self._job_payloads.get(job_id)
            if job is None or payload is None:
                return
            if self._is_terminal_job_status(job.status):
                return
            job.status = JobStatus.RUNNING
            job.attempt_count += 1
            job.updated_at = utcnow()
            job.next_run_at = None
            job.error = None
        try:
            if job.job_type == JobType.STORE_MEMORY:
                result_summary = self._process_store_memory_job(payload)
            elif job.job_type == JobType.DELIVER_NOTIFICATION:
                result_summary = self._process_notification_delivery_job(payload)
            elif job.job_type == JobType.SWEEP_EXPIRED_CLAIMS:
                result_summary = self._process_claim_expiry_sweep_job(payload)
            else:
                raise ValueError(f"Unsupported job type '{job.job_type}'.")
        except Exception as exc:
            retry_delay = None
            with self._job_lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                job.updated_at = utcnow()
                job.error = str(exc)
                if job.job_type == JobType.DELIVER_NOTIFICATION and job.attempt_count < job.max_attempts:
                    retry_delay = self._delivery_retry_delay(job.attempt_count)
                    job.status = JobStatus.RETRYING
                    job.next_run_at = job.updated_at + timedelta(seconds=retry_delay)
                elif job.job_type == JobType.DELIVER_NOTIFICATION:
                    job.status = JobStatus.DEAD_LETTERED
                    job.result_summary = {
                        "dead_lettered": True,
                        "attempt_count": job.attempt_count,
                    }
                else:
                    job.status = JobStatus.FAILED
            if job is not None and job.job_type == JobType.DELIVER_NOTIFICATION and retry_delay is not None:
                self._delivery_retry_scheduled_total += 1
                self._audit(
                    "deliver_notification_retry_scheduled",
                    actor_agent_id=job.agent_id,
                    details={
                        "job_id": job_id,
                        "attempt_count": str(job.attempt_count),
                        "retry_in_seconds": f"{retry_delay:.3f}",
                    },
                )
                self._submit_job(job_id, delay_seconds=retry_delay)
                return
            if (
                job is not None
                and job.job_type == JobType.DELIVER_NOTIFICATION
                and job.status == JobStatus.DEAD_LETTERED
            ):
                self._delivery_dead_letter_total += 1
                self._audit(
                    "deliver_notification_dead_letter",
                    actor_agent_id=job.agent_id,
                    details={
                        "job_id": job_id,
                        "error": str(exc)[:200],
                        "attempt_count": str(job.attempt_count),
                    },
                )
                return
            if job is not None and job.job_type == JobType.DELIVER_NOTIFICATION:
                self._audit(
                    "deliver_notification_failed",
                    actor_agent_id=job.agent_id,
                    details={"job_id": job_id, "error": str(exc)[:200]},
                )
            return

        with self._job_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = JobStatus.SUCCEEDED
            job.updated_at = utcnow()
            job.next_run_at = None
            result_summary.setdefault("attempt_count", job.attempt_count)
            job.result_summary = result_summary
            job.error = None
            self._job_payloads.pop(job_id, None)
        if job.job_type == JobType.SWEEP_EXPIRED_CLAIMS and payload.get("recurring"):
            self._schedule_claim_expiry_sweep(self.settings.claim_expiry_sweep_seconds)

    def _create_job(
        self,
        *,
        job_type: JobType,
        owner_agent_id: str,
        owner_org_id: str,
        requester_agent_id: str | None,
        payload_summary: dict[str, Any],
        payload: dict[str, Any],
        max_attempts: int = 1,
        audit_action: str | None = None,
        audit_details: dict[str, str] | None = None,
    ) -> BackgroundJob:
        now = utcnow()
        job = BackgroundJob(
            job_id=new_id("job"),
            job_type=job_type,
            agent_id=owner_agent_id,
            created_at=now,
            updated_at=now,
            org_id=owner_org_id,
            status=JobStatus.QUEUED,
            max_attempts=max(1, max_attempts),
            payload_summary=payload_summary,
        )
        with self._job_lock:
            self._jobs[job.job_id] = job
            self._job_payloads[job.job_id] = dict(payload)
        if audit_action is not None:
            details = dict(audit_details or {})
            details["job_id"] = job.job_id
            self._audit(audit_action, actor_agent_id=owner_agent_id, details=details)
        self._submit_job(job.job_id)
        if requester_agent_id is None:
            return job
        return self.get_job(job.job_id, requester_agent_id=requester_agent_id)

    def _enqueue_notification_delivery(
        self,
        *,
        owner: Agent,
        query: StandingQuery,
        claim: Claim,
        notification: Notification,
    ) -> BackgroundJob:
        webhook_url = query.filters["webhook_url"].strip()
        return self._create_job(
            job_type=JobType.DELIVER_NOTIFICATION,
            owner_agent_id=owner.agent_id,
            owner_org_id=owner.org_id,
            requester_agent_id=owner.agent_id,
            payload_summary={
                "query_id": query.query_id,
                "notification_id": notification.notification_id,
                "delivery_mode": query.delivery_mode.value,
            },
            payload={
                "query_id": query.query_id,
                "claim_id": claim.claim_id,
                "notification_id": notification.notification_id,
                "webhook_url": webhook_url,
            },
            max_attempts=self.settings.delivery_max_attempts,
            audit_action="enqueue_notification_delivery",
            audit_details={"query_id": query.query_id, "notification_id": notification.notification_id},
        )

    def _process_store_memory_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._store_memory_internal(**payload)
        return {
            "memory_id": result.memory.memory_id,
            "claim_count": len(result.claims),
            "entity_count": len(result.entities),
            "review_task_count": len(result.review_tasks),
        }

    def _process_notification_delivery_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = self.repository.get_query(payload["query_id"])
        if query is None:
            raise NotFoundError(f"Standing query '{payload['query_id']}' was not found.")
        notification = self.repository.get_notification(payload["notification_id"])
        if notification is None:
            raise NotFoundError(f"Notification '{payload['notification_id']}' was not found.")
        claim = self.repository.get_claim(payload["claim_id"])
        if claim is None:
            raise NotFoundError(f"Claim '{payload['claim_id']}' was not found.")

        self._notification_dispatcher.dispatch(
            DeliveryRequest(
                notification=notification,
                query=query,
                claim=claim,
                webhook_url=payload["webhook_url"],
            )
        )
        delivered = self.repository.mark_notification_delivered(notification.notification_id)
        if delivered is None:
            raise NotFoundError(f"Notification '{notification.notification_id}' could not be updated.")
        self._audit(
            "deliver_notification",
            actor_agent_id=query.agent_id,
            details={
                "query_id": query.query_id,
                "notification_id": notification.notification_id,
                "delivery_mode": query.delivery_mode.value,
            },
        )
        return {
            "notification_id": notification.notification_id,
            "claim_id": claim.claim_id,
            "delivery_mode": query.delivery_mode.value,
            "delivered": True,
        }

    def _process_claim_expiry_sweep_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = utcnow()
        scanned_claims = 0
        expired_claims = 0
        for claim in self.repository.list_claims():
            scanned_claims += 1
            if claim.expires_at is None or claim.validation_status == ValidationStatus.EXPIRED:
                continue
            if claim.expires_at <= now:
                claim.validation_status = ValidationStatus.EXPIRED
                claim.freshness_score = 0.0
                claim.updated_at = now
                self.repository.update_claim(claim)
                expired_claims += 1
        result = {
            "scanned_claims": scanned_claims,
            "expired_claims": expired_claims,
        }
        self._last_claim_expiry_sweep_at = now
        self._last_claim_expiry_sweep_result = result
        self._claim_expiry_sweep_runs += 1
        self._claims_expired_by_sweeps += expired_claims
        return result

    def _submit_job(self, job_id: str, delay_seconds: float = 0.0) -> None:
        if self._closing:
            return
        if delay_seconds > 0 and self._background_worker.is_running():
            self._schedule_callback(delay_seconds, lambda: self._background_worker.submit(job_id))
            return
        if self._background_worker.is_running():
            self._background_worker.submit(job_id)
            return
        self._process_job(job_id)

    def _schedule_callback(self, delay_seconds: float, callback: Any) -> None:
        if self._closing:
            return
        timer: Timer | None = None

        def run() -> None:
            try:
                if not self._closing:
                    callback()
            finally:
                with self._job_lock:
                    if timer is not None:
                        self._timers.discard(timer)

        timer = Timer(max(0.0, delay_seconds), run)
        timer.daemon = True
        with self._job_lock:
            self._timers.add(timer)
        timer.start()

    def _schedule_claim_expiry_sweep(self, delay_seconds: float) -> None:
        if self._closing or not self.settings.enable_claim_expiry_sweeps:
            return
        self._schedule_callback(
            delay_seconds,
            lambda: self.enqueue_claim_expiry_sweep(recurring=True),
        )

    def _cancel_timers(self) -> None:
        with self._job_lock:
            timers = list(self._timers)
            self._timers.clear()
        for timer in timers:
            timer.cancel()

    def _delivery_retry_delay(self, attempt_count: int) -> float:
        base = max(0.0, self.settings.delivery_retry_base_seconds)
        return base * (2 ** max(0, attempt_count - 1))

    def _is_terminal_job_status(self, status: JobStatus) -> bool:
        return status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.DEAD_LETTERED}

    def _audit(
        self,
        action: str,
        actor_agent_id: str,
        details: dict[str, str],
        target_agent_id: str | None = None,
    ) -> None:
        entry = AuditEntry(
            audit_id=new_id("aud"),
            action=action,
            actor_agent_id=actor_agent_id,
            target_agent_id=target_agent_id,
            details=details,
            timestamp=utcnow(),
        )
        self.repository.save_audit_entry(entry)
