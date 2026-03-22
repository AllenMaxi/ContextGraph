from __future__ import annotations

import unittest

from contextgraph_sdk import ContextGraph

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.models import JobStatus


class ContextGraphSDKTest(unittest.TestCase):
    def test_local_transport_round_trip(self) -> None:
        service = ContextGraphService()
        client = ContextGraph.local(service)

        agent = client.register_agent(
            "sdk-agent",
            "alpha",
            ["research"],
            default_visibility="org",
            default_price=0.001,
        )
        client.watch(agent["agent_id"], "Acme latency", name="monitor")
        client.store(
            agent_id=agent["agent_id"],
            content="Acme Corp reported API latency. Jane from Acme Corp needs a fix.",
            evidence=["meeting:incident-review"],
            citations=["ticket:INC-42"],
            expires_in_days=14,
        )

        hits = client.recall(agent["agent_id"], "Acme latency")
        notifications = client.notifications(agent["agent_id"])

        self.assertGreaterEqual(len(hits), 1)
        self.assertGreaterEqual(len(notifications), 1)
        self.assertEqual(agent["default_visibility"], "org")
        self.assertEqual(agent["default_price"], 0.001)
        self.assertIn("meeting:incident-review", hits[0]["claim"]["evidence"])
        self.assertIn("ticket:INC-42", hits[0]["claim"]["citations"])

    def test_local_transport_explain_recall_round_trip(self) -> None:
        service = ContextGraphService()
        client = ContextGraph.local(service)

        agent = client.register_agent("sdk-explain", "alpha", ["research"])
        client.store(
            agent_id=agent["agent_id"],
            content="Acme Corp reported API latency due to overloaded connection pools.",
            visibility="org",
        )

        explanation = client.explain_recall(agent["agent_id"], "Acme latency", decision_limit=10)

        self.assertEqual(explanation["query"], "Acme latency")
        self.assertGreaterEqual(len(explanation["hits"]), 1)
        self.assertGreaterEqual(len(explanation["decisions"]), 1)
        self.assertIn("score_breakdown", explanation["decisions"][0])

    def test_local_transport_exposes_public_agent_claim_notification_and_health_methods(self) -> None:
        service = ContextGraphService()
        try:
            client = ContextGraph.local(service)

            agent = client.register_agent("sdk-public", "alpha", ["research"])
            client.watch(agent["agent_id"], "Acme latency", name="monitor")
            stored = client.store(
                agent_id=agent["agent_id"],
                content="Acme Corp reported API latency in the EU region.",
                visibility="org",
            )

            agents = client.agents(agent["agent_id"])
            claim = client.claim(agent["agent_id"], stored["claims"][0]["claim_id"])
            notifications = client.notifications(agent["agent_id"], mark_delivered=True)
            health = client.health()

            self.assertIn(agent["agent_id"], {item["agent_id"] for item in agents})
            self.assertEqual(claim["claim_id"], stored["claims"][0]["claim_id"])
            self.assertTrue(notifications[0]["delivered"])
            self.assertEqual(health["status"], "ok")
        finally:
            service.close()

    def test_local_transport_async_round_trip(self) -> None:
        service = ContextGraphService(
            app_settings=Settings(enable_background_worker=True, background_worker_poll_seconds=0.01)
        )
        try:
            client = ContextGraph.local(service)
            agent = client.register_agent("sdk-async", "alpha", ["research"])

            job = client.store_async(
                agent_id=agent["agent_id"],
                content="Acme Corp reported API latency.",
                visibility="org",
            )
            completed = service.wait_for_job(job["job_id"], requester_agent_id=agent["agent_id"], timeout_seconds=1.0)

            self.assertEqual(completed.status, JobStatus.SUCCEEDED)
        finally:
            service.close()

    def test_local_transport_operator_endpoints(self) -> None:
        service = ContextGraphService()
        try:
            client = ContextGraph.local(service)
            agent = client.register_agent("sdk-operator", "alpha", ["research"])
            client.store(
                agent_id=agent["agent_id"],
                content="short note.",
                visibility="private",
            )

            review_queue = client.review_queue(agent["agent_id"])
            summary = client.operator_summary(agent["agent_id"])
            claims = client.claims(agent["agent_id"], only_needing_review=True)
            sweep_job = client.expire_claims(agent["agent_id"])

            self.assertEqual(len(review_queue), 1)
            self.assertEqual(summary["pending_review_count"], 1)
            self.assertEqual(len(claims), 1)
            self.assertEqual(sweep_job["job_type"], "sweep_expired_claims")
        finally:
            service.close()

    def test_local_transport_updates_agent_defaults_and_allows_store_override(self) -> None:
        service = ContextGraphService()
        try:
            client = ContextGraph.local(service)
            agent = client.register_agent("sdk-defaults", "alpha", ["research"])
            updated = client.update_agent_defaults(
                agent["agent_id"],
                default_visibility="shared",
                default_access_list=["globex"],
                default_price=0.002,
            )

            inherited = client.store(agent["agent_id"], "Shared note.")
            overridden = client.store(agent["agent_id"], "Internal note.", visibility="private", price=0.0)

            self.assertEqual(updated["default_visibility"], "shared")
            self.assertEqual(updated["default_access_list"], ["globex"])
            self.assertEqual(updated["default_price"], 0.002)
            self.assertEqual(inherited["memory"]["visibility"], "shared")
            self.assertEqual(inherited["memory"]["access_list"], ["globex"])
            self.assertEqual(inherited["memory"]["price"], 0.002)
            self.assertEqual(overridden["memory"]["visibility"], "private")
            self.assertEqual(overridden["memory"]["access_list"], [])
            self.assertEqual(overridden["memory"]["price"], 0.0)
        finally:
            service.close()

    def test_local_transport_supports_follow_discovery_feed_and_trust(self) -> None:
        service = ContextGraphService()
        try:
            client = ContextGraph.local(service)
            research = client.register_agent("research-bot", "acme", ["research"])
            ops = client.register_agent("ops-bot", "acme", ["operations"])
            partner = client.register_agent("partner-analyst", "globex", ["analysis"])

            client.update_agent_profile(
                requester_agent_id=partner["agent_id"],
                agent_id=partner["agent_id"],
                profile_visibility="published",
                profile_summary="Cross-org market analyst",
                profile_links={"orchestrator": "https://agents.example.com/partner-analyst"},
            )
            client.follow(ops["agent_id"], "agent", research["agent_id"])
            client.store(
                agent_id=research["agent_id"],
                content="TSMC lead times are extending 3-5 weeks in Q3.",
                visibility="org",
            )

            discovered = client.discover(requester_agent_id=ops["agent_id"], q="analyst")
            following = client.following(ops["agent_id"])
            feed = client.feed(ops["agent_id"])
            trust = client.agent_trust(ops["agent_id"], research["agent_id"])

            self.assertEqual(discovered["items"][0]["agent_id"], partner["agent_id"])
            self.assertEqual(len(following), 1)
            self.assertEqual(following[0]["target_id"], research["agent_id"])
            self.assertGreaterEqual(len(feed), 1)
            self.assertEqual(feed[0]["agent_id"], research["agent_id"])
            self.assertEqual(trust["agent_id"], research["agent_id"])
            self.assertEqual(trust["status"], "active")
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()
