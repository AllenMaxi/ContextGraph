# tests/test_subscription_repo.py
from __future__ import annotations

import unittest
from datetime import UTC, datetime

from contextgraph.in_memory import InMemoryRepository
from contextgraph.models import Subscription, SubscriptionTarget


class SubscriptionRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryRepository()
        self.now = datetime.now(tz=UTC)

    def test_save_and_get_subscription(self) -> None:
        sub = Subscription(
            subscription_id="sub_1",
            follower_agent_id="agt_alice",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_bob",
            created_at=self.now,
        )
        self.repo.save_subscription(sub)
        result = self.repo.get_subscription("sub_1")
        self.assertIsNotNone(result)
        self.assertEqual(result.follower_agent_id, "agt_alice")

    def test_get_subscriptions_by_follower(self) -> None:
        for i in range(3):
            self.repo.save_subscription(
                Subscription(
                    subscription_id=f"sub_{i}",
                    follower_agent_id="agt_alice",
                    target_type=SubscriptionTarget.TOPIC,
                    target_id=f"topic_{i}",
                    created_at=self.now,
                )
            )
        self.repo.save_subscription(
            Subscription(
                subscription_id="sub_other",
                follower_agent_id="agt_bob",
                target_type=SubscriptionTarget.AGENT,
                target_id="agt_alice",
                created_at=self.now,
            )
        )
        subs = self.repo.get_subscriptions_by_follower("agt_alice")
        self.assertEqual(len(subs), 3)

    def test_get_followers_of_agent(self) -> None:
        self.repo.save_subscription(
            Subscription(
                subscription_id="sub_1",
                follower_agent_id="agt_alice",
                target_type=SubscriptionTarget.AGENT,
                target_id="agt_bob",
                created_at=self.now,
            )
        )
        self.repo.save_subscription(
            Subscription(
                subscription_id="sub_2",
                follower_agent_id="agt_charlie",
                target_type=SubscriptionTarget.AGENT,
                target_id="agt_bob",
                created_at=self.now,
            )
        )
        followers = self.repo.get_followers_of_agent("agt_bob")
        self.assertEqual(len(followers), 2)

    def test_delete_subscription(self) -> None:
        self.repo.save_subscription(
            Subscription(
                subscription_id="sub_1",
                follower_agent_id="agt_alice",
                target_type=SubscriptionTarget.AGENT,
                target_id="agt_bob",
                created_at=self.now,
            )
        )
        self.repo.delete_subscription("sub_1")
        self.assertIsNone(self.repo.get_subscription("sub_1"))

    def test_get_nonexistent_subscription_returns_none(self) -> None:
        self.assertIsNone(self.repo.get_subscription("sub_nope"))
