from __future__ import annotations

import argparse
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from contextgraph_sdk import ContextGraph, MemoryDirectoryError

import contextgraph.cli as cli
from contextgraph import ContextGraphService
from contextgraph.config import Settings


def _make_service() -> ContextGraphService:
    return ContextGraphService(app_settings=Settings(repository_backend="memory", sentinel_enabled=False))


class MemoryDirectorySDKTest(unittest.TestCase):
    def test_sync_memory_directory_writes_skeleton_files_without_checkpoint(self) -> None:
        service = _make_service()
        try:
            client = ContextGraph.local(service)
            agent = client.register_agent("memdir-coder", "acme", ["coding"])
            with TemporaryDirectory() as workspace:
                session = client.create_session(
                    agent["agent_id"],
                    title="Memdir skeleton",
                    source="codex",
                    metadata={"workspace": workspace},
                )

                result = client.sync_memory_directory(agent["agent_id"], session["session_id"])

                memory_dir = Path(result["directory_path"])
                session_payload = json.loads((memory_dir / "session.json").read_text())
                self.assertEqual(session_payload["session_id"], session["session_id"])
                self.assertEqual(session_payload["latest_checkpoint_id"], "")
                self.assertEqual(result["checkpoint_id"], "")
                self.assertIsNone(json.loads((memory_dir / "latest_delta_pack.json").read_text()))
                self.assertIn("_No active items._", (memory_dir / "open_tasks.md").read_text())
                self.assertEqual(len(result["files_written"]), 11)
        finally:
            service.close()

    def test_sync_memory_directory_writes_branch_cache_metadata(self) -> None:
        service = _make_service()
        try:
            client = ContextGraph.local(service)
            agent = client.register_agent("memdir-brancher", "acme", ["coding"])
            with TemporaryDirectory() as workspace:
                root = client.create_session(
                    agent["agent_id"],
                    title="Branch root",
                    source="claude-code",
                    metadata={"workspace": workspace},
                )
                client.record_session_event(agent["agent_id"], root["session_id"], "todo", "Add migration tests.")
                base = client.checkpoint_session(agent["agent_id"], root["session_id"])
                branch = client.fork_session(agent["agent_id"], root["session_id"], title="grpc-branch")
                client.record_session_event(
                    agent["agent_id"],
                    branch["session_id"],
                    "file_change",
                    "Updated contextgraph/service.py",
                    metadata={"path": "contextgraph/service.py"},
                )
                client.checkpoint_session(agent["agent_id"], branch["session_id"])

                result = client.sync_memory_directory(agent["agent_id"], branch["session_id"])

                memory_dir = Path(result["directory_path"])
                session_payload = json.loads((memory_dir / "session.json").read_text())
                delta_payload = json.loads((memory_dir / "latest_delta_pack.json").read_text())
                self.assertEqual(session_payload["session_id"], branch["session_id"])
                self.assertEqual(session_payload["parent_session_id"], root["session_id"])
                self.assertEqual(session_payload["cache_status"], "prefix_hit")
                self.assertEqual(session_payload["cache_base_checkpoint_id"], base["checkpoint_id"])
                self.assertEqual(delta_payload["cache_status"], "prefix_hit")
                self.assertNotIn("state_snapshot", delta_payload)
                self.assertIn("Add migration tests.", (memory_dir / "open_tasks.md").read_text())
                self.assertIn("contextgraph/service.py", (memory_dir / "changed_files.md").read_text())
        finally:
            service.close()

    def test_sync_memory_directory_requires_workspace(self) -> None:
        service = _make_service()
        try:
            client = ContextGraph.local(service)
            agent = client.register_agent("memdir-noworkspace", "acme", ["coding"])
            session = client.create_session(agent["agent_id"], title="No workspace", source="codex")

            with self.assertRaises(MemoryDirectoryError):
                client.sync_memory_directory(agent["agent_id"], session["session_id"])
        finally:
            service.close()


class MemoryDirectoryCLITest(unittest.TestCase):
    def test_cli_acceptance_flow_syncs_repo_local_memory_directory(self) -> None:
        service = _make_service()
        try:
            client = ContextGraph.local(service)
            agent = client.register_agent("cli-memdir", "acme", ["coding"])
            with TemporaryDirectory() as workspace, TemporaryDirectory() as config_home:
                config_dir = Path(config_home)
                config_file = config_dir / "config.json"
                with (
                    patch.object(cli, "CONFIG_DIR", config_dir),
                    patch.object(cli, "CONFIG_FILE", config_file),
                    redirect_stdout(StringIO()),
                    redirect_stderr(StringIO()),
                ):
                    cli._save_config({"agent_id": agent["agent_id"]})
                    cli.cmd_session_start(
                        argparse.Namespace(
                            title="CLI session",
                            source="codex",
                            workspace=workspace,
                            activate=True,
                            json=False,
                        ),
                        client,
                    )
                    root_session_id = cli._load_config()["session_id"]
                    client.record_session_event(agent["agent_id"], root_session_id, "todo", "Add migration tests.")
                    cli.cmd_checkpoint(
                        argparse.Namespace(
                            session=root_session_id,
                            reason="manual",
                            token_budget=600,
                            json=False,
                        ),
                        client,
                    )
                    cli.cmd_session_fork(
                        argparse.Namespace(
                            session=root_session_id,
                            from_checkpoint=None,
                            title="CLI branch",
                            activate=True,
                            json=False,
                        ),
                        client,
                    )
                    branch_session_id = cli._load_config()["session_id"]
                    client.record_session_event(
                        agent["agent_id"],
                        branch_session_id,
                        "file_change",
                        "Updated contextgraph/service.py",
                        metadata={"path": "contextgraph/service.py"},
                    )
                    cli.cmd_checkpoint(
                        argparse.Namespace(
                            session=branch_session_id,
                            reason="manual",
                            token_budget=600,
                            json=False,
                        ),
                        client,
                    )
                    cli.cmd_memdir_sync(
                        argparse.Namespace(
                            session=branch_session_id,
                            workspace=None,
                            json=False,
                        ),
                        client,
                    )

                memory_dir = Path(workspace) / ".contextgraph"
                session_payload = json.loads((memory_dir / "session.json").read_text())
                self.assertEqual(session_payload["session_id"], branch_session_id)
                self.assertEqual(session_payload["cache_status"], "prefix_hit")
                self.assertIn("Add migration tests.", (memory_dir / "open_tasks.md").read_text())
                self.assertIn("contextgraph/service.py", (memory_dir / "changed_files.md").read_text())
        finally:
            service.close()
