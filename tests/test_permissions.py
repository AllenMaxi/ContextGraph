from __future__ import annotations

import unittest

from contextgraph.models import Claim, ValidationStatus, Visibility
from contextgraph.permissions import can_access_claim
from contextgraph.utils import utcnow


def _make_claim(
    visibility: Visibility,
    source_agent_id: str = "agent-a",
    source_org_id: str = "org-a",
    access_list: list[str] | None = None,
) -> Claim:
    now = utcnow()
    return Claim(
        claim_id="c1",
        memory_id="m1",
        source_agent_id=source_agent_id,
        statement="test claim",
        claim_type="attribute",
        relation_type=None,
        confidence=0.9,
        freshness_score=1.0,
        validation_status=ValidationStatus.UNREVIEWED,
        visibility=visibility,
        license="internal",
        entity_ids=[],
        created_at=now,
        expires_at=None,
        updated_at=now,
        source_org_id=source_org_id,
        access_list=access_list or [],
    )


class PermissionsTest(unittest.TestCase):
    def test_private_only_source_agent(self):
        claim = _make_claim(Visibility.PRIVATE)
        self.assertTrue(can_access_claim("agent-a", "org-a", claim))
        self.assertFalse(can_access_claim("agent-b", "org-a", claim))

    def test_org_visible_to_same_org(self):
        claim = _make_claim(Visibility.ORG)
        self.assertTrue(can_access_claim("agent-b", "org-a", claim))
        self.assertFalse(can_access_claim("agent-c", "org-b", claim))

    def test_shared_with_access_list_agent(self):
        claim = _make_claim(Visibility.SHARED, access_list=["agent-x", "org-b"])
        # Agent in access_list
        self.assertTrue(can_access_claim("agent-x", "org-c", claim))
        # Org in access_list
        self.assertTrue(can_access_claim("agent-y", "org-b", claim))
        # Not in list
        self.assertFalse(can_access_claim("agent-z", "org-c", claim))
        # Source agent always has access
        self.assertTrue(can_access_claim("agent-a", "org-a", claim))

    def test_published_visible_to_all(self):
        claim = _make_claim(Visibility.PUBLISHED)
        self.assertTrue(can_access_claim("anyone", "any-org", claim))

    def test_shared_empty_access_list_denies_all(self):
        claim = _make_claim(Visibility.SHARED, access_list=[])
        self.assertFalse(can_access_claim("agent-b", "org-b", claim))
        # But source agent still has access
        self.assertTrue(can_access_claim("agent-a", "org-a", claim))


class PaymentTest(unittest.TestCase):
    def test_free_claims_need_no_payment(self):
        from contextgraph.payment import PaymentGate

        gate = PaymentGate(enabled=False)
        gate.check_access(agent_id="a", claim_price=0.0, payment_token=None)

    def test_priced_claim_without_token_raises_402(self):
        from contextgraph.errors import PaymentRequiredError
        from contextgraph.payment import PaymentGate

        gate = PaymentGate(enabled=True)
        with self.assertRaises(PaymentRequiredError):
            gate.check_access(agent_id="a", claim_price=0.002, payment_token=None)

    def test_priced_claim_with_valid_token_passes(self):
        from contextgraph.payment import PaymentGate, PaymentReceipt

        gate = PaymentGate(enabled=True)
        receipt = gate.check_access(agent_id="a", claim_price=0.002, payment_token="x402_test_token")
        self.assertIsInstance(receipt, PaymentReceipt)

    def test_same_org_access_is_free(self):
        from contextgraph.payment import PaymentGate

        gate = PaymentGate(enabled=True)
        # Same-org agents don't pay each other
        result = gate.check_access(
            agent_id="a",
            claim_price=0.002,
            payment_token=None,
            requester_org="org-a",
            claim_org="org-a",
        )
        self.assertIsNone(result)


class IdentityTest(unittest.TestCase):
    def test_create_identity_without_chain(self):
        from contextgraph.identity import AgentIdentity

        identity = AgentIdentity(agent_id="a1")
        self.assertFalse(identity.is_verified)
        self.assertEqual(identity.erc8004_address, "")

    def test_create_identity_with_address(self):
        from contextgraph.identity import AgentIdentity

        identity = AgentIdentity(
            agent_id="a1",
            erc8004_address="0x1234567890abcdef1234567890abcdef12345678",
        )
        self.assertTrue(identity.has_chain_identity)
        self.assertFalse(identity.is_verified)

    def test_verify_identity_offline_mode(self):
        from contextgraph.identity import AgentIdentity, IdentityVerifier

        verifier = IdentityVerifier(enabled=False)
        identity = AgentIdentity(
            agent_id="a1",
            erc8004_address="0x1234567890abcdef1234567890abcdef12345678",
        )
        result = verifier.verify(identity)
        self.assertTrue(result.is_verified)
