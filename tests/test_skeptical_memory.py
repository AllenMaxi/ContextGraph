"""Tests for skeptical memory — confidence decay and staleness detection."""

from __future__ import annotations

import unittest
from datetime import timedelta

from contextgraph.bootstrap import create_service
from contextgraph.config import Settings
from contextgraph.utils import utcnow


class TestStalenessDetection(unittest.TestCase):
    def setUp(self) -> None:
        self.service = create_service(
            Settings(
                repository_backend="memory",
                sentinel_enabled=False,
                claim_staleness_threshold_days=14,
            )
        )
        self.agent = self.service.register_agent(name="alice", org_id="acme")

    def test_fresh_claim_no_staleness_warning(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The API uses rate limiting at 100 req/min.",
            visibility="private",
        )
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="API rate limiting",
            token_budget=4000,
        )
        for claim in pack.included_claims:
            self.assertEqual(claim.staleness_warning, "")
        self.assertEqual(pack.stale_claim_count, 0)

    def test_old_unreviewed_claim_gets_staleness_warning(self) -> None:
        result = self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The cache TTL is set to 300 seconds.",
            visibility="private",
        )
        # Age the claim artificially
        for claim in result.claims:
            claim.created_at = utcnow() - timedelta(days=30)
            self.service.repository.update_claim(claim)

        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="cache TTL",
            token_budget=4000,
        )
        stale = [c for c in pack.included_claims if c.staleness_warning]
        self.assertGreater(len(stale), 0)
        self.assertIn("30 days old", stale[0].staleness_warning)
        self.assertGreater(pack.stale_claim_count, 0)

    def test_attested_claim_not_stale(self) -> None:
        result = self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The database connection pool size is 20.",
            visibility="org",
        )
        reviewer = self.service.register_agent(name="bob", org_id="acme")
        for claim in result.claims:
            claim.created_at = utcnow() - timedelta(days=30)
            self.service.repository.update_claim(claim)
            self.service.review_claim(
                reviewer_agent_id=reviewer.agent_id,
                claim_id=claim.claim_id,
                decision="attested",
                reason="confirmed",
            )

        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="database connection pool",
            token_budget=4000,
        )
        for claim in pack.included_claims:
            self.assertEqual(claim.staleness_warning, "")

    def test_staleness_disabled_when_threshold_zero(self) -> None:
        service = create_service(
            Settings(
                repository_backend="memory",
                sentinel_enabled=False,
                claim_staleness_threshold_days=0,
            )
        )
        agent = service.register_agent(name="bob", org_id="acme")
        result = service.store_memory(
            agent_id=agent.agent_id,
            content="Monitoring uses Prometheus.",
            visibility="private",
        )
        for claim in result.claims:
            claim.created_at = utcnow() - timedelta(days=60)
            service.repository.update_claim(claim)

        pack = service.compile_context(
            agent_id=agent.agent_id,
            query="monitoring Prometheus",
            token_budget=4000,
        )
        for claim in pack.included_claims:
            self.assertEqual(claim.staleness_warning, "")


if __name__ == "__main__":
    unittest.main()
