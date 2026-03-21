from __future__ import annotations

import unittest
from io import BytesIO
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
                expires_in_days=14,
            )

        self.assertEqual(captured["url"], "http://localhost:8420/v1/memory/store")
        self.assertEqual(captured["method"], "POST")
        self.assertIn('"evidence": ["meeting:incident-review"]', captured["body"])
        self.assertIn('"citations": ["ticket:INC-42"]', captured["body"])
        self.assertIn('"expires_in_days": 14', captured["body"])


if __name__ == "__main__":
    unittest.main()
