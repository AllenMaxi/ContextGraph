from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    TestClient = None

from contextgraph import ContextGraphService
from contextgraph.web import FastAPI, create_app


@unittest.skipUnless(FastAPI is not None and TestClient is not None, "fastapi is not installed")
class ContextGraphWebTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.client = TestClient(create_app(self.service))

    def test_list_agents_requires_auth_and_hides_api_keys(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        )
        beta = self.client.post(
            "/v1/agents/register",
            json={"name": "beta-risk", "org_id": "beta", "capabilities": ["risk"]},
        )

        self.assertEqual(alpha.status_code, 201)
        self.assertEqual(beta.status_code, 201)

        unauthorized = self.client.get("/v1/agents")
        self.assertEqual(unauthorized.status_code, 401)

        headers = {"X-Agent-Key": alpha.json()["api_key"]}
        listed = self.client.get("/v1/agents", headers=headers)

        self.assertEqual(listed.status_code, 200)
        payload = listed.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["org_id"], "alpha")
        self.assertNotIn("api_key", payload[0])

    def test_store_rejects_mismatched_agent_id(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()
        beta = self.client.post(
            "/v1/agents/register",
            json={"name": "beta-risk", "org_id": "beta", "capabilities": ["risk"]},
        ).json()

        response = self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={
                "agent_id": beta["agent_id"],
                "content": "Acme Corp reported API latency.",
                "visibility": "shared",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_store_async_returns_job_and_job_status(self) -> None:
        self.service.start_background_worker()
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()

        job_response = self.client.post(
            "/v1/memory/store-async",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"content": "Acme Corp reported API latency.", "visibility": "shared"},
        )

        self.assertEqual(job_response.status_code, 200)
        job = job_response.json()
        self.assertIn(job["status"], {"queued", "running", "succeeded"})

        status_response = self.client.get(
            f"/v1/jobs/{job['job_id']}",
            headers={"X-Agent-Key": alpha["api_key"]},
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["job_id"], job["job_id"])

    def test_watch_webhook_validation_returns_bad_request(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()

        response = self.client.post(
            "/v1/watch",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={
                "delivery_mode": "webhook",
                "query": "Acme latency",
                "filters": {},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("webhook_url", response.json()["detail"])

    def test_operator_endpoints_and_console_render(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()

        self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"content": "short note.", "visibility": "private"},
        )

        review_queue = self.client.get("/v1/review-queue", headers={"X-Agent-Key": alpha["api_key"]})
        operator_summary = self.client.get("/v1/operator/summary", headers={"X-Agent-Key": alpha["api_key"]})

        # Console now uses cookie-based auth: POST to /console/login, then GET /console
        login_response = self.client.post(
            "/console/login",
            data={"api_key": alpha["api_key"]},
        )
        self.assertEqual(login_response.status_code, 200)  # 303 redirect followed by TestClient
        console = self.client.get("/console")

        self.assertEqual(review_queue.status_code, 200)
        self.assertEqual(len(review_queue.json()), 1)
        self.assertEqual(operator_summary.status_code, 200)
        self.assertEqual(operator_summary.json()["pending_review_count"], 1)
        self.assertIn("ContextGraph Console", console.text)


if __name__ == "__main__":
    unittest.main()
