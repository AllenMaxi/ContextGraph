from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from contextgraph_sdk import ContextGraph

if TYPE_CHECKING:
    from anthropic.types.beta import (
        BetaMemoryTool20250818CreateCommand,
        BetaMemoryTool20250818DeleteCommand,
        BetaMemoryTool20250818InsertCommand,
        BetaMemoryTool20250818RenameCommand,
        BetaMemoryTool20250818StrReplaceCommand,
        BetaMemoryTool20250818ViewCommand,
    )
else:
    BetaMemoryTool20250818CreateCommand = Any
    BetaMemoryTool20250818DeleteCommand = Any
    BetaMemoryTool20250818InsertCommand = Any
    BetaMemoryTool20250818RenameCommand = Any
    BetaMemoryTool20250818StrReplaceCommand = Any
    BetaMemoryTool20250818ViewCommand = Any

try:
    from anthropic.lib.tools import BetaAbstractMemoryTool
except ImportError:  # pragma: no cover - exercised indirectly in local tests

    class BetaAbstractMemoryTool:
        """Small fallback so the adapter stays importable without Anthropic installed."""

        def execute(self, command: Any) -> str:
            name = getattr(command, "command", "")
            handler = getattr(self, name, None)
            if not callable(handler):
                raise RuntimeError(f"Unsupported memory command '{name}'.")
            return handler(command)

        def clear_all_memory(self) -> str:
            raise RuntimeError("The Anthropic SDK is not installed.")


_MEMORY_ROOT = PurePosixPath("/memories")
_MAX_FILE_LINES = 999_999
_DEFAULT_INTEGRATION_NAME = "anthropic_memory_tool"
_DEFAULT_SOURCE_TYPE = "anthropic_memory_file"


@dataclass(slots=True)
class _MemorySnapshot:
    memory_id: str
    logical_path: str
    content: str
    revision: int
    curation_status: str


class ContextGraphAnthropicMemoryTool(BetaAbstractMemoryTool):
    """Anthropic Memory Tool adapter backed by governed ContextGraph snapshots."""

    def __init__(
        self,
        client: ContextGraph,
        agent_id: str,
        *,
        namespace: str = "default",
        default_visibility: str = "private",
        default_license: str = "internal",
        default_metadata: dict[str, str] | None = None,
        default_access_list: list[str] | None = None,
        default_price: float | None = None,
        default_expires_in_days: int | None = None,
        list_limit: int = 5000,
        integration_name: str = _DEFAULT_INTEGRATION_NAME,
    ) -> None:
        super().__init__()
        if not namespace.strip():
            raise ValueError("namespace must be a non-empty string.")
        if default_visibility not in {"private", "org", "shared", "published"}:
            raise ValueError(f"Unsupported default_visibility '{default_visibility}'.")
        if list_limit <= 0:
            raise ValueError("list_limit must be positive.")
        self.client = client
        self.agent_id = agent_id
        self.namespace = namespace.strip()
        self.default_visibility = default_visibility
        self.default_license = default_license
        self.default_metadata = dict(default_metadata or {})
        self.default_access_list = list(default_access_list or [])
        self.default_price = default_price
        self.default_expires_in_days = default_expires_in_days
        self.list_limit = list_limit
        self.integration_name = integration_name

    def view(self, command: BetaMemoryTool20250818ViewCommand) -> str:
        path = self._normalize_path(command.path)
        file_entry = self._get_exact_file(path, include_inactive=False)
        if file_entry is not None:
            return self._format_file_view(path, file_entry.content, getattr(command, "view_range", None))
        if self._path_is_directory(path):
            return self._format_directory_view(path)
        return self._missing_path_error(path)

    def create(self, command: BetaMemoryTool20250818CreateCommand) -> str:
        path = self._normalize_path(command.path, allow_root=False)
        self._ensure_path_available(path)
        self._create_snapshot(path, command.file_text)
        return f"File created successfully at: {path}"

    def str_replace(self, command: BetaMemoryTool20250818StrReplaceCommand) -> str:
        path = self._normalize_path(command.path, allow_root=False)
        entry = self._require_file(path)
        old_text = command.old_str
        new_text = command.new_str
        occurrence_count = entry.content.count(old_text)
        if occurrence_count == 0:
            return f"No replacement was performed, old_str `{old_text}` did not appear verbatim in {path}."
        if occurrence_count > 1:
            duplicate_lines = self._find_line_numbers(entry.content, old_text)
            return (
                f"No replacement was performed. Multiple occurrences of old_str `{old_text}` in lines: "
                f"{duplicate_lines}. Please ensure it is unique"
            )

        updated_content = entry.content.replace(old_text, new_text, 1)
        line_numbers = self._find_line_numbers(updated_content, new_text)
        focus_line = line_numbers[0] if line_numbers else 1
        self._create_snapshot(path, updated_content, supersedes=entry.memory_id)
        start_line = max(1, focus_line - 2)
        end_line = focus_line + 2
        snippet = self._format_file_view(path, updated_content, (start_line, end_line))
        return "The memory file has been edited.\n" + snippet

    def insert(self, command: BetaMemoryTool20250818InsertCommand) -> str:
        path = self._normalize_path(command.path, allow_root=False)
        entry = self._require_file(path)
        lines = entry.content.splitlines()
        insert_line = command.insert_line
        if insert_line < 0 or insert_line > len(lines):
            return (
                f"Error: Invalid `insert_line` parameter: {insert_line}. "
                f"It should be within the range of lines of the file: [0, {len(lines)}]"
            )
        lines.insert(insert_line, command.insert_text.rstrip("\n"))
        updated_content = "\n".join(lines)
        if entry.content.endswith("\n") or command.insert_text.endswith("\n"):
            updated_content = f"{updated_content}\n"
        self._create_snapshot(path, updated_content, supersedes=entry.memory_id)
        return f"The file {path} has been edited."

    def delete(self, command: BetaMemoryTool20250818DeleteCommand) -> str:
        path = self._normalize_path(command.path)
        if path == str(_MEMORY_ROOT):
            return "Error: Cannot delete the /memories directory itself"

        file_entry = self._get_exact_file(path, include_inactive=False)
        if file_entry is not None:
            self.client.update_memory_curation(self.agent_id, file_entry.memory_id, "archived", "anthropic_delete")
            return f"Successfully deleted {path}"

        descendants = self._list_active_descendants(path)
        if not descendants:
            return f"Error: The path {path} does not exist"
        for descendant in descendants:
            self.client.update_memory_curation(self.agent_id, descendant.memory_id, "archived", "anthropic_delete")
        return f"Successfully deleted {path}"

    def rename(self, command: BetaMemoryTool20250818RenameCommand) -> str:
        old_path = self._normalize_path(command.old_path)
        new_path = self._normalize_path(command.new_path)
        if old_path == str(_MEMORY_ROOT) or new_path == str(_MEMORY_ROOT):
            return "Error: Cannot rename the /memories directory itself"

        file_entry = self._get_exact_file(old_path, include_inactive=False)
        if file_entry is not None:
            self._ensure_path_available(new_path)
            self._create_snapshot(new_path, file_entry.content, supersedes=file_entry.memory_id)
            return f"Successfully renamed {old_path} to {new_path}"

        descendants = self._list_active_descendants(old_path)
        if not descendants:
            return f"Error: The path {old_path} does not exist"
        if new_path.startswith(f"{old_path}/"):
            return f"Error: The destination {new_path} already exists"

        rename_plan: list[tuple[_MemorySnapshot, str]] = []
        for descendant in descendants:
            suffix = descendant.logical_path[len(old_path) :]
            target_path = f"{new_path}{suffix}"
            rename_plan.append((descendant, target_path))

        occupied_targets = {entry.logical_path for entry in self._list_namespace_snapshots(include_inactive=False)}
        source_paths = {entry.logical_path for entry, _ in rename_plan}
        for _, target_path in rename_plan:
            if target_path in occupied_targets and target_path not in source_paths:
                return f"Error: The destination {target_path} already exists"

        for snapshot, target_path in rename_plan:
            self._ensure_path_available(target_path, ignore_paths=source_paths)
            self._create_snapshot(target_path, snapshot.content, supersedes=snapshot.memory_id)
        return f"Successfully renamed {old_path} to {new_path}"

    def clear_all_memory(self) -> str:
        active_snapshots = self._list_namespace_snapshots(include_inactive=False)
        for snapshot in active_snapshots:
            self.client.update_memory_curation(self.agent_id, snapshot.memory_id, "archived", "anthropic_clear_all")
        return f"Archived {len(active_snapshots)} memory file(s) in namespace '{self.namespace}'."

    def _normalize_path(self, path: str, *, allow_root: bool = True) -> str:
        candidate = PurePosixPath(path)
        if not path.startswith("/memories"):
            raise ValueError(f"Path must start with /memories, got: {path}")
        if not candidate.is_absolute():
            raise ValueError(f"Path must be absolute, got: {path}")
        if len(candidate.parts) < 2 or candidate.parts[1] != "memories":
            raise ValueError(f"Path must remain inside /memories, got: {path}")
        if any(part == ".." for part in candidate.parts):
            raise ValueError(f"Path {path} would escape /memories directory")
        normalized = str(candidate)
        if not allow_root and normalized == str(_MEMORY_ROOT):
            raise ValueError("Path must reference a file inside /memories.")
        return normalized

    def _path_is_directory(self, path: str) -> bool:
        if path == str(_MEMORY_ROOT):
            return True
        return bool(self._list_active_descendants(path))

    def _list_namespace_snapshots(self, *, include_inactive: bool) -> list[_MemorySnapshot]:
        memories = self.client.memories(
            self.agent_id,
            include_inactive=include_inactive,
            limit=self.list_limit,
        )
        snapshots: list[_MemorySnapshot] = []
        for memory in memories:
            if memory.get("source_type") != _DEFAULT_SOURCE_TYPE:
                continue
            ingest_metadata = memory.get("ingest_metadata") or {}
            if ingest_metadata.get("integration") != self.integration_name:
                continue
            if ingest_metadata.get("namespace") != self.namespace:
                continue
            logical_path = ingest_metadata.get("logical_path")
            if not logical_path:
                continue
            snapshots.append(
                _MemorySnapshot(
                    memory_id=memory["memory_id"],
                    logical_path=logical_path,
                    content=memory.get("content", ""),
                    revision=self._parse_revision(ingest_metadata.get("revision")),
                    curation_status=memory.get("curation_status", "active"),
                )
            )
        snapshots.sort(key=lambda item: (item.logical_path, item.revision, item.memory_id))
        return snapshots

    def _get_exact_file(self, path: str, *, include_inactive: bool) -> _MemorySnapshot | None:
        matches = [
            snapshot
            for snapshot in self._list_namespace_snapshots(include_inactive=include_inactive)
            if snapshot.logical_path == path
        ]
        if not matches:
            return None
        active_matches = [snapshot for snapshot in matches if snapshot.curation_status == "active"]
        candidates = active_matches or matches
        if len(candidates) > 1:
            raise RuntimeError(f"Multiple ContextGraph memory snapshots are mapped to {path}.")
        return candidates[0]

    def _require_file(self, path: str) -> _MemorySnapshot:
        entry = self._get_exact_file(path, include_inactive=False)
        if entry is None:
            raise RuntimeError(f"Error: The path {path} does not exist. Please provide a valid path.")
        return entry

    def _list_active_descendants(self, path: str) -> list[_MemorySnapshot]:
        prefix = f"{path}/"
        return [
            snapshot
            for snapshot in self._list_namespace_snapshots(include_inactive=False)
            if snapshot.logical_path.startswith(prefix)
        ]

    def _ensure_path_available(self, path: str, *, ignore_paths: set[str] | None = None) -> None:
        ignore_paths = ignore_paths or set()
        active_snapshots = self._list_namespace_snapshots(include_inactive=False)
        for snapshot in active_snapshots:
            if snapshot.logical_path in ignore_paths:
                continue
            if snapshot.logical_path == path:
                raise RuntimeError(f"Error: File {path} already exists")
            if snapshot.logical_path.startswith(f"{path}/") or path.startswith(f"{snapshot.logical_path}/"):
                raise RuntimeError(f"Error: File {path} already exists")

    def _create_snapshot(self, path: str, content: str, *, supersedes: str | None = None) -> dict[str, Any]:
        revision = self._next_revision(path)
        result = self.client.store(
            agent_id=self.agent_id,
            content=content,
            visibility=self.default_visibility,
            license=self.default_license,
            metadata=self.default_metadata,
            source_type=_DEFAULT_SOURCE_TYPE,
            source_uri=f"claude-memory://{self.namespace}{path}",
            source_label=PurePosixPath(path).name,
            ingest_metadata=self._build_ingest_metadata(path, revision, supersedes),
            access_list=self.default_access_list or None,
            price=self.default_price,
            expires_in_days=self.default_expires_in_days,
        )
        if supersedes is not None:
            try:
                self.client.update_memory_curation(self.agent_id, supersedes, "archived", f"superseded_by:{path}")
            except Exception:
                self.client.update_memory_curation(
                    self.agent_id,
                    result["memory"]["memory_id"],
                    "archived",
                    f"rollback_failed_supersede:{supersedes}",
                )
                raise
        return result

    def _build_ingest_metadata(self, path: str, revision: int, supersedes: str | None) -> dict[str, str]:
        ingest_metadata = {
            "integration": self.integration_name,
            "namespace": self.namespace,
            "logical_path": path,
            "revision": str(revision),
            "current": "true",
        }
        if supersedes:
            ingest_metadata["supersedes_memory_id"] = supersedes
        return ingest_metadata

    def _next_revision(self, path: str) -> int:
        revisions = [
            snapshot.revision
            for snapshot in self._list_namespace_snapshots(include_inactive=True)
            if snapshot.logical_path == path
        ]
        return max(revisions, default=0) + 1

    def _format_directory_view(self, path: str) -> str:
        files = self._list_namespace_snapshots(include_inactive=False)
        entries = self._build_directory_entries(path, files)
        lines = [
            f"Here're the files and directories up to 2 levels deep in {path}, excluding hidden items and node_modules:"
        ]
        lines.extend(f"{size}\t{entry_path}" for entry_path, size in entries)
        return "\n".join(lines)

    def _build_directory_entries(
        self,
        path: str,
        files: list[_MemorySnapshot],
    ) -> list[tuple[str, str]]:
        base = PurePosixPath(path)
        size_map: dict[str, int] = {path: 0}
        kind_map: dict[str, str] = {path: "dir"}

        for snapshot in files:
            file_path = PurePosixPath(snapshot.logical_path)
            if file_path == base or not str(file_path).startswith(f"{path}/"):
                continue
            relative_parts = file_path.relative_to(base).parts
            if any(part.startswith(".") or part == "node_modules" for part in relative_parts):
                continue
            file_size = len(snapshot.content.encode("utf-8"))
            size_map[path] += file_size
            for depth in range(1, min(len(relative_parts), 2) + 1):
                entry_path = str(base.joinpath(*relative_parts[:depth]))
                is_dir = depth < len(relative_parts)
                kind_map[entry_path] = "dir" if is_dir else "file"
                if is_dir:
                    size_map[entry_path] = size_map.get(entry_path, 0) + file_size
                else:
                    size_map[entry_path] = file_size

        entries = sorted(size_map.items(), key=lambda item: item[0])
        return [(entry_path, self._human_size(size_bytes)) for entry_path, size_bytes in entries]

    def _format_file_view(
        self,
        path: str,
        content: str,
        view_range: tuple[int, int] | list[int] | None,
    ) -> str:
        lines = content.splitlines()
        if len(lines) > _MAX_FILE_LINES:
            raise RuntimeError(f"File {path} exceeds maximum line limit of {_MAX_FILE_LINES:,} lines.")
        start_line = 1
        end_line = len(lines)
        if view_range:
            start_line = max(1, int(view_range[0]))
            end_candidate = int(view_range[1])
            end_line = len(lines) if end_candidate == -1 else end_candidate
        visible_lines = lines[start_line - 1 : end_line]
        numbered = [f"{line_number:>6}\t{line}" for line_number, line in enumerate(visible_lines, start=start_line)]
        if not numbered:
            numbered = [f"{start_line:>6}\t"]
        return f"Here's the content of {path} with line numbers:\n" + "\n".join(numbered)

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes}B"
        size = float(size_bytes)
        for unit in ("K", "M", "G", "T"):
            size /= 1024.0
            if size < 1024.0 or unit == "T":
                return f"{size:.1f}{unit}"
        return f"{size_bytes}B"

    @staticmethod
    def _parse_revision(value: str | None) -> int:
        try:
            return int(value or "0")
        except ValueError:
            return 0

    @staticmethod
    def _find_line_numbers(content: str, needle: str) -> list[int]:
        if not needle:
            return []
        line_numbers: list[int] = []
        for index, line in enumerate(content.splitlines(), start=1):
            if needle in line:
                line_numbers.append(index)
        return line_numbers

    @staticmethod
    def _missing_path_error(path: str) -> str:
        return f"The path {path} does not exist. Please provide a valid path."


__all__ = ["ContextGraphAnthropicMemoryTool"]
