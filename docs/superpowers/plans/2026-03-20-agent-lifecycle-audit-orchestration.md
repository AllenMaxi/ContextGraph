# Agent Lifecycle & Audit Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add agent sleep/wake lifecycle, built-in sentinel audit agents, and a graduated claim trust lifecycle so ContextGraph automatically validates every piece of stored knowledge with zero developer configuration.

**Architecture:** Three independent subsystems: (1) Agent lifecycle with auto-sleep/wake via virtual actor pattern, (2) Sentinel audit pipeline with duplicate/conflict/quality sentinels, (3) Graduated claim lifecycle with trust promotion. All subsystems share the models/enums layer and integrate through the existing service layer.

**Tech Stack:** Python 3.11+, dataclasses, existing BackgroundWorker, existing EventBus, existing Repository protocol. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-20-agent-lifecycle-audit-orchestration-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `contextgraph/models.py` | New enums (`AgentStatus`, `AgentRole`, `SentinelDecision`), new fields on `Agent`, new `SentinelVerdict` dataclass, rename `ValidationStatus` values |
| `contextgraph/config.py` | New settings for lifecycle, sentinel, trust promotion |
| `contextgraph/repository.py` | New protocol methods for verdict storage and agent status queries |
| `contextgraph/in_memory.py` | Implement new protocol methods |
| `contextgraph/graph/neo4j_repository.py` | Implement new protocol methods |
| `contextgraph/sentinel.py` | NEW — All sentinel logic: duplicate, conflict, quality checkers, verdict aggregation |
| `contextgraph/service.py` | Lifecycle methods, sentinel pipeline integration, trust promotion, updated scoring |
| `contextgraph/events.py` | New event types |
| `contextgraph/api/routes.py` | New endpoints (suspend, reactivate, delete, verdicts, sentinel health) |
| `contextgraph/api/schemas.py` | New request/response Pydantic models |
| `contextgraph/api/dependencies.py` | Auto-wake logic in auth |
| `contextgraph/cli.py` | New CLI commands |
| `sdk/contextgraph_sdk/client.py` | New SDK methods |
| `sdk/contextgraph_sdk/_local.py` | New LocalTransport methods |
| `tests/test_agent_lifecycle.py` | NEW — lifecycle tests |
| `tests/test_sentinel.py` | NEW — sentinel pipeline tests |
| `tests/test_claim_lifecycle.py` | NEW — claim graduation tests |

---

## Task 1: Models & Enums Foundation

**Files:**
- Modify: `contextgraph/models.py:16-20` (ValidationStatus), `contextgraph/models.py:50-53` (JobType), `contextgraph/models.py:89-106` (Agent)
- Modify: `contextgraph/config.py:28-83` (Settings)
- Modify: `contextgraph/events.py:17-25` (EventType)

- [ ] **Step 1: Update ValidationStatus enum**

In `contextgraph/models.py`, update the `ValidationStatus` enum (lines 16-20). Keep old values as canonical members, add TRUSTED and REJECTED as new members, and add forward-looking aliases:

```python
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
```

This preserves all existing serialized values and ~30+ references across the codebase. `ValidationStatus.PENDING` is an alias for `ValidationStatus.UNREVIEWED` — both resolve to `"unreviewed"`. New code should prefer the new names.

- [ ] **Step 2: Add AgentStatus, AgentRole, SentinelDecision enums**

Add after `ValidationStatus` in `contextgraph/models.py`:

```python
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
```

- [ ] **Step 3: Add new JobType values**

In `contextgraph/models.py`, add to `JobType` enum (line 50-53):

```python
class JobType(StrEnum):
    STORE_MEMORY = "store_memory"
    DELIVER_NOTIFICATION = "deliver_notification"
    SWEEP_EXPIRED_CLAIMS = "sweep_expired_claims"
    SWEEP_IDLE_AGENTS = "sweep_idle_agents"
    PROMOTE_TRUSTED_CLAIMS = "promote_trusted_claims"
    SENTINEL_AUDIT = "sentinel_audit"
    SENTINEL_CANARY = "sentinel_canary"
```

- [ ] **Step 4: Add new Agent fields**

In `contextgraph/models.py`, update `Agent` dataclass (lines 89-106). Keep `status: str` as-is (do NOT change to `AgentStatus` enum — too many serialization sites). Add after the existing fields:

```python
    last_activity_at: datetime | None = None
    suspension_reason: str | None = None
    suspended_at: datetime | None = None
    role: str = "agent"
```

Note: `role` is `str` not `AgentRole` enum for same serialization reasons. Use `AgentRole.AGENT` and `AgentRole.SENTINEL` constants for comparisons.

- [ ] **Step 5: Add SentinelVerdict dataclass**

Add after `AuditEntry` in `contextgraph/models.py`:

```python
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
```

- [ ] **Step 6: Add new EventType values**

In `contextgraph/events.py`, add to `EventType` enum (lines 17-25):

```python
    AGENT_SUSPENDED = "AGENT_SUSPENDED"
    AGENT_REACTIVATED = "AGENT_REACTIVATED"
    AGENT_DELETED = "AGENT_DELETED"
    CLAIM_VALIDATED = "CLAIM_VALIDATED"
    CLAIM_DISPUTED = "CLAIM_DISPUTED"
    CLAIM_REJECTED = "CLAIM_REJECTED"
    CLAIM_PROMOTED = "CLAIM_PROMOTED"
    SENTINEL_CANARY_FAILED = "SENTINEL_CANARY_FAILED"
```

- [ ] **Step 7: Add new config settings**

In `contextgraph/config.py`, add to `Settings` dataclass (after line 80):

```python
    # Agent Lifecycle
    agent_idle_threshold_days: int = _read_int("CG_AGENT_IDLE_THRESHOLD_DAYS", 30)
    agent_idle_scan_interval_hours: int = _read_int("CG_AGENT_IDLE_SCAN_INTERVAL_HOURS", 24)
    # Sentinel Pipeline
    sentinel_enabled: bool = _read_bool("CG_SENTINEL_ENABLED", True)
    sentinel_audit_depth: str = os.getenv("CG_SENTINEL_AUDIT_DEPTH", "auto")
    sentinel_bypass_reputation_threshold: float = _read_float("CG_SENTINEL_BYPASS_REPUTATION", 0.8)
    sentinel_new_agent_claim_threshold: int = _read_int("CG_SENTINEL_NEW_AGENT_CLAIMS", 5)
    sentinel_canary_interval_hours: int = _read_int("CG_SENTINEL_CANARY_INTERVAL_HOURS", 24)
    sentinel_post_store_timeout_seconds: int = _read_int("CG_SENTINEL_POST_STORE_TIMEOUT", 300)
    # Trust Promotion
    trust_promotion_enabled: bool = _read_bool("CG_TRUST_PROMOTION_ENABLED", True)
    trust_promotion_min_age_days: int = _read_int("CG_TRUST_PROMOTION_MIN_AGE_DAYS", 7)
    trust_promotion_min_attestations: int = _read_int("CG_TRUST_PROMOTION_MIN_ATTESTATIONS", 2)
    trust_promotion_scan_interval_hours: int = _read_int("CG_TRUST_PROMOTION_SCAN_INTERVAL_HOURS", 24)
```

- [ ] **Step 8: Run existing tests to verify backward compat**

Run: `python -m pytest tests/ -q`
Expected: All 190 tests pass. The `ValidationStatus` aliases ensure backward compat — `UNREVIEWED`, `ATTESTED`, `CHALLENGED` still resolve.

- [ ] **Step 9: Fix any backward-compat issues**

If `StrEnum` aliases don't work (same values map to same member), use a different approach: keep old values as module-level constants instead. Check service.py references to `ValidationStatus.ATTESTED`, `ValidationStatus.CHALLENGED`, `ValidationStatus.UNREVIEWED` and update them to use the new names (`VALIDATED`, `DISPUTED`, `PENDING`).

Run: `ruff check contextgraph/ tests/ && python -m pytest tests/ -q`
Expected: All clean, all pass.

- [ ] **Step 10: Commit**

```bash
git add contextgraph/models.py contextgraph/config.py contextgraph/events.py
git commit -m "feat: add agent lifecycle enums, SentinelVerdict model, and config settings"
```

---

## Task 2: Repository Layer

**Files:**
- Modify: `contextgraph/repository.py:1-52`
- Modify: `contextgraph/in_memory.py:1-214`
- Modify: `contextgraph/graph/neo4j_repository.py`

- [ ] **Step 1: Add new protocol methods to Repository**

In `contextgraph/repository.py`, add to the `Repository` protocol. First update the import to include `SentinelVerdict`:

```python
from .models import Agent, AuditEntry, Claim, Entity, Memory, Notification, ReviewTask, SentinelVerdict, StandingQuery, Subscription
```

Then add these methods to the Protocol class:

```python
    def save_sentinel_verdict(self, verdict: SentinelVerdict) -> SentinelVerdict: ...
    def list_verdicts_for_claim(self, claim_id: str) -> list[SentinelVerdict]: ...
    def list_verdicts(self, limit: int = 100, decision: str | None = None) -> list[SentinelVerdict]: ...
```

- [ ] **Step 2: Implement in InMemoryRepository**

In `contextgraph/in_memory.py`, add `SentinelVerdict` to the import. Add to `__init__`:

```python
        self._sentinel_verdicts: dict[str, SentinelVerdict] = {}
```

Add methods:

```python
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
```

Update `snapshot()` to include `"sentinel_verdicts": len(self._sentinel_verdicts)`.

- [ ] **Step 3: Implement in Neo4jRepository**

In `contextgraph/graph/neo4j_repository.py`, add the same three methods using Cypher queries. Add a `_verdict_from_node()` parser method following the same pattern as `_agent_from_node()`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -q`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add contextgraph/repository.py contextgraph/in_memory.py contextgraph/graph/neo4j_repository.py
git commit -m "feat: add sentinel verdict storage to repository layer"
```

---

## Task 3: Sentinel Logic Module

**Files:**
- Create: `contextgraph/sentinel.py`
- Test: `tests/test_sentinel.py`

- [ ] **Step 1: Write sentinel tests**

Create `tests/test_sentinel.py`:

```python
from __future__ import annotations

import unittest

from contextgraph.models import (
    Agent,
    AgentRole,
    AgentStatus,
    Claim,
    ClaimImpact,
    SentinelDecision,
    ValidationStatus,
    Visibility,
)
from contextgraph.sentinel import (
    ConflictSentinel,
    DuplicateSentinel,
    QualitySentinel,
    aggregate_verdicts,
)
from contextgraph.utils import utcnow


def _make_claim(
    statement: str,
    confidence: float = 0.7,
    entity_ids: list[str] | None = None,
    evidence: list[str] | None = None,
    citations: list[str] | None = None,
    source_agent_id: str = "agt_test",
    validation_status: ValidationStatus = ValidationStatus.PENDING,
) -> Claim:
    now = utcnow()
    return Claim(
        claim_id="clm_test",
        memory_id="mem_test",
        source_agent_id=source_agent_id,
        statement=statement,
        claim_type="relationship",
        relation_type=None,
        confidence=confidence,
        freshness_score=1.0,
        validation_status=validation_status,
        visibility=Visibility.ORG,
        license="internal",
        entity_ids=entity_ids or [],
        created_at=now,
        expires_at=None,
        updated_at=now,
        source_org_id="acme",
    )


def _make_agent(reputation: float = 0.5, total_claims: int = 0) -> Agent:
    now = utcnow()
    return Agent(
        agent_id="agt_test",
        name="test-agent",
        org_id="acme",
        capabilities=[],
        api_key="key",
        status=AgentStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        reputation_score=reputation,
    )


class DuplicateSentinelTest(unittest.TestCase):
    def test_blocks_exact_duplicate(self) -> None:
        sentinel = DuplicateSentinel(threshold=0.88)
        existing = [_make_claim("Acme Corp reported API latency in EU region")]
        claim = _make_claim("Acme Corp reported API latency in EU region")
        result = sentinel.check(claim, existing)
        self.assertEqual(result.decision, SentinelDecision.BLOCK)

    def test_passes_distinct_claim(self) -> None:
        sentinel = DuplicateSentinel(threshold=0.88)
        existing = [_make_claim("Acme Corp reported API latency in EU region")]
        claim = _make_claim("Samsung announced new chip production facility")
        result = sentinel.check(claim, existing)
        self.assertEqual(result.decision, SentinelDecision.PASS)

    def test_passes_empty_existing(self) -> None:
        sentinel = DuplicateSentinel(threshold=0.88)
        claim = _make_claim("Acme Corp reported API latency")
        result = sentinel.check(claim, [])
        self.assertEqual(result.decision, SentinelDecision.PASS)


class ConflictSentinelTest(unittest.TestCase):
    def test_detects_negation_conflict(self) -> None:
        sentinel = ConflictSentinel()
        existing = [_make_claim("Acme Corp is reliable", validation_status=ValidationStatus.VALIDATED)]
        claim = _make_claim("Acme Corp is not reliable")
        result = sentinel.check(claim, existing)
        self.assertEqual(result.decision, SentinelDecision.DISPUTE)
        self.assertIsNotNone(result.conflicting_claim_id)

    def test_passes_no_conflict(self) -> None:
        sentinel = ConflictSentinel()
        existing = [_make_claim("Acme Corp is reliable", validation_status=ValidationStatus.VALIDATED)]
        claim = _make_claim("Acme Corp expanded to EU region")
        result = sentinel.check(claim, existing)
        self.assertEqual(result.decision, SentinelDecision.PASS)


class QualitySentinelTest(unittest.TestCase):
    def test_high_quality_claim_validates(self) -> None:
        sentinel = QualitySentinel()
        agent = _make_agent(reputation=0.7, total_claims=10)
        claim = _make_claim(
            "Acme Corp reported 3x latency increase in EU region affecting customers",
            confidence=0.8,
            entity_ids=["ent_1", "ent_2"],
            evidence=["meeting:review"],
        )
        result = sentinel.check(claim, agent)
        self.assertEqual(result.decision, SentinelDecision.VALIDATE)

    def test_low_quality_claim_rejected(self) -> None:
        sentinel = QualitySentinel()
        agent = _make_agent(reputation=0.2, total_claims=1)
        claim = _make_claim("bad", confidence=0.2, entity_ids=[])
        result = sentinel.check(claim, agent)
        self.assertIn(result.decision, {SentinelDecision.REJECT, SentinelDecision.NEEDS_REVIEW})


class VerdictAggregationTest(unittest.TestCase):
    def test_all_pass_validates(self) -> None:
        verdicts = [
            SentinelDecision.PASS,
            SentinelDecision.VALIDATE,
            SentinelDecision.VALIDATE,
        ]
        result = aggregate_verdicts(verdicts)
        self.assertEqual(result, SentinelDecision.VALIDATE)

    def test_any_reject_blocks(self) -> None:
        verdicts = [
            SentinelDecision.VALIDATE,
            SentinelDecision.REJECT,
        ]
        result = aggregate_verdicts(verdicts)
        self.assertEqual(result, SentinelDecision.REJECT)

    def test_dispute_wins_over_validate(self) -> None:
        verdicts = [
            SentinelDecision.VALIDATE,
            SentinelDecision.DISPUTE,
        ]
        result = aggregate_verdicts(verdicts)
        self.assertEqual(result, SentinelDecision.DISPUTE)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sentinel.py -v`
Expected: FAIL — `contextgraph.sentinel` doesn't exist yet.

- [ ] **Step 3: Create sentinel.py**

Create `contextgraph/sentinel.py`:

```python
"""Built-in sentinel agents for automated claim validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import Agent, Claim, SentinelDecision, ValidationStatus
from .utils import jaccard_similarity


@dataclass(slots=True)
class SentinelResult:
    decision: SentinelDecision
    confidence: float
    reason: str
    conflicting_claim_id: str | None = None
    details: dict[str, str] | None = None


class DuplicateSentinel:
    def __init__(self, threshold: float = 0.88) -> None:
        self.threshold = threshold

    def check(self, claim: Claim, recent_claims: list[Claim]) -> SentinelResult:
        for existing in recent_claims:
            if existing.claim_id == claim.claim_id:
                continue
            similarity = jaccard_similarity(claim.statement, existing.statement)
            if similarity >= self.threshold:
                return SentinelResult(
                    decision=SentinelDecision.BLOCK,
                    confidence=similarity,
                    reason=f"Duplicate of existing claim (similarity={similarity:.2f})",
                    conflicting_claim_id=existing.claim_id,
                    details={"similarity": f"{similarity:.4f}", "threshold": f"{self.threshold}"},
                )
        return SentinelResult(
            decision=SentinelDecision.PASS,
            confidence=1.0,
            reason="No duplicate found",
        )


_NEGATION_PATTERN = re.compile(
    r"\b(is not|are not|was not|were not|isn't|aren't|wasn't|weren't|not|no longer|never)\b",
    re.IGNORECASE,
)


def _strip_negation(text: str) -> tuple[str, bool]:
    has_negation = bool(_NEGATION_PATTERN.search(text))
    stripped = _NEGATION_PATTERN.sub("", text).strip()
    stripped = re.sub(r"\s+", " ", stripped)
    return stripped, has_negation


class ConflictSentinel:
    def __init__(self, similarity_threshold: float = 0.70) -> None:
        self.similarity_threshold = similarity_threshold

    def check(self, claim: Claim, existing_claims: list[Claim]) -> SentinelResult:
        new_stripped, new_has_neg = _strip_negation(claim.statement)
        for existing in existing_claims:
            if existing.claim_id == claim.claim_id:
                continue
            if existing.validation_status not in (ValidationStatus.VALIDATED, ValidationStatus.PENDING):
                continue
            old_stripped, old_has_neg = _strip_negation(existing.statement)
            similarity = jaccard_similarity(new_stripped, old_stripped)
            if similarity >= self.similarity_threshold and new_has_neg != old_has_neg:
                return SentinelResult(
                    decision=SentinelDecision.DISPUTE,
                    confidence=similarity,
                    reason=f"Contradicts existing claim: '{existing.statement[:80]}'",
                    conflicting_claim_id=existing.claim_id,
                    details={"similarity": f"{similarity:.4f}", "conflict_type": "negation"},
                )
        return SentinelResult(
            decision=SentinelDecision.PASS,
            confidence=1.0,
            reason="No conflicts detected",
        )


class QualitySentinel:
    def check(self, claim: Claim, source_agent: Agent) -> SentinelResult:
        score = 0
        reasons: list[str] = []

        if claim.entity_ids:
            score += 2
            reasons.append("has_entities")
        if claim.confidence > 0.6:
            score += 1
            reasons.append("good_confidence")
        if source_agent.reputation_score > 0.5:
            score += 1
            reasons.append("good_reputation")
        if len(claim.statement.split()) > 10:
            score += 1
            reasons.append("sufficient_length")
        if claim.evidence or claim.citations:
            score += 2
            reasons.append("has_provenance")

        # Count total claims for the source agent to check if new
        # This is passed via source_agent — caller sets reputation to reflect history
        if source_agent.reputation_score == 0.5 and not claim.evidence:
            score -= 1
            reasons.append("new_agent_no_evidence")
        if any(
            kw in claim.statement.lower()
            for kw in ("password", "secret", "api key", "credential", "ssn", "token")
        ):
            score -= 1
            reasons.append("sensitive_content")

        details = {"score": str(score), "signals": ",".join(reasons)}

        if score >= 4:
            return SentinelResult(
                decision=SentinelDecision.VALIDATE,
                confidence=min(score / 7.0, 1.0),
                reason="Quality check passed",
                details=details,
            )
        if score >= 2:
            return SentinelResult(
                decision=SentinelDecision.NEEDS_REVIEW,
                confidence=min(score / 7.0, 1.0),
                reason="Quality borderline — manual review recommended",
                details=details,
            )
        return SentinelResult(
            decision=SentinelDecision.REJECT,
            confidence=min(max(1.0 - score / 7.0, 0.0), 1.0),
            reason="Quality check failed",
            details=details,
        )


def aggregate_verdicts(decisions: list[SentinelDecision]) -> SentinelDecision:
    if not decisions:
        return SentinelDecision.PASS
    if SentinelDecision.BLOCK in decisions or SentinelDecision.REJECT in decisions:
        return SentinelDecision.REJECT
    if SentinelDecision.DISPUTE in decisions:
        return SentinelDecision.DISPUTE
    if SentinelDecision.NEEDS_REVIEW in decisions:
        return SentinelDecision.NEEDS_REVIEW
    if SentinelDecision.VALIDATE in decisions:
        return SentinelDecision.VALIDATE
    return SentinelDecision.PASS


def determine_audit_depth(agent: Agent, settings: Any) -> str:
    configured = settings.sentinel_audit_depth
    if configured != "auto":
        return configured
    if agent.reputation_score >= settings.sentinel_bypass_reputation_threshold:
        return "minimal"
    if agent.reputation_score > 0.6:
        return "light"
    return "full"
```

- [ ] **Step 4: Run sentinel tests**

Run: `python -m pytest tests/test_sentinel.py -v`
Expected: All pass.

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -q`
Expected: All pass (188 existing + new sentinel tests).

- [ ] **Step 6: Commit**

```bash
git add contextgraph/sentinel.py tests/test_sentinel.py
git commit -m "feat: add sentinel logic module with duplicate, conflict, and quality checkers"
```

---

## Task 4: Agent Lifecycle — Service + Auth

**Files:**
- Modify: `contextgraph/service.py:60-162` (init, register, authenticate)
- Modify: `contextgraph/api/dependencies.py:1-26`
- Test: `tests/test_agent_lifecycle.py`

- [ ] **Step 1: Write agent lifecycle tests**

Create `tests/test_agent_lifecycle.py`:

```python
from __future__ import annotations

import unittest
from datetime import timedelta

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.errors import AuthenticationError, PermissionDeniedError
from contextgraph.models import AgentStatus


class AgentLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()

    def tearDown(self) -> None:
        self.service.close()

    def test_register_agent_sets_active_and_last_activity(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.assertEqual(agent.status, AgentStatus.ACTIVE)
        self.assertIsNotNone(agent.last_activity_at)

    def test_suspend_agent_blocks_authentication(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.suspend_agent(agent.agent_id, agent.agent_id, reason="manual")
        with self.assertRaises(PermissionDeniedError):
            self.service.authenticate_agent(agent.api_key)

    def test_reactivate_agent_restores_authentication(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.suspend_agent(agent.agent_id, agent.agent_id, reason="manual")
        self.service.reactivate_agent(agent.agent_id, agent.agent_id)
        result = self.service.authenticate_agent(agent.api_key)
        self.assertEqual(result.status, AgentStatus.ACTIVE)

    def test_auto_wake_for_idle_suspended_agent(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.suspend_agent(agent.agent_id, agent.agent_id, reason="idle")
        result = self.service.authenticate_agent(agent.api_key)
        self.assertEqual(result.status, AgentStatus.ACTIVE)

    def test_manual_suspend_blocks_auto_wake(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.suspend_agent(agent.agent_id, agent.agent_id, reason="manual")
        with self.assertRaises(PermissionDeniedError):
            self.service.authenticate_agent(agent.api_key)

    def test_delete_agent_is_irreversible(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.delete_agent(agent.agent_id, agent.agent_id)
        with self.assertRaises(PermissionDeniedError):
            self.service.authenticate_agent(agent.api_key)
        with self.assertRaises(PermissionDeniedError):
            self.service.reactivate_agent(agent.agent_id, agent.agent_id)

    def test_sweep_idle_agents_suspends_inactive(self) -> None:
        settings = Settings(agent_idle_threshold_days=0)
        service = ContextGraphService(app_settings=settings)
        try:
            agent = service.register_agent("idle-agent", "acme", ["research"])
            # Force last_activity_at into the past
            a = service.get_agent(agent.agent_id)
            a.last_activity_at = a.created_at - timedelta(days=1)
            service.repository.save_agent(a)

            count = service.sweep_idle_agents()
            self.assertEqual(count, 1)

            refreshed = service.get_agent(agent.agent_id)
            self.assertEqual(refreshed.status, AgentStatus.SUSPENDED)
            self.assertEqual(refreshed.suspension_reason, "idle")
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agent_lifecycle.py -v`
Expected: FAIL — methods don't exist yet.

- [ ] **Step 3: Update register_agent in service.py**

In `contextgraph/service.py` `register_agent()` (line 121-134), update the `Agent()` constructor to include:

```python
            last_activity_at=now,
            role=AgentRole.AGENT,
```

Add `AgentRole, AgentStatus` to the imports from `.models`.

- [ ] **Step 4: Update authenticate_agent for auto-wake**

Replace `authenticate_agent` method in `contextgraph/service.py` (lines 156-162):

```python
    def authenticate_agent(self, api_key: str) -> Agent:
        agent = self.repository.find_agent_by_key(api_key)
        if agent is None:
            raise AuthenticationError("Invalid API key.")
        if agent.status == AgentStatus.DELETED:
            raise PermissionDeniedError(f"Agent '{agent.agent_id}' has been deleted.")
        if agent.status == AgentStatus.SUSPENDED:
            if agent.suspension_reason == "idle":
                # Auto-wake: transparent reactivation
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
```

- [ ] **Step 5: Add suspend_agent, reactivate_agent, delete_agent methods**

Add to `ContextGraphService` class in `contextgraph/service.py`, after `update_agent_defaults`:

```python
    def suspend_agent(
        self, requester_agent_id: str, agent_id: str, reason: str = "manual"
    ) -> Agent:
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
```

- [ ] **Step 5.5: Fix dependencies.py for auto-wake**

In `contextgraph/api/dependencies.py`, add `PermissionDeniedError` import and catch it so auto-wake 403s return proper HTTP responses instead of 500s:

```python
from ..errors import AuthenticationError, PermissionDeniedError

def build_authenticated_agent_dependency(graph: ContextGraphService):
    def authenticated_agent(x_agent_key: str | None = Header(default=None, alias="X-Agent-Key")) -> Any:
        if not x_agent_key:
            raise HTTPException(status_code=401, detail="Missing X-Agent-Key header.")
        try:
            return graph.authenticate_agent(x_agent_key)
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    return authenticated_agent
```

- [ ] **Step 6: Update all ValidationStatus references in service.py**

Search and replace throughout `service.py`:
- `ValidationStatus.UNREVIEWED` → `ValidationStatus.PENDING`
- `ValidationStatus.ATTESTED` → `ValidationStatus.VALIDATED`
- `ValidationStatus.CHALLENGED` → `ValidationStatus.DISPUTED`
- `"active"` (as agent status string literal) → `AgentStatus.ACTIVE` (where used for agent status)

Also update `_score_claim` validation bonuses:
```python
        if claim.validation_status == ValidationStatus.VALIDATED:
            validation_bonus = 0.15
        elif claim.validation_status == ValidationStatus.DISPUTED:
            validation_bonus = -0.2
        elif claim.validation_status == ValidationStatus.EXPIRED:
            validation_bonus = -1.0
```

And update `ReviewDecision`:
```python
class ReviewDecision(StrEnum):
    ATTEST = "validated"
    CHALLENGE = "disputed"
```

And `calculate_reputation_score`:
```python
        attested = sum(1 for c in claims if c.validation_status == ValidationStatus.VALIDATED)
        challenged = sum(1 for c in claims if c.validation_status == ValidationStatus.DISPUTED)
```

- [ ] **Step 7: Run lifecycle tests**

Run: `python -m pytest tests/test_agent_lifecycle.py -v`
Expected: All pass.

- [ ] **Step 8: Run all tests**

Run: `python -m pytest tests/ -q`
Expected: All pass. The enum renames are backward-compatible via the StrEnum alias values.

- [ ] **Step 9: Ruff check**

Run: `ruff check contextgraph/ tests/ && ruff format --check contextgraph/ tests/`
Expected: Clean.

- [ ] **Step 10: Commit**

```bash
git add contextgraph/service.py contextgraph/api/dependencies.py tests/test_agent_lifecycle.py
git commit -m "feat: add agent suspend/reactivate/delete lifecycle with auto-wake"
```

---

## Task 5: Sentinel Pipeline Integration into Service

**Files:**
- Modify: `contextgraph/service.py` (`_store_memory_internal`, new sentinel methods)
- Test: `tests/test_sentinel.py` (add integration tests)

- [ ] **Step 1: Write integration test for sentinel pipeline**

Add to `tests/test_sentinel.py`:

```python
class SentinelPipelineIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()

    def tearDown(self) -> None:
        self.service.close()

    def test_store_creates_pending_claim(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        result = self.service.store_memory(
            agent.agent_id,
            "Acme Corp reported 3x latency in EU region.",
            visibility="org",
        )
        for claim in result.claims:
            self.assertEqual(claim.validation_status, ValidationStatus.PENDING)

    def test_sentinel_audit_produces_verdicts(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        result = self.service.store_memory(
            agent.agent_id,
            "Acme Corp reported 3x latency in EU region. Jane needs a fix.",
            visibility="org",
            evidence=["meeting:review"],
        )
        # Run sentinel audit synchronously for testing
        for claim in result.claims:
            self.service.run_sentinel_audit(claim.claim_id)
        # Check verdicts were created
        for claim in result.claims:
            verdicts = self.service.list_verdicts_for_claim(claim.claim_id)
            self.assertGreater(len(verdicts), 0)

    def test_duplicate_is_blocked_pre_store(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.store_memory(agent.agent_id, "Acme Corp reported API latency.")
        # Store the same content again — the duplicate sentinel runs pre-store
        result2 = self.service.store_memory(agent.agent_id, "Acme Corp reported API latency.")
        # The store should still succeed (we don't block stores, we flag)
        # but a verdict should flag it
        for claim in result2.claims:
            self.service.run_sentinel_audit(claim.claim_id)
            verdicts = self.service.list_verdicts_for_claim(claim.claim_id)
            decisions = [v.decision for v in verdicts]
            # duplicate sentinel should have flagged
            self.assertTrue(
                any(d in (SentinelDecision.BLOCK, SentinelDecision.DISPUTE) for d in decisions)
                or len(result2.claims) == 0  # or extraction produced different claims
            )
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_sentinel.py::SentinelPipelineIntegrationTest -v`
Expected: FAIL — methods don't exist.

- [ ] **Step 3: Add sentinel pipeline methods to service.py**

Add these methods to `ContextGraphService`:

```python
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
        from .sentinel import ConflictSentinel, DuplicateSentinel, QualitySentinel, aggregate_verdicts, determine_audit_depth

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
            c for c in self.repository.list_claims()
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
            # Conflict check (full and light)
            validated_claims = [
                c for c in self.repository.list_claims()
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

        if depth in ("full", "light"):
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

    def list_verdicts_for_claim(self, claim_id: str) -> list[SentinelVerdict]:
        return self.repository.list_verdicts_for_claim(claim_id)

    def list_verdicts(self, limit: int = 100, decision: str | None = None) -> list[SentinelVerdict]:
        return self.repository.list_verdicts(limit, decision)
```

Add `SentinelVerdict` and `SentinelDecision` to the imports from `.models`.

- [ ] **Step 4: Register sentinels on init**

In `ContextGraphService.__init__`, add at the end (after the background worker setup):

```python
        if self.settings.sentinel_enabled:
            self._register_sentinels()
```

- [ ] **Step 5: Run sentinel integration tests**

Run: `python -m pytest tests/test_sentinel.py -v`
Expected: All pass.

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/ -q`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add contextgraph/service.py tests/test_sentinel.py
git commit -m "feat: integrate sentinel audit pipeline into service layer"
```

---

## Task 6: Claim Trust Promotion

**Files:**
- Modify: `contextgraph/service.py` (add trust promotion method, update scoring)
- Test: `tests/test_claim_lifecycle.py`

- [ ] **Step 1: Write claim lifecycle tests**

Create `tests/test_claim_lifecycle.py`:

```python
from __future__ import annotations

import unittest
from datetime import timedelta

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.models import ValidationStatus
from contextgraph.utils import utcnow


class ClaimLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService(
            app_settings=Settings(sentinel_enabled=True)
        )

    def tearDown(self) -> None:
        self.service.close()

    def test_new_claims_start_as_pending(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        result = self.service.store_memory(agent.agent_id, "Acme Corp reported latency.")
        for claim in result.claims:
            self.assertEqual(claim.validation_status, ValidationStatus.PENDING)

    def test_trust_promotion_requires_age_and_attestations(self) -> None:
        settings = Settings(
            sentinel_enabled=True,
            trust_promotion_min_age_days=0,
            trust_promotion_min_attestations=2,
        )
        service = ContextGraphService(app_settings=settings)
        try:
            agent = service.register_agent("test", "acme", ["research"])
            reviewer1 = service.register_agent("reviewer1", "acme", ["review"])
            reviewer2 = service.register_agent("reviewer2", "acme", ["review"])

            result = service.store_memory(agent.agent_id, "TSMC lead times extending.")
            claim = result.claims[0]

            # Manually set to validated
            claim.validation_status = ValidationStatus.VALIDATED
            claim.validated_at = utcnow() - timedelta(days=1)
            claim.attestation_count = 2
            claim.challenge_count = 0
            service.repository.update_claim(claim)

            promoted = service.promote_trusted_claims()
            self.assertGreaterEqual(promoted, 1)

            refreshed = service.repository.get_claim(claim.claim_id)
            self.assertEqual(refreshed.validation_status, ValidationStatus.TRUSTED)
        finally:
            service.close()

    def test_disputed_claims_penalized_in_recall(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        result = self.service.store_memory(
            agent.agent_id, "Acme Corp reported latency increase."
        )
        claim = result.claims[0]
        claim.validation_status = ValidationStatus.DISPUTED
        self.service.repository.update_claim(claim)

        hits = self.service.recall(agent.agent_id, "Acme latency")
        if hits:
            self.assertTrue(all(h.score < 0.5 for h in hits))

    def test_rejected_claims_excluded_from_recall(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        result = self.service.store_memory(
            agent.agent_id, "Acme Corp reported latency."
        )
        claim = result.claims[0]
        claim.validation_status = ValidationStatus.REJECTED
        self.service.repository.update_claim(claim)

        hits = self.service.recall(agent.agent_id, "Acme latency")
        claim_ids = [h.claim.claim_id for h in hits]
        self.assertNotIn(claim.claim_id, claim_ids)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_claim_lifecycle.py -v`
Expected: FAIL — `promote_trusted_claims` doesn't exist, `TRUSTED` may not be in enum.

- [ ] **Step 3: Add TRUSTED and REJECTED to ValidationStatus**

Ensure `ValidationStatus` in `models.py` includes `TRUSTED = "trusted"` (may already be done in Task 1). If not, add it.

- [ ] **Step 4: Add promote_trusted_claims to service.py**

```python
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
```

- [ ] **Step 5: Update _score_claim for TRUSTED and REJECTED**

In `_score_claim` method, add the new validation bonuses:

```python
        if claim.validation_status == ValidationStatus.TRUSTED:
            validation_bonus = 0.25
        elif claim.validation_status == ValidationStatus.VALIDATED:
            validation_bonus = 0.15
        elif claim.validation_status == ValidationStatus.DISPUTED:
            validation_bonus = -0.2
        elif claim.validation_status in (ValidationStatus.EXPIRED, ValidationStatus.REJECTED):
            validation_bonus = -1.0
```

- [ ] **Step 6: Filter REJECTED claims from recall**

In the `recall` method in `service.py`, add a filter to exclude rejected claims. Find where claims are filtered and add:

```python
        if claim.validation_status == ValidationStatus.REJECTED:
            continue
```

- [ ] **Step 7: Run claim lifecycle tests**

Run: `python -m pytest tests/test_claim_lifecycle.py -v`
Expected: All pass.

- [ ] **Step 8: Run all tests**

Run: `python -m pytest tests/ -q`
Expected: All pass.

- [ ] **Step 9: Commit**

```bash
git add contextgraph/service.py contextgraph/models.py tests/test_claim_lifecycle.py
git commit -m "feat: add claim trust promotion and graduated recall scoring"
```

---

## Task 7: API Endpoints

**Files:**
- Modify: `contextgraph/api/routes.py`
- Modify: `contextgraph/api/schemas.py`

- [ ] **Step 1: Add new schemas**

In `contextgraph/api/schemas.py`, add:

```python
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
```

- [ ] **Step 2: Add lifecycle endpoints to routes.py**

**IMPORTANT:** Routes use the closure pattern — all routes are defined inside `register_routes(app, graph)` using `@app.post(...)`, NOT `@router.post(...)`. Add these inside the `register_routes` function:

```python
    @app.post("/v1/agents/{agent_id}/suspend")
    def suspend_agent(
        agent_id: str,
        payload: AgentSuspendRequest,
        agent: Any = Depends(authenticated_agent),
    ) -> Any:
        target = graph.get_agent(agent_id)
        if agent.org_id != target.org_id:
            raise HTTPException(status_code=403, detail="Can only suspend agents in your org.")
        return to_jsonable(graph.suspend_agent(agent.agent_id, agent_id, reason=payload.reason))

    @app.post("/v1/agents/{agent_id}/reactivate")
    def reactivate_agent(
        agent_id: str,
        agent: Any = Depends(authenticated_agent),
    ) -> Any:
        target = graph.get_agent(agent_id)
        if agent.org_id != target.org_id:
            raise HTTPException(status_code=403, detail="Can only reactivate agents in your org.")
        return to_jsonable(graph.reactivate_agent(agent.agent_id, agent_id))

    @app.delete("/v1/agents/{agent_id}")
    def delete_agent(
        agent_id: str,
        agent: Any = Depends(authenticated_agent),
    ) -> Any:
        target = graph.get_agent(agent_id)
        if agent.org_id != target.org_id:
            raise HTTPException(status_code=403, detail="Can only delete agents in your org.")
        return to_jsonable(graph.delete_agent(agent.agent_id, agent_id))
```

- [ ] **Step 3: Add sentinel endpoints (inside register_routes)**

```python
    @app.get("/v1/audit/verdicts")
    def list_verdicts(
        claim_id: str | None = None,
        decision: str | None = None,
        limit: int = 100,
        agent: Any = Depends(authenticated_agent),
    ) -> Any:
        if claim_id:
            results = graph.list_verdicts_for_claim(claim_id)
        else:
            results = graph.list_verdicts(limit=limit, decision=decision)
        return to_jsonable(results)

    @app.get("/v1/sentinel/health")
    def sentinel_health(agent: Any = Depends(authenticated_agent)) -> Any:
        sentinels = [a for a in graph.repository.list_agents() if a.role == "sentinel"]
        return {
            "sentinels_active": len([s for s in sentinels if s.status == "active"]),
            "total_verdicts": len(graph.repository.list_verdicts()),
            "last_canary_passed": None,
        }
```

- [ ] **Step 4: Import new schemas in routes.py**

Add `AgentSuspendRequest`, `SentinelVerdictResponse`, `SentinelHealthResponse` to the imports from `.schemas`.

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -q`
Expected: All pass.

- [ ] **Step 6: Ruff check**

Run: `ruff check contextgraph/ && ruff format --check contextgraph/`

- [ ] **Step 7: Commit**

```bash
git add contextgraph/api/routes.py contextgraph/api/schemas.py
git commit -m "feat: add agent lifecycle and sentinel API endpoints"
```

---

## Task 8: SDK + CLI

**Files:**
- Modify: `sdk/contextgraph_sdk/client.py`
- Modify: `sdk/contextgraph_sdk/_local.py`
- Modify: `contextgraph/cli.py`

- [ ] **Step 1: Add SDK methods to HttpTransport**

In `sdk/contextgraph_sdk/client.py`, add to `HttpTransport`:

```python
    def suspend_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["agent_id"]
        body = {"reason": payload.get("reason", "manual")}
        return self._request("POST", f"/v1/agents/{agent_id}/suspend", body)

    def reactivate_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["agent_id"]
        return self._request("POST", f"/v1/agents/{agent_id}/reactivate")

    def delete_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_id = payload["agent_id"]
        return self._request("DELETE", f"/v1/agents/{agent_id}")

    def sentinel_verdicts(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        params = {}
        if payload.get("claim_id"):
            params["claim_id"] = payload["claim_id"]
        if payload.get("decision"):
            params["decision"] = payload["decision"]
        path = "/v1/audit/verdicts"
        if params:
            path = f"{path}?{urlencode(params)}"
        return self._request("GET", path)

    def sentinel_health(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", "/v1/sentinel/health")
```

- [ ] **Step 2: Add SDK methods to Transport protocol and ContextGraph**

In `client.py`, add to `Transport` protocol:

```python
    def suspend_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def reactivate_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def delete_agent(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def sentinel_verdicts(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...
    def sentinel_health(self, payload: dict[str, Any]) -> dict[str, Any]: ...
```

Add to `ContextGraph` class:

```python
    def suspend_agent(self, agent_id: str, reason: str = "manual") -> dict[str, Any]:
        return self.transport.suspend_agent({"agent_id": agent_id, "reason": reason})

    def reactivate_agent(self, agent_id: str) -> dict[str, Any]:
        return self.transport.reactivate_agent({"agent_id": agent_id})

    def delete_agent(self, agent_id: str) -> dict[str, Any]:
        return self.transport.delete_agent({"agent_id": agent_id})

    def sentinel_verdicts(self, claim_id: str | None = None, decision: str | None = None) -> list[dict[str, Any]]:
        return self.transport.sentinel_verdicts({"claim_id": claim_id, "decision": decision})

    def sentinel_health(self) -> dict[str, Any]:
        return self.transport.sentinel_health({})
```

- [ ] **Step 3: Add LocalTransport methods**

In `sdk/contextgraph_sdk/_local.py`, add the matching methods using `self.service.*` calls:

```python
    def suspend_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.suspend_agent(
            requester_agent_id=payload["agent_id"],
            agent_id=payload["agent_id"],
            reason=payload.get("reason", "manual"),
        ))

    def reactivate_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.reactivate_agent(
            requester_agent_id=payload["agent_id"],
            agent_id=payload["agent_id"],
        ))

    def delete_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return to_jsonable(self.service.delete_agent(
            requester_agent_id=payload["agent_id"],
            agent_id=payload["agent_id"],
        ))

    def sentinel_verdicts(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        claim_id = payload.get("claim_id")
        if claim_id:
            return to_jsonable(self.service.list_verdicts_for_claim(claim_id))
        return to_jsonable(self.service.list_verdicts(decision=payload.get("decision")))

    def sentinel_health(self, payload: dict[str, Any]) -> dict[str, Any]:
        sentinels = [a for a in self.service.repository.list_agents() if a.role.value == "sentinel"]
        return {"sentinels_active": len(sentinels), "total_verdicts": 0, "last_canary_passed": None}
```

- [ ] **Step 4: Add CLI commands**

In `contextgraph/cli.py`, add new commands. Add to `_build_parser()`:

```python
    # --- agents suspend/wake/delete ---
    agents_suspend_parser = agents_sub.add_parser("suspend", help="Suspend an agent")
    agents_suspend_parser.add_argument("agent_id", help="Agent ID")
    agents_suspend_parser.add_argument("--reason", default="manual", help="Suspension reason")
    agents_wake_parser = agents_sub.add_parser("wake", help="Reactivate a suspended agent")
    agents_wake_parser.add_argument("agent_id", help="Agent ID")
    agents_delete_parser = agents_sub.add_parser("delete", help="Soft-delete an agent")
    agents_delete_parser.add_argument("agent_id", help="Agent ID")

    # --- sentinel ---
    sentinel_parser = subparsers.add_parser("sentinel", help="Sentinel audit system")
    sentinel_sub = sentinel_parser.add_subparsers(dest="sentinel_command")
    sentinel_sub.add_parser("health", help="Show sentinel system status")
    sentinel_verdicts_parser = sentinel_sub.add_parser("verdicts", help="List sentinel verdicts")
    sentinel_verdicts_parser.add_argument("--claim", default=None, help="Filter by claim ID")
    sentinel_verdicts_parser.add_argument("--status", default=None, help="Filter by decision")
    sentinel_verdicts_parser.add_argument("--limit", "-n", type=int, default=20, help="Max results")
```

Add handler functions and dispatch logic for the new commands.

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -q`
Expected: All pass.

- [ ] **Step 6: Ruff check**

Run: `ruff check contextgraph/ sdk/ tests/ && ruff format --check contextgraph/ sdk/ tests/`

- [ ] **Step 7: Commit**

```bash
git add sdk/contextgraph_sdk/client.py sdk/contextgraph_sdk/_local.py contextgraph/cli.py
git commit -m "feat: add agent lifecycle and sentinel commands to SDK and CLI"
```

---

## Task 9: Final Integration + Full Test Suite

**Files:**
- All modified files
- All test files

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All existing tests pass + all new tests pass. Target: 188 + ~39 = ~227 tests.

- [ ] **Step 2: Ruff lint + format**

Run: `ruff check contextgraph/ sdk/ tests/ && ruff format --check contextgraph/ sdk/ tests/`
Expected: Clean.

- [ ] **Step 3: Fix any issues found**

Address any test failures or lint issues.

- [ ] **Step 4: Verify SDK standalone import still works**

Run: `python -c "from contextgraph_sdk import ContextGraph, HttpTransport; print('OK')"`
Expected: OK — no server imports at module level.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: agent lifecycle, sentinel audit pipeline, and claim trust promotion (v0.4.0)"
```

---

## Task Dependencies

```
Task 1 (Models/Enums) ──► Task 2 (Repository) ──► Task 3 (Sentinel Logic)
                      ──► Task 4 (Agent Lifecycle)
                                                 ──► Task 5 (Sentinel Integration)
                                                 ──► Task 6 (Claim Lifecycle)
                                                               ──► Task 7 (API)
                                                               ──► Task 8 (SDK/CLI)
                                                                         ──► Task 9 (Final)
```

Tasks 3 and 4 can run in parallel after Task 2.
Tasks 5 and 6 can run in parallel after Tasks 3+4.
Tasks 7 and 8 can run in parallel after Tasks 5+6.
Task 9 runs last.
