# tests/test_reputation.py
from __future__ import annotations

import unittest

from contextgraph.service import ContextGraphService


class ReputationScoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("research-bot", "acme", ["research"])

    def test_new_agent_has_neutral_score(self) -> None:
        score = self.service.calculate_reputation_score(self.agent.agent_id)
        self.assertEqual(score, 0.5)

    def test_all_attested_claims_high_score(self) -> None:
        self.service.store_memory(self.agent.agent_id, "Acme Corp reported API latency spikes.", visibility="published")
        claims = self.service.list_claims(self.agent.agent_id)
        for claim in claims:
            self.service.review_claim(self.agent.agent_id, claim.claim_id, "attested", "Confirmed")
        score = self.service.calculate_reputation_score(self.agent.agent_id)
        self.assertGreater(score, 0.5)

    def test_all_challenged_claims_low_score(self) -> None:
        self.service.store_memory(self.agent.agent_id, "Globex Inc had server outages.", visibility="published")
        claims = self.service.list_claims(self.agent.agent_id)
        for claim in claims:
            self.service.review_claim(self.agent.agent_id, claim.claim_id, "challenged", "Incorrect")
        score = self.service.calculate_reputation_score(self.agent.agent_id)
        self.assertLess(score, 0.5)

    def test_review_claim_updates_agent_reputation(self) -> None:
        self.service.store_memory(self.agent.agent_id, "Acme Corp reported API latency.", visibility="published")
        claims = self.service.list_claims(self.agent.agent_id)
        self.service.review_claim(self.agent.agent_id, claims[0].claim_id, "attested", "Good")
        agent = self.service.get_agent(self.agent.agent_id)
        self.assertGreater(agent.reputation_score, 0.0)
