from __future__ import annotations

import unittest

from contextgraph import ContextGraphService
from contextgraph.models import ValidationStatus


class SentinelPipelineIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()

    def tearDown(self) -> None:
        self.service.close()

    def test_store_creates_pending_claim(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        result = self.service.store_memory(
            agent.agent_id,
            "Acme Corp reported 3x latency in EU region.",
            visibility="org",
        )
        for claim in result.claims:
            self.assertEqual(claim.validation_status, ValidationStatus.PENDING)

    def test_sentinel_audit_produces_verdicts(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        result = self.service.store_memory(
            agent.agent_id,
            "Acme Corp reported 3x latency in EU region. Jane needs a fix.",
            visibility="org",
            evidence=["meeting:review"],
        )
        for claim in result.claims:
            self.service.run_sentinel_audit(claim.claim_id)
        for claim in result.claims:
            verdicts = self.service.list_verdicts_for_claim(claim.claim_id)
            self.assertGreater(len(verdicts), 0)

    def test_sentinels_registered_on_init(self) -> None:
        agents = self.service.repository.list_agents()
        sentinel_names = [a.name for a in agents if a.org_id == "_system"]
        self.assertIn("sentinel_duplicate", sentinel_names)
        self.assertIn("sentinel_conflict", sentinel_names)
        self.assertIn("sentinel_quality", sentinel_names)


if __name__ == "__main__":
    unittest.main()
