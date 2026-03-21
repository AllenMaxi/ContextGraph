from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    TestClient = None

from contextgraph import ContextGraphService
from contextgraph.web import FastAPI, create_app


@unittest.skipUnless(FastAPI is not None and TestClient is not None, "fastapi is not installed")
class AgentDiscoveryApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.client = TestClient(create_app(self.service))
        self.viewer = self.client.post(
            "/v1/agents/register",
            json={"name": "viewer", "org_id": "acme", "capabilities": ["research"]},
        ).json()
        self.public = self.client.post(
            "/v1/agents/register",
            json={"name": "public", "org_id": "globex", "capabilities": ["market"]},
        ).json()
        self.hidden = self.client.post(
            "/v1/agents/register",
            json={"name": "hidden", "org_id": "globex", "capabilities": ["ops"], "default_visibility": "published"},
        ).json()
        self.client.patch(
            f"/v1/agents/{self.public['agent_id']}/profile",
            headers={"X-Agent-Key": self.public["api_key"]},
            json={"profile_visibility": "published", "profile_summary": "Public market analyst"},
        )

    def test_discover_endpoint_returns_only_visible_profiles(self) -> None:
        response = self.client.get("/v1/agents/discover", headers={"X-Agent-Key": self.viewer["api_key"]})
        self.assertEqual(response.status_code, 200)
        agent_ids = {item["agent_id"] for item in response.json()["items"]}
        self.assertIn(self.public["agent_id"], agent_ids)
        self.assertNotIn(self.hidden["agent_id"], agent_ids)

    def test_agent_profile_requires_visibility_for_cross_org_requests(self) -> None:
        public_response = self.client.get(
            f"/v1/agents/{self.public['agent_id']}",
            headers={"X-Agent-Key": self.viewer["api_key"]},
        )
        hidden_response = self.client.get(
            f"/v1/agents/{self.hidden['agent_id']}",
            headers={"X-Agent-Key": self.viewer["api_key"]},
        )
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(hidden_response.status_code, 403)

    def test_profile_update_is_self_scoped(self) -> None:
        response = self.client.patch(
            f"/v1/agents/{self.public['agent_id']}/profile",
            headers={"X-Agent-Key": self.viewer["api_key"]},
            json={"profile_summary": "attempted overwrite"},
        )
        self.assertEqual(response.status_code, 403)

    def test_follow_self_returns_bad_request(self) -> None:
        response = self.client.post(
            "/v1/follow",
            headers={"X-Agent-Key": self.viewer["api_key"]},
            json={"target_type": "agent", "target_id": self.viewer["agent_id"]},
        )
        self.assertEqual(response.status_code, 400)

    def test_dashboard_discover_and_agent_detail_render(self) -> None:
        login = self.client.post("/dashboard/login", data={"api_key": self.viewer["api_key"]})
        self.assertEqual(login.status_code, 200)

        discover = self.client.get("/dashboard/discover")
        detail = self.client.get(f"/dashboard/agents/{self.public['agent_id']}")

        self.assertEqual(discover.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Discover", discover.text)
        self.assertIn("public", discover.text)
        self.assertIn("Activity", detail.text)
        self.assertIn("Trust", detail.text)


if __name__ == "__main__":
    unittest.main()
