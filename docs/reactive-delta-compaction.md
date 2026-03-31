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

The goal is to survive repeated compactions and resumes without paying LLM costs on every checkpoint.

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
cg session start --title "Payments refactor" --source claude-code
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

Diff checkpoints:

```bash
cg context-diff
```

Run diagnostics:

```bash
cg doctor memory
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

## Deterministic First

Reactive Delta Compaction is intentionally deterministic by default:

- no embeddings requirement
- no mandatory LLM summarization
- no runtime hosting requirement

LLM-assisted rebasing can be layered on later without changing the event/checkpoint model.
