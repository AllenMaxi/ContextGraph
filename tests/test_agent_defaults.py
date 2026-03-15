from __future__ import annotations

import unittest

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.models import Visibility


class AgentDefaultsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.agent = self.service.register_agent("defaults-agent", "acme", ["research"])
        self.peer = self.service.register_agent("peer-agent", "acme", ["ops"])

    def test_register_agent_persists_defaults(self) -> None:
        agent = self.service.register_agent(
            "shared-agent",
            "globex",
            ["market"],
            default_visibility="shared",
            default_access_list=["partner-org", "partner-org"],
            default_price=0.002,
        )

        self.assertEqual(agent.default_visibility, Visibility.SHARED)
        self.assertEqual(agent.default_access_list, ["partner-org"])
        self.assertEqual(agent.default_price, 0.002)

    def test_update_agent_defaults_updates_only_requested_agent(self) -> None:
        updated = self.service.update_agent_defaults(
            requester_agent_id=self.agent.agent_id,
            agent_id=self.agent.agent_id,
            default_visibility="shared",
            default_access_list=["globex"],
            default_price=0.003,
        )
        peer = self.service.get_agent(self.peer.agent_id)

        self.assertEqual(updated.default_visibility, Visibility.SHARED)
        self.assertEqual(updated.default_access_list, ["globex"])
        self.assertEqual(updated.default_price, 0.003)
        self.assertEqual(peer.default_visibility, Visibility.PRIVATE)
        self.assertEqual(peer.default_access_list, [])
        self.assertEqual(peer.default_price, 0.0)

    def test_store_memory_uses_agent_defaults_when_policy_is_omitted(self) -> None:
        self.service.update_agent_defaults(
            requester_agent_id=self.agent.agent_id,
            agent_id=self.agent.agent_id,
            default_visibility="shared",
            default_access_list=["globex"],
            default_price=0.002,
        )

        result = self.service.store_memory(self.agent.agent_id, "Shared supplier note for Globex.")
        memory = self.service.repository.get_memory(result.memory.memory_id)

        self.assertIsNotNone(memory)
        self.assertEqual(memory.visibility, Visibility.SHARED)
        self.assertEqual(memory.access_list, ["globex"])
        self.assertEqual(memory.price, 0.002)
        for claim in result.claims:
            self.assertEqual(claim.visibility, Visibility.SHARED)
            self.assertEqual(claim.access_list, ["globex"])
            self.assertEqual(claim.price, 0.002)

    def test_explicit_store_override_beats_agent_defaults(self) -> None:
        self.service.update_agent_defaults(
            requester_agent_id=self.agent.agent_id,
            agent_id=self.agent.agent_id,
            default_visibility="shared",
            default_access_list=["globex"],
            default_price=0.002,
        )

        result = self.service.store_memory(
            self.agent.agent_id,
            "Internal supplier note for Acme only.",
            visibility="org",
            price=0.0,
        )

        self.assertEqual(result.memory.visibility, Visibility.ORG)
        self.assertEqual(result.memory.access_list, [])
        self.assertEqual(result.memory.price, 0.0)
        for claim in result.claims:
            self.assertEqual(claim.visibility, Visibility.ORG)
            self.assertEqual(claim.access_list, [])
            self.assertEqual(claim.price, 0.0)

    def test_updating_defaults_only_affects_future_memories(self) -> None:
        first = self.service.store_memory(self.agent.agent_id, "First private note.")
        self.service.update_agent_defaults(
            requester_agent_id=self.agent.agent_id,
            agent_id=self.agent.agent_id,
            default_visibility="published",
            default_price=0.001,
        )
        second = self.service.store_memory(self.agent.agent_id, "Second published note.")

        first_memory = self.service.repository.get_memory(first.memory.memory_id)
        second_memory = self.service.repository.get_memory(second.memory.memory_id)

        self.assertEqual(first_memory.visibility, Visibility.PRIVATE)
        self.assertEqual(first_memory.price, 0.0)
        self.assertEqual(second_memory.visibility, Visibility.PUBLISHED)
        self.assertEqual(second_memory.access_list, [])
        self.assertEqual(second_memory.price, 0.001)

    def test_enqueue_memory_store_uses_agent_defaults(self) -> None:
        service = ContextGraphService(
            app_settings=Settings(enable_background_worker=True, background_worker_poll_seconds=0.01)
        )
        try:
            agent = service.register_agent(
                "async-defaults",
                "acme",
                ["research"],
                default_visibility="shared",
                default_access_list=["globex"],
                default_price=0.004,
            )
            job = service.enqueue_memory_store(agent.agent_id, "Async shared note.")
            completed = service.wait_for_job(job.job_id, requester_agent_id=agent.agent_id, timeout_seconds=1.0)
            memories = [
                service.repository.get_memory(claim.memory_id)
                for claim in service.repository.list_claims()
                if claim.source_agent_id == agent.agent_id
            ]
        finally:
            service.close()

        self.assertEqual(completed.status.value, "succeeded")
        self.assertEqual(len(memories), 1)
        self.assertIsNotNone(memories[0])
        self.assertEqual(memories[0].visibility, Visibility.SHARED)
        self.assertEqual(memories[0].access_list, ["globex"])
        self.assertEqual(memories[0].price, 0.004)

    def test_shared_defaults_require_non_empty_access_list(self) -> None:
        with self.assertRaises(ValueError):
            self.service.register_agent(
                "invalid-shared",
                "acme",
                ["research"],
                default_visibility="shared",
            )

        with self.assertRaises(ValueError):
            self.service.update_agent_defaults(
                requester_agent_id=self.agent.agent_id,
                agent_id=self.agent.agent_id,
                default_visibility="shared",
            )


if __name__ == "__main__":
    unittest.main()
