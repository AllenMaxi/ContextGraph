"""Tests for the /playground interactive demo page."""

from __future__ import annotations

import unittest

from contextgraph.api.playground import _seed_playground_corpus
from contextgraph.bootstrap import create_service
from contextgraph.config import Settings


class TestPlaygroundSeed(unittest.TestCase):
    def setUp(self) -> None:
        self.service = create_service(Settings(repository_backend="memory", sentinel_enabled=False))

    def test_seed_creates_four_agents(self) -> None:
        agents = _seed_playground_corpus(self.service)
        self.assertIn("playground-alice", agents)
        self.assertIn("playground-carol", agents)
        self.assertIn("playground-bob", agents)
        self.assertIn("playground-oncall", agents)
        self.assertEqual(len(agents), 4)

    def test_seed_is_idempotent(self) -> None:
        agents1 = _seed_playground_corpus(self.service)
        agents2 = _seed_playground_corpus(self.service)
        self.assertEqual(agents1, agents2)

    def test_seed_is_independent_across_service_instances(self) -> None:
        _seed_playground_corpus(self.service)

        other_service = create_service(Settings(repository_backend="memory", sentinel_enabled=False))
        try:
            other_agents = _seed_playground_corpus(other_service)

            self.assertIn("playground-alice", other_agents)
            self.assertIn("playground-bob", other_agents)
            other_snapshot = other_service.repository.snapshot()
            self.assertGreaterEqual(other_snapshot["memories"], 6)
            self.assertGreater(other_snapshot["claims"], 0)
        finally:
            other_service.close()

    def test_seed_creates_memories(self) -> None:
        _seed_playground_corpus(self.service)
        snapshot = self.service.repository.snapshot()
        self.assertGreaterEqual(snapshot["memories"], 7)
        self.assertGreater(snapshot["claims"], 0)

    def test_alice_sees_more_than_bob(self) -> None:
        agents = _seed_playground_corpus(self.service)
        alice_pack = self.service.compile_context(
            agent_id=agents["playground-alice"],
            query="payment service",
            token_budget=4000,
        )
        bob_pack = self.service.compile_context(
            agent_id=agents["playground-bob"],
            query="payment service",
            token_budget=4000,
        )
        alice_total = len(alice_pack.included_claims) + len(alice_pack.conflicting_claims)
        bob_total = len(bob_pack.included_claims) + len(bob_pack.conflicting_claims)
        self.assertGreater(alice_total, bob_total)

    def test_shared_demo_claim_is_visible_to_bob_but_not_carol(self) -> None:
        agents = _seed_playground_corpus(self.service)
        bob_pack = self.service.compile_context(
            agent_id=agents["playground-bob"],
            query="partner preview gRPC sandbox",
            token_budget=4000,
        )
        carol_pack = self.service.compile_context(
            agent_id=agents["playground-carol"],
            query="partner preview gRPC sandbox",
            token_budget=4000,
        )
        bob_statements = [c.statement for c in bob_pack.included_claims + bob_pack.conflicting_claims]
        bob_visibilities = {c.visibility for c in bob_pack.included_claims + bob_pack.conflicting_claims}
        carol_statements = [c.statement for c in carol_pack.included_claims + carol_pack.conflicting_claims]

        self.assertTrue(any("Partner preview" in statement for statement in bob_statements))
        self.assertIn("shared", bob_visibilities)
        self.assertFalse(any("Partner preview" in statement for statement in carol_statements))


class TestPlaygroundRoute(unittest.TestCase):
    def setUp(self) -> None:
        try:
            from starlette.testclient import TestClient

            from contextgraph.web import create_app
        except ImportError:
            self.skipTest("FastAPI/starlette not available")
            return

        self.service = create_service(Settings(repository_backend="memory", sentinel_enabled=False))
        app = create_app(self.service)
        self.client = TestClient(app)

    def _column_html(self, html: str, agent_name: str) -> str:
        for chunk in html.split('<div class="pg-col">'):
            if f">{agent_name}</span>" in chunk:
                return chunk
        self.fail(f"Column for {agent_name} not found")

    def test_playground_renders_without_query(self) -> None:
        response = self.client.get("/playground")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ContextGraph Playground", response.text)
        self.assertIn("Compile", response.text)

    def test_playground_renders_with_query(self) -> None:
        response = self.client.get("/playground?q=payment+service&budget=2000")
        self.assertEqual(response.status_code, 200)
        text = response.text.lower()
        self.assertIn("alice", text)
        self.assertIn("carol", text)
        self.assertIn("bob", text)
        self.assertIn("claims", text)

    def test_playground_shows_different_claim_counts(self) -> None:
        response = self.client.get("/playground?q=payment+service+gRPC&budget=4000")
        self.assertEqual(response.status_code, 200)
        text = response.text.lower()
        self.assertIn("published and explicitly shared claims visible", text)

    def test_playground_renders_scope_badges_and_shared_access(self) -> None:
        response = self.client.get("/playground?q=partner+preview+gRPC+sandbox&budget=4000")
        self.assertEqual(response.status_code, 200)
        bob_column = self._column_html(response.text, "Bob")
        carol_column = self._column_html(response.text, "Carol")

        self.assertIn("Partner preview", bob_column)
        self.assertIn(">shared<", bob_column)
        self.assertIn(">published<", bob_column)
        self.assertIn("Published and explicitly shared claims visible", bob_column)
        self.assertNotIn("Partner preview", carol_column)
        self.assertIn(">org<", response.text)
        self.assertIn(">private<", response.text)

    def test_playground_budget_clamped(self) -> None:
        # Budget below minimum gets clamped to 50
        response = self.client.get("/playground?q=test&budget=1")
        self.assertEqual(response.status_code, 200)
        # Budget above maximum gets clamped to 8000
        response = self.client.get("/playground?q=test&budget=99999")
        self.assertEqual(response.status_code, 200)

    def test_playground_invalid_budget_uses_default(self) -> None:
        response = self.client.get("/playground?q=test&budget=notanumber")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
