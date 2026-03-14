from __future__ import annotations

from datetime import timedelta
import unittest

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.errors import AuthenticationError, PermissionDeniedError
from contextgraph.models import JobStatus, JobType, ReviewStatus, ValidationStatus
from contextgraph.utils import utcnow


class RecordingDispatcher:
    def __init__(self) -> None:
        self.deliveries = []

    def dispatch(self, delivery) -> None:
        self.deliveries.append(delivery)


class FailingDispatcher:
    def dispatch(self, delivery) -> None:
        raise RuntimeError("webhook endpoint unavailable")


class FlakyDispatcher:
    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.attempts = 0
        self.deliveries = []

    def dispatch(self, delivery) -> None:
        self.attempts += 1
        if self.attempts <= self.failures_before_success:
            raise RuntimeError(f"transient webhook failure #{self.attempts}")
        self.deliveries.append(delivery)


class ContextGraphServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.alpha = self.service.register_agent("alpha-support", "alpha", ["support"])
        self.alpha_peer = self.service.register_agent("alpha-research", "alpha", ["research"])
        self.beta = self.service.register_agent("beta-risk", "beta", ["risk"])

    def test_private_claims_are_not_visible_to_other_agents(self) -> None:
        self.service.store_memory(
            agent_id=self.alpha.agent_id,
            content="Acme Corp reported API latency. Jane from Acme Corp needs a fix.",
            visibility="private",
        )

        own_hits = self.service.recall(self.alpha.agent_id, "Acme latency")
        peer_hits = self.service.recall(self.alpha_peer.agent_id, "Acme latency")

        self.assertGreaterEqual(len(own_hits), 1)
        self.assertEqual(peer_hits, [])

    def test_shared_claims_are_visible_inside_same_org_only(self) -> None:
        self.service.store_memory(
            agent_id=self.alpha.agent_id,
            content="Acme Corp reported API latency. Jane from Acme Corp needs a fix.",
            visibility="org",
        )

        peer_hits = self.service.recall(self.alpha_peer.agent_id, "Acme latency")
        outsider_hits = self.service.recall(self.beta.agent_id, "Acme latency")

        self.assertGreaterEqual(len(peer_hits), 1)
        self.assertEqual(outsider_hits, [])

    def test_watch_creates_notifications_for_matching_claims(self) -> None:
        self.service.watch(agent_id=self.alpha_peer.agent_id, query="Acme latency", name="Acme issues")

        self.service.store_memory(
            agent_id=self.alpha.agent_id,
            content="Acme Corp reported API latency and needs a fix.",
            visibility="org",
        )

        notifications = self.service.get_notifications(self.alpha_peer.agent_id)
        self.assertGreaterEqual(len(notifications), 1)
        self.assertEqual(notifications[0].event_type, "claim.matched")

    def test_watch_filters_can_target_specific_source_agent(self) -> None:
        self.service.watch(
            agent_id=self.alpha_peer.agent_id,
            query="Acme latency",
            filters={"source_agent_id": self.alpha.agent_id},
        )

        self.service.store_memory(
            agent_id=self.alpha.agent_id,
            content="Acme Corp reported API latency and needs a fix.",
            visibility="org",
        )
        self.service.store_memory(
            agent_id=self.beta.agent_id,
            content="Acme Corp reported API latency and needs a workaround.",
            visibility="published",
        )

        notifications = self.service.get_notifications(self.alpha_peer.agent_id)

        self.assertEqual(len(notifications), 1)

    def test_webhook_watch_requires_url(self) -> None:
        with self.assertRaises(ValueError):
            self.service.watch(
                agent_id=self.alpha_peer.agent_id,
                query="Acme latency",
                delivery_mode="webhook",
            )

        with self.assertRaises(ValueError):
            self.service.watch(
                agent_id=self.alpha_peer.agent_id,
                query="Acme latency",
                delivery_mode="webhook",
                filters={"webhook_url": "ftp://invalid-endpoint"},
            )

    def test_webhook_watch_delivers_notification_via_job(self) -> None:
        dispatcher = RecordingDispatcher()
        service = ContextGraphService(
            app_settings=Settings(
                enable_background_worker=False,
                enable_claim_expiry_sweeps=False,
            ),
            notification_dispatcher=dispatcher,
        )
        try:
            alpha = service.register_agent("alpha-support", "alpha", ["support"])
            alpha_peer = service.register_agent("alpha-research", "alpha", ["research"])
            service.watch(
                agent_id=alpha_peer.agent_id,
                query="Acme latency",
                delivery_mode="webhook",
                filters={"webhook_url": "https://example.com/contextgraph"},
            )

            service.store_memory(
                agent_id=alpha.agent_id,
                content="Acme Corp reported API latency and needs a fix.",
                visibility="org",
            )

            notifications = service.get_notifications(alpha_peer.agent_id)
            jobs = service.list_jobs(alpha_peer.agent_id)
        finally:
            service.close()

        self.assertEqual(len(dispatcher.deliveries), 1)
        self.assertEqual(dispatcher.deliveries[0].webhook_url, "https://example.com/contextgraph")
        self.assertEqual(len(notifications), 1)
        self.assertTrue(notifications[0].delivered)
        delivery_jobs = [job for job in jobs if job.job_type == JobType.DELIVER_NOTIFICATION]
        self.assertEqual(len(delivery_jobs), 1)
        self.assertEqual(delivery_jobs[0].status, JobStatus.SUCCEEDED)
        self.assertTrue(delivery_jobs[0].result_summary["delivered"])

    def test_webhook_delivery_retries_until_success(self) -> None:
        dispatcher = FlakyDispatcher(failures_before_success=2)
        service = ContextGraphService(
            app_settings=Settings(
                enable_background_worker=True,
                enable_claim_expiry_sweeps=False,
                background_worker_poll_seconds=0.01,
                delivery_max_attempts=3,
                delivery_retry_base_seconds=0.01,
            ),
            notification_dispatcher=dispatcher,
        )
        try:
            alpha = service.register_agent("alpha-support", "alpha", ["support"])
            alpha_peer = service.register_agent("alpha-research", "alpha", ["research"])
            service.watch(
                agent_id=alpha_peer.agent_id,
                query="Acme latency",
                delivery_mode="webhook",
                filters={"webhook_url": "https://example.com/contextgraph"},
            )

            service.store_memory(
                agent_id=alpha.agent_id,
                content="Acme Corp reported API latency and needs a fix.",
                visibility="org",
            )

            delivery_job = next(
                job for job in service.list_jobs(alpha_peer.agent_id) if job.job_type == JobType.DELIVER_NOTIFICATION
            )
            completed = service.wait_for_job(
                delivery_job.job_id,
                requester_agent_id=alpha_peer.agent_id,
                timeout_seconds=1.0,
            )
            notifications = service.get_notifications(alpha_peer.agent_id)
            audits = service.list_audit_entries(alpha_peer.agent_id)
            health = service.health()
        finally:
            service.close()

        self.assertEqual(dispatcher.attempts, 3)
        self.assertEqual(len(dispatcher.deliveries), 1)
        self.assertEqual(completed.status, JobStatus.SUCCEEDED)
        self.assertEqual(completed.attempt_count, 3)
        self.assertTrue(notifications[0].delivered)
        retry_audits = [entry for entry in audits if entry.action == "deliver_notification_retry_scheduled"]
        self.assertEqual(len(retry_audits), 2)
        self.assertTrue(any(entry.action == "deliver_notification" for entry in audits))
        self.assertEqual(health["delivery_retry_scheduled_total"], 2)

    def test_webhook_delivery_dead_letters_after_retries(self) -> None:
        service = ContextGraphService(
            app_settings=Settings(
                enable_background_worker=False,
                enable_claim_expiry_sweeps=False,
                delivery_max_attempts=2,
                delivery_retry_base_seconds=0.01,
            ),
            notification_dispatcher=FailingDispatcher(),
        )
        try:
            alpha = service.register_agent("alpha-support", "alpha", ["support"])
            alpha_peer = service.register_agent("alpha-research", "alpha", ["research"])
            service.watch(
                agent_id=alpha_peer.agent_id,
                query="Acme latency",
                delivery_mode="webhook",
                filters={"webhook_url": "https://example.com/contextgraph"},
            )

            service.store_memory(
                agent_id=alpha.agent_id,
                content="Acme Corp reported API latency and needs a fix.",
                visibility="org",
            )

            notifications = service.get_notifications(alpha_peer.agent_id)
            jobs = service.list_jobs(alpha_peer.agent_id)
            audits = service.list_audit_entries(alpha_peer.agent_id)
            health = service.health()
        finally:
            service.close()

        self.assertEqual(len(notifications), 1)
        self.assertFalse(notifications[0].delivered)
        delivery_jobs = [job for job in jobs if job.job_type == JobType.DELIVER_NOTIFICATION]
        self.assertEqual(len(delivery_jobs), 1)
        self.assertEqual(delivery_jobs[0].status, JobStatus.DEAD_LETTERED)
        self.assertEqual(delivery_jobs[0].attempt_count, 2)
        self.assertIn("webhook endpoint unavailable", delivery_jobs[0].error or "")
        self.assertTrue(any(entry.action == "deliver_notification_dead_letter" for entry in audits))
        self.assertEqual(health["delivery_dead_letter_total"], 1)

    def test_claim_expiry_sweep_marks_expired_claims_and_updates_health(self) -> None:
        service = ContextGraphService(
            app_settings=Settings(
                enable_background_worker=False,
                enable_claim_expiry_sweeps=False,
            )
        )
        try:
            agent = service.register_agent("alpha-support", "alpha", ["support"])
            result = service.store_memory(
                agent_id=agent.agent_id,
                content="Acme Corp reported API latency.",
                visibility="org",
            )
            claim = result.claims[0]
            claim.expires_at = utcnow() - timedelta(seconds=1)
            service.repository.update_claim(claim)

            completed = service.enqueue_claim_expiry_sweep(requester_agent_id=agent.agent_id)
            refreshed = service.repository.get_claim(claim.claim_id)
            health = service.health()
        finally:
            service.close()

        self.assertEqual(completed.status, JobStatus.SUCCEEDED)
        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed.validation_status, ValidationStatus.EXPIRED)
        self.assertEqual(completed.result_summary["expired_claims"], 1)
        self.assertEqual(health["expired_claims"], 1)
        self.assertIsNotNone(health["last_claim_expiry_sweep_at"])
        self.assertEqual(health["claim_expiry_sweep_runs"], 1)
        self.assertEqual(health["claims_expired_by_sweeps"], 1)
        self.assertEqual(health["jobs_by_type"][JobType.SWEEP_EXPIRED_CLAIMS.value], 1)

    def test_review_claim_attests_it(self) -> None:
        result = self.service.store_memory(
            agent_id=self.alpha.agent_id,
            content="short note.",
            visibility="org",
        )
        claim = result.claims[0]
        reviewed = self.service.review_claim(
            reviewer_agent_id=self.alpha_peer.agent_id,
            claim_id=claim.claim_id,
            decision="attested",
            reason="confirmed by reviewer",
        )
        self.assertEqual(reviewed.validation_status, ValidationStatus.ATTESTED)
        tasks = self.service.list_review_tasks(requester_agent_id=self.alpha.agent_id)
        self.assertEqual(tasks[0].status, ReviewStatus.RESOLVED)

    def test_relate_finds_direct_path_for_shared_entities(self) -> None:
        self.service.store_memory(
            agent_id=self.alpha.agent_id,
            content="Jane from Acme Corp reported API latency.",
            visibility="org",
        )

        paths = self.service.relate(
            agent_id=self.alpha_peer.agent_id,
            entity_a="Jane",
            entity_b="Acme Corp",
        )

        self.assertGreaterEqual(len(paths), 1)
        self.assertIn("Jane", paths[0].entities)
        self.assertIn("Acme Corp", paths[0].entities)

    def test_authenticate_agent_uses_api_key(self) -> None:
        authenticated = self.service.authenticate_agent(self.alpha.api_key)

        self.assertEqual(authenticated.agent_id, self.alpha.agent_id)

    def test_authenticate_agent_rejects_bad_key(self) -> None:
        with self.assertRaises(AuthenticationError):
            self.service.authenticate_agent("bad-key")

    def test_list_agents_scopes_to_requester_org(self) -> None:
        visible = self.service.list_agents(requester_agent_id=self.alpha.agent_id)

        self.assertEqual({agent.org_id for agent in visible}, {"alpha"})

    def test_list_audit_entries_scopes_to_requester_org(self) -> None:
        self.service.store_memory(
            agent_id=self.alpha.agent_id,
            content="Acme Corp reported API latency.",
            visibility="org",
        )
        visible = self.service.list_audit_entries(requester_agent_id=self.beta.agent_id)

        self.assertFalse(any(entry.actor_agent_id == self.alpha.agent_id for entry in visible))

    def test_review_queue_exposes_open_claims_to_same_org_operator(self) -> None:
        result = self.service.store_memory(
            agent_id=self.alpha.agent_id,
            content="short note.",
            visibility="private",
        )

        queue = self.service.list_review_queue(requester_agent_id=self.alpha_peer.agent_id)

        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0].claim.claim_id, result.claims[0].claim_id)
        self.assertEqual(queue[0].source_agent.agent_id, self.alpha.agent_id)

    def test_operator_snapshot_summarizes_org_state(self) -> None:
        self.service.store_memory(
            agent_id=self.alpha.agent_id,
            content="short note.",
            visibility="private",
        )

        snapshot = self.service.operator_snapshot(requester_agent_id=self.alpha_peer.agent_id)

        self.assertEqual(snapshot["org_id"], "alpha")
        self.assertEqual(snapshot["pending_review_count"], 1)
        self.assertGreaterEqual(snapshot["claim_count"], 1)
        self.assertIn("health", snapshot)

    def test_enqueue_memory_store_processes_job(self) -> None:
        service = ContextGraphService(
            app_settings=Settings(enable_background_worker=True, background_worker_poll_seconds=0.01)
        )
        try:
            agent = service.register_agent("async-agent", "alpha", ["support"])
            job = service.enqueue_memory_store(
                agent_id=agent.agent_id,
                content="Acme Corp reported API latency.",
                visibility="org",
            )

            completed = service.wait_for_job(job.job_id, requester_agent_id=agent.agent_id, timeout_seconds=1.0)

            self.assertEqual(completed.status, JobStatus.SUCCEEDED)
            self.assertEqual(completed.result_summary["claim_count"], 1)
            self.assertGreaterEqual(len(service.recall(agent.agent_id, "Acme latency")), 1)
        finally:
            service.close()

    def test_get_job_enforces_scope(self) -> None:
        job = self.service.enqueue_memory_store(
            agent_id=self.alpha.agent_id,
            content="Acme Corp reported API latency.",
            visibility="org",
        )

        with self.assertRaises(PermissionDeniedError):
            self.service.get_job(job.job_id, requester_agent_id=self.beta.agent_id)

    def test_watch_webhook_rejects_private_ip(self) -> None:
        with self.assertRaises(ValueError):
            self.service.watch(
                self.alpha.agent_id, "test", "w", "webhook",
                filters={"webhook_url": "http://169.254.169.254/latest/meta-data/"},
            )

    def test_watch_webhook_rejects_localhost(self) -> None:
        with self.assertRaises(ValueError):
            self.service.watch(
                self.alpha.agent_id, "test", "w", "webhook",
                filters={"webhook_url": "http://127.0.0.1:8080/callback"},
            )


if __name__ == "__main__":
    unittest.main()
