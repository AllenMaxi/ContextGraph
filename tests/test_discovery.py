from __future__ import annotations

import unittest

from contextgraph import ContextGraphService


class AgentDiscoveryServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.viewer = self.service.register_agent("viewer", "acme", ["research"])
        self.same_org = self.service.register_agent("same-org", "acme", ["ops"])
        self.hidden = self.service.register_agent(
            "hidden-agent",
            "globex",
            ["sales"],
            default_visibility="published",
        )
        self.public = self.service.register_agent(
            "public-agent",
            "globex",
            ["market"],
            default_visibility="private",
        )
        self.shared = self.service.register_agent("shared-agent", "initech", ["analysis"])
        self.service.update_agent_profile(
            requester_agent_id=self.public.agent_id,
            agent_id=self.public.agent_id,
            profile_visibility="published",
            profile_summary="Cross-org market analyst",
            profile_links={"orchestrator": "https://agents.example.com/public-agent"},
        )
        self.service.update_agent_profile(
            requester_agent_id=self.shared.agent_id,
            agent_id=self.shared.agent_id,
            profile_visibility="shared",
            profile_access_list=["acme"],
            profile_summary="Shared with Acme only",
        )

    def tearDown(self) -> None:
        self.service.close()

    def test_discovery_uses_profile_visibility_not_memory_defaults(self) -> None:
        result = self.service.discover_agents(requester_agent_id=self.viewer.agent_id)
        agent_ids = {item["agent_id"] for item in result["items"]}

        self.assertIn(self.same_org.agent_id, agent_ids)
        self.assertIn(self.public.agent_id, agent_ids)
        self.assertIn(self.shared.agent_id, agent_ids)
        self.assertNotIn(self.hidden.agent_id, agent_ids)

    def test_get_agent_profile_hides_shared_access_list_cross_org(self) -> None:
        profile = self.service.get_agent_profile(self.viewer.agent_id, self.shared.agent_id)
        self.assertEqual(profile["profile_visibility"], "shared")
        self.assertEqual(profile["profile_access_list"], [])

    def test_same_org_profile_can_see_access_list(self) -> None:
        self.service.update_agent_profile(
            requester_agent_id=self.same_org.agent_id,
            agent_id=self.same_org.agent_id,
            profile_visibility="shared",
            profile_access_list=["partner-org"],
        )
        profile = self.service.get_agent_profile(self.viewer.agent_id, self.same_org.agent_id)
        self.assertEqual(profile["profile_access_list"], ["partner-org"])

    def test_cross_org_activity_filters_out_internal_audit_entries(self) -> None:
        self.service.store_memory(
            agent_id=self.public.agent_id,
            content="Acme Corp expanded supplier coverage in Europe.",
            visibility="published",
        )

        cross_org = self.service.get_agent_activity(self.viewer.agent_id, self.public.agent_id)
        self.assertTrue(cross_org["items"])
        self.assertTrue(all(item["audit"] is None for item in cross_org["items"]))

        same_org = self.service.get_agent_activity(self.same_org.agent_id, self.same_org.agent_id)
        self.assertTrue(any(item["audit"] is not None for item in same_org["items"]))


if __name__ == "__main__":
    unittest.main()
