from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Visibility(StrEnum):
    PRIVATE = "private"
    ORG = "org"
    SHARED = "shared"
    PUBLISHED = "published"


class ValidationStatus(StrEnum):
    # Canonical members (keep existing serialized values)
    UNREVIEWED = "unreviewed"
    ATTESTED = "attested"
    CHALLENGED = "challenged"
    EXPIRED = "expired"
    # New members
    REJECTED = "rejected"
    TRUSTED = "trusted"
    # Forward-looking aliases (point to same members)
    PENDING = "unreviewed"
    VALIDATED = "attested"
    DISPUTED = "challenged"


class AgentStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class AgentRole(StrEnum):
    AGENT = "agent"
    SENTINEL = "sentinel"


class SentinelDecision(StrEnum):
    PASS = "pass"
    VALIDATE = "validate"
    DISPUTE = "dispute"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"
    BLOCK = "block"


class MemoryCurationStatus(StrEnum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class ReviewStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class DeliveryMode(StrEnum):
    PULL = "pull"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"
    A2A = "a2a"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


class JobType(StrEnum):
    STORE_MEMORY = "store_memory"
    DELIVER_NOTIFICATION = "deliver_notification"
    SWEEP_EXPIRED_CLAIMS = "sweep_expired_claims"
    SWEEP_IDLE_AGENTS = "sweep_idle_agents"
    PROMOTE_TRUSTED_CLAIMS = "promote_trusted_claims"
    SENTINEL_AUDIT = "sentinel_audit"
    SENTINEL_CANARY = "sentinel_canary"


class SubscriptionTarget(StrEnum):
    AGENT = "agent"
    TOPIC = "topic"
    ENTITY = "entity"
    ORG = "org"


class ClaimImpact(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class ProvenanceEntry:
    agent_id: str
    action: str  # "created", "attested", "challenged", "derived", "updated"
    timestamp: datetime
    confidence_at_action: float
    detail: str = ""


@dataclass(slots=True)
class PatternFilter:
    entities: list[str] = field(default_factory=list)
    entity_types: list[str] = field(default_factory=list)
    relation_types: list[str] = field(default_factory=list)
    min_confidence: float = 0.0
    source_org_ids: list[str] = field(default_factory=list)
    visibility_levels: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Agent:
    agent_id: str
    name: str
    org_id: str
    capabilities: list[str]
    api_key: str
    status: str
    created_at: datetime
    updated_at: datetime
    erc8004_address: str = ""
    identity_verified: bool = False
    reputation_score: float = 0.0
    followers_count: int = 0
    default_visibility: Visibility = Visibility.PRIVATE
    default_access_list: list[str] = field(default_factory=list)
    default_price: float = 0.0
    last_activity_at: datetime | None = None
    suspension_reason: str | None = None
    suspended_at: datetime | None = None
    role: str = "agent"


@dataclass(slots=True)
class Memory:
    memory_id: str
    agent_id: str
    content: str
    visibility: Visibility
    validation_status: ValidationStatus
    license: str
    metadata: dict[str, str]
    created_at: datetime
    updated_at: datetime
    access_list: list[str] = field(default_factory=list)
    price: float = 0.0
    evidence: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    validated_at: datetime | None = None
    expires_at: datetime | None = None
    curation_status: MemoryCurationStatus = MemoryCurationStatus.ACTIVE
    curation_reason: str = ""
    curated_at: datetime | None = None


@dataclass(slots=True)
class Entity:
    entity_id: str
    name: str
    entity_type: str
    alias_key: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class Claim:
    claim_id: str
    memory_id: str
    source_agent_id: str
    statement: str
    claim_type: str
    relation_type: str | None
    confidence: float
    freshness_score: float
    validation_status: ValidationStatus
    visibility: Visibility
    license: str
    entity_ids: list[str]
    created_at: datetime
    expires_at: datetime | None
    updated_at: datetime
    review_reasons: list[str] = field(default_factory=list)
    source_org_id: str = ""
    access_list: list[str] = field(default_factory=list)
    price: float = 0.0
    evidence: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    validated_at: datetime | None = None
    # Provenance chain — immutable audit trail
    provenance: list[ProvenanceEntry] = field(default_factory=list)
    derived_from: list[str] = field(default_factory=list)
    # Quorum / consensus for high-impact claims
    impact: ClaimImpact = ClaimImpact.LOW
    quorum_required: int = 0
    quorum_met: bool = True
    attestation_count: int = 0
    challenge_count: int = 0


@dataclass(slots=True)
class StandingQuery:
    query_id: str
    agent_id: str
    name: str
    query: str
    filters: dict[str, str]
    delivery_mode: DeliveryMode
    status: str
    created_at: datetime
    updated_at: datetime
    pattern: PatternFilter | None = None


@dataclass(slots=True)
class Notification:
    notification_id: str
    query_id: str
    agent_id: str
    claim_id: str
    event_type: str
    created_at: datetime
    delivered: bool = False


@dataclass(slots=True)
class ReviewTask:
    task_id: str
    claim_id: str
    reason: str
    status: ReviewStatus
    created_at: datetime
    resolved_at: datetime | None = None


@dataclass(slots=True)
class AuditEntry:
    audit_id: str
    action: str
    actor_agent_id: str
    target_agent_id: str | None
    details: dict[str, str]
    timestamp: datetime


@dataclass(slots=True)
class SentinelVerdict:
    verdict_id: str
    sentinel_agent_id: str
    claim_id: str
    memory_id: str
    decision: SentinelDecision
    confidence: float
    reason: str
    conflicting_claim_id: str | None
    details: dict[str, str]
    timestamp: datetime


@dataclass(slots=True)
class BackgroundJob:
    job_id: str
    job_type: JobType
    agent_id: str
    org_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    attempt_count: int = 0
    max_attempts: int = 1
    next_run_at: datetime | None = None
    payload_summary: dict[str, Any] = field(default_factory=dict)
    result_summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(slots=True)
class ReviewQueueItem:
    review: ReviewTask
    claim: Claim
    source_agent: Agent


@dataclass(slots=True)
class RecallHit:
    claim: Claim
    score: float
    entities: list[Entity]
    memory_content: str = ""
    source_agent_name: str = ""
    source_reputation_score: float = 0.0


@dataclass(slots=True)
class RelationPath:
    entities: list[str]
    claim_ids: list[str]
    statements: list[str]


@dataclass(slots=True)
class StoreResult:
    memory: Memory
    claims: list[Claim]
    entities: list[Entity]
    review_tasks: list[ReviewTask]


@dataclass(slots=True)
class Subscription:
    subscription_id: str
    follower_agent_id: str
    target_type: SubscriptionTarget
    target_id: str
    created_at: datetime
    active: bool = True
