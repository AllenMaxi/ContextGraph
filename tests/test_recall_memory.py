# tests/test_recall_memory.py
from __future__ import annotations

import unittest

from contextgraph.service import ContextGraphService


class RecallMemoryContentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("research-bot", "acme", ["research"])
        self.service.store_memory(
            self.agent.agent_id,
            "Acme Corp reported API latency spikes in Q3 affecting 23% of clients. "
            "Root cause was connection pool exhaustion under concurrent load.",
            visibility="published",
        )

    def test_recall_returns_full_memory_content(self) -> None:
        hits = self.service.recall(self.agent.agent_id, "Acme API latency")
        self.assertGreater(len(hits), 0)
        hit = hits[0]
        self.assertIn("connection pool exhaustion", hit.memory_content)

    def test_recall_returns_source_agent_name(self) -> None:
        hits = self.service.recall(self.agent.agent_id, "Acme API latency")
        self.assertEqual(hits[0].source_agent_name, "research-bot")

    def test_recall_returns_reputation_score(self) -> None:
        hits = self.service.recall(self.agent.agent_id, "Acme API latency")
        self.assertIsInstance(hits[0].source_reputation_score, float)

    def test_same_org_recall_prefers_org_memory_over_generic_published_hit(self) -> None:
        assistant = self.service.register_agent("assistant-bot", "acme", ["assistant"])
        self.service.store_memory(
            self.agent.agent_id,
            "TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
            visibility="org",
        )
        self.service.store_memory(
            self.agent.agent_id,
            "Public industry note: semiconductor wafer prices increased this quarter.",
            visibility="published",
        )

        hits = self.service.recall(assistant.agent_id, "Should we adjust our semiconductor orders this quarter?")

        self.assertGreater(len(hits), 0)
        self.assertIn("Shift flexible orders to Samsung", hits[0].memory_content)
