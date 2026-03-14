# tests/test_claim_update.py
from __future__ import annotations

import unittest

from contextgraph.errors import NotFoundError, PermissionDeniedError
from contextgraph.models import Visibility
from contextgraph.service import ContextGraphService


class ClaimUpdateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.alice = self.service.register_agent("alice", "acme", ["research"])
        self.bob = self.service.register_agent("bob", "acme", ["support"])
        result = self.service.store_memory(
            self.alice.agent_id,
            "Acme Corp reported Q3 results.",
            visibility="org",
        )
        self.claim = result.claims[0]

    def test_source_agent_can_update_visibility(self) -> None:
        updated = self.service.update_claim(
            self.alice.agent_id,
            self.claim.claim_id,
            visibility="published",
        )
        self.assertEqual(updated.visibility, Visibility.PUBLISHED)

    def test_source_agent_can_update_price(self) -> None:
        updated = self.service.update_claim(
            self.alice.agent_id,
            self.claim.claim_id,
            price=0.005,
        )
        self.assertEqual(updated.price, 0.005)

    def test_source_agent_can_update_access_list(self) -> None:
        updated = self.service.update_claim(
            self.alice.agent_id,
            self.claim.claim_id,
            visibility="shared",
            access_list=["agt_external"],
        )
        self.assertEqual(updated.visibility, Visibility.SHARED)
        self.assertIn("agt_external", updated.access_list)

    def test_other_agent_cannot_update_claim(self) -> None:
        with self.assertRaises(PermissionDeniedError):
            self.service.update_claim(
                self.bob.agent_id,
                self.claim.claim_id,
                visibility="published",
            )

    def test_update_nonexistent_claim_raises_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.update_claim(self.alice.agent_id, "clm_fake", visibility="published")

    def test_update_with_no_fields_is_noop(self) -> None:
        updated = self.service.update_claim(self.alice.agent_id, self.claim.claim_id)
        self.assertEqual(updated.visibility, self.claim.visibility)
