"""Tests for background memory consolidation."""

from __future__ import annotations

import unittest
from datetime import timedelta

from contextgraph.bootstrap import create_service
from contextgraph.config import Settings
from contextgraph.models import ValidationStatus
from contextgraph.utils import utcnow


class TestMemoryConsolidation(unittest.TestCase):
    def setUp(self) -> None:
        self.service = create_service(
            Settings(
                repository_backend="memory",
                sentinel_enabled=False,
                trust_promotion_enabled=True,
                trust_promotion_min_age_days=7,
                trust_promotion_min_attestations=2,
            )
        )
        self.agent = self.service.register_agent(name="alice", org_id="acme")
        self.reviewer = self.service.register_agent(name="bob", org_id="acme")

    def test_archives_old_challenged_claims(self) -> None:
        result = self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Disputed fact that nobody defended.",
            visibility="org",
        )
        claim = result.claims[0]
        # Challenge it
        self.service.review_claim(
            reviewer_agent_id=self.reviewer.agent_id,
            claim_id=claim.claim_id,
            decision="challenged",
            reason="incorrect",
        )
        # Age it past 30 days
        claim = self.service.repository.get_claim(claim.claim_id)
        claim.created_at = utcnow() - timedelta(days=35)
        self.service.repository.update_claim(claim)

        stats = self.service.run_memory_consolidation()
        self.assertGreater(stats["archived_stale_challenged"], 0)

        updated = self.service.repository.get_claim(claim.claim_id)
        self.assertEqual(updated.validation_status, ValidationStatus.REJECTED)

    def test_flags_orphaned_claims(self) -> None:
        result = self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Fact in a memory that will be archived.",
            visibility="org",
        )
        # Archive the parent memory
        self.service.update_memory_curation(
            requester_agent_id=self.agent.agent_id,
            memory_id=result.memory.memory_id,
            curation_status="archived",
            reason="obsolete",
        )

        stats = self.service.run_memory_consolidation()
        self.assertGreater(stats["flagged_orphaned"], 0)

        for claim in result.claims:
            updated = self.service.repository.get_claim(claim.claim_id)
            self.assertEqual(updated.validation_status, ValidationStatus.EXPIRED)

    def test_no_action_on_healthy_claims(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Fresh healthy fact about the system.",
            visibility="org",
        )
        stats = self.service.run_memory_consolidation()
        self.assertEqual(stats["archived_stale_challenged"], 0)
        self.assertEqual(stats["flagged_orphaned"], 0)

    def test_recently_challenged_not_archived(self) -> None:
        result = self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Recently challenged claim.",
            visibility="org",
        )
        claim = result.claims[0]
        self.service.review_claim(
            reviewer_agent_id=self.reviewer.agent_id,
            claim_id=claim.claim_id,
            decision="challenged",
            reason="needs review",
        )
        # Only 5 days old — should NOT be archived
        claim = self.service.repository.get_claim(claim.claim_id)
        claim.created_at = utcnow() - timedelta(days=5)
        self.service.repository.update_claim(claim)

        stats = self.service.run_memory_consolidation()
        self.assertEqual(stats["archived_stale_challenged"], 0)

        updated = self.service.repository.get_claim(claim.claim_id)
        self.assertEqual(updated.validation_status, ValidationStatus.CHALLENGED)

    def test_consolidation_creates_audit_entry(self) -> None:
        self.service.run_memory_consolidation()
        entries = self.service.repository.list_audit_entries()
        consolidation_entries = [e for e in entries if e.action == "memory_consolidation"]
        self.assertGreater(len(consolidation_entries), 0)


if __name__ == "__main__":
    unittest.main()
