from __future__ import annotations

import unittest
from datetime import timedelta

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.models import ValidationStatus
from contextgraph.utils import utcnow


class ClaimLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService(app_settings=Settings(sentinel_enabled=True))

    def tearDown(self) -> None:
        self.service.close()

    def test_new_claims_start_as_pending(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        result = self.service.store_memory(agent.agent_id, "Acme Corp reported latency.")
        for claim in result.claims:
            self.assertEqual(claim.validation_status, ValidationStatus.PENDING)

    def test_trust_promotion_requires_age_and_attestations(self) -> None:
        settings = Settings(
            sentinel_enabled=True,
            trust_promotion_min_age_days=0,
            trust_promotion_min_attestations=2,
        )
        service = ContextGraphService(app_settings=settings)
        try:
            agent = service.register_agent("test", "acme", ["research"])
            result = service.store_memory(agent.agent_id, "TSMC lead times extending.")
            claim = result.claims[0]

            # Manually set to validated with required attestations
            claim.validation_status = ValidationStatus.VALIDATED
            claim.validated_at = utcnow() - timedelta(days=1)
            claim.attestation_count = 2
            claim.challenge_count = 0
            service.repository.update_claim(claim)

            promoted = service.promote_trusted_claims()
            self.assertGreaterEqual(promoted, 1)

            refreshed = service.repository.get_claim(claim.claim_id)
            self.assertEqual(refreshed.validation_status, ValidationStatus.TRUSTED)
        finally:
            service.close()

    def test_rejected_claims_excluded_from_recall(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        result = self.service.store_memory(agent.agent_id, "Acme Corp reported latency.")
        claim = result.claims[0]
        claim.validation_status = ValidationStatus.REJECTED
        self.service.repository.update_claim(claim)

        hits = self.service.recall(agent.agent_id, "Acme latency")
        claim_ids = [h.claim.claim_id for h in hits]
        self.assertNotIn(claim.claim_id, claim_ids)

    def test_trust_promotion_skips_challenged(self) -> None:
        settings = Settings(
            sentinel_enabled=True,
            trust_promotion_min_age_days=0,
            trust_promotion_min_attestations=1,
        )
        service = ContextGraphService(app_settings=settings)
        try:
            agent = service.register_agent("test", "acme", ["research"])
            result = service.store_memory(agent.agent_id, "TSMC delays expected.")
            claim = result.claims[0]

            claim.validation_status = ValidationStatus.VALIDATED
            claim.validated_at = utcnow() - timedelta(days=1)
            claim.attestation_count = 5
            claim.challenge_count = 1  # Has a challenge — should NOT promote
            service.repository.update_claim(claim)

            promoted = service.promote_trusted_claims()
            self.assertEqual(promoted, 0)
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()
