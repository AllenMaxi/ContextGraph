# tests/test_models.py
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from contextgraph.models import Subscription, SubscriptionTarget


class SubscriptionModelTest(unittest.TestCase):
    def test_subscription_target_enum_values(self) -> None:
        self.assertEqual(SubscriptionTarget.AGENT, "agent")
        self.assertEqual(SubscriptionTarget.TOPIC, "topic")
        self.assertEqual(SubscriptionTarget.ENTITY, "entity")
        self.assertEqual(SubscriptionTarget.ORG, "org")

    def test_subscription_dataclass_defaults(self) -> None:
        now = datetime.now(tz=timezone.utc)
        sub = Subscription(
            subscription_id="sub_001",
            follower_agent_id="agt_alice",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_bob",
            created_at=now,
        )
        self.assertTrue(sub.active)
        self.assertEqual(sub.target_type, SubscriptionTarget.AGENT)
