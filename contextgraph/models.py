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


class AgentDiscoverability(StrEnum):
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
    profile_visibility: AgentDiscoverability = AgentDiscoverability.ORG
    profile_access_list: list[str] = field(default_factory=list)
    profile_summary: str = ""
    profile_links: dict[str, str] = field(default_factory=dict)
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
    # Memory OS v1 extensions — all optional, additive-only
    source_type: str = ""  # e.g. "transcript", "document", "task_log", "handoff"
    source_uri: str = ""  # external reference URI
    source_label: str = ""  # human-readable source name
    section_refs: list[str] = field(default_factory=list)  # section labels within content
    ingest_metadata: dict[str, str] = field(default_factory=dict)  # ingestion-time metadata


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
    # Memory OS v1 — optional section-level provenance
    source_memory_section: str = ""  # section label within the source memory
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
class ClaimSearchResult:
    claim: Claim
    text_score_raw: float = 0.0


@dataclass(slots=True)
class RecallHit:
    claim: Claim
    score: float
    entities: list[Entity]
    memory_content: str = ""
    source_agent_name: str = ""
    source_reputation_score: float = 0.0


@dataclass(slots=True)
class RecallScoreBreakdown:
    text_score_raw: float = 0.0
    text_score: float = 0.0
    freshness: float = 0.0
    confidence_bonus: float = 0.0
    validation_bonus: float = 0.0
    context_bonus: float = 0.0
    final_score: float = 0.0


@dataclass(slots=True)
class RecallDecision:
    claim_id: str
    memory_id: str
    statement: str
    visibility: Visibility
    validation_status: ValidationStatus
    outcome: str
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0
    score_breakdown: RecallScoreBreakdown | None = None


@dataclass(slots=True)
class RecallExplanation:
    query: str
    total_claims: int
    hits: list[RecallHit] = field(default_factory=list)
    decisions: list[RecallDecision] = field(default_factory=list)
    filtered_counts: dict[str, int] = field(default_factory=dict)


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


# ---------------------------------------------------------------------------
# Memory OS v1 — Context Pack types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ContextPackClaim:
    """A claim included in a context pack with its relevance metadata."""

    claim_id: str
    statement: str
    source_memory_id: str
    source_agent_id: str
    confidence: float
    freshness_score: float
    validation_status: str
    score: float
    source_memory_section: str = ""
    source_label: str = ""
    locked: bool = False  # True when paid claim not unlocked


@dataclass(slots=True)
class ContextPackSource:
    """Source memory referenced by claims in a context pack."""

    memory_id: str
    agent_id: str
    source_type: str = ""
    source_label: str = ""
    source_uri: str = ""
    claim_count: int = 0


@dataclass(slots=True)
class ContextPackExplanation:
    """Detailed explanation of why claims were included/excluded."""

    included_reasons: dict[str, list[str]] = field(default_factory=dict)  # claim_id -> reasons
    excluded_reasons: dict[str, list[str]] = field(default_factory=dict)  # claim_id -> reasons
    conflict_pairs: list[tuple[str, str]] = field(default_factory=list)  # pairs of conflicting claim_ids
    filter_counts: dict[str, int] = field(default_factory=dict)  # filter_name -> count


@dataclass(slots=True)
class ContextPack:
    """Compiled, governed, token-budgeted context for an agent."""

    pack_id: str
    agent_id: str
    query: str
    included_claims: list[ContextPackClaim]
    sources: list[ContextPackSource]
    token_budget: int
    tokens_used: int
    generated_at: datetime
    summary: str = ""
    session_id: str = ""
    base_pack_id: str = ""
    delta_from_pack_id: str = ""
    checkpoint_reason: str = ""
    restoration_prompt: str = ""
    restoration_instructions: list[str] = field(default_factory=list)
    excluded_claims: list[ContextPackClaim] = field(default_factory=list)
    conflicting_claims: list[ContextPackClaim] = field(default_factory=list)
    explanation: ContextPackExplanation | None = None


# ---------------------------------------------------------------------------
# Memory OS v2 — Reactive Delta Compaction types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Session:
    session_id: str
    agent_id: str
    title: str
    source: str
    status: str
    metadata: dict[str, str]
    created_at: datetime
    updated_at: datetime
    parent_session_id: str = ""
    forked_from_checkpoint_id: str = ""
    latest_checkpoint_id: str = ""
    latest_delta_pack_id: str = ""
    checkpoint_count: int = 0
    event_count: int = 0


@dataclass(slots=True)
class SessionEvent:
    event_id: str
    session_id: str
    agent_id: str
    event_type: str
    content: str
    created_at: datetime
    metadata: dict[str, str] = field(default_factory=dict)
    sequence: int = 0
    important: bool = False


@dataclass(slots=True)
class DeltaPackDiff:
    added: dict[str, list[str]] = field(default_factory=dict)
    dropped: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class SessionStateEntry:
    value: str
    observed_at: datetime


@dataclass(slots=True)
class DeltaPack:
    delta_pack_id: str
    checkpoint_id: str
    session_id: str
    agent_id: str
    sequence: int
    checkpoint_reason: str
    generated_at: datetime
    token_budget: int
    tokens_used: int
    summary: str = ""
    base_pack_id: str = ""
    delta_from_pack_id: str = ""
    decisions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    open_tasks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    resolved_items: list[str] = field(default_factory=list)
    important_artifacts: list[str] = field(default_factory=list)
    external_references: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    stale_items: list[str] = field(default_factory=list)
    untrusted_items: list[str] = field(default_factory=list)
    dropped_items: list[str] = field(default_factory=list)
    restoration_prompt: str = ""
    restoration_instructions: list[str] = field(default_factory=list)
    included_event_ids: list[str] = field(default_factory=list)
    event_count: int = 0
    cache_status: str = "miss"
    cache_base_checkpoint_id: str = ""
    reused_event_count: int = 0
    recomputed_event_count: int = 0
    invalidated_reasons: list[str] = field(default_factory=list)
    state_snapshot: dict[str, list[SessionStateEntry]] = field(default_factory=dict)
    state_snapshot_version: str = ""
    state_snapshot_event_count: int = 0
    diff: DeltaPackDiff | None = None


@dataclass(slots=True)
class CompactionCheckpoint:
    checkpoint_id: str
    session_id: str
    agent_id: str
    sequence: int
    reason: str
    created_at: datetime
    delta_pack_id: str
    base_checkpoint_id: str = ""
    event_count: int = 0
    restoration_prompt: str = ""
    restoration_instructions: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass(slots=True)
class SessionEventResult:
    session: Session
    event: SessionEvent
    checkpoint: CompactionCheckpoint | None = None
    delta_pack: DeltaPack | None = None


@dataclass(slots=True)
class SessionResume:
    session: Session
    checkpoint: CompactionCheckpoint | None = None
    delta_pack: DeltaPack | None = None


@dataclass(slots=True)
class SessionDiff:
    session_id: str
    agent_id: str
    from_checkpoint_id: str
    to_checkpoint_id: str
    from_delta_pack_id: str = ""
    to_delta_pack_id: str = ""
    summary: str = ""
    added: dict[str, list[str]] = field(default_factory=dict)
    dropped: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class MemoryDoctorReport:
    session_id: str
    agent_id: str
    total_events: int
    checkpoint_count: int
    latest_checkpoint_at: datetime | None
    unresolved_task_count: int
    failure_count: int
    stale_item_count: int
    untrusted_item_count: int
    branch_backed: bool = False
    latest_cache_status: str = ""
    likely_prefix_reuse: bool = False
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    status: str = "ok"
