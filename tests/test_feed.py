# tests/test_feed.py
from __future__ import annotations

import unittest

from contextgraph.service import ContextGraphService


class KnowledgeFeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.alice = self.service.register_agent("alice", "acme", ["research"])
        self.bob = self.service.register_agent("bob", "acme", ["support"])

    def test_feed_empty_when_not_following_anyone(self) -> None:
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertEqual(len(feed), 0)

    def test_feed_shows_followed_agent_memories(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.store_memory(self.bob.agent_id, "Globex Inc had server outages.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertEqual(len(feed), 1)
        self.assertIn("server outages", feed[0]["memory_content"])

    def test_feed_shows_followed_topic_memories(self) -> None:
        self.service.follow(self.alice.agent_id, "topic", "semiconductor")
        self.service.store_memory(
            self.bob.agent_id,
            "TSMC semiconductor lead times extending in Q3 2026.",
            visibility="org",
        )
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertGreater(len(feed), 0)

    def test_feed_shows_followed_org_memories(self) -> None:
        self.service.follow(self.alice.agent_id, "org", "acme")
        self.service.store_memory(self.bob.agent_id, "Acme org note from Bob.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertEqual(len(feed), 1)
        self.assertIn("Acme org note", feed[0]["memory_content"])

    def test_feed_shows_followed_entity_memories(self) -> None:
        self.service.follow(self.alice.agent_id, "entity", "TSMC")
        self.service.store_memory(self.bob.agent_id, "TSMC supplier delays are growing.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertEqual(len(feed), 1)
        self.assertIn("TSMC supplier delays", feed[0]["memory_content"])

    def test_feed_respects_visibility(self) -> None:
        charlie = self.service.register_agent("charlie", "other_org", ["research"])
        self.service.follow(charlie.agent_id, "agent", self.bob.agent_id)
        self.service.store_memory(self.bob.agent_id, "Internal Acme data.", visibility="org")
        feed = self.service.get_feed(charlie.agent_id)
        self.assertEqual(len(feed), 0)

    def test_feed_deduplicates_memories(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.follow(self.alice.agent_id, "topic", "Acme")
        self.service.store_memory(self.bob.agent_id, "Acme Corp reported Q4 growth.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id)
        memory_ids = [item["memory_id"] for item in feed]
        self.assertEqual(len(memory_ids), len(set(memory_ids)))

    def test_feed_pagination(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        for i in range(5):
            self.service.store_memory(self.bob.agent_id, f"Report number {i} about Acme Corp.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id, limit=2)
        self.assertEqual(len(feed), 2)

    def test_feed_includes_source_reputation(self) -> None:
        self.service.follow(self.alice.agent_id, "agent", self.bob.agent_id)
        self.service.store_memory(self.bob.agent_id, "Globex Inc had server outages.", visibility="org")
        feed = self.service.get_feed(self.alice.agent_id)
        self.assertIn("source_reputation_score", feed[0])
