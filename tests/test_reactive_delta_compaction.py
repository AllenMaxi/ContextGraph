from __future__ import annotations

import unittest
from datetime import timedelta

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    TestClient = None

from contextgraph_sdk import ContextGraph

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.errors import PermissionDeniedError
from contextgraph.web import FastAPI, create_app


def _make_service() -> ContextGraphService:
    return ContextGraphService(app_settings=Settings(repository_backend="memory", sentinel_enabled=False))


class ReactiveDeltaCompactionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.agent = self.service.register_agent(name="coder", org_id="acme", capabilities=["coding"])
        self.other = self.service.register_agent(name="other", org_id="acme", capabilities=["coding"])
        self.session = self.service.create_session(
            agent_id=self.agent.agent_id,
            title="Payments refactor",
            source="claude-code",
            metadata={"workspace": "/tmp/project"},
        )

    def test_checkpoint_builds_structured_delta_pack(self) -> None:
        self.service.record_session_event(
            self.agent.agent_id, self.session.session_id, "decision", "Use gRPC internally."
        )
        self.service.record_session_event(
            self.agent.agent_id,
            self.session.session_id,
            "constraint",
            "Keep the public REST API stable.",
        )
        self.service.record_session_event(self.agent.agent_id, self.session.session_id, "todo", "Add migration tests.")
        self.service.record_session_event(
            self.agent.agent_id,
            self.session.session_id,
            "file_change",
            "Changed service.py",
            metadata={"path": "contextgraph/service.py"},
        )
        self.service.record_session_event(
            self.agent.agent_id,
            self.session.session_id,
            "command",
            "pytest tests/test_context_pack.py",
            metadata={"exit_code": "1", "error": "Context pack regression"},
        )

        pack = self.service.checkpoint_session(
            self.agent.agent_id, self.session.session_id, reason="manual", token_budget=500
        )

        self.assertEqual(pack.session_id, self.session.session_id)
        self.assertEqual(pack.checkpoint_reason, "manual")
        self.assertIn("Use gRPC internally.", pack.decisions)
        self.assertIn("Keep the public REST API stable.", pack.constraints)
        self.assertIn("Add migration tests.", pack.open_tasks)
        self.assertIn("contextgraph/service.py", pack.changed_files)
        self.assertIn("pytest tests/test_context_pack.py", pack.commands)
        self.assertIn("Context pack regression", pack.failures)
        self.assertTrue(pack.base_pack_id.startswith("dpk_"))
        self.assertEqual(pack.delta_from_pack_id, "")
        self.assertLessEqual(pack.tokens_used, 500)
        self.assertIn("Payments refactor", pack.restoration_prompt)

    def test_context_pressure_event_auto_checkpoints(self) -> None:
        result = self.service.record_session_event(
            self.agent.agent_id,
            self.session.session_id,
            "context_pressure",
            "Only 9 percent of the context window remains.",
            metadata={"context_remaining_pct": "9"},
        )

        self.assertIsNotNone(result.checkpoint)
        self.assertIsNotNone(result.delta_pack)
        refreshed = self.service.get_session(self.agent.agent_id, self.session.session_id)
        self.assertEqual(refreshed.latest_checkpoint_id, result.checkpoint.checkpoint_id)
        self.assertEqual(refreshed.latest_delta_pack_id, result.delta_pack.delta_pack_id)

    def test_resume_and_diff_reflect_resolved_items(self) -> None:
        self.service.record_session_event(self.agent.agent_id, self.session.session_id, "todo", "Add migration tests.")
        pack_one = self.service.checkpoint_session(self.agent.agent_id, self.session.session_id, reason="manual")
        checkpoints = self.service.list_compaction_checkpoints(self.agent.agent_id, self.session.session_id)

        self.service.record_session_event(
            self.agent.agent_id, self.session.session_id, "resolved", "Add migration tests."
        )
        pack_two = self.service.checkpoint_session(self.agent.agent_id, self.session.session_id, reason="manual")
        checkpoints = self.service.list_compaction_checkpoints(self.agent.agent_id, self.session.session_id)
        diff = self.service.context_diff(
            self.agent.agent_id,
            self.session.session_id,
            from_checkpoint_id=checkpoints[0].checkpoint_id,
            to_checkpoint_id=checkpoints[-1].checkpoint_id,
        )
        resume = self.service.resume_session(self.agent.agent_id, self.session.session_id)

        self.assertEqual(pack_one.sequence, 1)
        self.assertEqual(pack_two.sequence, 2)
        self.assertNotIn("Add migration tests.", resume.delta_pack.open_tasks)
        self.assertIn("Add migration tests.", resume.delta_pack.resolved_items)
        self.assertIn("Add migration tests.", diff.dropped.get("open_tasks", []))

    def test_many_checkpoints_do_not_lose_core_state(self) -> None:
        self.service.record_session_event(
            self.agent.agent_id, self.session.session_id, "decision", "Use pyproject for config."
        )
        self.service.record_session_event(
            self.agent.agent_id, self.session.session_id, "constraint", "Do not break SDK compatibility."
        )
        self.service.record_session_event(self.agent.agent_id, self.session.session_id, "todo", "Ship resume hooks.")

        for index in range(20):
            self.service.record_session_event(
                self.agent.agent_id,
                self.session.session_id,
                "note",
                f"Checkpoint note {index}",
            )
            self.service.checkpoint_session(
                self.agent.agent_id, self.session.session_id, reason="manual", token_budget=600
            )

        resume = self.service.resume_session(self.agent.agent_id, self.session.session_id)

        self.assertEqual(resume.session.checkpoint_count, 20)
        self.assertIn("Use pyproject for config.", resume.delta_pack.decisions)
        self.assertIn("Do not break SDK compatibility.", resume.delta_pack.constraints)
        self.assertIn("Ship resume hooks.", resume.delta_pack.open_tasks)

    def test_sessions_are_owner_scoped(self) -> None:
        with self.assertRaises(PermissionDeniedError):
            self.service.get_session(self.other.agent_id, self.session.session_id)

    def test_doctor_reports_stale_and_untrusted_items(self) -> None:
        self.service.record_session_event(
            self.agent.agent_id,
            self.session.session_id,
            "todo",
            "Validate third-party benchmark claims.",
            metadata={"trusted": "false"},
        )
        stored_event = self.service.repository.list_session_events(self.session.session_id)[0]
        stored_event.created_at = stored_event.created_at - timedelta(days=8)
        report_pack = self.service.checkpoint_session(self.agent.agent_id, self.session.session_id, reason="manual")
        report = self.service.doctor_memory(self.agent.agent_id, self.session.session_id)

        self.assertGreaterEqual(report.stale_item_count, 1)
        self.assertGreaterEqual(report.untrusted_item_count, 1)
        self.assertEqual(report_pack.sequence, 1)


class ReactiveDeltaCompactionSDKTest(unittest.TestCase):
    def test_sdk_round_trip_for_checkpoint_and_resume(self) -> None:
        service = _make_service()
        try:
            client = ContextGraph.local(service)
            agent = client.register_agent("sdk-coder", "acme", ["coding"])
            session = client.create_session(agent["agent_id"], title="SDK session", source="codex")
            result = client.record_session_event(
                agent["agent_id"],
                session["session_id"],
                "context_pressure",
                "Need to compact soon.",
                metadata={"context_remaining_pct": "12"},
            )
            resume = client.resume_session(agent["agent_id"], session["session_id"])
            diff = client.context_diff(agent["agent_id"], session["session_id"])

            self.assertIsNotNone(result["checkpoint"])
            self.assertEqual(resume["session"]["session_id"], session["session_id"])
            self.assertIn("Added", diff["summary"])
        finally:
            service.close()


@unittest.skipUnless(FastAPI is not None and TestClient is not None, "fastapi is not installed")
class ReactiveDeltaCompactionWebTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _make_service()
        self.client = TestClient(create_app(self.service))
        self.agent = self.client.post(
            "/v1/agents/register",
            json={"name": "web-coder", "org_id": "acme", "capabilities": ["coding"]},
        ).json()

    def test_session_endpoints_round_trip(self) -> None:
        headers = {"X-Agent-Key": self.agent["api_key"]}
        created = self.client.post(
            "/v1/sessions",
            headers=headers,
            json={"title": "Web session", "source": "claude-code"},
        )
        session_id = created.json()["session_id"]

        event = self.client.post(
            f"/v1/sessions/{session_id}/events",
            headers=headers,
            json={
                "event_type": "context_pressure",
                "content": "Compact now",
                "metadata": {"context_remaining_pct": "10"},
            },
        )
        resume = self.client.get(f"/v1/sessions/{session_id}/resume", headers=headers)
        diff = self.client.get(f"/v1/sessions/{session_id}/diff", headers=headers)
        doctor = self.client.get(f"/v1/sessions/{session_id}/doctor", headers=headers)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(event.status_code, 200)
        self.assertEqual(resume.status_code, 200)
        self.assertEqual(diff.status_code, 200)
        self.assertEqual(doctor.status_code, 200)
        self.assertEqual(resume.json()["session"]["session_id"], session_id)
        self.assertEqual(event.json()["delta_pack"]["checkpoint_reason"], "context_pressure")
