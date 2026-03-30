from __future__ import annotations

import unittest
from types import SimpleNamespace

from contextgraph_sdk import ContextGraph

from contextgraph import ContextGraphAnthropicMemoryTool, ContextGraphService


class ContextGraphAnthropicMemoryToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.client = ContextGraph.local(self.service)
        self.agent = self.client.register_agent("anthropic-adapter", "acme", ["assistant"])
        self.tool = ContextGraphAnthropicMemoryTool(self.client, self.agent["agent_id"], namespace="team-alpha")

    def tearDown(self) -> None:
        self.service.close()

    def test_create_and_view_store_snapshot_with_contextgraph_metadata(self) -> None:
        result = self.tool.create(
            SimpleNamespace(
                command="create",
                path="/memories/project/notes.md",
                file_text="alpha\nbeta",
            )
        )
        viewed = self.tool.view(
            SimpleNamespace(
                command="view",
                path="/memories/project/notes.md",
                view_range=None,
            )
        )

        memories = [
            memory
            for memory in self.client.memories(self.agent["agent_id"], include_inactive=True, limit=20)
            if memory["source_type"] == "anthropic_memory_file"
        ]

        self.assertEqual(result, "File created successfully at: /memories/project/notes.md")
        self.assertIn("Here's the content of /memories/project/notes.md with line numbers:", viewed)
        self.assertIn("alpha", viewed)
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["source_uri"], "claude-memory://team-alpha/memories/project/notes.md")
        self.assertEqual(memories[0]["source_label"], "notes.md")
        self.assertEqual(memories[0]["ingest_metadata"]["revision"], "1")

    def test_str_replace_creates_new_revision_and_archives_old_snapshot(self) -> None:
        self.tool.create(
            SimpleNamespace(
                command="create",
                path="/memories/project/notes.md",
                file_text="alpha\nbeta",
            )
        )

        edited = self.tool.str_replace(
            SimpleNamespace(
                command="str_replace",
                path="/memories/project/notes.md",
                old_str="beta",
                new_str="gamma",
            )
        )

        memories = [
            memory
            for memory in self.client.memories(self.agent["agent_id"], include_inactive=True, limit=20)
            if memory["source_type"] == "anthropic_memory_file"
        ]
        active = [memory for memory in memories if memory["curation_status"] == "active"]
        archived = [memory for memory in memories if memory["curation_status"] == "archived"]

        self.assertIn("The memory file has been edited.", edited)
        self.assertEqual(len(memories), 2)
        self.assertEqual(len(active), 1)
        self.assertEqual(len(archived), 1)
        self.assertEqual(active[0]["content"], "alpha\ngamma")
        self.assertEqual(active[0]["ingest_metadata"]["revision"], "2")
        self.assertEqual(active[0]["ingest_metadata"]["supersedes_memory_id"], archived[0]["memory_id"])

    def test_insert_rename_delete_and_directory_view_follow_snapshot_rules(self) -> None:
        self.tool.create(
            SimpleNamespace(
                command="create",
                path="/memories/project/notes.md",
                file_text="alpha\nbeta",
            )
        )
        self.tool.create(
            SimpleNamespace(
                command="create",
                path="/memories/project/todo.md",
                file_text="one\ntwo",
            )
        )

        inserted = self.tool.insert(
            SimpleNamespace(
                command="insert",
                path="/memories/project/notes.md",
                insert_line=1,
                insert_text="between",
            )
        )
        renamed = self.tool.rename(
            SimpleNamespace(
                command="rename",
                old_path="/memories/project",
                new_path="/memories/archive/project",
            )
        )
        listing = self.tool.view(
            SimpleNamespace(
                command="view",
                path="/memories/archive",
                view_range=None,
            )
        )
        deleted = self.tool.delete(
            SimpleNamespace(
                command="delete",
                path="/memories/archive/project",
            )
        )
        remaining_active = [
            memory
            for memory in self.client.memories(self.agent["agent_id"], include_inactive=False, limit=50)
            if memory["source_type"] == "anthropic_memory_file"
        ]

        self.assertEqual(inserted, "The file /memories/project/notes.md has been edited.")
        self.assertEqual(renamed, "Successfully renamed /memories/project to /memories/archive/project")
        self.assertIn("/memories/archive/project", listing)
        self.assertIn("/memories/archive/project/notes.md", listing)
        self.assertEqual(deleted, "Successfully deleted /memories/archive/project")
        self.assertEqual(remaining_active, [])

    def test_rejects_path_escape_and_duplicate_replacements(self) -> None:
        self.tool.create(
            SimpleNamespace(
                command="create",
                path="/memories/project/dup.md",
                file_text="dup\nkeep\ndup",
            )
        )

        with self.assertRaises(ValueError):
            self.tool.create(
                SimpleNamespace(
                    command="create",
                    path="/memories/../escape.md",
                    file_text="bad",
                )
            )

        duplicate = self.tool.str_replace(
            SimpleNamespace(
                command="str_replace",
                path="/memories/project/dup.md",
                old_str="dup",
                new_str="once",
            )
        )

        self.assertIn("Multiple occurrences of old_str `dup`", duplicate)


if __name__ == "__main__":
    unittest.main()
