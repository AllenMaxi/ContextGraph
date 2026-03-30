# Anthropic Memory Tool Adapter

ContextGraph can act as the backend for Anthropic's **Claude API Memory tool**.

This integration targets the **client-side Memory tool** described in the Claude API docs. It does **not** plug into:

- Claude app chat search or consumer memory
- Claude Code's local auto-memory files

## What It Adds

- `ContextGraphAnthropicMemoryTool` in [`contextgraph/anthropic_memory.py`](../contextgraph/anthropic_memory.py)
- optional install extra: `contextgraph[anthropic]`
- versioned memory snapshots stored in ContextGraph with governed provenance fields
- SDK memory helpers for listing, fetching, and curating memories without private internals

## Install

```bash
pip install -e ".[anthropic]"
pip install -e ./sdk
```

If you only need the public HTTP client, install the SDK separately and point it at a running ContextGraph server.

## Snapshot Model

Each Anthropic memory file under `/memories/...` is stored as a ContextGraph memory with:

- `source_type="anthropic_memory_file"`
- `source_uri="claude-memory://<namespace><path>"`
- `source_label=<basename>`
- `ingest_metadata` keys for:
  - `integration`
  - `namespace`
  - `logical_path`
  - `revision`
  - `current`
  - optional `supersedes_memory_id`

Edits create a new snapshot revision and archive the previous active snapshot.

## Important Behavior

- Default visibility is `private`
- Deletes are **archival**, not hard deletion
- The adapter only operates inside `/memories`
- Directory views follow Anthropic's documented formatting for the Memory tool

## Public APIs Used

The adapter relies only on public ContextGraph surfaces:

- `store(...)`
- `memories(...)`
- `memory(...)`
- `update_memory_curation(...)`

That keeps the Anthropic adapter usable with both `ContextGraph.local()` and `ContextGraph.http(...)`.

## Example

See [`examples/anthropic_memory_tool.py`](../examples/anthropic_memory_tool.py) for an end-to-end example using Anthropic's `tool_runner` with a ContextGraph-backed memory tool.

## Non-Goals For v1

- Claude consumer app memory integration
- Claude Code auto-memory replacement
- TypeScript adapter
