from __future__ import annotations

import unittest

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.models import JobStatus
from sdk.contextgraph_sdk import ContextGraph


class ContextGraphSDKTest(unittest.TestCase):
    def test_local_transport_round_trip(self) -> None:
        service = ContextGraphService()
        client = ContextGraph.local(service)

        agent = client.register_agent("sdk-agent", "alpha", ["research"])
        client.watch(agent["agent_id"], "Acme latency", name="monitor")
        client.store(
            agent_id=agent["agent_id"],
            content="Acme Corp reported API latency. Jane from Acme Corp needs a fix.",
            visibility="org",
        )

        hits = client.recall(agent["agent_id"], "Acme latency")
        notifications = client.notifications(agent["agent_id"])

        self.assertGreaterEqual(len(hits), 1)
        self.assertGreaterEqual(len(notifications), 1)

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


if __name__ == "__main__":
    unittest.main()
