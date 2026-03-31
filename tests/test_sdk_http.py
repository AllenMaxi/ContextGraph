from __future__ import annotations

import json
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib import error

from contextgraph_sdk import (
    AuthenticationError,
    ContextGraph,
    ContextGraphConnectionError,
    PermissionDeniedError,
)


class ContextGraphSDKHttpTransportTest(unittest.TestCase):
    def test_http_transport_maps_401_to_authentication_error(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="bad-key")
        http_error = error.HTTPError(
            url="http://localhost:8420/v1/memory/recall",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"detail":"Invalid API key."}'),
        )

        with (
            patch("contextgraph_sdk.client.request.urlopen", side_effect=http_error),
            self.assertRaises(AuthenticationError) as context,
        ):
            client.recall("agt_test", "Acme latency")

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(str(context.exception), "Invalid API key.")

    def test_http_transport_maps_403_to_permission_denied_error(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")
        http_error = error.HTTPError(
            url="http://localhost:8420/v1/memory/store",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=BytesIO(b'{"detail":"Authenticated agent does not match the requested agent_id."}'),
        )

        with (
            patch("contextgraph_sdk.client.request.urlopen", side_effect=http_error),
            self.assertRaises(PermissionDeniedError) as context,
        ):
            client.store("agt_other", "Acme Corp reported API latency.", visibility="shared")

        self.assertEqual(context.exception.status_code, 403)

    def test_http_transport_maps_connection_failures(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")
        url_error = error.URLError("connection refused")

        with (
            patch("contextgraph_sdk.client.request.urlopen", side_effect=url_error),
            self.assertRaises(ContextGraphConnectionError) as context,
        ):
            client.notifications("agt_test")

        self.assertIn("connection refused", str(context.exception))

    def test_http_transport_claims_uses_encoded_query_parameters(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"[]"

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.claims("agt_test", validation_status="unreviewed", only_needing_review=True, limit=25)

        self.assertEqual(
            captured["url"],
            "http://localhost:8420/v1/claims?validation_status=unreviewed&only_needing_review=true&limit=25",
        )

    def test_http_transport_updates_agent_defaults_via_agent_path(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = req.data.decode("utf-8")
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.update_agent_defaults(
                "agt_test",
                default_visibility="shared",
                default_access_list=["globex"],
                default_price=0.002,
            )

        self.assertEqual(captured["url"], "http://localhost:8420/v1/agents/agt_test/defaults")
        self.assertEqual(captured["method"], "PATCH")
        self.assertIn('"default_visibility": "shared"', captured["body"])
        self.assertIn('"default_access_list": ["globex"]', captured["body"])
        self.assertIn('"default_price": 0.002', captured["body"])

    def test_http_transport_store_includes_provenance_fields(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = req.data.decode("utf-8")
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.store(
                "agt_test",
                "Acme Corp reported API latency.",
                evidence=["meeting:incident-review"],
                citations=["ticket:INC-42"],
                source_type="anthropic_memory_file",
                source_uri="claude-memory://default/memories/project.md",
                source_label="project.md",
                section_refs=["Summary"],
                ingest_metadata={"integration": "anthropic_memory_tool"},
                expires_in_days=14,
            )

        self.assertEqual(captured["url"], "http://localhost:8420/v1/memory/store")
        self.assertEqual(captured["method"], "POST")
        self.assertIn('"evidence": ["meeting:incident-review"]', captured["body"])
        self.assertIn('"citations": ["ticket:INC-42"]', captured["body"])
        self.assertIn('"source_type": "anthropic_memory_file"', captured["body"])
        self.assertIn('"source_uri": "claude-memory://default/memories/project.md"', captured["body"])
        self.assertIn('"source_label": "project.md"', captured["body"])
        self.assertIn('"section_refs": ["Summary"]', captured["body"])
        self.assertIn('"ingest_metadata": {"integration": "anthropic_memory_tool"}', captured["body"])
        self.assertIn('"expires_in_days": 14', captured["body"])

    def test_http_transport_memory_helpers_use_expected_endpoints(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self._payload

        captured: list[tuple[str, str, str]] = []
        responses = [
            FakeResponse(b"[]"),
            FakeResponse(b"{}"),
            FakeResponse(b"{}"),
        ]

        def fake_urlopen(req):
            body = req.data.decode("utf-8") if req.data else ""
            captured.append((req.get_method(), req.full_url, body))
            return responses.pop(0)

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.memories("agt_test", include_inactive=True, limit=25)
            client.memory("agt_test", "mem_123")
            client.update_memory_curation("agt_test", "mem_123", "archived", "superseded")

        self.assertEqual(captured[0], ("GET", "http://localhost:8420/v1/memories?include_inactive=True&limit=25", ""))
        self.assertEqual(captured[1], ("GET", "http://localhost:8420/v1/memories/mem_123", ""))
        self.assertEqual(captured[2][0], "PATCH")
        self.assertEqual(captured[2][1], "http://localhost:8420/v1/memories/mem_123/curation")
        self.assertIn('"curation_status": "archived"', captured[2][2])
        self.assertIn('"reason": "superseded"', captured[2][2])

    def test_http_transport_fork_session_uses_fork_endpoint(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = req.data.decode("utf-8")
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.fork_session("agt_test", "ses_123", from_checkpoint_id="chk_1", title="branch")

        self.assertEqual(captured["url"], "http://localhost:8420/v1/sessions/ses_123/fork")
        self.assertEqual(captured["method"], "POST")
        self.assertIn('"from_checkpoint_id": "chk_1"', captured["body"])
        self.assertIn('"title": "branch"', captured["body"])

    def test_http_transport_explain_recall_uses_explain_endpoint_and_payment_header(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"query":"Acme latency","total_claims":1,"hits":[],"decisions":[],"filtered_counts":{}}'

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = req.data.decode("utf-8")
            captured["headers"] = {key.lower(): value for key, value in req.header_items()}
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.explain_recall(
                "agt_test",
                "Acme latency",
                limit=5,
                decision_limit=12,
                payment_token="x402_test_token",
            )

        self.assertEqual(captured["url"], "http://localhost:8420/v1/memory/recall/explain")
        self.assertEqual(captured["method"], "POST")
        self.assertIn('"query": "Acme latency"', captured["body"])
        self.assertIn('"limit": 5', captured["body"])
        self.assertIn('"decision_limit": 12', captured["body"])
        self.assertEqual(captured["headers"]["x-payment-token"], "x402_test_token")

    def test_http_transport_follow_uses_follow_endpoint(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = req.data.decode("utf-8")
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.follow("agt_test", "agent", "agt_target")

        self.assertEqual(captured["url"], "http://localhost:8420/v1/follow")
        self.assertEqual(captured["method"], "POST")
        self.assertIn('"target_type": "agent"', captured["body"])
        self.assertIn('"target_id": "agt_target"', captured["body"])

    def test_http_transport_session_helpers_use_expected_endpoints(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self._payload

        captured: list[tuple[str, str, str]] = []
        responses = [FakeResponse(b"{}") for _ in range(6)]

        def fake_urlopen(req):
            body = req.data.decode("utf-8") if req.data else ""
            captured.append((req.get_method(), req.full_url, body))
            return responses.pop(0)

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.create_session("agt_test", title="SDK session", source="codex")
            client.record_session_event("agt_test", "ses_123", "decision", "Use pyproject")
            client.checkpoint_session("agt_test", "ses_123", reason="manual", token_budget=1200)
            client.session_checkpoints("agt_test", "ses_123")
            client.context_diff("agt_test", "ses_123", from_checkpoint_id="chk_a", to_checkpoint_id="chk_b")
            client.doctor_memory("agt_test", "ses_123")

        self.assertEqual(captured[0][1], "http://localhost:8420/v1/sessions")
        self.assertIn('"title": "SDK session"', captured[0][2])
        self.assertEqual(captured[1][1], "http://localhost:8420/v1/sessions/ses_123/events")
        self.assertIn('"event_type": "decision"', captured[1][2])
        self.assertEqual(captured[2][1], "http://localhost:8420/v1/sessions/ses_123/checkpoint")
        self.assertIn('"reason": "manual"', captured[2][2])
        self.assertEqual(captured[3][1], "http://localhost:8420/v1/sessions/ses_123/checkpoints")
        self.assertEqual(
            captured[4][1],
            "http://localhost:8420/v1/sessions/ses_123/diff?from_checkpoint_id=chk_a&to_checkpoint_id=chk_b",
        )
        self.assertEqual(captured[5][1], "http://localhost:8420/v1/sessions/ses_123/doctor")

    def test_http_sync_memory_directory_uses_transport_and_writes_public_files(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self._payload

        with TemporaryDirectory() as workspace:
            session_payload = {
                "session_id": "ses_123",
                "agent_id": "agt_test",
                "title": "HTTP memdir",
                "source": "codex",
                "status": "active",
                "metadata": {"workspace": workspace},
                "created_at": "2026-03-31T09:00:00+00:00",
                "updated_at": "2026-03-31T09:05:00+00:00",
                "parent_session_id": "",
                "forked_from_checkpoint_id": "",
                "latest_checkpoint_id": "chk_1",
                "latest_delta_pack_id": "dpk_1",
                "checkpoint_count": 1,
                "event_count": 2,
            }
            resume_payload = {
                "session": session_payload,
                "checkpoint": {
                    "checkpoint_id": "chk_1",
                    "session_id": "ses_123",
                    "agent_id": "agt_test",
                    "sequence": 1,
                    "reason": "manual",
                    "created_at": "2026-03-31T09:05:00+00:00",
                    "delta_pack_id": "dpk_1",
                    "base_checkpoint_id": "",
                    "event_count": 2,
                    "restoration_prompt": "Resume from the latest checkpoint.",
                    "restoration_instructions": ["Inspect the changed files first."],
                    "summary": "Resume from the latest checkpoint.",
                },
                "delta_pack": {
                    "delta_pack_id": "dpk_1",
                    "checkpoint_id": "chk_1",
                    "session_id": "ses_123",
                    "agent_id": "agt_test",
                    "sequence": 1,
                    "checkpoint_reason": "manual",
                    "generated_at": "2026-03-31T09:05:00+00:00",
                    "token_budget": 600,
                    "tokens_used": 180,
                    "summary": "Resume from the latest checkpoint.",
                    "base_pack_id": "dpk_1",
                    "delta_from_pack_id": "",
                    "decisions": ["Keep the REST API stable."],
                    "constraints": [],
                    "open_tasks": ["Add migration tests."],
                    "failures": [],
                    "resolved_items": [],
                    "important_artifacts": [],
                    "external_references": [],
                    "changed_files": ["contextgraph/service.py"],
                    "commands": [],
                    "notes": [],
                    "stale_items": [],
                    "untrusted_items": [],
                    "dropped_items": [],
                    "restoration_prompt": "Resume from the latest checkpoint.",
                    "restoration_instructions": ["Inspect the changed files first."],
                    "included_event_ids": ["evt_1", "evt_2"],
                    "event_count": 2,
                    "cache_status": "miss",
                    "cache_base_checkpoint_id": "",
                    "reused_event_count": 0,
                    "recomputed_event_count": 2,
                    "invalidated_reasons": [],
                    "state_snapshot": {"open_tasks": []},
                },
            }
            doctor_payload = {
                "session_id": "ses_123",
                "agent_id": "agt_test",
                "total_events": 2,
                "checkpoint_count": 1,
                "latest_checkpoint_at": "2026-03-31T09:05:00+00:00",
                "unresolved_task_count": 1,
                "failure_count": 0,
                "stale_item_count": 0,
                "untrusted_item_count": 0,
                "branch_backed": False,
                "latest_cache_status": "miss",
                "likely_prefix_reuse": False,
                "warnings": [],
                "recommendations": [],
                "status": "ok",
            }

            responses = [
                FakeResponse(json.dumps(session_payload).encode("utf-8")),
                FakeResponse(json.dumps(resume_payload).encode("utf-8")),
                FakeResponse(json.dumps(doctor_payload).encode("utf-8")),
            ]
            captured: list[str] = []

            def fake_urlopen(req):
                captured.append(req.full_url)
                return responses.pop(0)

            with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
                result = client.sync_memory_directory("agt_test", "ses_123")

            memory_dir = Path(result["directory_path"])
            delta_payload = json.loads((memory_dir / "latest_delta_pack.json").read_text())
            self.assertEqual(captured[0], "http://localhost:8420/v1/sessions/ses_123")
            self.assertEqual(captured[1], "http://localhost:8420/v1/sessions/ses_123/resume")
            self.assertEqual(captured[2], "http://localhost:8420/v1/sessions/ses_123/doctor")
            self.assertNotIn("state_snapshot", delta_payload)
            self.assertIn("Keep the REST API stable.", (memory_dir / "decisions.md").read_text())
            self.assertEqual(result["checkpoint_id"], "chk_1")

    def test_http_transport_feed_uses_encoded_query_parameters(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"[]"

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.feed("agt_test", limit=5, offset=10)

        self.assertEqual(captured["url"], "http://localhost:8420/v1/feed?limit=5&offset=10")

    def test_http_transport_unfollow_handles_empty_204_response(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b""

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            result = client.unfollow("agt_test", "sub_123")

        self.assertIsNone(result)
        self.assertEqual(captured["url"], "http://localhost:8420/v1/follow/sub_123")
        self.assertEqual(captured["method"], "DELETE")

    def test_http_transport_agents_uses_agents_endpoint(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"[]"

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.agents("agt_test")

        self.assertEqual(captured["url"], "http://localhost:8420/v1/agents")
        self.assertEqual(captured["method"], "GET")

    def test_http_transport_claim_uses_claim_detail_endpoint(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.claim("agt_test", "clm_123")

        self.assertEqual(captured["url"], "http://localhost:8420/v1/claims/clm_123")
        self.assertEqual(captured["method"], "GET")

    def test_http_transport_notifications_supports_mark_delivered(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"[]"

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.notifications("agt_test", mark_delivered=True)

        self.assertEqual(captured["url"], "http://localhost:8420/v1/notifications/agt_test?mark_delivered=true")
        self.assertEqual(captured["method"], "GET")

    def test_http_transport_health_uses_health_endpoint(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"status":"ok"}'

        captured = {}

        def fake_urlopen(req):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            return FakeResponse()

        with patch("contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            result = client.health()

        self.assertEqual(captured["url"], "http://localhost:8420/health")
        self.assertEqual(captured["method"], "GET")
        self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()
