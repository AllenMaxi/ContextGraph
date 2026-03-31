from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exceptions import MemoryDirectoryError

_INTERNAL_DELTA_PACK_FIELDS = {"state_snapshot", "state_snapshot_version", "state_snapshot_event_count"}
_EMPTY_PLACEHOLDER = "_No active items._"

_MARKDOWN_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("decisions.md", "Decisions", "decisions"),
    ("constraints.md", "Constraints", "constraints"),
    ("open_tasks.md", "Open Tasks", "open_tasks"),
    ("failures.md", "Failures", "failures"),
    ("changed_files.md", "Changed Files", "changed_files"),
    ("important_artifacts.md", "Important Artifacts", "important_artifacts"),
)


def strip_internal_delta_pack_fields(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if key in _INTERNAL_DELTA_PACK_FIELDS:
                continue
            cleaned[key] = strip_internal_delta_pack_fields(item)
        return cleaned
    if isinstance(value, list):
        return [strip_internal_delta_pack_fields(item) for item in value]
    return value


def sync_memory_directory(
    client: Any,
    *,
    agent_id: str,
    session_id: str,
    workspace_path: str | None = None,
    include_doctor: bool = True,
) -> dict[str, Any]:
    session = client.session(agent_id, session_id)
    workspace_root = _resolve_workspace_path(workspace_path, session)
    memory_dir = workspace_root / ".contextgraph"
    resume = client.resume_session(agent_id, session_id)
    session_payload = dict(resume.get("session") or session)
    checkpoint = dict(resume.get("checkpoint") or {})
    pack = strip_internal_delta_pack_fields(resume.get("delta_pack"))
    doctor = client.doctor_memory(agent_id, session_id) if include_doctor else None

    memory_dir.mkdir(parents=True, exist_ok=True)
    files_written: list[str] = []

    latest_checkpoint_id = str(session_payload.get("latest_checkpoint_id") or checkpoint.get("checkpoint_id") or "")
    latest_delta_pack_id = str(session_payload.get("latest_delta_pack_id") or _pack_value(pack, "delta_pack_id") or "")
    session_document = {
        "session_id": str(session_payload.get("session_id", session_id)),
        "title": str(session_payload.get("title", "")),
        "source": str(session_payload.get("source", "")),
        "updated_at": str(session_payload.get("updated_at", "")),
        "parent_session_id": str(session_payload.get("parent_session_id", "")),
        "forked_from_checkpoint_id": str(session_payload.get("forked_from_checkpoint_id", "")),
        "latest_checkpoint_id": latest_checkpoint_id,
        "latest_delta_pack_id": latest_delta_pack_id,
        "checkpoint_count": int(session_payload.get("checkpoint_count", 0) or 0),
        "event_count": int(session_payload.get("event_count", 0) or 0),
        "cache_status": str(_pack_value(pack, "cache_status") or ""),
        "cache_base_checkpoint_id": str(_pack_value(pack, "cache_base_checkpoint_id") or ""),
        "reused_event_count": int(_pack_value(pack, "reused_event_count") or 0),
        "recomputed_event_count": int(_pack_value(pack, "recomputed_event_count") or 0),
        "invalidated_reasons": list(_pack_value(pack, "invalidated_reasons") or []),
    }

    _write_json(memory_dir / "session.json", session_document, files_written)
    _write_json(memory_dir / "latest_delta_pack.json", pack, files_written)
    _write_json(memory_dir / "doctor.json", doctor, files_written)

    restoration_prompt = str(_pack_value(pack, "restoration_prompt") or "").strip()
    _write_text(
        memory_dir / "resume_prompt.md",
        f"{restoration_prompt}\n" if restoration_prompt else f"{_EMPTY_PLACEHOLDER}\n",
        files_written,
    )
    _write_text(
        memory_dir / "restoration_instructions.md",
        _render_markdown_list(
            "Restoration Instructions",
            _coerce_string_list(_pack_value(pack, "restoration_instructions")),
        ),
        files_written,
    )
    for filename, title, key in _MARKDOWN_SECTIONS:
        _write_text(
            memory_dir / filename,
            _render_markdown_list(title, _coerce_string_list(_pack_value(pack, key))),
            files_written,
        )

    return {
        "directory_path": str(memory_dir),
        "session_id": session_document["session_id"],
        "checkpoint_id": latest_checkpoint_id,
        "cache_status": session_document["cache_status"],
        "files_written": files_written,
    }


def _resolve_workspace_path(workspace_path: str | None, session: dict[str, Any]) -> Path:
    workspace_hint = (workspace_path or session.get("metadata", {}).get("workspace") or "").strip()
    if not workspace_hint:
        raise MemoryDirectoryError(
            "Cannot sync .contextgraph: no workspace path was provided and session.metadata['workspace'] is empty."
        )
    workspace_root = Path(workspace_hint).expanduser()
    if not workspace_root.is_absolute():
        workspace_root = (Path.cwd() / workspace_root).resolve()
    else:
        workspace_root = workspace_root.resolve()
    if not workspace_root.exists():
        raise MemoryDirectoryError(f"Cannot sync .contextgraph: workspace does not exist: {workspace_root}")
    if not workspace_root.is_dir():
        raise MemoryDirectoryError(f"Cannot sync .contextgraph: workspace is not a directory: {workspace_root}")
    return workspace_root


def _render_markdown_list(title: str, items: list[str]) -> str:
    lines = [f"# {title}", ""]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append(_EMPTY_PLACEHOLDER)
    return "\n".join(lines).rstrip() + "\n"


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _pack_value(pack: Any, key: str) -> Any:
    if isinstance(pack, dict):
        return pack.get(key)
    return None


def _write_json(path: Path, payload: Any, files_written: list[str]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    files_written.append(str(path))


def _write_text(path: Path, content: str, files_written: list[str]) -> None:
    path.write_text(content)
    files_written.append(str(path))
