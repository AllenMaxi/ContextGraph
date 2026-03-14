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
    UNREVIEWED = "unreviewed"
    ATTESTED = "attested"
    CHALLENGED = "challenged"
    EXPIRED = "expired"


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


class SubscriptionTarget(StrEnum):
    AGENT = "agent"
    TOPIC = "topic"
    ENTITY = "entity"
    ORG = "org"


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


@dataclass(slots=True)
class Memory:
    memory_id: str
    agent_id: str
    content: str
    visibility: Visibility
    license: str
    metadata: dict[str, str]
    created_at: datetime
    updated_at: datetime


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
