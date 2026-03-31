# Reactive Delta Compaction

Reactive Delta Compaction turns ContextGraph into a session-continuity backend for coding agents.

Instead of storing a giant chat summary after compaction, ContextGraph records **structured session events** and compiles them into deterministic **delta packs** with:

- decisions
- constraints
- open tasks
- failures
- resolved items
- important artifacts
- changed files
- restoration prompts and instructions
- cache metadata for prefix reuse and fallback recomputation
- a repo-local `.contextgraph/` directory for human-visible working state

The goal is to survive repeated compactions and resumes without paying LLM costs on every checkpoint.

Branch-aware context cache builds on top of that:

- fork a session from a checkpoint
- inherit the checkpoint's canonical reduced state snapshot
- recompute only the new events on the branch
- fall back to full lineage recomputation if the inherited snapshot is missing, corrupt, or outdated

## Core API

Create a session:

```bash
POST /v1/sessions
```

Record an event:

```bash
POST /v1/sessions/{session_id}/events
```

Create a checkpoint:

```bash
POST /v1/sessions/{session_id}/checkpoint
```

Fork a branch-backed session:

```bash
POST /v1/sessions/{session_id}/fork
```

Resume from the latest checkpoint:

```bash
GET /v1/sessions/{session_id}/resume
```

Inspect context drift:

```bash
GET /v1/sessions/{session_id}/diff
```

Run the memory doctor:

```bash
GET /v1/sessions/{session_id}/doctor
```

Sync the repo-local memory directory through the SDK or CLI. No extra HTTP endpoint is needed because `.contextgraph/` is intentionally a client-side workspace artifact.

## Branch-Aware Cache Metadata

Every delta pack now exposes branch/cache metadata:

- `cache_status`: `miss`, `prefix_hit`, or `fallback_recompute`
- `cache_base_checkpoint_id`: inherited checkpoint reused by the branch, if any
- `reused_event_count`: how many events came from the inherited prefix snapshot
- `recomputed_event_count`: how many events were reduced for this checkpoint call
- `invalidated_reasons`: why ContextGraph had to ignore a snapshot and recompute

These fields are public. The underlying canonical snapshot is persisted internally and is not returned by the public HTTP or SDK responses.

## Event Types

The deterministic reducer understands these event types out of the box:

- `decision`
- `constraint`
- `todo`
- `failure`
- `resolved`
- `artifact`
- `reference`
- `file_change`
- `command`
- `plan_change`
- `context_pressure`
- `note`

Unknown event types fall back to `note`.

## Generic JSON Hook Protocol

Hook adapters can post a payload like:

```json
{
  "event_type": "context_pressure",
  "content": "Only 10 percent of the context window remains.",
  "metadata": {
    "context_remaining_pct": "10",
    "workspace": "/path/to/repo"
  },
  "auto_checkpoint": true,
  "checkpoint_reason": "context_pressure"
}
```

Minimal contract:

- `event_type`: structured category for the reducer
- `content`: the durable fact to preserve
- `metadata`: optional string map
- `auto_checkpoint`: optional boolean
- `checkpoint_reason`: optional reason label

## CLI

Start a session:

```bash
cg session start --title "Payments refactor" --source claude-code --workspace "$PWD"
```

Fork a branch from the latest checkpoint:

```bash
cg session fork --title "grpc-branch"
```

Fork from a specific checkpoint:

```bash
cg session fork --from-checkpoint chk_123456 --title "hotfix-branch"
```

Record an event:

```bash
cg session event decision "Keep the REST API stable."
```

Checkpoint manually:

```bash
cg checkpoint --reason manual --token-budget 1600
```

Resume:

```bash
cg resume
```

Sync the repo-local memory directory:

```bash
cg memdir sync
```

Diff checkpoints:

```bash
cg context-diff
```

Run diagnostics:

```bash
cg doctor memory
```

Checkpoint and resume output now surface cache status, cache base checkpoint, reuse counts, and branch lineage.

## `.contextgraph/` Memory Directory

When a session includes `metadata["workspace"]`, ContextGraph can materialize the current durable state into `<workspace>/.contextgraph/`.

Files written in v1:

- `session.json`
- `latest_delta_pack.json`
- `doctor.json`
- `resume_prompt.md`
- `restoration_instructions.md`
- `decisions.md`
- `constraints.md`
- `open_tasks.md`
- `failures.md`
- `changed_files.md`
- `important_artifacts.md`

This is the visible layer on top of reactive checkpoints and branch-aware cache:

- agents survive compaction without hiding the state in one API response
- branches show which checkpoint they inherited from and whether the last pack was a `prefix_hit`
- humans can review decisions, failures, and open tasks directly in the repo

```python
sync = client.sync_memory_directory(
    agent["agent_id"],
    branch["session_id"],
    workspace_path="/path/to/repo",
)
print(sync["directory_path"])
```

## Hook Adapter Templates

Reference scripts live in:

- [`examples/hooks/claude_code_precompact.py`](../examples/hooks/claude_code_precompact.py)
- [`examples/hooks/claude_code_postcompact.py`](../examples/hooks/claude_code_postcompact.py)
- [`examples/hooks/codex_template.py`](../examples/hooks/codex_template.py)
- [`examples/hooks/cline_template.py`](../examples/hooks/cline_template.py)
- [`examples/hooks/opencode_template.py`](../examples/hooks/opencode_template.py)

Expected environment variables:

- `CG_SERVER_URL`
- `CG_AGENT_KEY`
- `CG_AGENT_ID`
- optional `CG_WORKSPACE`
- optional `CG_DELTA_TOKEN_BUDGET`

The helper persists a per-workspace session ID in `~/.contextgraph/hook_sessions/`.
When checkpoint/resume flows run through the helper templates, they also refresh the repo-local `.contextgraph/` directory when the workspace path is available.

## Example Branch Flow

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()
agent = client.register_agent("branch-coder", "acme", ["coding"])
root = client.create_session(agent["agent_id"], title="Payments refactor", source="claude-code")

client.record_session_event(agent["agent_id"], root["session_id"], "decision", "Keep the REST API stable.")
base = client.checkpoint_session(agent["agent_id"], root["session_id"])

branch = client.fork_session(agent["agent_id"], root["session_id"], title="grpc-branch")
client.record_session_event(
    agent["agent_id"],
    branch["session_id"],
    "file_change",
    "Updated contextgraph/service.py",
    metadata={"path": "contextgraph/service.py"},
)

child = client.checkpoint_session(agent["agent_id"], branch["session_id"])
print(child["cache_status"])             # prefix_hit
print(child["cache_base_checkpoint_id"]) # inherited checkpoint
print(child["reused_event_count"])       # reused prefix work
```

## Deterministic First

Reactive Delta Compaction is intentionally deterministic by default:

- no embeddings requirement
- no mandatory LLM summarization
- no runtime hosting requirement

LLM-assisted rebasing can be layered on later without changing the event/checkpoint model.
