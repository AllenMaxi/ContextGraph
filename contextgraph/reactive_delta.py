from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from .models import DeltaPack, DeltaPackDiff, SessionEvent
from .utils import jaccard_similarity, utcnow

SESSION_BUCKETS = (
    "decisions",
    "constraints",
    "open_tasks",
    "failures",
    "resolved_items",
    "important_artifacts",
    "external_references",
    "changed_files",
    "commands",
    "notes",
)

_URL_PATTERN = re.compile(r"https?://[^\s)>]+")
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*+]|\d+\.)\s*")


def _normalize_item(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _split_text_items(content: str) -> list[str]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if len(lines) <= 1:
        single = content.strip()
        return [single] if single else []
    cleaned = [_BULLET_PREFIX.sub("", line).strip() for line in lines]
    return [line for line in cleaned if line]


def _split_metadata_items(raw: str) -> list[str]:
    value = raw.strip()
    if not value:
        return []
    if "\n" in value:
        return _split_text_items(value)
    if "," in value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def _iter_urls(content: str, metadata: dict[str, str]) -> list[str]:
    found = list(_URL_PATTERN.findall(content))
    for key, value in metadata.items():
        if key.lower() in {"url", "uri", "source_uri", "reference_url"} and value.strip():
            found.append(value.strip())
    return [item for item in dict.fromkeys(found) if item]


def _iter_paths(metadata: dict[str, str], content: str) -> list[str]:
    values: list[str] = []
    for key, value in metadata.items():
        if key.lower() in {"path", "file", "files", "changed_file", "changed_files"} and value.strip():
            values.extend(_split_metadata_items(value))
    if not values and ("/" in content or "." in content):
        values.extend(_split_text_items(content))
    return [item for item in dict.fromkeys(values) if item]


def _add_state_item(
    state: dict[str, dict[str, tuple[str, datetime]]],
    bucket: str,
    item: str,
    timestamp: datetime,
) -> None:
    cleaned = item.strip()
    if not cleaned:
        return
    norm = _normalize_item(cleaned)
    if not norm:
        return
    state[bucket][norm] = (cleaned, timestamp)


def _remove_matching_items(
    state: dict[str, dict[str, tuple[str, datetime]]],
    buckets: tuple[str, ...],
    item: str,
) -> list[str]:
    removed: list[str] = []
    target = _normalize_item(item)
    if not target:
        return removed
    for bucket in buckets:
        entries = list(state[bucket].items())
        for norm, (existing, _timestamp) in entries:
            similarity = jaccard_similarity(target, norm)
            if similarity >= 0.72 or target in norm or norm in target:
                removed.append(existing)
                state[bucket].pop(norm, None)
    return removed


def _event_items(event: SessionEvent) -> list[str]:
    metadata = dict(event.metadata or {})
    for key in ("item", "items", "decision", "constraint", "task", "artifact", "command", "note"):
        raw = metadata.get(key, "")
        if raw.strip():
            return _split_metadata_items(raw)
    return _split_text_items(event.content)


def reduce_session_events(
    events: list[SessionEvent],
    *,
    stale_after: timedelta = timedelta(days=7),
) -> dict[str, Any]:
    ordered = sorted(events, key=lambda event: (event.sequence, event.created_at.isoformat(), event.event_id))
    state: dict[str, dict[str, tuple[str, datetime]]] = {bucket: {} for bucket in SESSION_BUCKETS}
    untrusted_map: dict[str, str] = {}
    latest_timestamp = max(ordered[-1].created_at, utcnow()) if ordered else utcnow()

    for event in ordered:
        event_type = event.event_type.strip().lower() or "note"
        metadata = dict(event.metadata or {})
        items = _event_items(event)
        confidence = metadata.get("confidence", "").strip()
        trusted = metadata.get("trusted", "").strip().lower()
        try:
            confidence_value = float(confidence) if confidence else None
        except ValueError:
            confidence_value = None
        is_untrusted = trusted in {"false", "0", "no"} or (confidence_value is not None and confidence_value < 0.6)

        for item in items:
            if is_untrusted:
                untrusted_map[_normalize_item(item)] = item

        if event_type in {"decision", "decisions"}:
            for item in items:
                _add_state_item(state, "decisions", item, event.created_at)
        elif event_type in {"constraint", "constraints", "instruction", "instructions"}:
            for item in items:
                _add_state_item(state, "constraints", item, event.created_at)
        elif event_type in {"todo", "task", "open_task", "plan_item", "plan_change"}:
            for item in items:
                _add_state_item(state, "open_tasks", item, event.created_at)
        elif event_type in {"failure", "blocker", "error"}:
            for item in items:
                _add_state_item(state, "failures", item, event.created_at)
        elif event_type in {"resolved", "resolution", "fix", "done"}:
            for item in items:
                _add_state_item(state, "resolved_items", item, event.created_at)
                _remove_matching_items(state, ("open_tasks", "failures", "notes"), item)
        elif event_type in {"artifact", "reference", "memory_hit", "document"}:
            artifact_items = items or [event.content.strip()]
            for item in artifact_items:
                _add_state_item(state, "important_artifacts", item, event.created_at)
            for url in _iter_urls(event.content, metadata):
                _add_state_item(state, "external_references", url, event.created_at)
        elif event_type in {"file_change", "file_edit", "diff", "path"}:
            for path in _iter_paths(metadata, event.content):
                _add_state_item(state, "changed_files", path, event.created_at)
                _add_state_item(state, "important_artifacts", path, event.created_at)
        elif event_type in {"command", "tool", "bash"}:
            command_items = items or _split_metadata_items(metadata.get("command", ""))
            for item in command_items:
                _add_state_item(state, "commands", item, event.created_at)
            exit_code = metadata.get("exit_code", "").strip()
            if exit_code and exit_code != "0":
                failure_text = (
                    metadata.get("error", "").strip()
                    or f"Command failed: {command_items[0] if command_items else event.content.strip()}"
                )
                _add_state_item(state, "failures", failure_text, event.created_at)
        elif event_type in {"context_pressure", "compact", "checkpoint"}:
            note = event.content.strip() or metadata.get("reason", "").strip()
            if note:
                _add_state_item(state, "notes", note, event.created_at)
        else:
            for item in items:
                _add_state_item(state, "notes", item, event.created_at)

        for url in _iter_urls(event.content, metadata):
            _add_state_item(state, "external_references", url, event.created_at)

    sections: dict[str, list[str]] = {}
    stale_items: list[str] = []
    for bucket in SESSION_BUCKETS:
        items = [entry[0] for entry in state[bucket].values()]
        sections[bucket] = items
        if bucket not in {"open_tasks", "failures", "notes"}:
            continue
        for item, timestamp in state[bucket].values():
            if latest_timestamp - timestamp >= stale_after:
                stale_items.append(item)

    sections["stale_items"] = list(dict.fromkeys(stale_items))
    sections["untrusted_items"] = list(untrusted_map.values())
    sections["included_event_ids"] = [event.event_id for event in ordered]
    sections["event_count"] = len(ordered)
    return sections


def delta_pack_sections(pack: DeltaPack | None) -> dict[str, list[str]]:
    if pack is None:
        return {bucket: [] for bucket in SESSION_BUCKETS}
    return {
        "decisions": list(pack.decisions),
        "constraints": list(pack.constraints),
        "open_tasks": list(pack.open_tasks),
        "failures": list(pack.failures),
        "resolved_items": list(pack.resolved_items),
        "important_artifacts": list(pack.important_artifacts),
        "external_references": list(pack.external_references),
        "changed_files": list(pack.changed_files),
        "commands": list(pack.commands),
        "notes": list(pack.notes),
    }


def compute_delta_pack_diff(previous: DeltaPack | None, current_sections: dict[str, list[str]]) -> DeltaPackDiff:
    previous_sections = delta_pack_sections(previous)
    added: dict[str, list[str]] = {}
    dropped: dict[str, list[str]] = {}

    for bucket in SESSION_BUCKETS:
        previous_items = previous_sections.get(bucket, [])
        current_items = current_sections.get(bucket, [])
        previous_norm = {_normalize_item(item): item for item in previous_items}
        current_norm = {_normalize_item(item): item for item in current_items}

        bucket_added = [item for norm, item in current_norm.items() if norm not in previous_norm]
        bucket_dropped = [item for norm, item in previous_norm.items() if norm not in current_norm]
        if bucket_added:
            added[bucket] = bucket_added
        if bucket_dropped:
            dropped[bucket] = bucket_dropped

    return DeltaPackDiff(added=added, dropped=dropped)


def flatten_diff_items(diff: DeltaPackDiff) -> list[str]:
    items: list[str] = []
    for bucket_items in diff.dropped.values():
        items.extend(bucket_items)
    return list(dict.fromkeys(item for item in items if item))


def default_restoration_instructions(sections: dict[str, list[str]]) -> list[str]:
    instructions: list[str] = []
    if sections.get("decisions"):
        instructions.append("Re-establish the confirmed decisions before making new changes.")
    if sections.get("constraints"):
        instructions.append("Honor the active constraints and project rules during the next steps.")
    if sections.get("open_tasks"):
        instructions.append("Resume from the open tasks and keep resolved items closed unless new evidence appears.")
    if sections.get("failures"):
        instructions.append("Address outstanding failures and blockers before broadening scope.")
    if sections.get("changed_files"):
        instructions.append("Inspect the changed files first to restore codebase state quickly.")
    if sections.get("external_references"):
        instructions.append("Use the referenced external material as source of truth when needed.")
    if not instructions:
        instructions.append("Resume from the latest session notes and continue cautiously.")
    return instructions


def build_restoration_prompt(
    *,
    title: str,
    source: str,
    summary: str,
    sections: dict[str, list[str]],
    instructions: list[str],
) -> str:
    lines = [
        "Resume the coding session with the structured checkpoint below.",
        f"Session: {title or 'Untitled session'}",
        f"Source: {source or 'generic'}",
    ]
    if summary:
        lines.extend(["", "Summary:", summary])
    for bucket in ("decisions", "constraints", "open_tasks", "failures", "changed_files", "important_artifacts"):
        items = sections.get(bucket, [])
        if not items:
            continue
        label = bucket.replace("_", " ").title()
        lines.append("")
        lines.append(f"{label}:")
        lines.extend(f"- {item}" for item in items)
    if instructions:
        lines.append("")
        lines.append("Restoration instructions:")
        lines.extend(f"- {item}" for item in instructions)
    return "\n".join(lines).strip()
