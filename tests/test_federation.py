from __future__ import annotations

import unittest

from contextgraph.a2a_server import A2AServer, A2ATask
from contextgraph.federation import FederationManager, FederationPeer, FederationResult
from contextgraph.models import Claim, ValidationStatus, Visibility
from contextgraph.utils import utcnow


def _make_claim(visibility: Visibility, claim_id: str = "c1") -> Claim:
    now = utcnow()
    return Claim(
        claim_id=claim_id,
        memory_id="m1",
        source_agent_id="agent-a",
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
        source_org_id="org-a",
        access_list=[],
    )


class StubTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[str, list]] = []

    def send_claims(self, peer: FederationPeer, claims: list) -> FederationResult:
        self.sent.append((peer.node_id, claims))
        return FederationResult(peer_node_id=peer.node_id, claims_sent=len(claims), success=True)

    def fetch_claims(self, peer: FederationPeer, since: str | None = None) -> list:
        return [{"claim_id": "remote_c1", "visibility": "published", "statement": "remote claim"}]


class FederationManagerTest(unittest.TestCase):

    def test_only_published_claims_are_federated(self):
        transport = StubTransport()
        mgr = FederationManager(
            node_id="node-1",
            peers=[FederationPeer(node_id="node-2", base_url="https://peer.example.com", api_key="k")],
            transport=transport,
            enabled=True,
        )
        private = _make_claim(Visibility.PRIVATE, "c1")
        org = _make_claim(Visibility.ORG, "c2")
        published = _make_claim(Visibility.PUBLISHED, "c3")

        results = mgr.federate_claims([private, org, published])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].claims_sent, 1)
        self.assertEqual(len(transport.sent), 1)
        self.assertEqual(len(transport.sent[0][1]), 1)

    def test_disabled_federation_sends_nothing(self):
        transport = StubTransport()
        mgr = FederationManager(node_id="node-1", transport=transport, enabled=False)
        published = _make_claim(Visibility.PUBLISHED)

        results = mgr.federate_claims([published])

        self.assertEqual(results, [])
        self.assertEqual(transport.sent, [])

    def test_duplicate_claims_not_sent_twice(self):
        transport = StubTransport()
        mgr = FederationManager(
            node_id="node-1",
            peers=[FederationPeer(node_id="node-2", base_url="https://peer.example.com", api_key="k")],
            transport=transport,
            enabled=True,
        )
        published = _make_claim(Visibility.PUBLISHED, "c1")

        mgr.federate_claims([published])
        mgr.federate_claims([published])

        self.assertEqual(len(transport.sent), 1)

    def test_fetch_from_peers(self):
        transport = StubTransport()
        mgr = FederationManager(
            node_id="node-1",
            peers=[FederationPeer(node_id="node-2", base_url="https://peer.example.com", api_key="k")],
            transport=transport,
            enabled=True,
        )

        claims = mgr.fetch_from_peers()

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["claim_id"], "remote_c1")

    def test_status_reports_peer_count(self):
        mgr = FederationManager(
            node_id="node-1",
            peers=[FederationPeer(node_id="node-2", base_url="https://peer.example.com", api_key="k")],
            enabled=True,
        )

        status = mgr.status()

        self.assertEqual(status["peer_count"], 1)
        self.assertEqual(status["node_id"], "node-1")
        self.assertTrue(status["enabled"])


class A2AServerTest(unittest.TestCase):

    def test_agent_card_includes_skills(self):
        server = A2AServer(node_id="node-1", base_url="https://example.com", enabled=True)
        card = server.agent_card()

        self.assertIn("ContextGraph", card["name"])
        self.assertGreaterEqual(len(card["skills"]), 4)
        skill_ids = [s["id"] for s in card["skills"]]
        self.assertIn("store_memory", skill_ids)
        self.assertIn("recall_memory", skill_ids)

    def test_disabled_server_rejects_tasks(self):
        server = A2AServer(node_id="node-1", base_url="https://example.com", enabled=False)

        result = server.handle_task({"task_id": "t1", "skill_id": "recall_memory"})

        self.assertEqual(result["status"], "failed")

    def test_task_without_service_fails(self):
        server = A2AServer(node_id="node-1", base_url="https://example.com", enabled=True)

        result = server.handle_task({"task_id": "t1", "skill_id": "recall_memory"})

        self.assertEqual(result["status"], "failed")

    def test_federation_ingest_rejects_non_published(self):
        server = A2AServer(node_id="node-1", base_url="https://example.com", enabled=True)

        result = server.handle_federation_ingest(
            claims_data=[{"visibility": "private"}, {"visibility": "published"}],
            source_node_id="node-2",
            federation_key="",
        )

        self.assertEqual(result["ingested"], 1)

    def test_federation_ingest_validates_key(self):
        server = A2AServer(node_id="node-1", base_url="https://example.com", enabled=True)
        server.set_federation_key("secret-key")

        result = server.handle_federation_ingest(
            claims_data=[{"visibility": "published"}],
            source_node_id="node-2",
            federation_key="wrong-key",
        )

        self.assertEqual(result["ingested"], 0)
        self.assertIn("Invalid", result["error"])

    def test_status_reports_task_counts(self):
        server = A2AServer(node_id="node-1", base_url="https://example.com", enabled=True)

        status = server.status()

        self.assertEqual(status["node_id"], "node-1")
        self.assertEqual(status["total_tasks"], 0)


if __name__ == "__main__":
    unittest.main()
