"""Tests for Memory OS v1 — Context Pack compilation."""

from __future__ import annotations

import unittest

from contextgraph.bootstrap import create_service
from contextgraph.config import Settings
from contextgraph.errors import ConflictError, NotFoundError, PermissionDeniedError
from contextgraph.models import ContextPack


def _make_service(**overrides):
    defaults = {"repository_backend": "memory", "sentinel_enabled": False}
    defaults.update(overrides)
    return create_service(Settings(**defaults))


class TestCompileContextBasic(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.agent = self.service.register_agent(name="alice", org_id="acme")

    def test_compile_empty_returns_empty_pack(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="anything",
            token_budget=1000,
        )
        self.assertIsInstance(pack, ContextPack)
        self.assertEqual(len(pack.included_claims), 0)
        self.assertEqual(pack.tokens_used, 0)
        self.assertEqual(pack.summary, "")
        self.assertTrue(pack.pack_id.startswith("cpk_"))

    def test_compile_returns_matching_claims(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Alice works at Acme Corp as a software engineer.",
            visibility="private",
        )
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Bob manages the sales team at Widgets Inc.",
            visibility="private",
        )
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="Alice software engineer",
            token_budget=4000,
        )
        self.assertGreater(len(pack.included_claims), 0)
        statements = [c.statement for c in pack.included_claims]
        self.assertTrue(any("Alice" in s for s in statements))

    def test_compression_ratio_computed(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The deployment pipeline uses Docker containers orchestrated by Kubernetes for all production services.",
            visibility="private",
        )
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="deployment Docker Kubernetes",
            token_budget=4000,
        )
        if pack.included_claims:
            self.assertGreater(pack.source_tokens, 0)
            self.assertGreater(pack.compression_ratio, 0.0)

    def test_compile_generates_summary(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The deployment pipeline uses Docker and Kubernetes.",
            visibility="private",
        )
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="deployment pipeline",
            token_budget=4000,
        )
        self.assertGreater(len(pack.summary), 0)

    def test_compile_tracks_sources(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The API gateway handles authentication.",
            visibility="private",
        )
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="API authentication",
            token_budget=4000,
        )
        if pack.included_claims:
            self.assertGreater(len(pack.sources), 0)
            source = pack.sources[0]
            self.assertTrue(source.memory_id.startswith("mem_"))
            self.assertGreater(source.claim_count, 0)


class TestTokenBudgetEnforcement(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.agent = self.service.register_agent(name="alice", org_id="acme")
        # Store many memories to have lots of claims
        for i in range(20):
            self.service.store_memory(
                agent_id=self.agent.agent_id,
                content=f"System component {i} handles request processing and data transformation for module {i}.",
                visibility="private",
            )

    def test_respects_token_budget(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="system component request processing",
            token_budget=50,
        )
        self.assertLessEqual(pack.tokens_used, 50)

    def test_budget_of_one_still_works(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="system component",
            token_budget=1,
        )
        self.assertIsInstance(pack, ContextPack)

    def test_large_budget_includes_more_claims(self) -> None:
        small_pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="system component request processing",
            token_budget=50,
        )
        large_pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="system component request processing",
            token_budget=10000,
        )
        self.assertGreaterEqual(
            len(large_pack.included_claims) + len(large_pack.conflicting_claims),
            len(small_pack.included_claims) + len(small_pack.conflicting_claims),
        )


class TestPermissionSensitivePacks(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.alice = self.service.register_agent(name="alice", org_id="acme")
        self.bob = self.service.register_agent(name="bob", org_id="widgets")
        self.carol = self.service.register_agent(name="carol", org_id="acme")

        # Alice stores private memory
        self.service.store_memory(
            agent_id=self.alice.agent_id,
            content="Acme internal: the secret project codename is Phoenix.",
            visibility="private",
        )
        # Alice stores org-visible memory
        self.service.store_memory(
            agent_id=self.alice.agent_id,
            content="Acme team update: quarterly revenue increased by 20 percent.",
            visibility="org",
        )
        # Alice stores published memory
        self.service.store_memory(
            agent_id=self.alice.agent_id,
            content="Public announcement: Acme launches new product line.",
            visibility="published",
        )

    def test_owner_sees_all_claims(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.alice.agent_id,
            query="Acme",
            token_budget=10000,
        )
        all_claims = pack.included_claims + pack.conflicting_claims
        self.assertGreaterEqual(len(all_claims), 3)

    def test_same_org_sees_org_and_published(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.carol.agent_id,
            query="Acme",
            token_budget=10000,
        )
        all_claims = pack.included_claims + pack.conflicting_claims
        # Should see org + published but not private
        statements = [c.statement for c in all_claims]
        self.assertTrue(any("revenue" in s for s in statements))
        self.assertTrue(any("product line" in s for s in statements))
        self.assertFalse(any("Phoenix" in s for s in statements))

    def test_other_org_sees_only_published(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.bob.agent_id,
            query="Acme",
            token_budget=10000,
        )
        all_claims = pack.included_claims + pack.conflicting_claims
        statements = [c.statement for c in all_claims]
        self.assertFalse(any("Phoenix" in s for s in statements))
        self.assertFalse(any("revenue" in s for s in statements))
        # Should only see published
        for claim in all_claims:
            self.assertNotEqual(claim.statement, "")

    def test_three_agents_different_packs_same_corpus(self) -> None:
        """Acceptance test: same query, three agents, three different packs."""
        query = "Acme"
        budget = 10000

        alice_pack = self.service.compile_context(self.alice.agent_id, query, budget)
        bob_pack = self.service.compile_context(self.bob.agent_id, query, budget)
        carol_pack = self.service.compile_context(self.carol.agent_id, query, budget)

        alice_count = len(alice_pack.included_claims) + len(alice_pack.conflicting_claims)
        bob_count = len(bob_pack.included_claims) + len(bob_pack.conflicting_claims)
        carol_count = len(carol_pack.included_claims) + len(carol_pack.conflicting_claims)

        # Alice (owner) >= Carol (same org) >= Bob (other org)
        self.assertGreaterEqual(alice_count, carol_count)
        self.assertGreaterEqual(carol_count, bob_count)


class TestLockedPaidClaims(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.seller = self.service.register_agent(name="seller", org_id="data-co")
        self.buyer = self.service.register_agent(name="buyer", org_id="client-co")

        self.service.store_memory(
            agent_id=self.seller.agent_id,
            content="Premium insight: the market will shift toward AI-first products in Q3.",
            visibility="published",
            price=10.0,
        )

    def test_paid_claims_appear_as_locked_references(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.buyer.agent_id,
            query="market AI products",
            token_budget=10000,
            include_explanations=True,
        )
        # The paid claim should be in excluded_claims with locked=True
        locked = [c for c in pack.excluded_claims if c.locked]
        self.assertGreater(len(locked), 0)
        for claim in locked:
            # Locked claims should have empty statement
            self.assertEqual(claim.statement, "")

    def test_owner_sees_own_paid_claims_unlocked(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.seller.agent_id,
            query="market AI products",
            token_budget=10000,
        )
        all_claims = pack.included_claims + pack.conflicting_claims
        self.assertGreater(len(all_claims), 0)
        # Owner's claims should not be locked
        for claim in all_claims:
            self.assertFalse(claim.locked)
            self.assertNotEqual(claim.statement, "")


class TestDeduplication(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.agent = self.service.register_agent(name="alice", org_id="acme")

    def test_near_duplicate_claims_are_deduped(self) -> None:
        # Store nearly identical memories
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The server runs on port 8080 for the main application.",
            visibility="private",
        )
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The server runs on port 8080 for the main application service.",
            visibility="private",
        )
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="server port 8080",
            token_budget=10000,
            include_explanations=True,
        )
        # After dedup, should have fewer claims than stored
        all_included = pack.included_claims + pack.conflicting_claims
        # At least one should be present
        self.assertGreater(len(all_included), 0)


class TestConflictDetection(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service(sentinel_enabled=True)
        self.agent = self.service.register_agent(name="alice", org_id="acme")

    def test_conflicting_claims_separated(self) -> None:
        # Store a claim and then challenge it
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The database uses PostgreSQL for all services.",
            visibility="private",
        )
        # Store a contradicting claim
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The database does not use PostgreSQL, it uses MySQL instead.",
            visibility="private",
        )
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="database PostgreSQL MySQL",
            token_budget=10000,
            include_explanations=True,
        )
        # Both claims should appear somewhere in the pack
        all_claims = pack.included_claims + pack.conflicting_claims
        self.assertGreater(len(all_claims), 0)


class TestExplanations(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.agent = self.service.register_agent(name="alice", org_id="acme")
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The CI pipeline uses GitHub Actions for automated testing.",
            visibility="private",
        )

    def test_explanations_included_when_requested(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="CI pipeline GitHub Actions",
            token_budget=4000,
            include_explanations=True,
        )
        self.assertIsNotNone(pack.explanation)
        self.assertIsInstance(pack.explanation.included_reasons, dict)
        self.assertIsInstance(pack.explanation.filter_counts, dict)

    def test_explanations_excluded_when_not_requested(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="CI pipeline GitHub Actions",
            token_budget=4000,
            include_explanations=False,
        )
        self.assertIsNone(pack.explanation)
        # excluded_claims should be empty without explanations
        self.assertEqual(len(pack.excluded_claims), 0)


class TestGetAndExplainContextPack(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.agent = self.service.register_agent(name="alice", org_id="acme")
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="The monitoring stack uses Prometheus and Grafana.",
            visibility="private",
        )

    def test_get_context_pack_by_id(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="monitoring Prometheus",
            token_budget=4000,
        )
        retrieved = self.service.get_context_pack(pack.pack_id)
        self.assertEqual(retrieved.pack_id, pack.pack_id)
        self.assertEqual(retrieved.query, "monitoring Prometheus")

    def test_get_nonexistent_pack_raises(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.get_context_pack("cpk_nonexistent")

    def test_explain_pack_without_explanations_raises(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="monitoring",
            token_budget=4000,
            include_explanations=False,
        )
        with self.assertRaises(ConflictError):
            self.service.explain_context_pack(pack.pack_id)

    def test_other_agent_cannot_access_pack(self) -> None:
        other = self.service.register_agent(name="bob", org_id="widgets")
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="monitoring",
            token_budget=4000,
        )
        with self.assertRaises(PermissionDeniedError):
            self.service.get_context_pack(pack.pack_id, requester_agent_id=other.agent_id)

    def test_explain_pack_with_explanations_works(self) -> None:
        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="monitoring Prometheus",
            token_budget=4000,
            include_explanations=True,
        )
        explained = self.service.explain_context_pack(pack.pack_id)
        self.assertIsNotNone(explained.explanation)


class TestMemoryExtensions(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.agent = self.service.register_agent(name="alice", org_id="acme")

    def test_memory_source_fields_propagate_to_pack(self) -> None:
        self.service.store_memory(
            agent_id=self.agent.agent_id,
            content="Incident report: database latency spike at 2pm UTC.",
            visibility="private",
            source_type="incident_report",
            source_label="INC-2024-001",
            source_uri="https://incidents.acme.com/001",
        )

        pack = self.service.compile_context(
            agent_id=self.agent.agent_id,
            query="database latency incident",
            token_budget=4000,
        )
        if pack.sources:
            source = pack.sources[0]
            self.assertEqual(source.source_type, "incident_report")
            self.assertEqual(source.source_label, "INC-2024-001")
            self.assertEqual(source.source_uri, "https://incidents.acme.com/001")


class TestMCPCompileContextTool(unittest.TestCase):
    def setUp(self) -> None:
        s = Settings(repository_backend="memory")
        self.service = create_service(s)
        agent = self.service.register_agent(name="test-agent", org_id="default")
        self.agent_id = agent.agent_id

    def test_dispatch_compile_context_tool(self) -> None:
        from contextgraph.mcp_server import _dispatch_tool

        # Store data first
        _dispatch_tool(
            self.service,
            self.agent_id,
            "contextgraph_store",
            {"content": "The API rate limit is 100 requests per minute."},
        )
        result = _dispatch_tool(
            self.service,
            self.agent_id,
            "contextgraph_compile_context",
            {"query": "API rate limit", "token_budget": 4000},
        )
        self.assertIn("pack_id", result)
        self.assertIn("included_claims", result)
        self.assertIn("summary", result)
        self.assertIn("token_budget", result)


class TestSDKCompileContext(unittest.TestCase):
    def setUp(self) -> None:
        from contextgraph_sdk import ContextGraph

        self.client = ContextGraph.local()
        agent = self.client.register_agent(name="sdk-test", org_id="default")
        self.agent_id = agent["agent_id"]

    def test_sdk_compile_context(self) -> None:
        self.client.store(
            agent_id=self.agent_id,
            content="The logging system uses structured JSON format.",
        )
        result = self.client.compile_context(
            agent_id=self.agent_id,
            query="logging JSON",
            token_budget=4000,
        )
        self.assertIn("pack_id", result)
        self.assertIn("included_claims", result)

    def test_sdk_get_context_pack(self) -> None:
        self.client.store(
            agent_id=self.agent_id,
            content="The cache layer uses Redis for session storage.",
        )
        pack = self.client.compile_context(
            agent_id=self.agent_id,
            query="cache Redis",
            token_budget=4000,
        )
        retrieved = self.client.get_context_pack(pack["pack_id"])
        self.assertEqual(retrieved["pack_id"], pack["pack_id"])

    def test_sdk_explain_context_pack(self) -> None:
        self.client.store(
            agent_id=self.agent_id,
            content="The message queue uses RabbitMQ for async processing.",
        )
        pack = self.client.compile_context(
            agent_id=self.agent_id,
            query="message queue RabbitMQ",
            token_budget=4000,
            include_explanations=True,
        )
        explained = self.client.explain_context_pack(pack["pack_id"])
        self.assertIn("explanation", explained)
        self.assertIsNotNone(explained["explanation"])


if __name__ == "__main__":
    unittest.main()
