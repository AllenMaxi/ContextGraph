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
            json={"content": "Acme Corp reported API latency.", "visibility": "org"},
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
        self.assertIn("data-api-key=", console.text)
        self.assertIn("X-Agent-Key", console.text)
        self.assertIn('data-page="overview"', console.text)
        self.assertIn("Knowledge Overview", console.text)
        self.assertIn("Internal Memories", console.text)
        self.assertIn("Locked Discoveries", console.text)
        self.assertIn("Validation and Expiry", console.text)
        self.assertIn("Needs Review", console.text)
        self.assertIn("reviewClaimDecision", console.text)
        self.assertIn("updateMemoryCuration", console.text)
        self.assertIn("Review History", console.text)
        self.assertIn("Audit Trail", console.text)

    def test_update_memory_access_endpoint_updates_memory_policy(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()

        stored = self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"content": "Acme Corp reported API latency. Follow-up planned.", "visibility": "org"},
        ).json()

        response = self.client.patch(
            f"/v1/memories/{stored['memory']['memory_id']}/access",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"visibility": "shared", "access_list": ["partner-org"], "price": 0.002},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["visibility"], "shared")
        self.assertEqual(body["access_list"], ["partner-org"])
        self.assertEqual(body["price"], 0.002)

    def test_recall_explain_endpoint_returns_hits_decisions_and_filtered_counts(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()
        beta = self.client.post(
            "/v1/agents/register",
            json={"name": "beta-risk", "org_id": "beta", "capabilities": ["risk"]},
        ).json()

        self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"content": "Acme Corp reported API latency in an internal incident review.", "visibility": "org"},
        )
        self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"content": "Acme Corp reported API latency in a public postmortem.", "visibility": "published"},
        )

        response = self.client.post(
            "/v1/memory/recall/explain",
            headers={"X-Agent-Key": beta["api_key"]},
            json={"query": "Acme latency", "limit": 5, "decision_limit": 10},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["query"], "Acme latency")
        self.assertGreaterEqual(len(body["hits"]), 1)
        self.assertGreaterEqual(len(body["decisions"]), 1)
        self.assertIn("score_breakdown", body["decisions"][0])
        self.assertGreaterEqual(body["filtered_counts"].get("access_denied", 0), 1)

    def test_register_with_defaults_and_store_without_policy_uses_agent_defaults(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={
                "name": "alpha-support",
                "org_id": "alpha",
                "capabilities": ["support"],
                "default_visibility": "shared",
                "default_access_list": ["partner-org"],
                "default_price": 0.002,
            },
        ).json()

        stored = self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"content": "Acme partner note."},
        )

        self.assertEqual(stored.status_code, 200)
        body = stored.json()
        self.assertEqual(alpha["default_visibility"], "shared")
        self.assertEqual(alpha["default_access_list"], ["partner-org"])
        self.assertEqual(alpha["default_price"], 0.002)
        self.assertEqual(body["memory"]["visibility"], "shared")
        self.assertEqual(body["memory"]["access_list"], ["partner-org"])
        self.assertEqual(body["memory"]["price"], 0.002)

    def test_store_rejects_shared_without_access_list(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()

        response = self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"content": "Acme partner note.", "visibility": "shared"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("access_list", response.json()["detail"])

    def test_store_accepts_evidence_citations_and_expiry(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()

        response = self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={
                "content": "Acme partner note.",
                "visibility": "org",
                "evidence": ["meeting:weekly-ops"],
                "citations": ["ticket:SUP-42"],
                "expires_in_days": 5,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["memory"]["validation_status"], "unreviewed")
        self.assertIn("meeting:weekly-ops", body["memory"]["evidence"])
        self.assertIn("ticket:SUP-42", body["memory"]["citations"])
        self.assertIsNotNone(body["memory"]["expires_at"])
        self.assertIn("meeting:weekly-ops", body["claims"][0]["evidence"])
        self.assertIn("ticket:SUP-42", body["claims"][0]["citations"])

    def test_store_accepts_source_fields_and_memory_endpoints_round_trip(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()

        stored = self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={
                "content": "Anthropic adapter memory snapshot.",
                "visibility": "private",
                "source_type": "anthropic_memory_file",
                "source_uri": "claude-memory://default/memories/project.md",
                "source_label": "project.md",
                "section_refs": ["Summary"],
                "ingest_metadata": {
                    "integration": "anthropic_memory_tool",
                    "namespace": "default",
                    "logical_path": "/memories/project.md",
                    "revision": "1",
                    "current": "true",
                },
            },
        )
        listed = self.client.get("/v1/memories?limit=1", headers={"X-Agent-Key": alpha["api_key"]})
        fetched = self.client.get(
            f"/v1/memories/{stored.json()['memory']['memory_id']}",
            headers={"X-Agent-Key": alpha["api_key"]},
        )

        self.assertEqual(stored.status_code, 200)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(stored.json()["memory"]["source_type"], "anthropic_memory_file")
        self.assertEqual(stored.json()["memory"]["source_label"], "project.md")
        self.assertEqual(stored.json()["memory"]["ingest_metadata"]["logical_path"], "/memories/project.md")
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(fetched.json()["source_uri"], "claude-memory://default/memories/project.md")

    def test_memory_curation_endpoint_hides_memory_from_active_list(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()

        stored = self.client.post(
            "/v1/memory/store",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"content": "Acme partner note.", "visibility": "org"},
        ).json()

        curated = self.client.patch(
            f"/v1/memories/{stored['memory']['memory_id']}/curation",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"curation_status": "archived", "reason": "outdated guidance"},
        )
        all_memories = self.client.get("/v1/memories?include_inactive=true", headers={"X-Agent-Key": alpha["api_key"]})
        active_memories = self.client.get("/v1/memories", headers={"X-Agent-Key": alpha["api_key"]})

        self.assertEqual(curated.status_code, 200)
        self.assertEqual(curated.json()["curation_status"], "archived")
        self.assertEqual(curated.json()["curation_reason"], "outdated guidance")
        self.assertEqual(all_memories.status_code, 200)
        self.assertEqual(len(all_memories.json()), 1)
        self.assertEqual(active_memories.status_code, 200)
        self.assertEqual(active_memories.json(), [])

    def test_patch_agent_defaults_requires_same_agent(self) -> None:
        alpha = self.client.post(
            "/v1/agents/register",
            json={"name": "alpha-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()
        beta = self.client.post(
            "/v1/agents/register",
            json={"name": "beta-support", "org_id": "alpha", "capabilities": ["support"]},
        ).json()

        forbidden = self.client.patch(
            f"/v1/agents/{alpha['agent_id']}/defaults",
            headers={"X-Agent-Key": beta["api_key"]},
            json={"default_visibility": "shared", "default_access_list": ["partner-org"]},
        )
        allowed = self.client.patch(
            f"/v1/agents/{alpha['agent_id']}/defaults",
            headers={"X-Agent-Key": alpha["api_key"]},
            json={"default_visibility": "org", "default_price": 0.001},
        )

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["default_visibility"], "org")
        self.assertEqual(allowed.json()["default_access_list"], [])
        self.assertEqual(allowed.json()["default_price"], 0.001)


if __name__ == "__main__":
    unittest.main()
