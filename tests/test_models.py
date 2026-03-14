# tests/test_models.py
from __future__ import annotations

import unittest
from datetime import UTC, datetime

from contextgraph.models import Claim, RecallHit, Subscription, SubscriptionTarget, ValidationStatus, Visibility


class SubscriptionModelTest(unittest.TestCase):
    def test_subscription_target_enum_values(self) -> None:
        self.assertEqual(SubscriptionTarget.AGENT, "agent")
        self.assertEqual(SubscriptionTarget.TOPIC, "topic")
        self.assertEqual(SubscriptionTarget.ENTITY, "entity")
        self.assertEqual(SubscriptionTarget.ORG, "org")

    def test_subscription_dataclass_defaults(self) -> None:
        now = datetime.now(tz=UTC)
        sub = Subscription(
            subscription_id="sub_001",
            follower_agent_id="agt_alice",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_bob",
            created_at=now,
        )
        self.assertTrue(sub.active)
        self.assertEqual(sub.target_type, SubscriptionTarget.AGENT)


class RecallHitModelTest(unittest.TestCase):
    def test_recall_hit_new_fields_have_defaults(self) -> None:
        now = datetime.now(tz=UTC)
        claim = Claim(
            claim_id="clm_1",
            memory_id="mem_1",
            source_agent_id="agt_1",
            statement="Test",
            claim_type="attribute",
            relation_type=None,
            confidence=0.9,
            freshness_score=1.0,
            validation_status=ValidationStatus.UNREVIEWED,
            visibility=Visibility.PUBLISHED,
            license="internal",
            entity_ids=[],
            created_at=now,
            expires_at=None,
            updated_at=now,
        )
        hit = RecallHit(claim=claim, score=0.85, entities=[])
        self.assertEqual(hit.memory_content, "")
        self.assertEqual(hit.source_agent_name, "")
        self.assertEqual(hit.source_reputation_score, 0.0)

    def test_recall_hit_with_new_fields(self) -> None:
        now = datetime.now(tz=UTC)
        claim = Claim(
            claim_id="clm_1",
            memory_id="mem_1",
            source_agent_id="agt_1",
            statement="Test",
            claim_type="attribute",
            relation_type=None,
            confidence=0.9,
            freshness_score=1.0,
            validation_status=ValidationStatus.UNREVIEWED,
            visibility=Visibility.PUBLISHED,
            license="internal",
            entity_ids=[],
            created_at=now,
            expires_at=None,
            updated_at=now,
        )
        hit = RecallHit(
            claim=claim,
            score=0.85,
            entities=[],
            memory_content="Full analysis here...",
            source_agent_name="research-bot",
            source_reputation_score=0.92,
        )
        self.assertEqual(hit.memory_content, "Full analysis here...")
        self.assertEqual(hit.source_agent_name, "research-bot")
        self.assertEqual(hit.source_reputation_score, 0.92)
