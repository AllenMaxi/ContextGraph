from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from contextgraph_sdk import ContextGraph

STATE_DIR = Path.home() / ".contextgraph" / "hook_sessions"


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _workspace_key(tool_name: str, workspace: str) -> str:
    raw = f"{tool_name}:{workspace}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _state_path(tool_name: str, workspace: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"{_workspace_key(tool_name, workspace)}.json"


def build_client() -> ContextGraph:
    server_url = _required_env("CG_SERVER_URL")
    api_key = _required_env("CG_AGENT_KEY")
    return ContextGraph.http(server_url, api_key=api_key)


def read_hook_payload() -> dict[str, Any]:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def ensure_session(client: ContextGraph, *, agent_id: str, tool_name: str, workspace: str) -> str:
    path = _state_path(tool_name, workspace)
    if path.exists():
        payload = json.loads(path.read_text())
        session_id = str(payload.get("session_id", "")).strip()
        if session_id:
            return session_id

    session = client.create_session(
        agent_id=agent_id,
        title=f"{Path(workspace).name or 'workspace'} ({tool_name})",
        source=tool_name,
        metadata={"workspace": workspace},
    )
    path.write_text(json.dumps({"session_id": session["session_id"]}, indent=2) + "\n")
    return session["session_id"]


def emit_hook_event(
    *,
    tool_name: str,
    event_type: str,
    content: str,
    metadata: dict[str, str] | None = None,
    auto_checkpoint: bool = False,
    checkpoint_reason: str | None = None,
) -> dict[str, Any]:
    client = build_client()
    agent_id = _required_env("CG_AGENT_ID")
    workspace = os.environ.get("CG_WORKSPACE", os.getcwd())
    session_id = ensure_session(client, agent_id=agent_id, tool_name=tool_name, workspace=workspace)
    token_budget = int(os.environ.get("CG_DELTA_TOKEN_BUDGET", "1600"))
    result = client.record_session_event(
        agent_id=agent_id,
        session_id=session_id,
        event_type=event_type,
        content=content,
        metadata=metadata or {},
        auto_checkpoint=auto_checkpoint,
        token_budget=token_budget,
        checkpoint_reason=checkpoint_reason,
    )
    return {"session_id": session_id, **result}
