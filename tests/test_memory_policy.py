from __future__ import annotations

import unittest

from contextgraph.config import Settings
from contextgraph.errors import PaymentRequiredError
from contextgraph.models import Visibility
from contextgraph.service import ContextGraphService


class MemoryPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.alice = self.service.register_agent("alice", "acme", ["research"])
        self.acme_peer = self.service.register_agent("acme-peer", "acme", ["ops"])
        self.globex = self.service.register_agent("globex", "globex", ["supply"])

    def test_store_memory_persists_memory_policy_and_claim_mirror(self) -> None:
        result = self.service.store_memory(
            self.alice.agent_id,
            "Acme supplier note. Acme sourcing note.",
            visibility="shared",
            access_list=["globex"],
            price=0.002,
        )

        memory = self.service.repository.get_memory(result.memory.memory_id)

        self.assertIsNotNone(memory)
        self.assertEqual(memory.visibility, Visibility.SHARED)
        self.assertEqual(memory.access_list, ["globex"])
        self.assertEqual(memory.price, 0.002)
        for claim in result.claims:
            self.assertEqual(claim.visibility, Visibility.SHARED)
            self.assertEqual(claim.access_list, ["globex"])
            self.assertEqual(claim.price, 0.002)

    def test_update_memory_access_rewrites_all_sibling_claims(self) -> None:
        result = self.service.store_memory(
            self.alice.agent_id,
            "Acme supplier note. Acme sourcing note.",
            visibility="org",
        )

        updated = self.service.update_memory_access(
            requester_agent_id=self.alice.agent_id,
            memory_id=result.memory.memory_id,
            visibility="published",
            price=0.005,
            access_list=["globex"],
        )

        sibling_claims = [claim for claim in self.service.repository.list_claims() if claim.memory_id == updated.memory_id]
        self.assertEqual(updated.visibility, Visibility.PUBLISHED)
        self.assertEqual(updated.access_list, ["globex"])
        self.assertEqual(updated.price, 0.005)
        for claim in sibling_claims:
            self.assertEqual(claim.visibility, Visibility.PUBLISHED)
            self.assertEqual(claim.access_list, ["globex"])
            self.assertEqual(claim.price, 0.005)

    def test_update_claim_compatibility_updates_parent_memory_policy(self) -> None:
        result = self.service.store_memory(
            self.alice.agent_id,
            "Acme supplier note. Acme sourcing note.",
            visibility="org",
        )

        updated_claim = self.service.update_claim(
            requester_agent_id=self.alice.agent_id,
            claim_id=result.claims[0].claim_id,
            visibility="shared",
            price=0.003,
            access_list=["globex"],
        )
        memory = self.service.repository.get_memory(result.memory.memory_id)
        sibling_claims = [claim for claim in self.service.repository.list_claims() if claim.memory_id == result.memory.memory_id]

        self.assertEqual(updated_claim.visibility, Visibility.SHARED)
        self.assertEqual(memory.visibility, Visibility.SHARED)
        self.assertEqual(memory.access_list, ["globex"])
        self.assertEqual(memory.price, 0.003)
        for claim in sibling_claims:
            self.assertEqual(claim.visibility, Visibility.SHARED)
            self.assertEqual(claim.access_list, ["globex"])
            self.assertEqual(claim.price, 0.003)

    def test_recall_normalizes_legacy_mixed_policy_and_blocks_cross_org_leak(self) -> None:
        result = self.service.store_memory(
            self.alice.agent_id,
            "Public fact. Private fact.",
            visibility="org",
        )
        leaked_claim = result.claims[0]
        leaked_claim.visibility = Visibility.PUBLISHED
        self.service.repository.update_claim(leaked_claim)

        hits = self.service.recall(self.globex.agent_id, "Public fact")
        normalized = self.service.repository.get_claim(leaked_claim.claim_id)

        self.assertEqual(hits, [])
        self.assertEqual(normalized.visibility, Visibility.ORG)

    def test_cross_org_shared_memory_by_org_id_is_accessible(self) -> None:
        self.service.store_memory(
            self.alice.agent_id,
            "Shared to Globex only.",
            visibility="shared",
            access_list=["globex"],
        )

        hits = self.service.recall(self.globex.agent_id, "Globex")
        self.assertEqual(len(hits), 1)
        self.assertIn("Shared to Globex", hits[0].memory_content)

    def test_cross_org_shared_memory_by_agent_id_is_accessible(self) -> None:
        self.service.store_memory(
            self.alice.agent_id,
            "Shared to one external agent only.",
            visibility="shared",
            access_list=[self.globex.agent_id],
        )

        hits = self.service.recall(self.globex.agent_id, "external agent")
        self.assertEqual(len(hits), 1)
        self.assertIn("Shared to one external agent", hits[0].memory_content)

    def test_feed_locks_priced_cross_org_memory(self) -> None:
        service = ContextGraphService(
            app_settings=Settings(enable_payments=True, enable_claim_expiry_sweeps=False)
        )
        try:
            source = service.register_agent("source", "acme", ["research"])
            consumer = service.register_agent("consumer", "globex", ["market"])
            service.follow(consumer.agent_id, "agent", source.agent_id)
            service.store_memory(
                source.agent_id,
                "Deep supplier analysis with recommended order shifts.",
                visibility="published",
                price=0.002,
            )

            feed = service.get_feed(consumer.agent_id)
        finally:
            service.close()

        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0]["memory_content"], "")
        self.assertTrue(feed[0]["is_locked"])
        self.assertTrue(feed[0]["requires_payment"])
        self.assertEqual(feed[0]["price"], 0.002)

    def test_priced_cross_org_recall_requires_payment_but_unlocks_with_token(self) -> None:
        service = ContextGraphService(
            app_settings=Settings(enable_payments=True, enable_claim_expiry_sweeps=False)
        )
        try:
            source = service.register_agent("source", "acme", ["research"])
            consumer = service.register_agent("consumer", "globex", ["market"])
            service.store_memory(
                source.agent_id,
                "Deep supplier analysis with recommended order shifts.",
                visibility="published",
                price=0.002,
            )

            with self.assertRaises(PaymentRequiredError):
                service.recall(consumer.agent_id, "supplier analysis")

            hits = service.recall(consumer.agent_id, "supplier analysis", payment_token="x402_test_token")
        finally:
            service.close()

        self.assertEqual(len(hits), 1)
        self.assertIn("recommended order shifts", hits[0].memory_content)
