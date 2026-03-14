from __future__ import annotations

import os
import unittest

try:
    from neo4j import GraphDatabase
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    GraphDatabase = None

from contextgraph.config import Settings
from contextgraph.graph.neo4j_repository import Neo4jRepository
from contextgraph.models import ReviewStatus
from contextgraph.service import ContextGraphService


@unittest.skipUnless(
    GraphDatabase is not None and os.getenv("CG_RUN_NEO4J_TESTS") == "1",
    "neo4j integration tests require neo4j and CG_RUN_NEO4J_TESTS=1",
)
class ContextGraphNeo4jIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.repository = Neo4jRepository(
                uri=os.getenv("CG_NEO4J_URI", "bolt://localhost:7687"),
                user=os.getenv("CG_NEO4J_USER", "neo4j"),
                password=os.getenv("CG_NEO4J_PASSWORD", "contextgraph"),
            )
        except Exception as exc:  # pragma: no cover - environment-dependent
            raise unittest.SkipTest(str(exc)) from exc

    @classmethod
    def tearDownClass(cls) -> None:
        cls.repository.close()

    def setUp(self) -> None:
        settings = Settings(repository_backend="neo4j")
        self.service = ContextGraphService(repository=self.repository, app_settings=settings)
        self.owner = self.service.register_agent("neo4j-owner", "neo4j-org", ["support"])
        self.reviewer = self.service.register_agent("neo4j-reviewer", "neo4j-org", ["review"])

    def test_get_claim_preserves_entity_ids(self) -> None:
        result = self.service.store_memory(
            agent_id=self.owner.agent_id,
            content="Jane from Acme Corp reported API latency.",
            visibility="org",
        )

        fetched = self.repository.get_claim(result.claims[0].claim_id)

        self.assertIsNotNone(fetched)
        self.assertGreaterEqual(len(fetched.entity_ids), 1)

    def test_review_resolution_persists_to_neo4j(self) -> None:
        result = self.service.store_memory(
            agent_id=self.owner.agent_id,
            content="short note.",
            visibility="org",
        )

        task = result.review_tasks[0]
        self.service.review_claim(
            reviewer_agent_id=self.reviewer.agent_id,
            claim_id=result.claims[0].claim_id,
            decision="attested",
            reason="confirmed in neo4j test",
        )
        stored_task = self.repository.get_review_task(task.task_id)

        self.assertIsNotNone(stored_task)
        self.assertEqual(stored_task.status, ReviewStatus.RESOLVED)
        self.assertIsNotNone(stored_task.resolved_at)


if __name__ == "__main__":
    unittest.main()
