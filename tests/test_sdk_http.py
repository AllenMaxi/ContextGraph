from __future__ import annotations

from io import BytesIO
import unittest
from unittest.mock import patch
from urllib import error

from sdk.contextgraph_sdk import (
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

        with patch("sdk.contextgraph_sdk.client.request.urlopen", side_effect=http_error):
            with self.assertRaises(AuthenticationError) as context:
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

        with patch("sdk.contextgraph_sdk.client.request.urlopen", side_effect=http_error):
            with self.assertRaises(PermissionDeniedError) as context:
                client.store("agt_other", "Acme Corp reported API latency.", visibility="shared")

        self.assertEqual(context.exception.status_code, 403)

    def test_http_transport_maps_connection_failures(self) -> None:
        client = ContextGraph.http("http://localhost:8420", api_key="key_ok")
        url_error = error.URLError("connection refused")

        with patch("sdk.contextgraph_sdk.client.request.urlopen", side_effect=url_error):
            with self.assertRaises(ContextGraphConnectionError) as context:
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

        with patch("sdk.contextgraph_sdk.client.request.urlopen", side_effect=fake_urlopen):
            client.claims("agt_test", validation_status="unreviewed", only_needing_review=True, limit=25)

        self.assertEqual(
            captured["url"],
            "http://localhost:8420/v1/claims?validation_status=unreviewed&only_needing_review=true&limit=25",
        )


if __name__ == "__main__":
    unittest.main()
