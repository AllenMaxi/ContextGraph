# tests/test_follow.py
from __future__ import annotations

import unittest

from contextgraph.errors import NotFoundError, PermissionDeniedError
from contextgraph.service import ContextGraphService


class FollowServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.alice = self.service.register_agent("alice", "acme", ["research"])
        self.bob = self.service.register_agent("bob", "acme", ["support"])

    def test_follow_agent(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.assertEqual(sub.follower_agent_id, self.alice.agent_id)
        self.assertEqual(sub.target_id, self.bob.agent_id)

    def test_follow_topic(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "topic", "semiconductor")
        self.assertEqual(sub.target_type.value, "topic")
        self.assertEqual(sub.target_id, "semiconductor")

    def test_duplicate_follow_raises_conflict(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        with self.assertRaises(ValueError):
            self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)

    def test_unfollow(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.unfollow(self.alice.agent_id, sub.subscription_id)
        following = self.service.list_following(self.alice.agent_id)
        self.assertEqual(len(following), 0)

    def test_unfollow_by_other_agent_raises_permission_denied(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        with self.assertRaises(PermissionDeniedError):
            self.service.unfollow(self.bob.agent_id, sub.subscription_id)

    def test_list_following(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.follow(self.alice.agent_id, "topic", "AI")
        following = self.service.list_following(self.alice.agent_id)
        self.assertEqual(len(following), 2)

    def test_list_followers(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        followers = self.service.list_followers(self.bob.agent_id)
        self.assertEqual(len(followers), 1)
        self.assertEqual(followers[0].follower_agent_id, self.alice.agent_id)

    def test_follow_updates_followers_count(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        bob = self.service.get_agent(self.bob.agent_id)
        self.assertEqual(bob.followers_count, 1)

    def test_unfollow_decrements_followers_count(self) -> None:
        sub = self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.unfollow(self.alice.agent_id, sub.subscription_id)
        bob = self.service.get_agent(self.bob.agent_id)
        self.assertEqual(bob.followers_count, 0)

    def test_max_subscriptions_enforced(self) -> None:
        for i in range(200):
            self.service.follow(self.alice.agent_id, "topic", f"topic_{i}")
        with self.assertRaises(ValueError):
            self.service.follow(self.alice.agent_id, "topic", "topic_overflow")
