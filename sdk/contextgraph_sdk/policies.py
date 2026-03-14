from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contextgraph.extraction import RuleBasedExtractor
from contextgraph.utils import jaccard_similarity

from .client import ContextGraph


IMPORTANT_KEYWORDS = {
    "deadline",
    "delayed",
    "error",
    "escalation",
    "fix",
    "incident",
    "latency",
    "outage",
    "pricing",
    "renewal",
    "request",
    "requested",
    "risk",
    "security",
    "severity",
    "urgent",
    "vendor",
}

SENSITIVE_KEYWORDS = {
    "api key",
    "credential",
    "password",
    "private key",
    "salary",
    "secret",
    "ssn",
    "token",
}

TASK_TOPIC_DEFAULTS = {
    "incident": ["latency", "outage", "severity"],
    "renewal": ["renewal risk", "pricing", "support"],
    "diligence": ["risk", "pricing", "compliance"],
    "research": ["pricing", "expansion", "regulation"],
    "security": ["risk", "security", "incident"],
    "support": ["latency", "fix", "escalation"],
}


@dataclass(slots=True)
class MemoryContext:
    workflow: str | None = None
    task_id: str | None = None
    task_type: str | None = None
    entity_names: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    source: str | None = None
    severity: str | None = None
    sensitive: bool = False
    shared_across_org: bool = True
    deadline: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MemoryPolicyDecision:
    should_store: bool
    visibility: str
    importance_score: int
    reasons: list[str] = field(default_factory=list)
    duplicate_claim_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class MemoryStoreOutcome:
    decision: MemoryPolicyDecision
    result: dict[str, Any] | None = None


@dataclass(slots=True)
class SubscriptionContext:
    task_id: str | None = None
    title: str | None = None
    task_type: str | None = None
    source_agent_id: str | None = None
    entity_names: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    delivery_mode: str = "pull"
    webhook_url: str | None = None
    filters: dict[str, str] = field(default_factory=dict)
    max_queries: int = 8


@dataclass(slots=True)
class SubscriptionPlan:
    query: str
    name: str
    delivery_mode: str
    filters: dict[str, str]
    reason: str
    created: bool = False
    query_id: str | None = None


class MemoryPolicyHelper:
    def __init__(
        self,
        client: ContextGraph,
        *,
        duplicate_similarity_threshold: float = 0.88,
        recent_claim_limit: int = 100,
    ) -> None:
        self.client = client
        self.extractor = RuleBasedExtractor()
        self.duplicate_similarity_threshold = duplicate_similarity_threshold
        self.recent_claim_limit = recent_claim_limit

    def evaluate(
        self,
        agent_id: str,
        content: str,
        *,
        context: MemoryContext | None = None,
        visibility: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> MemoryPolicyDecision:
        context = context or MemoryContext()
        content = content.strip()
        if not content:
            return MemoryPolicyDecision(
                should_store=False,
                visibility=visibility or self._default_visibility(context),
                importance_score=0,
                reasons=["empty_content"],
                metadata=dict(metadata or {}),
            )

        lowered = content.lower()
        extracted_claims = self.extractor.extract(content)
        reasons: list[str] = []
        score = 0

        if extracted_claims:
            score += 2
            reasons.append("extractable_claims")
        if any(keyword in lowered for keyword in IMPORTANT_KEYWORDS):
            score += 1
            reasons.append("important_keyword")
        if context.entity_names:
            score += 1
            reasons.append("task_entities")
        if context.severity and context.severity.lower() in {"high", "critical", "sev1", "sev2"}:
            score += 2
            reasons.append("high_severity")
        if context.deadline or any(term in lowered for term in {"today", "tomorrow", "asap", "deadline"}):
            score += 1
            reasons.append("deadline_or_urgency")
        if context.task_type and context.task_type.lower() in TASK_TOPIC_DEFAULTS:
            score += 1
            reasons.append("tracked_workflow")

        decision_visibility = visibility or self._default_visibility(context, content=lowered)
        duplicate_claim_id = self._find_duplicate_claim(agent_id, extracted_claims)
        if duplicate_claim_id is not None:
            reasons.append("duplicate_claim")
            return MemoryPolicyDecision(
                should_store=False,
                visibility=decision_visibility,
                importance_score=score,
                reasons=reasons,
                duplicate_claim_id=duplicate_claim_id,
                metadata=self._build_metadata(context, metadata, reasons, score),
            )

        should_store = score >= 2 and len(content.split()) >= 3
        if not should_store and len(content.split()) < 3:
            reasons.append("too_short")

        return MemoryPolicyDecision(
            should_store=should_store,
            visibility=decision_visibility,
            importance_score=score,
            reasons=reasons,
            metadata=self._build_metadata(context, metadata, reasons, score),
        )

    def store_if_important(
        self,
        agent_id: str,
        content: str,
        *,
        context: MemoryContext | None = None,
        visibility: str | None = None,
        metadata: dict[str, str] | None = None,
        asynchronous: bool = True,
    ) -> MemoryStoreOutcome:
        decision = self.evaluate(
            agent_id=agent_id,
            content=content,
            context=context,
            visibility=visibility,
            metadata=metadata,
        )
        if not decision.should_store:
            return MemoryStoreOutcome(decision=decision)
        if asynchronous:
            result = self.client.store_async(
                agent_id=agent_id,
                content=content,
                visibility=decision.visibility,
                metadata=decision.metadata,
            )
        else:
            result = self.client.store(
                agent_id=agent_id,
                content=content,
                visibility=decision.visibility,
                metadata=decision.metadata,
            )
        return MemoryStoreOutcome(decision=decision, result=result)

    def _default_visibility(self, context: MemoryContext, content: str = "") -> str:
        lowered = content.lower() if content else ""
        if context.sensitive or any(keyword in lowered for keyword in SENSITIVE_KEYWORDS):
            return "private"
        if context.shared_across_org:
            return "shared"
        return "private"

    def _find_duplicate_claim(self, agent_id: str, extracted_claims: list[Any]) -> str | None:
        if not extracted_claims:
            return None
        existing_claims = self.client.claims(agent_id, limit=self.recent_claim_limit)
        for candidate in extracted_claims:
            for existing in existing_claims:
                existing_claim = existing if "statement" in existing else existing.get("claim", {})
                statement = str(existing_claim.get("statement", ""))
                if not statement:
                    continue
                if jaccard_similarity(candidate.statement, statement) >= self.duplicate_similarity_threshold:
                    return str(existing_claim.get("claim_id", ""))
        return None

    def _build_metadata(
        self,
        context: MemoryContext,
        metadata: dict[str, str] | None,
        reasons: list[str],
        score: int,
    ) -> dict[str, str]:
        built = dict(metadata or {})
        built["memory_policy_reasons"] = ",".join(reasons)
        built["memory_policy_score"] = str(score)
        built["memory_policy_source"] = "sdk"
        if context.workflow:
            built.setdefault("workflow", context.workflow)
        if context.task_id:
            built.setdefault("task_id", context.task_id)
        if context.task_type:
            built.setdefault("task_type", context.task_type)
        if context.source:
            built.setdefault("source", context.source)
        if context.severity:
            built.setdefault("severity", context.severity)
        if context.tags:
            built.setdefault("tags", ",".join(context.tags))
        return built


class SubscriptionPolicyManager:
    def __init__(self, client: ContextGraph) -> None:
        self.client = client

    def ensure_task_subscriptions(
        self,
        agent_id: str,
        context: SubscriptionContext,
    ) -> list[SubscriptionPlan]:
        plans = self._derive_plans(context)
        existing = self.client.watches(agent_id, include_inactive=False)
        results: list[SubscriptionPlan] = []
        for plan in plans:
            matched = self._match_existing(existing, plan)
            if matched is not None:
                plan.created = False
                plan.query_id = str(matched.get("query_id"))
                results.append(plan)
                continue
            created = self.client.watch(
                agent_id=agent_id,
                query=plan.query,
                name=plan.name,
                delivery_mode=plan.delivery_mode,
                filters=plan.filters,
            )
            plan.created = True
            plan.query_id = str(created.get("query_id"))
            results.append(plan)
        return results

    def deactivate_task_subscriptions(self, agent_id: str, task_id: str) -> list[dict[str, Any]]:
        watches = self.client.watches(agent_id, include_inactive=False)
        deactivated: list[dict[str, Any]] = []
        for watch in watches:
            filters = watch.get("filters", {})
            if filters.get("task_id") != task_id:
                continue
            deactivated.append(self.client.deactivate_watch(agent_id, str(watch["query_id"])))
        return deactivated

    def _derive_plans(self, context: SubscriptionContext) -> list[SubscriptionPlan]:
        queries: list[SubscriptionPlan] = []
        base_filters = dict(context.filters)
        if context.task_id:
            base_filters.setdefault("task_id", context.task_id)
        base_filters.setdefault("policy_source", "subscription_manager")
        if context.task_type:
            base_filters.setdefault("task_type", context.task_type)
        if context.source_agent_id:
            base_filters.setdefault("source_agent_id", context.source_agent_id)
        if context.webhook_url:
            base_filters["webhook_url"] = context.webhook_url

        topics = list(context.topics)
        if context.task_type:
            for topic in TASK_TOPIC_DEFAULTS.get(context.task_type.lower(), []):
                if topic not in topics:
                    topics.append(topic)
        raw_queries: list[tuple[str, str]] = []
        for entity in context.entity_names:
            raw_queries.append((entity, "entity"))
        for topic in topics:
            raw_queries.append((topic, "topic"))
        for keyword in context.keywords:
            raw_queries.append((keyword, "keyword"))
        for entity in context.entity_names:
            for topic in topics:
                raw_queries.append((f"{entity} {topic}", "entity_topic"))

        seen: set[str] = set()
        for query, reason in raw_queries:
            normalized = " ".join(query.split()).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            name_parts = [context.title or context.task_type or "Subscription", normalized]
            name = " - ".join(part for part in name_parts if part)
            queries.append(
                SubscriptionPlan(
                    query=normalized,
                    name=name[:120],
                    delivery_mode=context.delivery_mode,
                    filters=dict(base_filters),
                    reason=reason,
                )
            )
            if len(queries) >= max(1, context.max_queries):
                break
        return queries

    def _match_existing(self, existing: list[dict[str, Any]], plan: SubscriptionPlan) -> dict[str, Any] | None:
        for watch in existing:
            if watch.get("query") != plan.query:
                continue
            if watch.get("delivery_mode") != plan.delivery_mode:
                continue
            if dict(watch.get("filters", {})) != plan.filters:
                continue
            if watch.get("status") != "active":
                continue
            return watch
        return None
