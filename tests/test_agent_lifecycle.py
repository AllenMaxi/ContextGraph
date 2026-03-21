from __future__ import annotations

import unittest
from datetime import timedelta

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.errors import PermissionDeniedError
from contextgraph.models import AgentStatus


class AgentLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()

    def tearDown(self) -> None:
        self.service.close()

    def test_register_agent_sets_active_and_last_activity(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.assertEqual(agent.status, AgentStatus.ACTIVE)
        self.assertIsNotNone(agent.last_activity_at)

    def test_suspend_agent_blocks_authentication(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.suspend_agent(agent.agent_id, agent.agent_id, reason="manual")
        with self.assertRaises(PermissionDeniedError):
            self.service.authenticate_agent(agent.api_key)

    def test_reactivate_agent_restores_authentication(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.suspend_agent(agent.agent_id, agent.agent_id, reason="manual")
        self.service.reactivate_agent(agent.agent_id, agent.agent_id)
        result = self.service.authenticate_agent(agent.api_key)
        self.assertEqual(result.status, AgentStatus.ACTIVE)

    def test_auto_wake_for_idle_suspended_agent(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.suspend_agent(agent.agent_id, agent.agent_id, reason="idle")
        result = self.service.authenticate_agent(agent.api_key)
        self.assertEqual(result.status, AgentStatus.ACTIVE)

    def test_manual_suspend_blocks_auto_wake(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.suspend_agent(agent.agent_id, agent.agent_id, reason="manual")
        with self.assertRaises(PermissionDeniedError):
            self.service.authenticate_agent(agent.api_key)

    def test_delete_agent_is_irreversible(self) -> None:
        agent = self.service.register_agent("test", "acme", ["research"])
        self.service.delete_agent(agent.agent_id, agent.agent_id)
        with self.assertRaises(PermissionDeniedError):
            self.service.authenticate_agent(agent.api_key)
        with self.assertRaises(PermissionDeniedError):
            self.service.reactivate_agent(agent.agent_id, agent.agent_id)

    def test_sweep_idle_agents_suspends_inactive(self) -> None:
        settings = Settings(agent_idle_threshold_days=0)
        service = ContextGraphService(app_settings=settings)
        try:
            agent = service.register_agent("idle-agent", "acme", ["research"])
            # Force last_activity_at into the past
            a = service.get_agent(agent.agent_id)
            a.last_activity_at = a.created_at - timedelta(days=1)
            service.repository.save_agent(a)

            count = service.sweep_idle_agents()
            self.assertEqual(count, 1)

            refreshed = service.get_agent(agent.agent_id)
            self.assertEqual(refreshed.status, AgentStatus.SUSPENDED)
            self.assertEqual(refreshed.suspension_reason, "idle")
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()
