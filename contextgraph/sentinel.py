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

        if source_agent.reputation_score == 0.5 and not claim.evidence:
            score -= 1
            reasons.append("new_agent_no_evidence")
        if any(kw in claim.statement.lower() for kw in ("password", "secret", "api key", "credential", "ssn", "token")):
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
