from __future__ import annotations

from datetime import datetime

from ..models import DeliveryMode, JobStatus, JobType, SubscriptionTarget, ValidationStatus, Visibility
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
    access_list: list[str] | None = Field(
        default=None, description="Agent/org IDs allowed access (for 'shared' visibility)"
    )
    price: float | None = Field(
        default=None, ge=0.0, description="Price per recall (0 = free). Currency set via CG_PAYMENT_CURRENCY."
    )


class RecallRequest(BaseModel):
    agent_id: str | None = None
    query: str
    limit: int = Field(default=10, ge=1, le=100)


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


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    memory_id: str
    agent_id: str
    content: str
    visibility: Visibility
    license: str
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    access_list: list[str] = Field(default_factory=list)
    price: float = 0.0


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


class AgentDefaultsUpdateRequest(BaseModel):
    default_visibility: Visibility | None = None
    default_access_list: list[str] | None = None
    default_price: float | None = Field(default=None, ge=0.0)


class TrustScoreResponse(BaseModel):
    agent_id: str
    reputation_score: float
    total_claims: int
    attested_claims: int
    challenged_claims: int
    unreviewed_claims: int
    followers_count: int


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
