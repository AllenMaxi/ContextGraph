from __future__ import annotations

from typing import TYPE_CHECKING

from .bootstrap import create_service
from .config import Settings, settings
from .delivery import DeliveryRequest, NotificationDispatcher, WebhookNotificationDispatcher
from .eval_dataset import (
    AgentTraceRecord,
    build_evaluation_cases_from_traces,
    load_agent_trace_records,
    write_evaluation_cases,
)
from .evaluation import EvaluationCase, EvaluationReport, evaluate_extractor, load_evaluation_cases, report_to_dict
from .extraction import Extractor, RuleBasedExtractor
from .models import (
    Agent,
    AuditEntry,
    BackgroundJob,
    Claim,
    ClaimSearchResult,
    CompactionCheckpoint,
    ContextPack,
    ContextPackClaim,
    ContextPackExplanation,
    ContextPackSource,
    DeltaPack,
    DeltaPackDiff,
    MemoryDoctorReport,
    Notification,
    RecallDecision,
    RecallExplanation,
    RecallHit,
    RecallScoreBreakdown,
    RelationPath,
    ReviewTask,
    Session,
    SessionDiff,
    SessionEvent,
    SessionEventResult,
    SessionResume,
    StandingQuery,
    StoreResult,
)
from .service import ContextGraphService
from .web import create_app

if TYPE_CHECKING:
    from .anthropic_memory import ContextGraphAnthropicMemoryTool


def __getattr__(name: str) -> object:
    if name == "ContextGraphAnthropicMemoryTool":
        from .anthropic_memory import ContextGraphAnthropicMemoryTool

        return ContextGraphAnthropicMemoryTool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Agent",
    "AgentTraceRecord",
    "AuditEntry",
    "BackgroundJob",
    "build_evaluation_cases_from_traces",
    "Claim",
    "ClaimSearchResult",
    "CompactionCheckpoint",
    "ContextGraphAnthropicMemoryTool",
    "ContextGraphService",
    "ContextPack",
    "ContextPackClaim",
    "ContextPackExplanation",
    "ContextPackSource",
    "DeltaPack",
    "DeltaPackDiff",
    "DeliveryRequest",
    "EvaluationCase",
    "EvaluationReport",
    "Extractor",
    "MemoryDoctorReport",
    "NotificationDispatcher",
    "RuleBasedExtractor",
    "WebhookNotificationDispatcher",
    "create_app",
    "create_service",
    "evaluate_extractor",
    "load_agent_trace_records",
    "load_evaluation_cases",
    "Notification",
    "RecallDecision",
    "RecallExplanation",
    "RecallHit",
    "RecallScoreBreakdown",
    "RelationPath",
    "report_to_dict",
    "ReviewTask",
    "Session",
    "SessionDiff",
    "SessionEvent",
    "SessionEventResult",
    "SessionResume",
    "Settings",
    "StandingQuery",
    "StoreResult",
    "settings",
    "write_evaluation_cases",
]
