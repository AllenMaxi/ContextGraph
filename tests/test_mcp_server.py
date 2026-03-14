"""Tests for contextgraph.mcp_server."""

from __future__ import annotations

import unittest

from contextgraph.bootstrap import create_service
from contextgraph.config import Settings
from contextgraph.mcp_server import TOOLS, _dispatch_tool


class TestToolDefinitionsAreComplete(unittest.TestCase):
    def test_tool_definitions_are_complete(self) -> None:
        self.assertEqual(len(TOOLS), 6)
        expected_names = {
            "contextgraph_store",
            "contextgraph_recall",
            "contextgraph_relate",
            "contextgraph_watch",
            "contextgraph_notifications",
            "contextgraph_review",
        }
        actual_names = {t["name"] for t in TOOLS}
        self.assertEqual(actual_names, expected_names)
        # Every tool should have description and inputSchema
        for tool in TOOLS:
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)
            self.assertIsInstance(tool["description"], str)
            self.assertTrue(len(tool["description"]) > 0)


class TestDispatchStoreTool(unittest.TestCase):
    def setUp(self) -> None:
        s = Settings(repository_backend="memory")
        self.service = create_service(s)
        agent = self.service.register_agent(name="test-agent", org_id="default")
        self.agent_id = agent.agent_id

    def test_dispatch_store_tool(self) -> None:
        result = _dispatch_tool(
            self.service,
            self.agent_id,
            "contextgraph_store",
            {"content": "Alice works at Acme Corp and she reported a bug."},
        )
        self.assertIn("memory_id", result)
        self.assertIn("claims", result)
        self.assertIsInstance(result["claims"], list)
        self.assertGreater(len(result["claims"]), 0)
        self.assertIn("entities", result)


class TestDispatchRecallTool(unittest.TestCase):
    def setUp(self) -> None:
        s = Settings(repository_backend="memory")
        self.service = create_service(s)
        agent = self.service.register_agent(name="test-agent", org_id="default")
        self.agent_id = agent.agent_id

    def test_dispatch_recall_tool(self) -> None:
        # Store something first so there is data to recall
        _dispatch_tool(
            self.service,
            self.agent_id,
            "contextgraph_store",
            {"content": "Bob manages the engineering team at Widgets Inc."},
        )
        result = _dispatch_tool(
            self.service,
            self.agent_id,
            "contextgraph_recall",
            {"query": "engineering team"},
        )
        self.assertIsInstance(result, list)
        # Should find at least one matching claim
        self.assertGreater(len(result), 0)
        hit = result[0]
        self.assertIn("claim_id", hit)
        self.assertIn("statement", hit)
        self.assertIn("score", hit)


class TestDispatchUnknownToolReturnsError(unittest.TestCase):
    def setUp(self) -> None:
        s = Settings(repository_backend="memory")
        self.service = create_service(s)
        agent = self.service.register_agent(name="test-agent", org_id="default")
        self.agent_id = agent.agent_id

    def test_dispatch_unknown_tool_returns_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _dispatch_tool(
                self.service,
                self.agent_id,
                "contextgraph_nonexistent",
                {},
            )
        self.assertIn("Unknown tool", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
