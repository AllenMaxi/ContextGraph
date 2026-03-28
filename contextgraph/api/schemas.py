from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import (
    AgentDiscoverability,
    DeliveryMode,
    JobStatus,
    JobType,
    MemoryCurationStatus,
    SubscriptionTarget,
    ValidationStatus,
    Visibility,
)
from ..service import ReviewDecision
from ._compat import BaseModel, ConfigDict, Field


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    name: str
    org_id: str
    capabilities: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime
    erc8004_address: str = ""
    identity_verified: bool = False
    reputation_score: float = 0.0
    followers_count: int = 0
    default_visibility: Visibility = Visibility.PRIVATE
    default_access_list: list[str] = Field(default_factory=list)
    default_price: float = 0.0
    profile_visibility: AgentDiscoverability = AgentDiscoverability.ORG
    profile_access_list: list[str] = Field(default_factory=list)
    profile_summary: str = ""
    profile_links: dict[str, str] = Field(default_factory=dict)


class AgentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    name: str
    org_id: str
    capabilities: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime
    identity_verified: bool = False
    reputation_score: float = 0.0
    followers_count: int = 0
    profile_visibility: AgentDiscoverability = AgentDiscoverability.ORG
    profile_access_list: list[str] = Field(default_factory=list)
    profile_summary: str = ""
    profile_links: dict[str, str] = Field(default_factory=dict)


class AgentRegistrationRequest(BaseModel):
    name: str
    org_id: str
    capabilities: list[str] = Field(default_factory=list)
    erc8004_address: str = Field(default="", description="ERC-8004 on-chain address (optional)")
    default_visibility: Visibility | None = None
    default_access_list: list[str] | None = None
    default_price: float | None = Field(default=None, ge=0.0)


class AgentRegistrationResponse(AgentResponse):
    api_key: str


class MemoryStoreRequest(BaseModel):
    agent_id: str | None = None
    content: str = Field(..., max_length=102400)
    visibility: Visibility | None = None
    license: str = "internal"
    metadata: dict[str, str] = Field(default_factory=dict)
    evidence: list[str] | None = Field(default=None, description="Human-readable provenance notes for this memory.")
    citations: list[str] | None = Field(default=None, description="Source pointers such as URLs, paths, or ticket IDs.")
    access_list: list[str] | None = Field(
        default=None, description="Agent/org IDs allowed access (for 'shared' visibility)"
    )
    price: float | None = Field(
        default=None, ge=0.0, description="Price per recall (0 = free). Currency set via CG_PAYMENT_CURRENCY."
    )
    expires_in_days: int | None = Field(
        default=None,
        ge=0,
        description="Days until this memory expires. Set to 0 to disable automatic expiry.",
    )


class RecallRequest(BaseModel):
    agent_id: str | None = None
    query: str
    limit: int = Field(default=10, ge=1, le=100)


class RecallExplainRequest(RecallRequest):
    decision_limit: int = Field(default=25, ge=1, le=200)


class RelateRequest(BaseModel):
    agent_id: str | None = None
    entity_a: str
    entity_b: str
    max_depth: int = Field(default=2, ge=1, le=10)


class WatchRequest(BaseModel):
    agent_id: str | None = None
    query: str
    name: str | None = None
    delivery_mode: DeliveryMode = DeliveryMode.PULL
    filters: dict[str, str] = Field(default_factory=dict)


class ReviewClaimRequest(BaseModel):
    reviewer_agent_id: str | None = None
    claim_id: str
    decision: ReviewDecision
    reason: str = ""


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_id: str
    name: str
    entity_type: str
    alias_key: str
    created_at: datetime
    updated_at: datetime


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    entity_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    expires_at: datetime | None
    updated_at: datetime
    review_reasons: list[str] = Field(default_factory=list)
    source_org_id: str = ""
    access_list: list[str] = Field(default_factory=list)
    price: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    validated_at: datetime | None = None


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    memory_id: str
    agent_id: str
    content: str
    visibility: Visibility
    validation_status: ValidationStatus
    license: str
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    access_list: list[str] = Field(default_factory=list)
    price: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    validated_at: datetime | None = None
    expires_at: datetime | None = None
    curation_status: MemoryCurationStatus = MemoryCurationStatus.ACTIVE
    curation_reason: str = ""
    curated_at: datetime | None = None
    # Memory OS v1 extensions
    source_type: str = ""
    source_uri: str = ""
    source_label: str = ""
    section_refs: list[str] = Field(default_factory=list)
    ingest_metadata: dict[str, str] = Field(default_factory=dict)


class ReviewTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    claim_id: str
    reason: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None


class ReviewQueueItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review: ReviewTaskResponse
    claim: ClaimResponse
    source_agent: AgentResponse


class StandingQueryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query_id: str
    agent_id: str
    name: str
    query: str
    filters: dict[str, str] = Field(default_factory=dict)
    delivery_mode: DeliveryMode
    status: str
    created_at: datetime
    updated_at: datetime


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_id: str
    query_id: str
    agent_id: str
    claim_id: str
    event_type: str
    created_at: datetime
    delivered: bool = False


class RecallHitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim: ClaimResponse
    score: float
    entities: list[EntityResponse] = Field(default_factory=list)
    memory_content: str = ""
    source_agent_name: str = ""
    source_reputation_score: float = 0.0


class RecallScoreBreakdownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    text_score_raw: float = 0.0
    text_score: float = 0.0
    freshness: float = 0.0
    confidence_bonus: float = 0.0
    validation_bonus: float = 0.0
    context_bonus: float = 0.0
    final_score: float = 0.0


class RecallDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: str
    memory_id: str
    statement: str
    visibility: Visibility
    validation_status: ValidationStatus
    outcome: str
    reasons: list[str] = Field(default_factory=list)
    score: float = 0.0
    score_breakdown: RecallScoreBreakdownResponse | None = None


class RecallExplanationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    total_claims: int
    hits: list[RecallHitResponse] = Field(default_factory=list)
    decisions: list[RecallDecisionResponse] = Field(default_factory=list)
    filtered_counts: dict[str, int] = Field(default_factory=dict)


class RelationPathResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entities: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    statements: list[str] = Field(default_factory=list)


class StoreResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    memory: MemoryResponse
    claims: list[ClaimResponse] = Field(default_factory=list)
    entities: list[EntityResponse] = Field(default_factory=list)
    review_tasks: list[ReviewTaskResponse] = Field(default_factory=list)


class AuditEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    action: str
    actor_agent_id: str
    target_agent_id: str | None
    details: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime


class BackgroundJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    job_type: JobType
    agent_id: str
    org_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    attempt_count: int
    max_attempts: int
    next_run_at: datetime | None = None
    payload_summary: dict[str, object] = Field(default_factory=dict)
    result_summary: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class OperatorSummaryResponse(BaseModel):
    org_id: str
    pending_review_count: int
    claim_count: int
    expired_claim_count: int
    reviewed_claim_count: int
    job_status_counts: dict[str, int] = Field(default_factory=dict)
    health: dict[str, object] = Field(default_factory=dict)


class FollowRequest(BaseModel):
    target_type: SubscriptionTarget
    target_id: str


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subscription_id: str
    follower_agent_id: str
    target_type: SubscriptionTarget
    target_id: str
    created_at: datetime
    active: bool


class ClaimUpdateRequest(BaseModel):
    visibility: Visibility | None = None
    price: float | None = Field(default=None, ge=0.0)
    access_list: list[str] | None = None


class MemoryAccessUpdateRequest(BaseModel):
    visibility: Visibility | None = None
    price: float | None = Field(default=None, ge=0.0)
    access_list: list[str] | None = None


class MemoryCurationUpdateRequest(BaseModel):
    curation_status: MemoryCurationStatus
    reason: str = ""


class AgentDefaultsUpdateRequest(BaseModel):
    default_visibility: Visibility | None = None
    default_access_list: list[str] | None = None
    default_price: float | None = Field(default=None, ge=0.0)


class AgentProfileUpdateRequest(BaseModel):
    profile_visibility: AgentDiscoverability | None = None
    profile_access_list: list[str] | None = None
    profile_summary: str | None = Field(default=None, max_length=500)
    profile_links: dict[str, str] | None = None


class TrustScoreResponse(BaseModel):
    agent_id: str
    reputation_score: float
    total_claims: int
    attested_claims: int
    challenged_claims: int
    unreviewed_claims: int
    followers_count: int
    sentinel_verdict_count: int = 0
    status: str = "active"


class FeedItemResponse(BaseModel):
    memory_id: str
    memory_content: str
    agent_id: str
    visibility: str
    claims: list[ClaimResponse] = Field(default_factory=list)
    entities: list[EntityResponse] = Field(default_factory=list)
    source_agent_name: str
    source_org_id: str = ""
    source_reputation_score: float
    created_at: datetime
    is_paid: bool = False
    price: float = 0.0
    is_locked: bool = False
    requires_payment: bool = False


class DiscoverAgentsResponse(BaseModel):
    items: list[AgentProfileResponse] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class AgentActivityItemResponse(BaseModel):
    event_type: str
    timestamp: datetime
    claim: dict[str, Any] | None = None
    verdict: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None
    details: dict[str, str] = Field(default_factory=dict)


class AgentActivityResponse(BaseModel):
    items: list[AgentActivityItemResponse] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class AgentSuspendRequest(BaseModel):
    reason: str = "manual"


class SentinelVerdictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verdict_id: str
    sentinel_agent_id: str
    claim_id: str
    memory_id: str
    decision: str
    confidence: float
    reason: str
    conflicting_claim_id: str | None = None
    details: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime


class SentinelHealthResponse(BaseModel):
    sentinels_active: int
    total_verdicts: int
    last_canary_passed: bool | None = None


# ---------------------------------------------------------------------------
# Memory OS v1 — Context Pack schemas
# ---------------------------------------------------------------------------


class CompileContextRequest(BaseModel):
    agent_id: str | None = None
    query: str
    token_budget: int = Field(default=4000, ge=1, le=128000)
    limit: int = Field(default=50, ge=1, le=500)
    include_explanations: bool = False


class ContextPackClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    locked: bool = False


class ContextPackSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    memory_id: str
    agent_id: str
    source_type: str = ""
    source_label: str = ""
    source_uri: str = ""
    claim_count: int = 0


class ContextPackExplanationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    included_reasons: dict[str, list[str]] = Field(default_factory=dict)
    excluded_reasons: dict[str, list[str]] = Field(default_factory=dict)
    conflict_pairs: list[list[str]] = Field(default_factory=list)
    filter_counts: dict[str, int] = Field(default_factory=dict)


class ContextPackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pack_id: str
    agent_id: str
    query: str
    summary: str = ""
    included_claims: list[ContextPackClaimResponse] = Field(default_factory=list)
    conflicting_claims: list[ContextPackClaimResponse] = Field(default_factory=list)
    excluded_claims: list[ContextPackClaimResponse] = Field(default_factory=list)
    sources: list[ContextPackSourceResponse] = Field(default_factory=list)
    token_budget: int
    tokens_used: int
    generated_at: datetime
    explanation: ContextPackExplanationResponse | None = None
