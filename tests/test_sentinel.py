from __future__ import annotations

import unittest

from contextgraph.models import (
    Agent,
    Claim,
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

_claim_counter = 0


def _make_claim(
    statement: str,
    confidence: float = 0.7,
    entity_ids: list[str] | None = None,
    evidence: list[str] | None = None,
    citations: list[str] | None = None,
    source_agent_id: str = "agt_test",
    validation_status: ValidationStatus = ValidationStatus.PENDING,
) -> Claim:
    global _claim_counter
    _claim_counter += 1
    now = utcnow()
    return Claim(
        claim_id=f"clm_test_{_claim_counter}",
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
        evidence=evidence or [],
        citations=citations or [],
    )


def _make_agent(reputation: float = 0.5, total_claims: int = 0) -> Agent:
    now = utcnow()
    return Agent(
        agent_id="agt_test",
        name="test-agent",
        org_id="acme",
        capabilities=[],
        api_key="key",
        status="active",
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
