from __future__ import annotations

import unittest

from contextgraph.config import Settings
from contextgraph.errors import PaymentRequiredError
from contextgraph.in_memory import InMemoryRepository
from contextgraph.models import Visibility
from contextgraph.service import ContextGraphService


class GuardedInMemoryRepository(InMemoryRepository):
    def __init__(self) -> None:
        super().__init__()
        self.disallow_list_claims = False

    def list_claims(self):  # type: ignore[override]
        if self.disallow_list_claims:
            raise AssertionError("recall should not require repository.list_claims full scans")
        return super().list_claims()


class RecallRepositorySearchTest(unittest.TestCase):
    def test_repository_search_prunes_inaccessible_claims_for_requester(self) -> None:
        repository = InMemoryRepository()
        service = ContextGraphService(repository=repository)
        owner = service.register_agent("support-bot", "acme", ["support"])
        outsider = service.register_agent("risk-bot", "globex", ["risk"])
        service.store_memory(
            agent_id=owner.agent_id,
            content="Acme Corp reported API latency in an internal incident review.",
            visibility="org",
        )
        service.store_memory(
            agent_id=owner.agent_id,
            content="Acme Corp reported API latency in a public postmortem.",
            visibility="published",
        )

        results = repository.search_claims(
            "Acme latency",
            requester_agent_id=outsider.agent_id,
            requester_org_id=outsider.org_id,
        )

        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(all(item.claim.visibility == Visibility.PUBLISHED for item in results))

    def test_recall_still_raises_payment_required_for_locked_match(self) -> None:
        repository = InMemoryRepository()
        service = ContextGraphService(repository=repository, app_settings=Settings(enable_payments=True))
        seller = service.register_agent("seller", "alpha", ["research"])
        buyer = service.register_agent("buyer", "beta", ["research"])
        service.store_memory(
            agent_id=seller.agent_id,
            content="Acme Corp reported API latency in a premium diagnostic note.",
            visibility="published",
            price=0.002,
        )

        with self.assertRaises(PaymentRequiredError):
            service.recall(buyer.agent_id, "Acme latency")

    def test_recall_uses_repository_candidate_search_without_full_claim_scan(self) -> None:
        repository = GuardedInMemoryRepository()
        service = ContextGraphService(repository=repository)
        agent = service.register_agent("support-bot", "acme", ["support"])
        service.store_memory(
            agent_id=agent.agent_id,
            content="Acme Corp reported API latency due to connection pool exhaustion.",
            visibility="org",
        )

        repository.disallow_list_claims = True

        hits = service.recall(agent.agent_id, "Acme latency")

        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("connection pool exhaustion", hits[0].memory_content)

    def test_explain_recall_uses_repository_candidate_search_without_full_claim_scan(self) -> None:
        repository = GuardedInMemoryRepository()
        service = ContextGraphService(repository=repository)
        owner = service.register_agent("support-bot", "acme", ["support"])
        outsider = service.register_agent("risk-bot", "globex", ["risk"])
        service.store_memory(
            agent_id=owner.agent_id,
            content="Acme Corp reported API latency and an internal remediation plan.",
            visibility="org",
        )
        service.store_memory(
            agent_id=owner.agent_id,
            content="Acme Corp published a public API latency postmortem.",
            visibility="published",
        )

        repository.disallow_list_claims = True

        explanation = service.explain_recall(outsider.agent_id, "Acme latency")

        self.assertGreaterEqual(len(explanation.hits), 1)
        self.assertGreaterEqual(explanation.filtered_counts.get("access_denied", 0), 1)


if __name__ == "__main__":
    unittest.main()
