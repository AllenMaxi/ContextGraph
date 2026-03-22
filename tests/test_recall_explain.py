from __future__ import annotations

import unittest

from contextgraph.config import Settings
from contextgraph.service import ContextGraphService


class RecallExplainTest(unittest.TestCase):
    def test_explain_recall_includes_score_breakdown_for_visible_hits(self) -> None:
        service = ContextGraphService()
        agent = service.register_agent("research-bot", "acme", ["research"])
        service.store_memory(
            agent.agent_id,
            "Acme Corp reported API latency spikes in Q3 due to connection pool exhaustion.",
            visibility="org",
        )

        explanation = service.explain_recall(agent.agent_id, "Acme API latency")

        self.assertGreaterEqual(len(explanation.hits), 1)
        self.assertGreaterEqual(len(explanation.decisions), 1)
        self.assertEqual(explanation.decisions[0].outcome, "hit")
        self.assertIsNotNone(explanation.decisions[0].score_breakdown)
        self.assertEqual(explanation.decisions[0].score_breakdown.final_score, explanation.hits[0].score)

    def test_explain_recall_counts_access_denied_without_leaking_claim_details(self) -> None:
        service = ContextGraphService()
        owner = service.register_agent("alpha-support", "alpha", ["support"])
        outsider = service.register_agent("beta-risk", "beta", ["risk"])
        service.store_memory(
            owner.agent_id,
            "Acme Corp reported API latency and internal remediation steps.",
            visibility="org",
        )

        explanation = service.explain_recall(outsider.agent_id, "Acme latency")

        self.assertEqual(explanation.hits, [])
        self.assertEqual(explanation.decisions, [])
        self.assertGreaterEqual(explanation.filtered_counts.get("access_denied", 0), 1)

    def test_explain_recall_counts_payment_required_for_locked_cross_org_memory(self) -> None:
        service = ContextGraphService(app_settings=Settings(enable_payments=True))
        seller = service.register_agent("seller", "alpha", ["research"])
        buyer = service.register_agent("buyer", "beta", ["research"])
        service.store_memory(
            seller.agent_id,
            "Acme Corp reported API latency and priced this diagnostic note.",
            visibility="published",
            price=0.002,
        )

        explanation = service.explain_recall(buyer.agent_id, "Acme latency")

        self.assertEqual(explanation.hits, [])
        self.assertGreaterEqual(explanation.filtered_counts.get("payment_required", 0), 1)
        self.assertGreaterEqual(len(explanation.decisions), 1)
        self.assertEqual(explanation.decisions[0].reasons, ["payment_required"])
        self.assertIsNotNone(explanation.decisions[0].score_breakdown)


if __name__ == "__main__":
    unittest.main()
