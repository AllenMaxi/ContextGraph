from __future__ import annotations

import logging
import math
from collections import deque
from datetime import datetime, timedelta
from enum import StrEnum
from threading import RLock, Timer
from time import monotonic, sleep
from typing import Any

from .background import BackgroundWorker
from .config import Settings, settings
from .delivery import DeliveryRequest, NotificationDispatcher, WebhookNotificationDispatcher, validate_webhook_url
from .errors import AuthenticationError, ConflictError, NotFoundError, PaymentRequiredError, PermissionDeniedError
from .extraction import Extractor, RuleBasedExtractor
from .identity import AgentIdentity, IdentityVerifier
from .in_memory import InMemoryRepository
from .models import (
    Agent,
    AgentDiscoverability,
    AgentRole,
    AgentStatus,
    AuditEntry,
    BackgroundJob,
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
    Entity,
    JobStatus,
    JobType,
    Memory,
    MemoryCurationStatus,
    MemoryDoctorReport,
    Notification,
    PatternFilter,
    ProvenanceEntry,
    RecallDecision,
    RecallExplanation,
    RecallHit,
    RecallScoreBreakdown,
    RelationPath,
    ReviewQueueItem,
    ReviewStatus,
    ReviewTask,
    SentinelDecision,
    SentinelVerdict,
    Session,
    SessionDiff,
    SessionEvent,
    SessionEventResult,
    SessionResume,
    StandingQuery,
    StoreResult,
    Subscription,
    SubscriptionTarget,
    ValidationStatus,
    Visibility,
)
from .payment import PaymentGate
from .permissions import can_access_claim
from .reactive_delta import (
    SESSION_BUCKETS,
    STATE_SNAPSHOT_VERSION,
    build_restoration_prompt,
    compute_delta_pack_diff,
    default_restoration_instructions,
    flatten_diff_items,
    reduce_session_events,
)
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
        self._normalized_memory_policies: set[str] = set()
        self._background_worker = BackgroundWorker(
            name="contextgraph-worker",
            handler=self._process_job,
            poll_interval_seconds=self.settings.background_worker_poll_seconds,
        )
        self._last_consolidation_result: dict[str, int] = {}
        if self.settings.enable_background_worker:
            self._background_worker.start()
            if self.settings.enable_claim_expiry_sweeps:
                self._schedule_claim_expiry_sweep(self.settings.claim_expiry_sweep_seconds)
            if self.settings.enable_memory_consolidation:
                self._schedule_memory_consolidation(self.settings.memory_consolidation_interval_hours * 3600.0)
        if self.settings.sentinel_enabled:
            self._register_sentinels()

    def _register_sentinels(self) -> None:
        """Register built-in sentinel agents (idempotent)."""
        for name in ("sentinel_duplicate", "sentinel_conflict", "sentinel_quality"):
            existing = [a for a in self.repository.list_agents() if a.name == name and a.org_id == "_system"]
            if existing:
                continue
            now = utcnow()
            sentinel = Agent(
                agent_id=new_id("agt"),
                name=name,
                org_id="_system",
                capabilities=["sentinel"],
                api_key=new_api_key(),
                status=AgentStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                role=AgentRole.SENTINEL,
                last_activity_at=now,
            )
            self.repository.save_agent(sentinel)

    def _get_sentinel_agent(self, name: str) -> Agent | None:
        for agent in self.repository.list_agents():
            if agent.name == name and agent.org_id == "_system" and agent.role == AgentRole.SENTINEL:
                return agent
        return None

    def run_sentinel_audit(self, claim_id: str) -> list[SentinelVerdict]:
        from .sentinel import (
            ConflictSentinel,
            DuplicateSentinel,
            QualitySentinel,
            aggregate_verdicts,
            determine_audit_depth,
        )

        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise NotFoundError(f"Claim '{claim_id}' not found.")

        source_agent = self.get_agent(claim.source_agent_id)
        depth = determine_audit_depth(source_agent, self.settings)

        if depth == "off":
            return []

        now = utcnow()
        verdicts: list[SentinelVerdict] = []
        decisions: list[SentinelDecision] = []

        # Get recent claims for duplicate/conflict checks
        recent_claims = [
            c
            for c in self.repository.list_claims()
            if c.source_agent_id == claim.source_agent_id and c.claim_id != claim.claim_id
        ][-100:]

        # Duplicate check (always runs)
        dup_sentinel = DuplicateSentinel()
        dup_result = dup_sentinel.check(claim, recent_claims)
        dup_agent = self._get_sentinel_agent("sentinel_duplicate")
        if dup_agent:
            verdict = SentinelVerdict(
                verdict_id=new_id("vrd"),
                sentinel_agent_id=dup_agent.agent_id,
                claim_id=claim.claim_id,
                memory_id=claim.memory_id,
                decision=dup_result.decision,
                confidence=dup_result.confidence,
                reason=dup_result.reason,
                conflicting_claim_id=dup_result.conflicting_claim_id,
                details=dict(dup_result.details or {}),
                timestamp=now,
            )
            self.repository.save_sentinel_verdict(verdict)
            verdicts.append(verdict)
            decisions.append(dup_result.decision)

        if depth in ("full", "light"):
            # Conflict check
            validated_claims = [
                c
                for c in self.repository.list_claims()
                if c.validation_status in (ValidationStatus.VALIDATED, ValidationStatus.PENDING)
                and c.claim_id != claim.claim_id
            ]
            conflict_sentinel = ConflictSentinel()
            conflict_result = conflict_sentinel.check(claim, validated_claims)
            conflict_agent = self._get_sentinel_agent("sentinel_conflict")
            if conflict_agent and depth == "full":
                verdict = SentinelVerdict(
                    verdict_id=new_id("vrd"),
                    sentinel_agent_id=conflict_agent.agent_id,
                    claim_id=claim.claim_id,
                    memory_id=claim.memory_id,
                    decision=conflict_result.decision,
                    confidence=conflict_result.confidence,
                    reason=conflict_result.reason,
                    conflicting_claim_id=conflict_result.conflicting_claim_id,
                    details=dict(conflict_result.details or {}),
                    timestamp=now,
                )
                self.repository.save_sentinel_verdict(verdict)
                verdicts.append(verdict)
                decisions.append(conflict_result.decision)

            # Quality check
            quality_sentinel = QualitySentinel()
            quality_result = quality_sentinel.check(claim, source_agent)
            quality_agent = self._get_sentinel_agent("sentinel_quality")
            if quality_agent:
                verdict = SentinelVerdict(
                    verdict_id=new_id("vrd"),
                    sentinel_agent_id=quality_agent.agent_id,
                    claim_id=claim.claim_id,
                    memory_id=claim.memory_id,
                    decision=quality_result.decision,
                    confidence=quality_result.confidence,
                    reason=quality_result.reason,
                    conflicting_claim_id=quality_result.conflicting_claim_id,
                    details=dict(quality_result.details or {}),
                    timestamp=now,
                )
                self.repository.save_sentinel_verdict(verdict)
                verdicts.append(verdict)
                decisions.append(quality_result.decision)

        # Aggregate and apply
        final = aggregate_verdicts(decisions)
        if final == SentinelDecision.VALIDATE:
            claim.validation_status = ValidationStatus.VALIDATED
            claim.validated_at = now
        elif final == SentinelDecision.DISPUTE:
            claim.validation_status = ValidationStatus.DISPUTED
        elif final == SentinelDecision.REJECT:
            claim.validation_status = ValidationStatus.REJECTED
        elif final == SentinelDecision.NEEDS_REVIEW:
            review = ReviewTask(
                task_id=new_id("rev"),
                claim_id=claim.claim_id,
                reason="sentinel_needs_review",
                status=ReviewStatus.OPEN,
                created_at=now,
            )
            self.repository.save_review_task(review)

        claim.updated_at = now
        self.repository.update_claim(claim)
        self._sync_memory_validation(claim.memory_id)

        return verdicts

    def promote_trusted_claims(self) -> int:
        if not self.settings.trust_promotion_enabled:
            return 0
        now = utcnow()
        min_age = timedelta(days=self.settings.trust_promotion_min_age_days)
        min_attestations = self.settings.trust_promotion_min_attestations
        count = 0
        for claim in self.repository.list_claims():
            if claim.validation_status != ValidationStatus.VALIDATED:
                continue
            if claim.validated_at is None:
                continue
            if now - claim.validated_at < min_age:
                continue
            if claim.attestation_count < min_attestations:
                continue
            if claim.challenge_count > 0:
                continue
            claim.validation_status = ValidationStatus.TRUSTED
            claim.updated_at = now
            self.repository.update_claim(claim)
            self._audit(
                "promote_trusted_claim",
                actor_agent_id=claim.source_agent_id,
                details={"claim_id": claim.claim_id, "attestation_count": str(claim.attestation_count)},
            )
            count += 1
        return count

    def list_verdicts_for_claim(self, claim_id: str) -> list[SentinelVerdict]:
        return self.repository.list_verdicts_for_claim(claim_id)

    def list_verdicts(self, limit: int = 100, decision: str | None = None) -> list[SentinelVerdict]:
        return self.repository.list_verdicts(limit, decision)

    def register_agent(
        self,
        name: str,
        org_id: str,
        capabilities: list[str] | None = None,
        admin_key: str | None = None,
        erc8004_address: str = "",
        default_visibility: str | None = None,
        default_access_list: list[str] | None = None,
        default_price: float | None = None,
    ) -> Agent:
        configured_admin_key = self.settings.admin_key
        if configured_admin_key and (not admin_key or admin_key != configured_admin_key):
            raise PermissionDeniedError("Agent registration requires a valid admin key when CG_ADMIN_KEY is set.")
        resolved_default_visibility, resolved_default_access_list, resolved_default_price = self._resolve_policy_fields(
            visibility=default_visibility,
            access_list=default_access_list,
            price=default_price,
            fallback_visibility=Visibility.PRIVATE,
            fallback_access_list=[],
            fallback_price=0.0,
        )
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
            default_visibility=resolved_default_visibility,
            default_access_list=resolved_default_access_list,
            default_price=resolved_default_price,
            profile_visibility=AgentDiscoverability.ORG,
            last_activity_at=now,
            role="agent",
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
        if agent.status == AgentStatus.DELETED:
            raise PermissionDeniedError(f"Agent '{agent.agent_id}' has been deleted.")
        if agent.status == AgentStatus.SUSPENDED:
            if agent.suspension_reason == "idle":
                # Auto-wake: transparent reactivation (virtual actor pattern)
                agent.status = AgentStatus.ACTIVE
                agent.suspension_reason = None
                agent.suspended_at = None
                agent.last_activity_at = utcnow()
                agent.updated_at = utcnow()
                self.repository.save_agent(agent)
                self._audit(
                    "auto_reactivation",
                    actor_agent_id=agent.agent_id,
                    details={"reason": "idle_agent_api_call"},
                )
                return agent
            raise PermissionDeniedError(
                f"Agent '{agent.agent_id}' is suspended: {agent.suspension_reason or 'no reason provided'}. "
                "Contact your admin to reactivate."
            )
        # Update last activity
        agent.last_activity_at = utcnow()
        self.repository.save_agent(agent)
        return agent

    def update_agent_defaults(
        self,
        requester_agent_id: str,
        agent_id: str,
        default_visibility: str | None = None,
        default_access_list: list[str] | None = None,
        default_price: float | None = None,
    ) -> Agent:
        requester = self.get_agent(requester_agent_id)
        if requester.agent_id != agent_id:
            raise PermissionDeniedError("Agents may only update their own default memory policy.")

        resolved_visibility, resolved_access_list, resolved_price = self._resolve_policy_fields(
            visibility=default_visibility,
            access_list=default_access_list,
            price=default_price,
            fallback_visibility=requester.default_visibility,
            fallback_access_list=requester.default_access_list,
            fallback_price=requester.default_price,
        )
        requester.default_visibility = resolved_visibility
        requester.default_access_list = resolved_access_list
        requester.default_price = resolved_price
        requester.updated_at = utcnow()
        self.repository.save_agent(requester)
        self._audit(
            "update_agent_defaults",
            actor_agent_id=requester.agent_id,
            details={"agent_id": requester.agent_id},
        )
        return requester

    def suspend_agent(self, requester_agent_id: str, agent_id: str, reason: str = "manual") -> Agent:
        agent = self.get_agent(agent_id)
        if agent.status == AgentStatus.DELETED:
            raise PermissionDeniedError("Cannot suspend a deleted agent.")
        if agent.status == AgentStatus.SUSPENDED:
            return agent
        now = utcnow()
        agent.status = AgentStatus.SUSPENDED
        agent.suspension_reason = reason
        agent.suspended_at = now
        agent.updated_at = now
        self.repository.save_agent(agent)
        self._audit(
            "suspend_agent",
            actor_agent_id=requester_agent_id,
            target_agent_id=agent_id,
            details={"reason": reason},
        )
        return agent

    def reactivate_agent(self, requester_agent_id: str, agent_id: str) -> Agent:
        agent = self.get_agent(agent_id)
        if agent.status == AgentStatus.DELETED:
            raise PermissionDeniedError("Cannot reactivate a deleted agent.")
        if agent.status == AgentStatus.ACTIVE:
            return agent
        now = utcnow()
        agent.status = AgentStatus.ACTIVE
        agent.suspension_reason = None
        agent.suspended_at = None
        agent.last_activity_at = now
        agent.updated_at = now
        self.repository.save_agent(agent)
        self._audit(
            "reactivate_agent",
            actor_agent_id=requester_agent_id,
            target_agent_id=agent_id,
            details={},
        )
        return agent

    def delete_agent(self, requester_agent_id: str, agent_id: str) -> Agent:
        agent = self.get_agent(agent_id)
        if agent.status == AgentStatus.DELETED:
            return agent
        now = utcnow()
        agent.status = AgentStatus.DELETED
        agent.updated_at = now
        self.repository.save_agent(agent)
        self._audit(
            "delete_agent",
            actor_agent_id=requester_agent_id,
            target_agent_id=agent_id,
            details={},
        )
        return agent

    def sweep_idle_agents(self) -> int:
        threshold = utcnow() - timedelta(days=self.settings.agent_idle_threshold_days)
        agents = self.repository.list_agents()
        count = 0
        for agent in agents:
            if agent.status != AgentStatus.ACTIVE:
                continue
            if agent.role == AgentRole.SENTINEL:
                continue
            activity = agent.last_activity_at or agent.created_at
            if activity < threshold:
                self.suspend_agent(agent.agent_id, agent.agent_id, reason="idle")
                count += 1
        return count

    def _resolve_policy_fields(
        self,
        *,
        visibility: str | Visibility | None,
        access_list: list[str] | None,
        price: float | None,
        fallback_visibility: str | Visibility,
        fallback_access_list: list[str] | None,
        fallback_price: float,
    ) -> tuple[Visibility, list[str], float]:
        resolved_visibility = self._coerce_visibility(visibility, fallback_visibility)
        resolved_price = fallback_price if price is None else price
        if resolved_price < 0:
            raise ValueError("Price must be greater than or equal to 0.")

        fallback_acl = self._dedupe_access_list(fallback_access_list or [])
        raw_access_list = fallback_acl if access_list is None else self._dedupe_access_list(access_list)
        resolved_access_list = raw_access_list if resolved_visibility == Visibility.SHARED else []
        if resolved_visibility == Visibility.SHARED and not resolved_access_list:
            raise ValueError("Shared visibility requires a non-empty access_list.")
        return resolved_visibility, resolved_access_list, resolved_price

    def _coerce_visibility(
        self,
        visibility: str | Visibility | None,
        fallback_visibility: str | Visibility,
    ) -> Visibility:
        candidate = fallback_visibility if visibility is None else visibility
        if isinstance(candidate, Visibility):
            return candidate
        return Visibility(candidate)

    def _resolve_profile_fields(
        self,
        *,
        profile_visibility: str | AgentDiscoverability | None,
        profile_access_list: list[str] | None,
        profile_summary: str | None,
        profile_links: dict[str, str] | None,
        fallback_visibility: str | AgentDiscoverability,
        fallback_access_list: list[str] | None,
        fallback_summary: str,
        fallback_links: dict[str, str] | None,
    ) -> tuple[AgentDiscoverability, list[str], str, dict[str, str]]:
        resolved_visibility = self._coerce_profile_visibility(profile_visibility, fallback_visibility)
        fallback_acl = self._dedupe_access_list(fallback_access_list or [])
        raw_access_list = fallback_acl if profile_access_list is None else self._dedupe_access_list(profile_access_list)
        resolved_access_list = raw_access_list if resolved_visibility == AgentDiscoverability.SHARED else []
        if resolved_visibility == AgentDiscoverability.SHARED and not resolved_access_list:
            raise ValueError("Shared profile visibility requires a non-empty profile_access_list.")

        resolved_summary = fallback_summary if profile_summary is None else profile_summary.strip()
        if len(resolved_summary) > 500:
            raise ValueError("Profile summary must be 500 characters or fewer.")

        resolved_links = self._sanitize_profile_links(fallback_links if profile_links is None else profile_links)
        return resolved_visibility, resolved_access_list, resolved_summary, resolved_links

    def _coerce_profile_visibility(
        self,
        profile_visibility: str | AgentDiscoverability | None,
        fallback_visibility: str | AgentDiscoverability,
    ) -> AgentDiscoverability:
        candidate = fallback_visibility if profile_visibility is None else profile_visibility
        if isinstance(candidate, AgentDiscoverability):
            return candidate
        return AgentDiscoverability(candidate)

    def _dedupe_access_list(self, access_list: list[str]) -> list[str]:
        return [item for item in dict.fromkeys(access_list) if item]

    def _dedupe_strings(self, values: list[str] | None) -> list[str]:
        return [item.strip() for item in dict.fromkeys(values or []) if item and item.strip()]

    def _sanitize_profile_links(self, profile_links: dict[str, str] | None) -> dict[str, str]:
        cleaned: dict[str, str] = {}
        for raw_label, raw_url in dict(profile_links or {}).items():
            label = raw_label.strip()
            url = raw_url.strip()
            if not label or not url:
                continue
            if not url.startswith(("http://", "https://")):
                raise ValueError("Profile links must use http:// or https:// URLs.")
            cleaned[label] = url
        return cleaned

    def _derive_provenance(
        self,
        agent: Agent,
        metadata: dict[str, str] | None,
        evidence: list[str] | None,
        citations: list[str] | None,
    ) -> tuple[list[str], list[str]]:
        metadata = dict(metadata or {})
        evidence_items = [f"source_agent:{agent.agent_id}", f"source_org:{agent.org_id}"]
        citation_items: list[str] = []
        for key, value in metadata.items():
            if not value:
                continue
            label = f"{key}:{value}"
            lower_key = key.lower()
            if any(token in lower_key for token in ("url", "uri", "file", "path", "ref", "ticket", "doc", "commit")):
                citation_items.append(label)
                continue
            if "source" in lower_key or "evidence" in lower_key:
                evidence_items.append(label)
        evidence_items.extend(evidence or [])
        citation_items.extend(citations or [])
        return self._dedupe_strings(evidence_items), self._dedupe_strings(citation_items)

    def _resolve_expires_at(self, now: datetime, expires_in_days: int | None) -> datetime | None:
        ttl_days = self.settings.default_claim_ttl_days if expires_in_days is None else expires_in_days
        if ttl_days <= 0:
            return None
        return now + timedelta(days=ttl_days)

    def _memory_is_active(self, memory: Memory) -> bool:
        return memory.curation_status == MemoryCurationStatus.ACTIVE

    def _can_curate_memory(self, requester: Agent, memory: Memory) -> bool:
        source_agent = self.repository.get_agent(memory.agent_id)
        if requester.agent_id == memory.agent_id:
            return True
        return source_agent is not None and source_agent.org_id == requester.org_id

    def _sync_memory_validation(self, memory_id: str, claims: list[Claim] | None = None) -> Memory | None:
        memory = self.repository.get_memory(memory_id)
        if memory is None:
            return None
        sibling_claims = claims if claims is not None else self.repository.list_claims_for_memory(memory_id)
        if not sibling_claims:
            memory.validation_status = ValidationStatus.UNREVIEWED
            memory.validated_at = None
            memory.expires_at = None
            memory.updated_at = utcnow()
            self.repository.update_memory(memory)
            return memory

        if all(claim.validation_status == ValidationStatus.EXPIRED for claim in sibling_claims):
            memory.validation_status = ValidationStatus.EXPIRED
        elif any(claim.validation_status == ValidationStatus.CHALLENGED for claim in sibling_claims):
            memory.validation_status = ValidationStatus.CHALLENGED
        elif any(claim.validation_status == ValidationStatus.ATTESTED for claim in sibling_claims):
            memory.validation_status = ValidationStatus.ATTESTED
        else:
            memory.validation_status = ValidationStatus.UNREVIEWED

        validated_times = [claim.validated_at for claim in sibling_claims if claim.validated_at is not None]
        expiries = [claim.expires_at for claim in sibling_claims if claim.expires_at is not None]
        memory.validated_at = max(validated_times) if validated_times else None
        memory.expires_at = max(expiries) if expiries else None
        memory.updated_at = utcnow()
        self.repository.update_memory(memory)
        return memory

    def store_memory(
        self,
        agent_id: str,
        content: str,
        visibility: str | None = None,
        license: str = "internal",
        metadata: dict[str, str] | None = None,
        evidence: list[str] | None = None,
        citations: list[str] | None = None,
        source_type: str | None = None,
        source_uri: str | None = None,
        source_label: str | None = None,
        section_refs: list[str] | None = None,
        ingest_metadata: dict[str, str] | None = None,
        access_list: list[str] | None = None,
        price: float | None = None,
        expires_in_days: int | None = None,
    ) -> StoreResult:
        agent = self.get_agent(agent_id)
        resolved_visibility, resolved_access_list, resolved_price = self._resolve_policy_fields(
            visibility=visibility,
            access_list=access_list,
            price=price,
            fallback_visibility=agent.default_visibility,
            fallback_access_list=agent.default_access_list,
            fallback_price=agent.default_price,
        )
        return self._store_memory_internal(
            agent_id=agent_id,
            content=content,
            visibility=resolved_visibility.value,
            license=license,
            metadata=metadata,
            evidence=evidence,
            citations=citations,
            source_type=source_type,
            source_uri=source_uri,
            source_label=source_label,
            section_refs=section_refs,
            ingest_metadata=ingest_metadata,
            access_list=resolved_access_list,
            price=resolved_price,
            expires_in_days=expires_in_days,
        )

    def enqueue_memory_store(
        self,
        agent_id: str,
        content: str,
        visibility: str | None = None,
        license: str = "internal",
        metadata: dict[str, str] | None = None,
        evidence: list[str] | None = None,
        citations: list[str] | None = None,
        source_type: str | None = None,
        source_uri: str | None = None,
        source_label: str | None = None,
        section_refs: list[str] | None = None,
        ingest_metadata: dict[str, str] | None = None,
        access_list: list[str] | None = None,
        price: float | None = None,
        expires_in_days: int | None = None,
    ) -> BackgroundJob:
        agent = self.get_agent(agent_id)
        resolved_visibility, resolved_access_list, resolved_price = self._resolve_policy_fields(
            visibility=visibility,
            access_list=access_list,
            price=price,
            fallback_visibility=agent.default_visibility,
            fallback_access_list=agent.default_access_list,
            fallback_price=agent.default_price,
        )
        return self._create_job(
            job_type=JobType.STORE_MEMORY,
            owner_agent_id=agent.agent_id,
            owner_org_id=agent.org_id,
            requester_agent_id=agent.agent_id,
            payload_summary={
                "visibility": resolved_visibility.value,
                "license": license,
                "price": f"{resolved_price:.4f}",
                "expires_in_days": str(
                    expires_in_days if expires_in_days is not None else self.settings.default_claim_ttl_days
                ),
                "content_preview": content.strip()[:120],
            },
            payload={
                "agent_id": agent_id,
                "content": content,
                "visibility": resolved_visibility.value,
                "license": license,
                "metadata": dict(metadata or {}),
                "evidence": list(evidence or []),
                "citations": list(citations or []),
                "source_type": source_type or "",
                "source_uri": source_uri or "",
                "source_label": source_label or "",
                "section_refs": list(section_refs or []),
                "ingest_metadata": dict(ingest_metadata or {}),
                "access_list": resolved_access_list,
                "price": resolved_price,
                "expires_in_days": expires_in_days,
            },
            max_attempts=1,
            audit_action="enqueue_memory_store",
            audit_details={"visibility": resolved_visibility.value},
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

    # ------------------------------------------------------------------
    # Impact classification & provenance helpers
    # ------------------------------------------------------------------

    def _classify_impact(self, visibility: Visibility, price: float, entity_count: int) -> ClaimImpact:
        if price > 0 and visibility == Visibility.PUBLISHED and entity_count >= 3:
            return ClaimImpact.CRITICAL
        if price > 0 or (visibility == Visibility.PUBLISHED and entity_count >= 2):
            return ClaimImpact.HIGH
        if visibility in (Visibility.SHARED, Visibility.PUBLISHED) and entity_count >= 1:
            return ClaimImpact.MEDIUM
        return ClaimImpact.LOW

    def _default_quorum(self, impact: ClaimImpact) -> int:
        if impact == ClaimImpact.CRITICAL:
            return 2
        if impact == ClaimImpact.HIGH:
            return 2
        return 0

    def _make_provenance_entry(
        self, agent_id: str, action: str, confidence: float, detail: str = ""
    ) -> ProvenanceEntry:
        return ProvenanceEntry(
            agent_id=agent_id,
            action=action,
            timestamp=utcnow(),
            confidence_at_action=confidence,
            detail=detail,
        )

    def _store_memory_internal(
        self,
        agent_id: str,
        content: str,
        visibility: str = "private",
        license: str = "internal",
        metadata: dict[str, str] | None = None,
        evidence: list[str] | None = None,
        citations: list[str] | None = None,
        source_type: str | None = None,
        source_uri: str | None = None,
        source_label: str | None = None,
        section_refs: list[str] | None = None,
        ingest_metadata: dict[str, str] | None = None,
        access_list: list[str] | None = None,
        price: float = 0.0,
        expires_in_days: int | None = None,
    ) -> StoreResult:
        agent = self.get_agent(agent_id)
        now = utcnow()
        visibility_enum = Visibility(visibility)
        evidence_items, citation_items = self._derive_provenance(agent, metadata, evidence, citations)
        expires_at = self._resolve_expires_at(now, expires_in_days)
        memory = Memory(
            memory_id=new_id("mem"),
            agent_id=agent.agent_id,
            content=content.strip(),
            visibility=visibility_enum,
            validation_status=ValidationStatus.UNREVIEWED,
            license=license,
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
            access_list=list(access_list or []),
            price=price,
            evidence=evidence_items,
            citations=citation_items,
            validated_at=None,
            expires_at=expires_at,
            curation_status=MemoryCurationStatus.ACTIVE,
            curation_reason="",
            curated_at=None,
            source_type=(source_type or "").strip(),
            source_uri=(source_uri or "").strip(),
            source_label=(source_label or "").strip(),
            section_refs=list(section_refs or []),
            ingest_metadata=dict(ingest_metadata or {}),
        )
        self.repository.save_memory(memory)

        created_entities: dict[str, Entity] = {}
        created_claims: list[Claim] = []
        review_tasks: list[ReviewTask] = []

        for extracted in self.extractor.extract(content):
            entity_ids: list[str] = []
            for raw_entity in extracted.entities:
                entity = self._upsert_entity(raw_entity.name, raw_entity.entity_type)
                created_entities[entity.entity_id] = entity
                entity_ids.append(entity.entity_id)

            impact = self._classify_impact(visibility_enum, price, len(entity_ids))
            quorum_required = self._default_quorum(impact)
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
                evidence=list(evidence_items),
                citations=list(citation_items),
                validated_at=None,
                provenance=[self._make_provenance_entry(agent.agent_id, "created", extracted.confidence)],
                impact=impact,
                quorum_required=quorum_required,
                quorum_met=quorum_required == 0,
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
        self._normalized_memory_policies.add(memory.memory_id)

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
        candidates = self._search_recall_candidates(
            query=query,
            candidate_limit=self._recall_candidate_limit(limit=limit),
            requester=requester,
        )
        hits: list[RecallHit] = []
        payment_blocked_error: PaymentRequiredError | None = None
        for candidate in candidates:
            _, hit, payment_error = self._evaluate_recall_candidate(
                requester=requester,
                query=query,
                claim=candidate.claim,
                payment_gate=payment_gate,
                payment_token=payment_token,
                text_score_raw=candidate.text_score_raw,
            )
            if payment_blocked_error is None and payment_error is not None:
                payment_blocked_error = payment_error
            if hit is not None:
                hits.append(hit)
        hits.sort(key=lambda item: item.score, reverse=True)
        self._audit("recall", actor_agent_id=agent_id, details={"query": query, "limit": str(limit)})
        if not hits and payment_blocked_error is not None:
            raise payment_blocked_error
        return hits[:limit]

    def explain_recall(
        self,
        agent_id: str,
        query: str,
        limit: int = 10,
        payment_token: str | None = None,
        decision_limit: int = 25,
    ) -> RecallExplanation:
        requester = self.get_agent(agent_id)
        payment_gate = PaymentGate(enabled=self.settings.enable_payments, currency=self.settings.payment_currency)
        candidates = self._search_recall_candidates(
            query=query,
            candidate_limit=self._recall_candidate_limit(limit=limit, decision_limit=decision_limit),
        )

        hits: list[RecallHit] = []
        decisions: list[RecallDecision] = []
        filtered_counts: dict[str, int] = {}

        for candidate in candidates:
            decision, hit, _ = self._evaluate_recall_candidate(
                requester=requester,
                query=query,
                claim=candidate.claim,
                payment_gate=payment_gate,
                payment_token=payment_token,
                text_score_raw=candidate.text_score_raw,
            )
            if hit is not None:
                hits.append(hit)
            if decision.outcome != "hit":
                for reason in decision.reasons:
                    filtered_counts[reason] = filtered_counts.get(reason, 0) + 1
            if decision.reasons == ["access_denied"]:
                continue
            if len(decisions) < max(1, decision_limit):
                decisions.append(decision)

        hits.sort(key=lambda item: item.score, reverse=True)
        decisions.sort(key=lambda item: (item.outcome == "hit", item.score), reverse=True)
        self._audit(
            "explain_recall",
            actor_agent_id=agent_id,
            details={"query": query, "limit": str(limit), "decision_limit": str(decision_limit)},
        )
        return RecallExplanation(
            query=query,
            total_claims=self.repository.snapshot().get("claims", len(candidates)),
            hits=hits[:limit],
            decisions=decisions,
            filtered_counts=filtered_counts,
        )

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
        pattern: dict[str, Any] | None = None,
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
        # Build pattern filter if provided
        pattern_filter: PatternFilter | None = None
        if pattern:
            pattern_filter = PatternFilter(
                entities=pattern.get("entities", []),
                entity_types=pattern.get("entity_types", []),
                relation_types=pattern.get("relation_types", []),
                min_confidence=float(pattern.get("min_confidence", 0.0)),
                source_org_ids=pattern.get("source_org_ids", []),
                visibility_levels=pattern.get("visibility_levels", []),
            )
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
            pattern=pattern_filter,
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
            claim.attestation_count += 1
        elif decision == ReviewDecision.CHALLENGE:
            claim.validation_status = ValidationStatus.CHALLENGED
            claim.challenge_count += 1
            # Challenges reset quorum progress
            claim.quorum_met = False
        else:
            raise ValueError(f"Unsupported review decision '{decision}'.")
        if reason:
            claim.review_reasons.append(reason)
        claim.validated_at = utcnow()
        claim.updated_at = claim.validated_at
        # Append provenance entry
        claim.provenance.append(
            self._make_provenance_entry(reviewer_agent_id, decision, claim.confidence, detail=reason)
        )
        # Check quorum
        if claim.quorum_required > 0 and claim.attestation_count >= claim.quorum_required:
            claim.quorum_met = True
        self.repository.update_claim(claim)
        self._sync_memory_validation(claim.memory_id)

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

        # Recalculate source agent reputation
        source_agent = self.get_agent(claim.source_agent_id)
        source_agent.reputation_score = self.calculate_reputation_score(claim.source_agent_id)
        self.repository.save_agent(source_agent)

        return claim

    def update_claim(
        self,
        requester_agent_id: str,
        claim_id: str,
        visibility: str | None = None,
        price: float | None = None,
        access_list: list[str] | None = None,
    ) -> Claim:
        self.get_agent(requester_agent_id)
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            raise NotFoundError(f"Claim '{claim_id}' not found.")
        memory = self.update_memory_access(
            requester_agent_id=requester_agent_id,
            memory_id=claim.memory_id,
            visibility=visibility,
            price=price,
            access_list=access_list,
            audit_action="update_claim",
            audit_target=claim_id,
        )
        updated_claim = self.repository.get_claim(claim_id)
        if updated_claim is None:
            raise NotFoundError(f"Claim '{claim_id}' not found after update.")
        self._normalized_memory_policies.add(memory.memory_id)
        return updated_claim

    def update_memory_access(
        self,
        requester_agent_id: str,
        memory_id: str,
        visibility: str | None = None,
        price: float | None = None,
        access_list: list[str] | None = None,
        audit_action: str = "update_memory_access",
        audit_target: str | None = None,
    ) -> Memory:
        self.get_agent(requester_agent_id)
        memory = self.repository.get_memory(memory_id)
        if memory is None:
            raise NotFoundError(f"Memory '{memory_id}' not found.")
        if memory.agent_id != requester_agent_id:
            raise PermissionDeniedError("Only the source agent can update a memory policy.")
        resolved_visibility, resolved_access_list, resolved_price = self._resolve_policy_fields(
            visibility=visibility,
            access_list=access_list,
            price=price,
            fallback_visibility=memory.visibility,
            fallback_access_list=memory.access_list,
            fallback_price=memory.price,
        )
        memory.visibility = resolved_visibility
        memory.access_list = resolved_access_list
        memory.price = resolved_price

        memory.updated_at = utcnow()
        self.repository.update_memory(memory)
        claims = self._normalize_memory_policy(memory.memory_id, force=True, audit=False)
        self._audit(
            audit_action,
            actor_agent_id=requester_agent_id,
            details={"memory_id": memory_id, "target_id": audit_target or memory_id},
        )
        if claims:
            self._emit_notifications(claims)
        self._normalized_memory_policies.add(memory.memory_id)
        return memory

    def update_memory_curation(
        self,
        requester_agent_id: str,
        memory_id: str,
        curation_status: str,
        reason: str = "",
    ) -> Memory:
        requester = self.get_agent(requester_agent_id)
        memory = self.repository.get_memory(memory_id)
        if memory is None:
            raise NotFoundError(f"Memory '{memory_id}' not found.")
        if not self._can_curate_memory(requester, memory):
            raise PermissionDeniedError("Only the source agent or source org may curate this memory.")
        memory.curation_status = MemoryCurationStatus(curation_status)
        memory.curation_reason = reason.strip()
        memory.curated_at = utcnow()
        memory.updated_at = memory.curated_at
        self.repository.update_memory(memory)
        self._audit(
            "update_memory_curation",
            actor_agent_id=requester_agent_id,
            details={
                "memory_id": memory_id,
                "curation_status": memory.curation_status.value,
                "reason": memory.curation_reason,
            },
        )
        return memory

    def list_agents(self, requester_agent_id: str) -> list[Agent]:
        agents = self.repository.list_agents()
        requester = self.get_agent(requester_agent_id)
        return [agent for agent in agents if agent.org_id == requester.org_id]

    def discover_agents(
        self,
        requester_agent_id: str,
        q: str = "",
        status: str | None = None,
        min_reputation: float = 0.0,
        org_id: str | None = None,
        visibility: str | None = None,
        sort_by: str = "reputation",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, object]:
        requester = self.get_agent(requester_agent_id)
        query = q.strip().lower()
        visibility_filter = AgentDiscoverability(visibility) if visibility else None
        sort_options = {"reputation", "followers", "created_at", "name"}
        if sort_by not in sort_options:
            raise ValueError(f"Unsupported sort_by '{sort_by}'.")

        candidates: list[Agent] = []
        for agent in self.repository.list_agents():
            if agent.role == AgentRole.SENTINEL or agent.status == AgentStatus.DELETED:
                continue
            if not self._can_view_agent_profile(requester, agent):
                continue
            if status is not None and agent.status != status:
                continue
            if org_id is not None and agent.org_id != org_id:
                continue
            if agent.reputation_score < min_reputation:
                continue
            if visibility_filter is not None and agent.profile_visibility != visibility_filter:
                continue
            if query:
                haystack = " ".join(
                    [
                        agent.name.lower(),
                        agent.org_id.lower(),
                        " ".join(cap.lower() for cap in agent.capabilities),
                        agent.profile_summary.lower(),
                    ]
                )
                if query not in haystack:
                    continue
            candidates.append(agent)

        if sort_by == "followers":
            candidates.sort(
                key=lambda item: (item.followers_count, item.reputation_score, item.created_at), reverse=True
            )
        elif sort_by == "created_at":
            candidates.sort(key=lambda item: item.created_at, reverse=True)
        elif sort_by == "name":
            candidates.sort(key=lambda item: (item.name.lower(), item.created_at))
        else:
            candidates.sort(
                key=lambda item: (item.reputation_score, item.followers_count, item.created_at),
                reverse=True,
            )

        total = len(candidates)
        page = candidates[max(offset, 0) : max(offset, 0) + min(max(limit, 1), 100)]
        return {
            "items": [self._serialize_agent_profile(requester, agent) for agent in page],
            "total": total,
            "limit": min(max(limit, 1), 100),
            "offset": max(offset, 0),
        }

    def get_agent_profile(self, requester_agent_id: str, agent_id: str) -> dict[str, Any]:
        requester = self.get_agent(requester_agent_id)
        agent = self._get_visible_agent_for_requester(requester, agent_id)
        return self._serialize_agent_profile(requester, agent)

    def update_agent_profile(
        self,
        requester_agent_id: str,
        agent_id: str,
        profile_visibility: str | None = None,
        profile_access_list: list[str] | None = None,
        profile_summary: str | None = None,
        profile_links: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        requester = self.get_agent(requester_agent_id)
        if requester.agent_id != agent_id:
            raise PermissionDeniedError("Agents may only update their own discovery profile.")

        resolved_visibility, resolved_access_list, resolved_summary, resolved_links = self._resolve_profile_fields(
            profile_visibility=profile_visibility,
            profile_access_list=profile_access_list,
            profile_summary=profile_summary,
            profile_links=profile_links,
            fallback_visibility=requester.profile_visibility,
            fallback_access_list=requester.profile_access_list,
            fallback_summary=requester.profile_summary,
            fallback_links=requester.profile_links,
        )
        requester.profile_visibility = resolved_visibility
        requester.profile_access_list = resolved_access_list
        requester.profile_summary = resolved_summary
        requester.profile_links = resolved_links
        requester.updated_at = utcnow()
        self.repository.save_agent(requester)
        self._audit(
            "update_agent_profile",
            actor_agent_id=requester.agent_id,
            details={
                "agent_id": requester.agent_id,
                "profile_visibility": requester.profile_visibility.value,
            },
        )
        return self._serialize_agent_profile(requester, requester)

    def list_agent_claims(
        self,
        requester_agent_id: str,
        agent_id: str,
        limit: int = 100,
    ) -> list[Claim]:
        requester = self.get_agent(requester_agent_id)
        target = self._get_visible_agent_for_requester(requester, agent_id)
        include_private_same_org = requester.org_id == target.org_id
        claims = [
            claim
            for claim in self._list_claims_with_normalized_policies()
            if claim.source_agent_id == target.agent_id
            and self._can_access_claim(requester, claim, include_private_same_org=include_private_same_org)
        ]
        claims.sort(key=lambda item: item.updated_at, reverse=True)
        return claims[:limit]

    def get_agent_activity(
        self,
        requester_agent_id: str,
        agent_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, object]:
        requester = self.get_agent(requester_agent_id)
        target = self._get_visible_agent_for_requester(requester, agent_id)
        include_private_same_org = requester.org_id == target.org_id
        visible_claims = [
            claim
            for claim in self._list_claims_with_normalized_policies()
            if claim.source_agent_id == target.agent_id
            and self._can_access_claim(requester, claim, include_private_same_org=include_private_same_org)
        ]

        items: list[dict[str, Any]] = []
        for claim in visible_claims:
            items.append(
                {
                    "event_type": "claim_created",
                    "timestamp": claim.created_at,
                    "claim": self._serialize_claim_summary(claim),
                    "verdict": None,
                    "audit": None,
                    "details": {
                        "validation_status": claim.validation_status.value,
                        "visibility": claim.visibility.value,
                    },
                }
            )
            for verdict in self.repository.list_verdicts_for_claim(claim.claim_id):
                items.append(
                    {
                        "event_type": "sentinel_verdict",
                        "timestamp": verdict.timestamp,
                        "claim": self._serialize_claim_summary(claim),
                        "verdict": self._serialize_verdict_summary(verdict),
                        "audit": None,
                        "details": {"decision": verdict.decision.value},
                    }
                )

        if include_private_same_org:
            for entry in self.repository.list_audit_entries():
                if entry.actor_agent_id != target.agent_id and entry.target_agent_id != target.agent_id:
                    continue
                items.append(
                    {
                        "event_type": entry.action,
                        "timestamp": entry.timestamp,
                        "claim": None,
                        "verdict": None,
                        "audit": {
                            "audit_id": entry.audit_id,
                            "action": entry.action,
                            "actor_agent_id": entry.actor_agent_id,
                            "target_agent_id": entry.target_agent_id,
                            "details": dict(entry.details),
                        },
                        "details": dict(entry.details),
                    }
                )

        items.sort(key=lambda item: item["timestamp"], reverse=True)
        total = len(items)
        page = items[max(offset, 0) : max(offset, 0) + min(max(limit, 1), 100)]
        return {
            "items": page,
            "total": total,
            "limit": min(max(limit, 1), 100),
            "offset": max(offset, 0),
        }

    def get_agent_trust_summary(self, requester_agent_id: str, agent_id: str) -> dict[str, Any]:
        requester = self.get_agent(requester_agent_id)
        target = self._get_visible_agent_for_requester(requester, agent_id)
        visible_claims = self.list_agent_claims(
            requester_agent_id=requester.agent_id, agent_id=target.agent_id, limit=10_000
        )
        verdict_count = sum(len(self.repository.list_verdicts_for_claim(claim.claim_id)) for claim in visible_claims)
        return {
            "agent_id": target.agent_id,
            "reputation_score": target.reputation_score,
            "total_claims": len(visible_claims),
            "attested_claims": sum(
                1 for claim in visible_claims if claim.validation_status == ValidationStatus.ATTESTED
            ),
            "challenged_claims": sum(
                1 for claim in visible_claims if claim.validation_status == ValidationStatus.CHALLENGED
            ),
            "unreviewed_claims": sum(
                1 for claim in visible_claims if claim.validation_status == ValidationStatus.UNREVIEWED
            ),
            "followers_count": target.followers_count,
            "sentinel_verdict_count": verdict_count,
            "status": target.status,
        }

    def get_memory_for_agent(
        self,
        requester_agent_id: str,
        memory_id: str,
        include_private_same_org: bool = False,
        include_inactive: bool = False,
    ) -> Memory:
        requester = self.get_agent(requester_agent_id)
        memory = self._get_memory_with_normalized_policy(memory_id)
        if memory is None:
            raise NotFoundError(f"Memory '{memory_id}' was not found.")
        if not include_inactive and not self._memory_is_active(memory):
            raise PermissionDeniedError("Requester cannot access this memory.")
        if memory.agent_id == requester.agent_id:
            return memory
        source_org = self._memory_source_org(memory)
        if include_private_same_org and source_org == requester.org_id:
            return memory
        representative_claim = next(iter(self.repository.list_claims_for_memory(memory_id)), None)
        if representative_claim is not None and self._can_access_claim(
            requester,
            representative_claim,
            include_private_same_org=include_private_same_org,
        ):
            return memory
        raise PermissionDeniedError("Requester cannot access this memory.")

    def list_memories(
        self,
        requester_agent_id: str,
        include_private_same_org: bool = False,
        include_inactive: bool = False,
        limit: int = 500,
    ) -> list[Memory]:
        requester = self.get_agent(requester_agent_id)
        memories: list[Memory] = []
        seen: set[str] = set()
        for claim in self._list_claims_with_normalized_policies():
            memory = self._get_memory_with_normalized_policy(claim.memory_id)
            if memory is None:
                continue
            if not include_inactive and not self._memory_is_active(memory):
                continue
            if not self._can_access_claim(requester, claim, include_private_same_org=include_private_same_org):
                continue
            if memory.memory_id in seen:
                continue
            seen.add(memory.memory_id)
            memories.append(memory)
        memories.sort(key=lambda item: item.updated_at, reverse=True)
        return memories[:limit]

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
        memory = self._get_memory_with_normalized_policy(claim.memory_id)
        if memory is not None and not self._memory_is_active(memory) and not include_private_same_org:
            raise PermissionDeniedError("Requester cannot access this claim.")
        if self._can_access_claim(requester, claim, include_private_same_org=include_private_same_org):
            return self.repository.get_claim(claim_id) or claim
        raise PermissionDeniedError("Requester cannot access this claim.")

    def list_claims(
        self,
        requester_agent_id: str,
        validation_status: str | None = None,
        include_private_same_org: bool = False,
        include_inactive: bool = False,
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
        for claim in self._list_claims_with_normalized_policies():
            memory = self._get_memory_with_normalized_policy(claim.memory_id)
            if memory is not None and not self._memory_is_active(memory) and not include_inactive:
                continue
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
            "last_consolidation": self._last_consolidation_result or {},
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

    def _get_visible_agent_for_requester(self, requester: Agent, agent_id: str) -> Agent:
        agent = self.get_agent(agent_id)
        if self._can_view_agent_profile(requester, agent):
            return agent
        raise PermissionDeniedError("Requester cannot access this agent profile.")

    def _can_view_agent_profile(self, requester: Agent, target: Agent) -> bool:
        if requester.agent_id == target.agent_id:
            return True
        if requester.org_id == target.org_id:
            return True
        if target.status == AgentStatus.DELETED or target.role == AgentRole.SENTINEL:
            return False
        if target.profile_visibility == AgentDiscoverability.PUBLISHED:
            return True
        if target.profile_visibility == AgentDiscoverability.SHARED:
            access_list = set(target.profile_access_list)
            return requester.agent_id in access_list or requester.org_id in access_list
        return False

    def _serialize_agent_profile(self, requester: Agent, agent: Agent) -> dict[str, Any]:
        same_org = requester.org_id == agent.org_id or requester.agent_id == agent.agent_id
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "org_id": agent.org_id,
            "capabilities": list(agent.capabilities),
            "status": agent.status,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
            "identity_verified": agent.identity_verified,
            "reputation_score": agent.reputation_score,
            "followers_count": agent.followers_count,
            "profile_visibility": agent.profile_visibility,
            "profile_access_list": list(agent.profile_access_list) if same_org else [],
            "profile_summary": agent.profile_summary,
            "profile_links": dict(agent.profile_links),
        }

    def _serialize_claim_summary(self, claim: Claim) -> dict[str, Any]:
        return {
            "claim_id": claim.claim_id,
            "statement": claim.statement,
            "validation_status": claim.validation_status.value,
            "visibility": claim.visibility.value,
            "impact": claim.impact.value,
            "confidence": claim.confidence,
            "created_at": claim.created_at,
            "updated_at": claim.updated_at,
        }

    def _serialize_verdict_summary(self, verdict: SentinelVerdict) -> dict[str, Any]:
        return {
            "verdict_id": verdict.verdict_id,
            "sentinel_agent_id": verdict.sentinel_agent_id,
            "decision": verdict.decision.value,
            "confidence": verdict.confidence,
            "reason": verdict.reason,
            "timestamp": verdict.timestamp,
        }

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
        memory = self._get_memory_with_normalized_policy(claim.memory_id)
        if memory is None:
            # Fall back to the mirrored claim policy if the parent memory is missing.
            if can_access_claim(requester.agent_id, requester.org_id, claim):
                return True
            return include_private_same_org and claim.source_org_id == requester.org_id

        mirrored_claim = self.repository.get_claim(claim.claim_id) or claim
        if can_access_claim(requester.agent_id, requester.org_id, mirrored_claim):
            return True

        if include_private_same_org:
            source_org = self._memory_source_org(memory)
            if source_org == requester.org_id:
                return True
        return False

    def _list_claims_with_normalized_policies(self) -> list[Claim]:
        claims = self.repository.list_claims()
        for memory_id in {claim.memory_id for claim in claims}:
            self._normalize_memory_policy(memory_id)
        return self.repository.list_claims()

    def _recall_candidate_limit(self, limit: int, decision_limit: int | None = None) -> int:
        baseline = max(limit, decision_limit or 0, 25)
        return min(max(baseline * 10, 50), 500)

    def _search_recall_candidates(
        self,
        query: str,
        candidate_limit: int,
        requester: Agent | None = None,
        exclude_priced_cross_org: bool = False,
    ) -> list[ClaimSearchResult]:
        search_fn = getattr(self.repository, "search_claims", None)
        if callable(search_fn):
            raw_candidates = search_fn(
                query,
                limit=candidate_limit,
                requester_agent_id=requester.agent_id if requester is not None else None,
                requester_org_id=requester.org_id if requester is not None else None,
                exclude_priced_cross_org=exclude_priced_cross_org,
            )
        else:
            all_claims = self._list_claims_with_normalized_policies()
            self._sync_bm25_index(all_claims)
            raw_candidates = []
            for claim in all_claims:
                score = self._bm25.score(claim.claim_id, query)
                if score <= 0:
                    continue
                raw_candidates.append(ClaimSearchResult(claim=claim, text_score_raw=score))
            raw_candidates.sort(key=lambda item: item.text_score_raw, reverse=True)
            raw_candidates = raw_candidates[:candidate_limit]

        for memory_id in {candidate.claim.memory_id for candidate in raw_candidates}:
            self._normalize_memory_policy(memory_id)

        refreshed_candidates: list[ClaimSearchResult] = []
        for candidate in raw_candidates:
            refreshed_claim = self.repository.get_claim(candidate.claim.claim_id) or candidate.claim
            refreshed_candidates.append(
                ClaimSearchResult(
                    claim=refreshed_claim,
                    text_score_raw=candidate.text_score_raw,
                )
            )
        return refreshed_candidates

    def _get_memory_with_normalized_policy(self, memory_id: str) -> Memory | None:
        memory = self.repository.get_memory(memory_id)
        if memory is None:
            return None
        self._normalize_memory_policy(memory_id)
        return self.repository.get_memory(memory_id) or memory

    def _normalize_memory_policy(self, memory_id: str, force: bool = False, audit: bool = True) -> list[Claim]:
        memory = self.repository.get_memory(memory_id)
        if memory is None:
            return []
        claims = self.repository.list_claims_for_memory(memory_id)
        if not claims:
            self._normalized_memory_policies.add(memory_id)
            return []
        source_org_id = self._memory_source_org(memory)
        if not force and memory_id in self._normalized_memory_policies:
            policies_match = all(
                claim.visibility == memory.visibility
                and claim.access_list == memory.access_list
                and claim.price == memory.price
                and ((not source_org_id) or claim.source_org_id == source_org_id)
                for claim in claims
            )
            if policies_match:
                return claims

        target_access_list = self._normalize_access_lists(memory.visibility, memory.access_list, claims)
        target_price = max([memory.price] + [claim.price for claim in claims])
        memory_changed = memory.access_list != target_access_list or memory.price != target_price
        if memory_changed:
            memory.access_list = target_access_list
            memory.price = target_price
            memory.updated_at = utcnow()
            self.repository.update_memory(memory)

        normalized_claims: list[Claim] = []
        claims_changed = 0
        for claim in claims:
            if self._apply_memory_policy_to_claim(claim, memory):
                claims_changed += 1
            normalized_claims.append(claim)

        if audit and (memory_changed or claims_changed):
            self._audit(
                "normalize_memory_policy",
                actor_agent_id=memory.agent_id,
                details={
                    "memory_id": memory_id,
                    "normalized_claim_count": str(len(normalized_claims)),
                    "claims_changed": str(claims_changed),
                },
            )

        self._normalized_memory_policies.add(memory_id)
        return normalized_claims

    def _normalize_access_lists(
        self,
        visibility: Visibility,
        memory_access_list: list[str],
        claims: list[Claim],
    ) -> list[str]:
        if visibility != Visibility.SHARED:
            return []
        lists = [self._dedupe_access_list(memory_access_list)]
        lists.extend(self._dedupe_access_list(claim.access_list) for claim in claims)
        non_empty = [items for items in lists if items]
        if not non_empty:
            return []
        if all(items == non_empty[0] for items in non_empty[1:]):
            return non_empty[0]

        intersection = set(non_empty[0])
        for items in non_empty[1:]:
            intersection &= set(items)
        if not intersection:
            return []
        return [item for item in non_empty[0] if item in intersection]

    def _apply_memory_policy_to_claim(self, claim: Claim, memory: Memory, persist: bool = True) -> bool:
        source_org_id = self._memory_source_org(memory)
        changed = False
        if claim.visibility != memory.visibility:
            claim.visibility = memory.visibility
            changed = True
        if claim.access_list != memory.access_list:
            claim.access_list = list(memory.access_list)
            changed = True
        if claim.price != memory.price:
            claim.price = memory.price
            changed = True
        if source_org_id and claim.source_org_id != source_org_id:
            claim.source_org_id = source_org_id
            changed = True
        if changed and persist:
            claim.updated_at = max(claim.updated_at, memory.updated_at)
            self.repository.update_claim(claim)
        return changed

    def _memory_source_org(self, memory: Memory) -> str:
        source_agent = self.repository.get_agent(memory.agent_id)
        return source_agent.org_id if source_agent is not None else ""

    def _memory_requires_payment(self, requester: Agent, memory: Memory) -> bool:
        return (
            self.settings.enable_payments and memory.price > 0 and requester.org_id != self._memory_source_org(memory)
        )

    def _check_memory_payment(
        self,
        requester: Agent,
        memory: Memory,
        payment_gate: PaymentGate,
        payment_token: str | None,
    ) -> None:
        payment_gate.check_access(
            agent_id=requester.agent_id,
            claim_price=memory.price,
            payment_token=payment_token,
            requester_org=requester.org_id,
            claim_org=self._memory_source_org(memory),
        )

    def _score_claim(
        self,
        requester: Agent,
        query: str,
        claim: Claim,
        text_score_raw: float | None = None,
    ) -> float:
        breakdown = self._score_claim_breakdown(requester, query, claim, text_score_raw=text_score_raw)
        if breakdown is None:
            return 0.0
        return breakdown.final_score

    def _score_claim_breakdown(
        self,
        requester: Agent,
        query: str,
        claim: Claim,
        text_score_raw: float | None = None,
    ) -> RecallScoreBreakdown | None:
        if text_score_raw is None:
            # Use BM25 if the claim is indexed; fall back to Jaccard otherwise.
            if self._bm25.has_document(claim.claim_id):
                text_score_raw = self._bm25.score(claim.claim_id, query)
            else:
                text_score_raw = jaccard_similarity(query, claim.statement)

        if text_score_raw == 0:
            return None

        # Normalize BM25 score into roughly [0, 1] range for combination
        # with the other signals. Cap at 1.0.
        if text_score_raw > 1.0 or self._bm25.has_document(claim.claim_id):
            text_score = min(text_score_raw / (text_score_raw + 1.0), 1.0)
        else:
            text_score = text_score_raw

        freshness = self._freshness_factor(claim)
        validation_bonus = 0.0
        if claim.validation_status == ValidationStatus.TRUSTED:
            validation_bonus = 0.25
        elif claim.validation_status == ValidationStatus.ATTESTED:
            validation_bonus = 0.15
        elif claim.validation_status == ValidationStatus.CHALLENGED:
            validation_bonus = -0.2
        elif claim.validation_status in (ValidationStatus.EXPIRED, ValidationStatus.REJECTED):
            validation_bonus = -1.0

        confidence_bonus = claim.confidence * 0.2
        context_bonus = self._visibility_preference_bonus(requester, claim)
        final_score = text_score * 0.55 + freshness * 0.1 + confidence_bonus + validation_bonus + context_bonus
        return RecallScoreBreakdown(
            text_score_raw=round(text_score_raw, 4),
            text_score=round(text_score, 4),
            freshness=round(freshness, 4),
            confidence_bonus=round(confidence_bonus, 4),
            validation_bonus=round(validation_bonus, 4),
            context_bonus=round(context_bonus, 4),
            final_score=round(final_score, 4),
        )

    def _build_recall_hit(self, claim: Claim, memory: Memory, score: float) -> RecallHit:
        entities = [self.repository.get_entity(entity_id) for entity_id in claim.entity_ids]
        source_agent = self.repository.get_agent(claim.source_agent_id)
        return RecallHit(
            claim=claim,
            score=round(score, 4),
            entities=[entity for entity in entities if entity is not None],
            memory_content=memory.content,
            source_agent_name=source_agent.name if source_agent else "",
            source_reputation_score=source_agent.reputation_score if source_agent else 0.0,
        )

    def _evaluate_recall_candidate(
        self,
        *,
        requester: Agent,
        query: str,
        claim: Claim,
        payment_gate: PaymentGate,
        payment_token: str | None,
        text_score_raw: float | None = None,
    ) -> tuple[RecallDecision, RecallHit | None, PaymentRequiredError | None]:
        if claim.validation_status == ValidationStatus.REJECTED:
            return (
                RecallDecision(
                    claim_id=claim.claim_id,
                    memory_id=claim.memory_id,
                    statement=claim.statement,
                    visibility=claim.visibility,
                    validation_status=claim.validation_status,
                    outcome="filtered",
                    reasons=["rejected_claim"],
                ),
                None,
                None,
            )

        memory = self.repository.get_memory(claim.memory_id)
        if memory is None:
            return (
                RecallDecision(
                    claim_id=claim.claim_id,
                    memory_id=claim.memory_id,
                    statement="",
                    visibility=claim.visibility,
                    validation_status=claim.validation_status,
                    outcome="filtered",
                    reasons=["missing_memory"],
                ),
                None,
                None,
            )
        if not self._memory_is_active(memory):
            return (
                RecallDecision(
                    claim_id=claim.claim_id,
                    memory_id=claim.memory_id,
                    statement=claim.statement,
                    visibility=claim.visibility,
                    validation_status=claim.validation_status,
                    outcome="filtered",
                    reasons=["memory_inactive"],
                ),
                None,
                None,
            )
        if not self._can_access(requester, claim):
            return (
                RecallDecision(
                    claim_id="",
                    memory_id="",
                    statement="",
                    visibility=Visibility.PRIVATE,
                    validation_status=ValidationStatus.UNREVIEWED,
                    outcome="filtered",
                    reasons=["access_denied"],
                ),
                None,
                None,
            )

        breakdown = self._score_claim_breakdown(requester, query, claim, text_score_raw=text_score_raw)
        if breakdown is None or breakdown.final_score <= 0:
            return (
                RecallDecision(
                    claim_id=claim.claim_id,
                    memory_id=claim.memory_id,
                    statement=claim.statement,
                    visibility=claim.visibility,
                    validation_status=claim.validation_status,
                    outcome="filtered",
                    reasons=["no_text_match"],
                ),
                None,
                None,
            )
        try:
            self._check_memory_payment(
                requester=requester,
                memory=memory,
                payment_gate=payment_gate,
                payment_token=payment_token,
            )
        except PaymentRequiredError as exc:
            return (
                RecallDecision(
                    claim_id=claim.claim_id,
                    memory_id=claim.memory_id,
                    statement=claim.statement,
                    visibility=claim.visibility,
                    validation_status=claim.validation_status,
                    outcome="filtered",
                    reasons=["payment_required"],
                    score=breakdown.final_score,
                    score_breakdown=breakdown,
                ),
                None,
                exc,
            )

        hit = self._build_recall_hit(claim, memory, breakdown.final_score)
        return (
            RecallDecision(
                claim_id=claim.claim_id,
                memory_id=claim.memory_id,
                statement=claim.statement,
                visibility=claim.visibility,
                validation_status=claim.validation_status,
                outcome="hit",
                score=breakdown.final_score,
                score_breakdown=breakdown,
            ),
            hit,
            None,
        )

    def _visibility_preference_bonus(self, requester: Agent, claim: Claim) -> float:
        same_org = bool(claim.source_org_id and claim.source_org_id == requester.org_id)

        if claim.visibility == Visibility.PRIVATE and claim.source_agent_id == requester.agent_id:
            return 0.12
        if claim.visibility == Visibility.ORG and same_org:
            return 0.1
        if claim.visibility == Visibility.SHARED:
            return 0.06 if same_org else 0.04
        if claim.visibility == Visibility.PUBLISHED and same_org:
            return 0.01
        return 0.0

    def _freshness_factor(self, claim: Claim) -> float:
        now = utcnow()
        if claim.expires_at is None:
            return claim.freshness_score
        if claim.expires_at <= now:
            if claim.validation_status != ValidationStatus.EXPIRED:
                claim.validation_status = ValidationStatus.EXPIRED
                claim.freshness_score = 0.0
                claim.updated_at = now
                self.repository.update_claim(claim)
                self._sync_memory_validation(claim.memory_id)
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
        memory = self._get_memory_with_normalized_policy(claim.memory_id)
        if memory is not None and not self._memory_is_active(memory):
            return False
        if not self._can_access(owner, claim):
            return False

        # Pattern-based matching (graph-native)
        if query.pattern is not None and not self._matches_pattern(query.pattern, claim):
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

    def _matches_pattern(self, pattern: PatternFilter, claim: Claim) -> bool:
        """Check if a claim matches a graph-native pattern filter."""
        # Entity alias matching
        if pattern.entities:
            claim_entities = [self.repository.get_entity(eid) for eid in claim.entity_ids]
            claim_aliases = {e.alias_key for e in claim_entities if e is not None}
            pattern_aliases = {normalize_alias(e) for e in pattern.entities}
            if not pattern_aliases & claim_aliases:
                return False

        # Entity type matching
        if pattern.entity_types:
            claim_entities = [self.repository.get_entity(eid) for eid in claim.entity_ids]
            claim_types = {e.entity_type for e in claim_entities if e is not None}
            if not set(pattern.entity_types) & claim_types:
                return False

        # Relation type matching
        if pattern.relation_types and claim.relation_type not in pattern.relation_types:
            return False

        # Confidence threshold
        if pattern.min_confidence > 0 and claim.confidence < pattern.min_confidence:
            return False

        # Source org filter
        if pattern.source_org_ids and claim.source_org_id not in pattern.source_org_ids:
            return False

        # Visibility filter
        return not (pattern.visibility_levels and claim.visibility.value not in pattern.visibility_levels)

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
        changed_memory_ids: set[str] = set()
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
                changed_memory_ids.add(claim.memory_id)
        for memory_id in changed_memory_ids:
            self._sync_memory_validation(memory_id)
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

    def _schedule_memory_consolidation(self, delay_seconds: float) -> None:
        if self._closing or not self.settings.enable_memory_consolidation:
            return

        def _run_and_reschedule() -> None:
            try:
                self._last_consolidation_result = self.run_memory_consolidation()
            except Exception:
                logger.exception("Memory consolidation sweep failed")
            self._schedule_memory_consolidation(delay_seconds)

        self._schedule_callback(delay_seconds, _run_and_reschedule)

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

    _MAX_SUBSCRIPTIONS = 200

    def follow(self, agent_id: str, target_type: str, target_id: str) -> Subscription:
        self.get_agent(agent_id)
        target_enum = SubscriptionTarget(target_type)

        # Validate target exists for agent/org types
        if target_enum == SubscriptionTarget.AGENT:
            if agent_id == target_id:
                raise ValueError("Agents cannot follow themselves.")
            self.get_agent(target_id)
        elif target_enum == SubscriptionTarget.ORG and not any(
            a.org_id == target_id for a in self.repository.list_agents()
        ):
            raise NotFoundError(f"No agents found in org '{target_id}'.")

        # Check duplicate
        existing = self.repository.get_subscriptions_by_follower(agent_id)
        for sub in existing:
            if sub.target_type == target_enum and sub.target_id == target_id:
                raise ValueError(f"Already following {target_type}:{target_id}")

        # Check max limit
        if len(existing) >= self._MAX_SUBSCRIPTIONS:
            raise ValueError(f"Maximum {self._MAX_SUBSCRIPTIONS} subscriptions reached.")

        subscription = Subscription(
            subscription_id=new_id("sub"),
            follower_agent_id=agent_id,
            target_type=target_enum,
            target_id=target_id,
            created_at=utcnow(),
        )
        self.repository.save_subscription(subscription)

        # Update followers_count for agent targets
        if target_enum == SubscriptionTarget.AGENT:
            target_agent = self.get_agent(target_id)
            target_agent.followers_count = len(self.repository.get_followers_of_agent(target_id))
            self.repository.save_agent(target_agent)

        self._audit("follow", actor_agent_id=agent_id, details={"target_type": target_type, "target_id": target_id})
        return subscription

    def unfollow(self, agent_id: str, subscription_id: str) -> None:
        self.get_agent(agent_id)
        sub = self.repository.get_subscription(subscription_id)
        if sub is None:
            raise NotFoundError(f"Subscription '{subscription_id}' not found.")
        if sub.follower_agent_id != agent_id:
            raise PermissionDeniedError("Only the subscriber can unfollow.")

        self.repository.delete_subscription(subscription_id)

        # Update followers_count for agent targets
        if sub.target_type == SubscriptionTarget.AGENT:
            target_agent = self.get_agent(sub.target_id)
            target_agent.followers_count = len(self.repository.get_followers_of_agent(sub.target_id))
            self.repository.save_agent(target_agent)

        self._audit("unfollow", actor_agent_id=agent_id, details={"subscription_id": subscription_id})

    def list_following(self, agent_id: str) -> list[Subscription]:
        self.get_agent(agent_id)
        return self.repository.get_subscriptions_by_follower(agent_id)

    def list_followers(self, agent_id: str) -> list[Subscription]:
        self.get_agent(agent_id)
        return self.repository.get_followers_of_agent(agent_id)

    def get_feed(self, agent_id: str, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        requester = self.get_agent(agent_id)
        subscriptions = self.repository.get_subscriptions_by_follower(agent_id)
        if not subscriptions:
            return []

        all_claims = self._list_claims_with_normalized_policies()
        self._sync_bm25_index(all_claims)

        # Group claims by memory_id
        claims_by_memory: dict[str, list[Claim]] = {}
        for claim in all_claims:
            claims_by_memory.setdefault(claim.memory_id, []).append(claim)

        # Collect matching memory_ids from subscriptions
        matched_memory_ids: set[str] = set()
        for sub in subscriptions:
            for memory_id, mem_claims in claims_by_memory.items():
                for claim in mem_claims:
                    if not self._can_access(requester, claim):
                        continue
                    if self._matches_subscription(sub, claim):
                        matched_memory_ids.add(memory_id)
                        break

        # Build feed items
        now = utcnow()
        feed_items: list[dict[str, Any]] = []
        for memory_id in matched_memory_ids:
            memory = self._get_memory_with_normalized_policy(memory_id)
            if memory is None or not self._memory_is_active(memory):
                continue
            mem_claims = claims_by_memory.get(memory_id, [])
            if not mem_claims:
                continue
            source_agent = self.repository.get_agent(mem_claims[0].source_agent_id)
            if source_agent is None:
                continue

            requires_payment = self._memory_requires_payment(requester, memory)
            is_locked = requires_payment
            entities: list[Entity] = []
            for claim in mem_claims:
                for eid in claim.entity_ids:
                    entity = self.repository.get_entity(eid)
                    if entity and entity not in entities:
                        entities.append(entity)

            age_hours = (now - memory.created_at).total_seconds() / 3600
            recency = math.exp(-age_hours / 168)
            score = recency * 0.6 + source_agent.reputation_score * 0.4

            feed_items.append(
                {
                    "memory_id": memory.memory_id,
                    "memory_content": "" if is_locked else memory.content,
                    "agent_id": memory.agent_id,
                    "visibility": memory.visibility.value,
                    "claims": mem_claims,
                    "entities": entities,
                    "source_agent_name": source_agent.name,
                    "source_org_id": source_agent.org_id,
                    "source_reputation_score": source_agent.reputation_score,
                    "created_at": memory.created_at,
                    "is_paid": memory.price > 0,
                    "price": memory.price,
                    "is_locked": is_locked,
                    "requires_payment": requires_payment,
                    "feed_score": round(score, 4),
                }
            )

        feed_items.sort(key=lambda item: item["feed_score"], reverse=True)
        return feed_items[offset : offset + limit]

    def _matches_subscription(self, sub: Subscription, claim: Claim) -> bool:
        if sub.target_type == SubscriptionTarget.AGENT:
            return claim.source_agent_id == sub.target_id
        if sub.target_type == SubscriptionTarget.ORG:
            return claim.source_org_id == sub.target_id
        if sub.target_type == SubscriptionTarget.ENTITY:
            alias = normalize_alias(sub.target_id)
            for eid in claim.entity_ids:
                entity = self.repository.get_entity(eid)
                if entity and entity.alias_key == alias:
                    return True
            return False
        if sub.target_type == SubscriptionTarget.TOPIC:
            return self._bm25.score(claim.claim_id, sub.target_id) > 0
        return False

    def calculate_reputation_score(self, agent_id: str) -> float:
        claims = [c for c in self.repository.list_claims() if c.source_agent_id == agent_id]
        if not claims:
            return 0.5
        attested = sum(1 for c in claims if c.validation_status == ValidationStatus.ATTESTED)
        challenged = sum(1 for c in claims if c.validation_status == ValidationStatus.CHALLENGED)
        total_reviewed = attested + challenged
        if total_reviewed == 0:
            return 0.5
        base = attested / total_reviewed
        volume_factor = min(1.0, total_reviewed / 20)
        return round(base * 0.7 + volume_factor * 0.3, 2)

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

    # ------------------------------------------------------------------
    # Memory OS v1 — Context Compiler
    # ------------------------------------------------------------------

    _TOKENS_PER_WORD: float = 1.3

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using word_count * 1.3."""
        return max(1, int(len(text.split()) * self._TOKENS_PER_WORD))

    def compile_context(
        self,
        agent_id: str,
        query: str,
        token_budget: int = 4000,
        limit: int = 50,
        include_explanations: bool = False,
    ) -> ContextPack:
        """Compile a governed, token-budgeted context pack for an agent.

        Pipeline:
        1. Retrieve candidate claims via repository-native search
        2. Apply ACL, freshness, trust, curation, and payment filters
        3. Score and rank candidates
        4. Detect near-exact duplicates (Jaccard >= 0.88)
        5. Detect conflicts using existing sentinel conflict signals
        6. Group by source memory
        7. Truncate to fit token budget
        8. Build extractive summary from top claim statements
        """
        if token_budget <= 0:
            token_budget = 1

        requester = self.get_agent(agent_id)
        now = utcnow()

        # Step 1: Retrieve candidates
        candidates = self._search_recall_candidates(
            query=query,
            candidate_limit=min(max(limit * 10, 50), 500),
            requester=requester,
        )

        # Step 2-3: Filter and score
        scored: list[tuple[Claim, float, Memory]] = []
        excluded: list[tuple[Claim, list[str]]] = []
        locked_claims: list[tuple[Claim, float]] = []

        included_reasons: dict[str, list[str]] = {}
        excluded_reasons: dict[str, list[str]] = {}

        for candidate in candidates:
            claim = candidate.claim

            # Rejected claims
            if claim.validation_status == ValidationStatus.REJECTED:
                excluded.append((claim, ["rejected_claim"]))
                if include_explanations:
                    excluded_reasons[claim.claim_id] = ["rejected_claim"]
                continue

            # Memory must be active
            memory = self.repository.get_memory(claim.memory_id)
            if memory is None or not self._memory_is_active(memory):
                excluded.append((claim, ["memory_inactive"]))
                if include_explanations:
                    excluded_reasons[claim.claim_id] = ["memory_inactive"]
                continue

            # ACL check
            if not self._can_access(requester, claim):
                excluded.append((claim, ["access_denied"]))
                if include_explanations:
                    excluded_reasons[claim.claim_id] = ["access_denied"]
                continue

            # Score
            breakdown = self._score_claim_breakdown(requester, query, claim, text_score_raw=candidate.text_score_raw)
            if breakdown is None or breakdown.final_score <= 0:
                excluded.append((claim, ["no_text_match"]))
                if include_explanations:
                    excluded_reasons[claim.claim_id] = ["no_text_match"]
                continue

            # Payment gate — locked claims become references
            is_locked = (
                claim.price > 0
                and claim.source_agent_id != requester.agent_id
                and claim.source_org_id != requester.org_id
            )

            if is_locked:
                locked_claims.append((claim, breakdown.final_score))
            else:
                scored.append((claim, breakdown.final_score, memory))
                if include_explanations:
                    reasons = [f"text_score={breakdown.text_score:.3f}"]
                    if breakdown.validation_bonus > 0:
                        reasons.append(f"validation_bonus={breakdown.validation_bonus:.3f}")
                    if breakdown.freshness > 0.5:
                        reasons.append(f"fresh={breakdown.freshness:.3f}")
                    included_reasons[claim.claim_id] = reasons

        # Sort by score descending
        scored.sort(key=lambda item: item[1], reverse=True)
        locked_claims.sort(key=lambda item: item[1], reverse=True)

        # Step 4: Deduplicate near-exact matches (Jaccard >= 0.88)
        deduped: list[tuple[Claim, float, Memory]] = []
        seen_statements: list[str] = []
        for claim, score, memory in scored:
            is_dup = False
            for seen in seen_statements:
                if jaccard_similarity(claim.statement, seen) >= 0.88:
                    is_dup = True
                    if include_explanations:
                        excluded_reasons[claim.claim_id] = ["near_duplicate"]
                    break
            if not is_dup:
                deduped.append((claim, score, memory))
                seen_statements.append(claim.statement)
        scored = deduped

        # Step 5: Detect conflicts using sentinel verdicts
        conflict_pairs: list[tuple[str, str]] = []
        conflicting_claim_ids: set[str] = set()
        scored_ids = {claim.claim_id for claim, _, _ in scored}
        for claim, _, _ in scored:
            verdicts = self.repository.list_verdicts_for_claim(claim.claim_id)
            for verdict in verdicts:
                if (
                    verdict.decision in (SentinelDecision.DISPUTE, SentinelDecision.REJECT)
                    and verdict.conflicting_claim_id
                    and verdict.conflicting_claim_id in scored_ids
                ):
                    pair = tuple(sorted([claim.claim_id, verdict.conflicting_claim_id]))
                    if pair not in conflict_pairs:
                        conflict_pairs.append(pair)
                    conflicting_claim_ids.add(claim.claim_id)
                    conflicting_claim_ids.add(verdict.conflicting_claim_id)

        # Step 6-7: Truncate to token budget
        # Reserve 20% of budget for summary
        summary_budget = max(int(token_budget * 0.2), 10)
        claims_budget = token_budget - summary_budget

        included_pack_claims: list[ContextPackClaim] = []
        conflicting_pack_claims: list[ContextPackClaim] = []
        excluded_pack_claims: list[ContextPackClaim] = []
        source_map: dict[str, ContextPackSource] = {}
        tokens_used = 0

        for claim, score, memory in scored:
            claim_tokens = self._estimate_tokens(claim.statement)
            if tokens_used + claim_tokens > claims_budget and included_pack_claims:
                # Budget exceeded — remaining go to excluded
                if include_explanations:
                    excluded_reasons.setdefault(claim.claim_id, []).append("token_budget_exceeded")
                excluded_pack_claims.append(self._build_context_pack_claim(claim, score, memory, locked=False))
                continue

            tokens_used += claim_tokens
            pack_claim = self._build_context_pack_claim(claim, score, memory, locked=False)

            if claim.claim_id in conflicting_claim_ids:
                conflicting_pack_claims.append(pack_claim)
            else:
                included_pack_claims.append(pack_claim)

            # Track source
            if memory.memory_id not in source_map:
                source_map[memory.memory_id] = ContextPackSource(
                    memory_id=memory.memory_id,
                    agent_id=memory.agent_id,
                    source_type=memory.source_type,
                    source_label=memory.source_label,
                    source_uri=memory.source_uri,
                    claim_count=0,
                )
            source_map[memory.memory_id].claim_count += 1

        # Add locked claims as references (only when explanations are requested)
        if include_explanations:
            for claim, score in locked_claims:
                if len(included_pack_claims) + len(conflicting_pack_claims) + len(excluded_pack_claims) >= limit:
                    break
                memory = self.repository.get_memory(claim.memory_id)
                pack_claim = self._build_context_pack_claim(claim, score, memory, locked=True)
                excluded_pack_claims.append(pack_claim)
                excluded_reasons[claim.claim_id] = ["payment_required"]

        # Step 8: Build extractive summary from top included claims
        # Summary is extractive (stitched from claim statements), so it shares
        # content with included claims. We cap total tokens_used at the budget.
        summary_parts: list[str] = []
        summary_tokens = 0
        remaining_budget = max(0, token_budget - tokens_used)
        effective_summary_budget = min(summary_budget, remaining_budget)
        all_included = included_pack_claims + conflicting_pack_claims
        for pc in all_included:
            part_tokens = self._estimate_tokens(pc.statement)
            if summary_tokens + part_tokens > effective_summary_budget and summary_parts:
                break
            summary_parts.append(pc.statement)
            summary_tokens += part_tokens
        summary = " ".join(summary_parts) if summary_parts else ""

        tokens_used = min(tokens_used + summary_tokens, token_budget)

        # Build explanation if requested
        explanation = None
        if include_explanations:
            filter_counts: dict[str, int] = {}
            for reasons in excluded_reasons.values():
                for r in reasons:
                    filter_counts[r] = filter_counts.get(r, 0) + 1
            explanation = ContextPackExplanation(
                included_reasons=included_reasons,
                excluded_reasons=excluded_reasons,
                conflict_pairs=conflict_pairs,
                filter_counts=filter_counts,
            )

        # Compute compression ratio from source memories
        source_memory_ids_seen: set[str] = set()
        source_tokens_total = 0
        for _claim, _score, memory in scored:
            if memory.memory_id not in source_memory_ids_seen:
                source_memory_ids_seen.add(memory.memory_id)
                source_tokens_total += self._estimate_tokens(memory.content)
        compression_ratio = round(source_tokens_total / tokens_used, 1) if tokens_used > 0 else 0.0
        stale_claim_count = sum(1 for c in included_pack_claims + conflicting_pack_claims if c.staleness_warning)

        pack = ContextPack(
            pack_id=new_id("cpk"),
            agent_id=agent_id,
            query=query,
            included_claims=included_pack_claims,
            sources=list(source_map.values()),
            token_budget=token_budget,
            tokens_used=tokens_used,
            generated_at=now,
            source_tokens=source_tokens_total,
            compression_ratio=compression_ratio,
            stale_claim_count=stale_claim_count,
            summary=summary,
            excluded_claims=excluded_pack_claims if include_explanations else [],
            conflicting_claims=conflicting_pack_claims,
            explanation=explanation,
        )

        self.repository.save_context_pack(pack)
        self._audit(
            "compile_context",
            actor_agent_id=agent_id,
            details={
                "pack_id": pack.pack_id,
                "query": query,
                "token_budget": str(token_budget),
                "included": str(len(included_pack_claims)),
                "conflicts": str(len(conflicting_pack_claims)),
            },
        )
        return pack

    def get_context_pack(self, pack_id: str, requester_agent_id: str | None = None) -> ContextPack:
        """Retrieve a previously compiled context pack."""
        pack = self.repository.get_context_pack(pack_id)
        if pack is None:
            raise NotFoundError(f"Context pack '{pack_id}' not found.")
        if requester_agent_id is not None and pack.agent_id != requester_agent_id:
            raise PermissionDeniedError("Cannot access another agent's context pack.")
        return pack

    def explain_context_pack(self, pack_id: str, requester_agent_id: str | None = None) -> ContextPack:
        """Retrieve a context pack with full explanation details."""
        pack = self.get_context_pack(pack_id, requester_agent_id=requester_agent_id)
        if pack.explanation is None:
            raise ConflictError(
                f"Context pack '{pack_id}' was compiled without explanations. Recompile with include_explanations=True."
            )
        return pack

    def _check_claim_staleness(self, claim: Claim) -> str:
        """Return a staleness warning if claim is old without recent attestation."""
        threshold_days = self.settings.claim_staleness_threshold_days
        if threshold_days <= 0:
            return ""
        age = (utcnow() - claim.created_at).days
        if age < threshold_days:
            return ""
        if claim.validation_status in (ValidationStatus.TRUSTED, ValidationStatus.ATTESTED):
            return ""
        return f"Claim is {age} days old with status '{claim.validation_status.value}' — verify before acting"

    def _build_context_pack_claim(
        self,
        claim: Claim,
        score: float,
        memory: Memory | None,
        locked: bool,
    ) -> ContextPackClaim:
        return ContextPackClaim(
            claim_id=claim.claim_id,
            statement="" if locked else claim.statement,
            source_memory_id=claim.memory_id,
            source_agent_id=claim.source_agent_id,
            confidence=claim.confidence,
            freshness_score=self._freshness_factor(claim),
            validation_status=claim.validation_status.value,
            score=round(score, 4),
            source_memory_section=claim.source_memory_section,
            source_label=memory.source_label if memory else "",
            locked=locked,
            staleness_warning=self._check_claim_staleness(claim) if not locked else "",
        )

    # ------------------------------------------------------------------
    # Memory OS — Background Memory Consolidation
    # ------------------------------------------------------------------

    def run_memory_consolidation(self) -> dict[str, int]:
        """Run a background memory consolidation sweep.

        Actions:
        1. Archive challenged claims older than 30 days with no attestation
        2. Flag orphaned claims whose parent memory was archived/hidden
        3. Promote well-attested claims meeting trust promotion thresholds
        """
        now = utcnow()
        stats = {"archived_stale_challenged": 0, "promoted": 0, "flagged_orphaned": 0}

        for claim in self.repository.list_claims():
            # 1. Archive old challenged claims with no attestations
            if (
                claim.validation_status == ValidationStatus.CHALLENGED
                and claim.attestation_count == 0
                and (now - claim.created_at).days > 30
            ):
                claim.validation_status = ValidationStatus.REJECTED
                claim.updated_at = now
                self.repository.update_claim(claim)
                stats["archived_stale_challenged"] += 1
                continue

            # 2. Flag orphaned claims (parent memory archived/hidden)
            memory = self.repository.get_memory(claim.memory_id)
            if (
                memory is not None
                and memory.curation_status != MemoryCurationStatus.ACTIVE
                and claim.validation_status
                not in (
                    ValidationStatus.REJECTED,
                    ValidationStatus.EXPIRED,
                )
            ):
                claim.validation_status = ValidationStatus.EXPIRED
                claim.updated_at = now
                self.repository.update_claim(claim)
                stats["flagged_orphaned"] += 1

        # 3. Promote trusted claims (reuse existing method)
        stats["promoted"] = self.promote_trusted_claims()

        self._audit(
            "memory_consolidation",
            actor_agent_id="_system",
            details={k: str(v) for k, v in stats.items()},
        )
        return stats

    # ------------------------------------------------------------------
    # Memory OS v2 — Reactive Delta Compaction
    # ------------------------------------------------------------------

    def create_session(
        self,
        agent_id: str,
        title: str = "",
        source: str = "generic",
        metadata: dict[str, str] | None = None,
    ) -> Session:
        agent = self.get_agent(agent_id)
        now = utcnow()
        session = Session(
            session_id=new_id("ses"),
            agent_id=agent.agent_id,
            title=title.strip() or f"{agent.name} session",
            source=(source or "generic").strip() or "generic",
            status="active",
            metadata={str(key): str(value) for key, value in dict(metadata or {}).items() if value is not None},
            created_at=now,
            updated_at=now,
        )
        self.repository.save_session(session)
        self._audit(
            "create_session",
            actor_agent_id=agent.agent_id,
            details={"session_id": session.session_id, "source": session.source},
        )
        return session

    def fork_session(
        self,
        agent_id: str,
        session_id: str,
        from_checkpoint_id: str | None = None,
        title: str | None = None,
    ) -> Session:
        parent_session = self.get_session(agent_id, session_id)
        checkpoints = self.repository.list_compaction_checkpoints(session_id)
        if not checkpoints:
            raise ConflictError("Cannot fork a session that has no checkpoints yet.")

        checkpoint_map = {checkpoint.checkpoint_id: checkpoint for checkpoint in checkpoints}
        if from_checkpoint_id is None:
            base_checkpoint = checkpoints[-1]
        else:
            base_checkpoint = checkpoint_map.get(from_checkpoint_id)
            if base_checkpoint is None:
                raise NotFoundError(f"Checkpoint '{from_checkpoint_id}' not found.")

        now = utcnow()
        child_session = Session(
            session_id=new_id("ses"),
            agent_id=parent_session.agent_id,
            title=(title or "").strip() or f"{parent_session.title} branch",
            source=parent_session.source,
            status="active",
            metadata=dict(parent_session.metadata),
            created_at=now,
            updated_at=now,
            parent_session_id=parent_session.session_id,
            forked_from_checkpoint_id=base_checkpoint.checkpoint_id,
        )
        self.repository.save_session(child_session)
        self._audit(
            "fork_session",
            actor_agent_id=agent_id,
            details={
                "session_id": child_session.session_id,
                "parent_session_id": parent_session.session_id,
                "from_checkpoint_id": base_checkpoint.checkpoint_id,
            },
        )
        return child_session

    def get_session(self, requester_agent_id: str, session_id: str) -> Session:
        session = self.repository.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Session '{session_id}' not found.")
        if session.agent_id != requester_agent_id:
            raise PermissionDeniedError("Cannot access another agent's session.")
        return session

    def list_sessions(self, requester_agent_id: str) -> list[Session]:
        sessions = self.repository.list_sessions_for_agent(requester_agent_id)
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

    def list_session_events(self, requester_agent_id: str, session_id: str) -> list[SessionEvent]:
        self.get_session(requester_agent_id, session_id)
        return self.repository.list_session_events(session_id)

    def _session_branch_backed(self, session: Session) -> bool:
        return bool(session.parent_session_id and session.forked_from_checkpoint_id)

    def _is_snapshot_pack_reusable(self, pack: DeltaPack | None) -> tuple[bool, list[str]]:
        if pack is None:
            return False, ["missing_delta_pack"]
        reasons: list[str] = []
        if pack.state_snapshot_version != STATE_SNAPSHOT_VERSION:
            reasons.append("snapshot_version_mismatch")
        if not pack.state_snapshot:
            reasons.append("missing_state_snapshot")
        return not reasons, reasons

    def _build_effective_session_events(
        self,
        session: Session,
        *,
        upto_event_count: int | None = None,
        visited: set[str] | None = None,
    ) -> tuple[list[SessionEvent], list[str]]:
        local_events = self.repository.list_session_events(session.session_id)
        if upto_event_count is not None:
            local_events = local_events[: max(upto_event_count, 0)]

        issues: list[str] = []
        if not self._session_branch_backed(session):
            return list(local_events), issues

        lineage_seen = set(visited or set())
        if session.session_id in lineage_seen:
            return list(local_events), ["lineage_cycle_detected"]
        lineage_seen.add(session.session_id)

        parent_session = self.repository.get_session(session.parent_session_id)
        if parent_session is None:
            return list(local_events), ["missing_parent_session"]

        base_checkpoint = self.repository.get_compaction_checkpoint(session.forked_from_checkpoint_id)
        if base_checkpoint is None:
            return list(local_events), ["missing_fork_base_checkpoint"]
        if base_checkpoint.session_id != parent_session.session_id:
            return list(local_events), ["fork_checkpoint_parent_mismatch"]

        parent_events, parent_issues = self._build_effective_session_events(
            parent_session,
            upto_event_count=base_checkpoint.event_count,
            visited=lineage_seen,
        )
        issues.extend(parent_issues)
        return parent_events + list(local_events), issues

    def _branch_cache_seed(
        self,
        session: Session,
        events: list[SessionEvent],
    ) -> tuple[CompactionCheckpoint | None, DeltaPack | None, list[SessionEvent], int, list[str]]:
        issues: list[str] = []
        if not self._session_branch_backed(session):
            return None, None, events, 0, issues

        if session.latest_checkpoint_id and session.latest_delta_pack_id:
            latest_checkpoint = self.repository.get_compaction_checkpoint(session.latest_checkpoint_id)
            latest_pack = self.repository.get_delta_pack(session.latest_delta_pack_id)
            if latest_checkpoint is None:
                issues.append("missing_latest_checkpoint")
            elif latest_pack is None:
                issues.append("missing_latest_delta_pack")
            else:
                new_events = events[latest_checkpoint.event_count :]
                return latest_checkpoint, latest_pack, new_events, latest_pack.state_snapshot_event_count, issues

        base_checkpoint = self.repository.get_compaction_checkpoint(session.forked_from_checkpoint_id)
        if base_checkpoint is None:
            issues.append("missing_fork_base_checkpoint")
            return None, None, events, 0, issues
        base_pack = self.repository.get_delta_pack(base_checkpoint.delta_pack_id)
        if base_pack is None:
            issues.append("missing_fork_base_delta_pack")
            return base_checkpoint, None, events, 0, issues
        return base_checkpoint, base_pack, events, base_pack.state_snapshot_event_count, issues

    def _branch_has_reusable_prefix(self, session: Session) -> bool:
        if not self._session_branch_backed(session):
            return False
        if session.latest_delta_pack_id:
            latest_pack = self.repository.get_delta_pack(session.latest_delta_pack_id)
            valid, _reasons = self._is_snapshot_pack_reusable(latest_pack)
            if valid:
                return True
        base_checkpoint = self.repository.get_compaction_checkpoint(session.forked_from_checkpoint_id)
        if base_checkpoint is None:
            return False
        base_pack = self.repository.get_delta_pack(base_checkpoint.delta_pack_id)
        valid, _reasons = self._is_snapshot_pack_reusable(base_pack)
        return valid

    def record_session_event(
        self,
        agent_id: str,
        session_id: str,
        event_type: str,
        content: str,
        metadata: dict[str, str] | None = None,
        important: bool | None = None,
        auto_checkpoint: bool = False,
        token_budget: int = 1600,
        checkpoint_reason: str | None = None,
    ) -> SessionEventResult:
        session = self.get_session(agent_id, session_id)
        now = utcnow()
        events = self.repository.list_session_events(session_id)
        clean_metadata = {str(key): str(value) for key, value in dict(metadata or {}).items() if value is not None}
        normalized_type = (event_type or "note").strip().lower() or "note"
        inferred_important = normalized_type in {
            "decision",
            "constraint",
            "todo",
            "task",
            "open_task",
            "failure",
            "blocker",
            "error",
            "resolved",
            "plan_change",
            "context_pressure",
            "checkpoint",
            "compact",
        }
        event = SessionEvent(
            event_id=new_id("evt"),
            session_id=session_id,
            agent_id=agent_id,
            event_type=normalized_type,
            content=content.strip(),
            created_at=now,
            metadata=clean_metadata,
            sequence=len(events) + 1,
            important=inferred_important if important is None else important,
        )
        self.repository.save_session_event(event)
        session.updated_at = now
        session.event_count += 1
        self.repository.update_session(session)

        checkpoint = None
        delta_pack = None
        if auto_checkpoint or self._should_auto_checkpoint(event):
            reason = checkpoint_reason or self._checkpoint_reason_for_event(event)
            checkpoint, delta_pack = self._checkpoint_session_internal(
                session, reason=reason, token_budget=token_budget
            )

        self._audit(
            "record_session_event",
            actor_agent_id=agent_id,
            details={"session_id": session_id, "event_id": event.event_id, "event_type": normalized_type},
        )
        return SessionEventResult(session=session, event=event, checkpoint=checkpoint, delta_pack=delta_pack)

    def checkpoint_session(
        self,
        agent_id: str,
        session_id: str,
        reason: str = "manual",
        token_budget: int = 1600,
    ) -> DeltaPack:
        session = self.get_session(agent_id, session_id)
        _checkpoint, delta_pack = self._checkpoint_session_internal(
            session,
            reason=(reason or "manual").strip() or "manual",
            token_budget=token_budget,
        )
        return delta_pack

    def list_compaction_checkpoints(self, requester_agent_id: str, session_id: str) -> list[CompactionCheckpoint]:
        self.get_session(requester_agent_id, session_id)
        return self.repository.list_compaction_checkpoints(session_id)

    def resume_session(self, requester_agent_id: str, session_id: str) -> SessionResume:
        session = self.get_session(requester_agent_id, session_id)
        checkpoint = (
            self.repository.get_compaction_checkpoint(session.latest_checkpoint_id)
            if session.latest_checkpoint_id
            else None
        )
        delta_pack = (
            self.repository.get_delta_pack(session.latest_delta_pack_id) if session.latest_delta_pack_id else None
        )
        return SessionResume(session=session, checkpoint=checkpoint, delta_pack=delta_pack)

    def context_diff(
        self,
        requester_agent_id: str,
        session_id: str,
        from_checkpoint_id: str | None = None,
        to_checkpoint_id: str | None = None,
    ) -> SessionDiff:
        session = self.get_session(requester_agent_id, session_id)
        checkpoints = self.repository.list_compaction_checkpoints(session_id)
        if not checkpoints:
            raise ConflictError("No checkpoints exist for this session yet.")

        checkpoint_map = {checkpoint.checkpoint_id: checkpoint for checkpoint in checkpoints}
        if to_checkpoint_id is None:
            to_checkpoint = checkpoints[-1]
        else:
            to_checkpoint = checkpoint_map.get(to_checkpoint_id)
            if to_checkpoint is None:
                raise NotFoundError(f"Checkpoint '{to_checkpoint_id}' not found.")

        if from_checkpoint_id is None:
            candidate_sequence = to_checkpoint.sequence - 1
            from_checkpoint = next(
                (checkpoint for checkpoint in checkpoints if checkpoint.sequence == candidate_sequence),
                None,
            )
        else:
            from_checkpoint = checkpoint_map.get(from_checkpoint_id)
            if from_checkpoint is None:
                raise NotFoundError(f"Checkpoint '{from_checkpoint_id}' not found.")

        to_pack = self.repository.get_delta_pack(to_checkpoint.delta_pack_id)
        if to_pack is None:
            raise NotFoundError(f"Delta pack '{to_checkpoint.delta_pack_id}' not found.")
        from_pack = self.repository.get_delta_pack(from_checkpoint.delta_pack_id) if from_checkpoint else None
        diff = compute_delta_pack_diff(from_pack, self._delta_pack_sections(to_pack))
        summary = self._build_diff_summary(diff)
        return SessionDiff(
            session_id=session_id,
            agent_id=session.agent_id,
            from_checkpoint_id=from_checkpoint.checkpoint_id if from_checkpoint else "",
            to_checkpoint_id=to_checkpoint.checkpoint_id,
            from_delta_pack_id=from_pack.delta_pack_id if from_pack else "",
            to_delta_pack_id=to_pack.delta_pack_id,
            summary=summary,
            added=diff.added,
            dropped=diff.dropped,
        )

    def doctor_memory(self, requester_agent_id: str, session_id: str) -> MemoryDoctorReport:
        session = self.get_session(requester_agent_id, session_id)
        checkpoints = self.repository.list_compaction_checkpoints(session_id)
        latest_checkpoint = checkpoints[-1] if checkpoints else None
        latest_pack = (
            self.repository.get_delta_pack(session.latest_delta_pack_id) if session.latest_delta_pack_id else None
        )
        warnings: list[str] = []
        recommendations: list[str] = []
        if latest_checkpoint is None:
            warnings.append("No checkpoints have been created for this session yet.")
            recommendations.append("Create a checkpoint before the next context-boundary event.")
        else:
            events_since_checkpoint = max(session.event_count - latest_checkpoint.event_count, 0)
            if events_since_checkpoint >= 15:
                warnings.append(f"{events_since_checkpoint} events have accumulated since the last checkpoint.")
                recommendations.append("Create a fresh checkpoint to avoid compaction drift.")
        if latest_pack is not None:
            if latest_pack.stale_items:
                warnings.append(f"{len(latest_pack.stale_items)} stale items need review or refresh.")
                recommendations.append("Refresh or drop stale notes before the next resume.")
            if latest_pack.untrusted_items:
                warnings.append(f"{len(latest_pack.untrusted_items)} items are marked untrusted.")
                recommendations.append("Validate untrusted items before treating them as durable context.")
            if len(latest_pack.open_tasks) > 12:
                recommendations.append("Reduce or group open tasks to keep restoration payloads focused.")
        status = "warning" if warnings else "ok"
        return MemoryDoctorReport(
            session_id=session_id,
            agent_id=session.agent_id,
            total_events=session.event_count,
            checkpoint_count=session.checkpoint_count,
            latest_checkpoint_at=latest_checkpoint.created_at if latest_checkpoint else None,
            unresolved_task_count=len(latest_pack.open_tasks) if latest_pack else 0,
            failure_count=len(latest_pack.failures) if latest_pack else 0,
            stale_item_count=len(latest_pack.stale_items) if latest_pack else 0,
            untrusted_item_count=len(latest_pack.untrusted_items) if latest_pack else 0,
            branch_backed=self._session_branch_backed(session),
            latest_cache_status=latest_pack.cache_status if latest_pack else "",
            likely_prefix_reuse=self._branch_has_reusable_prefix(session),
            warnings=warnings,
            recommendations=recommendations,
            status=status,
        )

    def _should_auto_checkpoint(self, event: SessionEvent) -> bool:
        if event.event_type in {"context_pressure", "checkpoint", "compact", "plan_change"}:
            return True
        remaining = event.metadata.get("context_remaining_pct", "").strip()
        if remaining:
            try:
                return float(remaining) <= 15.0
            except ValueError:
                return False
        return False

    def _checkpoint_reason_for_event(self, event: SessionEvent) -> str:
        if event.event_type in {"context_pressure", "compact"}:
            return "context_pressure"
        if event.event_type == "plan_change":
            return "plan_change"
        if event.event_type == "checkpoint":
            return "manual"
        return "reactive"

    def _estimate_compaction_tokens(
        self,
        sections: dict[str, list[str]],
        summary: str,
        instructions: list[str],
    ) -> int:
        tokens = self._estimate_tokens(summary) if summary else 0
        for bucket in SESSION_BUCKETS:
            items = sections.get(bucket, [])
            if not items:
                continue
            tokens += 4
            for item in items:
                tokens += self._estimate_tokens(item) + 2
        for instruction in instructions:
            tokens += self._estimate_tokens(instruction) + 2
        return max(tokens, 1)

    def _build_delta_summary(self, sections: dict[str, list[str]], token_budget: int) -> str:
        remaining = max(token_budget, 1)
        parts: list[str] = []
        for bucket in (
            "decisions",
            "constraints",
            "open_tasks",
            "failures",
            "changed_files",
            "important_artifacts",
            "notes",
        ):
            for item in sections.get(bucket, [])[:2]:
                part = f"{bucket.replace('_', ' ')}: {item}"
                part_tokens = self._estimate_tokens(part)
                if parts and remaining < part_tokens:
                    return " ".join(parts)
                if remaining < part_tokens:
                    break
                parts.append(part)
                remaining -= part_tokens
        return " ".join(parts)

    def _trim_delta_sections(self, sections: dict[str, list[str]], token_budget: int) -> dict[str, list[str]]:
        trimmed = {bucket: [] for bucket in SESSION_BUCKETS}
        remaining = max(token_budget, 1)
        for bucket in (
            "decisions",
            "constraints",
            "open_tasks",
            "failures",
            "changed_files",
            "important_artifacts",
            "external_references",
            "commands",
            "resolved_items",
            "notes",
        ):
            items = sections.get(bucket, [])
            if not items or remaining <= 0:
                continue
            remaining -= 4
            if remaining <= 0:
                break
            for item in items:
                item_tokens = self._estimate_tokens(item) + 2
                if item_tokens > remaining:
                    break
                trimmed[bucket].append(item)
                remaining -= item_tokens
        return trimmed

    def _delta_pack_sections(self, pack: DeltaPack) -> dict[str, list[str]]:
        return {
            "decisions": list(pack.decisions),
            "constraints": list(pack.constraints),
            "open_tasks": list(pack.open_tasks),
            "failures": list(pack.failures),
            "resolved_items": list(pack.resolved_items),
            "important_artifacts": list(pack.important_artifacts),
            "external_references": list(pack.external_references),
            "changed_files": list(pack.changed_files),
            "commands": list(pack.commands),
            "notes": list(pack.notes),
        }

    def _build_diff_summary(self, diff: Any) -> str:
        added_count = sum(len(items) for items in diff.added.values())
        dropped_count = sum(len(items) for items in diff.dropped.values())
        if added_count == 0 and dropped_count == 0:
            return "No material context changes between checkpoints."
        return f"Added {added_count} item(s) and dropped {dropped_count} item(s) across the compared checkpoints."

    def _checkpoint_session_internal(
        self,
        session: Session,
        *,
        reason: str,
        token_budget: int,
    ) -> tuple[CompactionCheckpoint, DeltaPack]:
        now = utcnow()
        events = self.repository.list_session_events(session.session_id)
        previous_pack = (
            self.repository.get_delta_pack(session.latest_delta_pack_id) if session.latest_delta_pack_id else None
        )
        branch_backed = self._session_branch_backed(session)
        cache_status = "miss"
        cache_base_checkpoint_id = ""
        cache_base_pack: DeltaPack | None = None
        reused_event_count = 0
        recomputed_event_count = len(events)
        invalidated_reasons: list[str] = []

        reduced: dict[str, Any] | None = None
        if branch_backed:
            seed_checkpoint, seed_pack, seed_events, seed_event_count, seed_issues = self._branch_cache_seed(
                session, events
            )
            invalidated_reasons.extend(seed_issues)
            valid_snapshot, snapshot_issues = self._is_snapshot_pack_reusable(seed_pack)
            if valid_snapshot and seed_pack is not None:
                try:
                    reduced = reduce_session_events(seed_events, base_snapshot=seed_pack.state_snapshot)
                    cache_status = "prefix_hit"
                    cache_base_checkpoint_id = seed_checkpoint.checkpoint_id if seed_checkpoint else ""
                    cache_base_pack = seed_pack
                    reused_event_count = seed_event_count
                    recomputed_event_count = len(seed_events)
                except ValueError:
                    invalidated_reasons.append("corrupt_state_snapshot")
            else:
                invalidated_reasons.extend(snapshot_issues)

        if reduced is None:
            if branch_backed:
                effective_events, lineage_issues = self._build_effective_session_events(session)
                invalidated_reasons.extend(lineage_issues)
                reduced = reduce_session_events(effective_events)
                cache_status = "fallback_recompute"
                reused_event_count = 0
                recomputed_event_count = len(effective_events)
            else:
                reduced = reduce_session_events(events)
                cache_status = "miss"
                reused_event_count = 0
                recomputed_event_count = len(events)

        full_sections = {bucket: list(reduced.get(bucket, [])) for bucket in SESSION_BUCKETS}
        summary_budget = max(int(max(token_budget, 1) * 0.25), 20)
        summary = self._build_delta_summary(full_sections, summary_budget)
        summary_tokens = self._estimate_tokens(summary) if summary else 0
        trimmed_sections = self._trim_delta_sections(full_sections, max(token_budget - summary_tokens - 40, 1))
        diff = compute_delta_pack_diff(previous_pack, trimmed_sections)
        instructions = default_restoration_instructions(trimmed_sections)
        prompt = build_restoration_prompt(
            title=session.title,
            source=session.source,
            summary=summary,
            sections=trimmed_sections,
            instructions=instructions,
        )
        while self._estimate_compaction_tokens(trimmed_sections, summary, instructions) > token_budget:
            trimmed = False
            for bucket in (
                "notes",
                "commands",
                "external_references",
                "important_artifacts",
                "changed_files",
                "failures",
                "open_tasks",
            ):
                if trimmed_sections[bucket]:
                    trimmed_sections[bucket].pop()
                    trimmed = True
                    break
            if not trimmed:
                break
            instructions = default_restoration_instructions(trimmed_sections)
            prompt = build_restoration_prompt(
                title=session.title,
                source=session.source,
                summary=summary,
                sections=trimmed_sections,
                instructions=instructions,
            )

        delta_pack_id = new_id("dpk")
        checkpoint_id = new_id("chk")
        if previous_pack and previous_pack.base_pack_id:
            base_pack_id = previous_pack.base_pack_id
        elif cache_base_pack and cache_base_pack.base_pack_id:
            base_pack_id = cache_base_pack.base_pack_id
        else:
            base_pack_id = delta_pack_id
        delta_pack = DeltaPack(
            delta_pack_id=delta_pack_id,
            checkpoint_id=checkpoint_id,
            session_id=session.session_id,
            agent_id=session.agent_id,
            sequence=session.checkpoint_count + 1,
            checkpoint_reason=reason,
            generated_at=now,
            token_budget=token_budget,
            tokens_used=min(self._estimate_compaction_tokens(trimmed_sections, summary, instructions), token_budget),
            summary=summary,
            base_pack_id=base_pack_id,
            delta_from_pack_id=previous_pack.delta_pack_id if previous_pack else "",
            decisions=trimmed_sections["decisions"],
            constraints=trimmed_sections["constraints"],
            open_tasks=trimmed_sections["open_tasks"],
            failures=trimmed_sections["failures"],
            resolved_items=trimmed_sections["resolved_items"],
            important_artifacts=trimmed_sections["important_artifacts"],
            external_references=trimmed_sections["external_references"],
            changed_files=trimmed_sections["changed_files"],
            commands=trimmed_sections["commands"],
            notes=trimmed_sections["notes"],
            stale_items=list(reduced.get("stale_items", [])),
            untrusted_items=list(reduced.get("untrusted_items", [])),
            dropped_items=flatten_diff_items(diff),
            restoration_prompt=prompt,
            restoration_instructions=instructions,
            included_event_ids=list(reduced.get("included_event_ids", [])),
            event_count=session.event_count,
            cache_status=cache_status,
            cache_base_checkpoint_id=cache_base_checkpoint_id,
            reused_event_count=reused_event_count,
            recomputed_event_count=recomputed_event_count,
            invalidated_reasons=list(dict.fromkeys(item for item in invalidated_reasons if item)),
            state_snapshot=dict(reduced.get("state_snapshot", {})),
            state_snapshot_version=str(reduced.get("state_snapshot_version", STATE_SNAPSHOT_VERSION)),
            state_snapshot_event_count=reused_event_count + recomputed_event_count,
            diff=diff,
        )
        checkpoint = CompactionCheckpoint(
            checkpoint_id=checkpoint_id,
            session_id=session.session_id,
            agent_id=session.agent_id,
            sequence=delta_pack.sequence,
            reason=reason,
            created_at=now,
            delta_pack_id=delta_pack.delta_pack_id,
            base_checkpoint_id=session.latest_checkpoint_id,
            event_count=delta_pack.event_count,
            restoration_prompt=delta_pack.restoration_prompt,
            restoration_instructions=list(delta_pack.restoration_instructions),
            summary=delta_pack.summary,
        )
        self.repository.save_delta_pack(delta_pack)
        self.repository.save_compaction_checkpoint(checkpoint)
        session.latest_checkpoint_id = checkpoint.checkpoint_id
        session.latest_delta_pack_id = delta_pack.delta_pack_id
        session.checkpoint_count += 1
        session.updated_at = now
        self.repository.update_session(session)
        self._audit(
            "checkpoint_session",
            actor_agent_id=session.agent_id,
            details={
                "session_id": session.session_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "delta_pack_id": delta_pack.delta_pack_id,
                "reason": reason,
                "cache_status": delta_pack.cache_status,
            },
        )
        return checkpoint, delta_pack
