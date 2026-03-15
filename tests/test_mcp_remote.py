from __future__ import annotations

import json
import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    TestClient = None

from contextgraph.config import Settings
from contextgraph.web import FastAPI, create_app


@unittest.skipUnless(FastAPI is not None and TestClient is not None, "fastapi is not installed")
class ContextGraphRemoteMCPTest(unittest.TestCase):
    def _create_remote_client(self) -> TestClient:
        from contextgraph import ContextGraphService

        service = ContextGraphService(app_settings=Settings(enable_remote_mcp=True))
        self.addCleanup(service.close)
        return TestClient(create_app(service))

    def test_remote_mcp_initialize_and_tools_list(self) -> None:
        client = self._create_remote_client()

        initialize = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        tools = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )

        self.assertEqual(initialize.status_code, 200)
        self.assertEqual(initialize.json()["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(tools.status_code, 200)
        self.assertGreaterEqual(len(tools.json()["result"]["tools"]), 6)

    def test_remote_mcp_tool_call_requires_auth(self) -> None:
        client = self._create_remote_client()

        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "contextgraph_notifications", "arguments": {}},
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], -32001)

    def test_remote_mcp_tool_call_round_trip(self) -> None:
        client = self._create_remote_client()
        registered = client.post(
            "/v1/agents/register",
            json={"name": "remote-agent", "org_id": "alpha", "capabilities": ["assistant"]},
        ).json()
        headers = {"Authorization": f"Bearer {registered['api_key']}"}

        stored = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "contextgraph_store",
                    "arguments": {
                        "content": "Vendor X expanded into Germany.",
                        "evidence": ["meeting:weekly-ops"],
                        "citations": ["ticket:SUP-42"],
                        "expires_in_days": 14,
                    },
                },
            },
        )
        recalled = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "contextgraph_recall",
                    "arguments": {"query": "Germany", "limit": 5},
                },
            },
        )

        self.assertEqual(stored.status_code, 200)
        stored_payload = stored.json()["result"]["content"][0]["text"]
        self.assertIn("meeting:weekly-ops", stored_payload)
        self.assertIn("ticket:SUP-42", stored_payload)

        self.assertEqual(recalled.status_code, 200)
        recalled_payload = json.loads(recalled.json()["result"]["content"][0]["text"])
        self.assertEqual(len(recalled_payload), 1)
        self.assertEqual(recalled_payload[0]["statement"], "Vendor X expanded into Germany")

    def test_remote_mcp_server_card_is_available(self) -> None:
        client = self._create_remote_client()

        response = client.get("/.well-known/mcp/server-card.json")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["remotes"][0]["type"], "streamable-http")
        self.assertEqual(body["remotes"][0]["url"], "http://testserver/mcp")


if __name__ == "__main__":
    unittest.main()
