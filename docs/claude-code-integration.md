# Claude Code + ContextGraph Integration Guide

Add governed, persistent memory to Claude Code. Sessions survive compaction boundaries, decisions and context are checkpointed into structured delta packs, and the latest state is always inspectable in your repo.

## What You Get

- **Session persistence across compaction** — when Claude Code compacts your conversation, ContextGraph checkpoints decisions, open tasks, failures, and constraints into a structured delta pack before context is lost
- **Resumable sessions** — after compaction, the restoration prompt and structured state are available immediately
- **Repo-local inspection** — session state syncs to `.contextgraph/` in your workspace so you can review what the agent remembers
- **Branch-aware context** — fork sessions from checkpoints when exploring alternative approaches

## Prerequisites

```bash
# Install ContextGraph with server extras
pip install contextgraph[server]
pip install contextgraph-sdk

# Start the server
contextgraph-server
# API: http://localhost:8420

# Register an agent
cg auth login
# Note your agent_id and API key
```

## Option A: Hook-Based Integration (Recommended)

Claude Code supports lifecycle hooks that fire before and after compaction. ContextGraph ships hook scripts that plug directly into this lifecycle.

### 1. Set environment variables

Add these to your shell profile or `.env`:

```bash
export CG_SERVER_URL="http://localhost:8420"
export CG_AGENT_KEY="cgk_your_api_key_here"
export CG_AGENT_ID="agt_your_agent_id_here"
export CG_WORKSPACE="$PWD"  # optional, defaults to cwd
```

### 2. Configure Claude Code hooks

Add to your Claude Code `settings.json` (or `.claude/settings.json` in the project):

```json
{
  "hooks": {
    "PreCompact": [
      {
        "command": "python3 examples/hooks/claude_code_precompact.py",
        "timeout": 10000
      }
    ],
    "PostCompact": [
      {
        "command": "python3 examples/hooks/claude_code_postcompact.py",
        "timeout": 10000
      }
    ]
  }
}
```

> Adjust paths to where you cloned ContextGraph, or copy the hook files into your project.

### 3. How the lifecycle works

```
Claude Code session running
        │
        ▼
Context window fills up
        │
        ▼
PreCompact hook fires
  → claude_code_precompact.py
  → Emits "context_pressure" event
  → Auto-checkpoints into a delta pack
  → Syncs .contextgraph/ directory
        │
        ▼
Claude Code compacts conversation
        │
        ▼
PostCompact hook fires
  → claude_code_postcompact.py
  → Calls resume_session()
  → Syncs .contextgraph/ with latest state
  → Prints restoration data for Claude Code
```

### What the hooks do

**PreCompact** (`claude_code_precompact.py`):
- Records a `context_pressure` event with `auto_checkpoint=True`
- The checkpoint compiles all session events into a structured delta pack
- Syncs the delta pack to `.contextgraph/` in your workspace

**PostCompact** (`claude_code_postcompact.py`):
- Calls `resume_session()` to fetch the latest checkpoint and delta pack
- Syncs `.contextgraph/` again with the current state
- Outputs the restoration data as JSON

## Option B: MCP Integration

Alternatively, configure ContextGraph as an MCP server so Claude Code can use session tools directly.

### 1. Add to MCP config

In your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "contextgraph": {
      "command": "python3",
      "args": ["-m", "contextgraph.mcp_server"],
      "env": {
        "CG_AGENT_ID": "agt_your_agent_id_here",
        "CG_AGENT_NAME": "claude-code",
        "CG_AGENT_ORG": "your-org"
      }
    }
  }
}
```

### 2. Available MCP tools

| Tool | Purpose |
|------|---------|
| `contextgraph_session_start` | Start a new coding session |
| `contextgraph_session_event` | Record a decision, constraint, task, failure, file change, etc. |
| `contextgraph_checkpoint` | Checkpoint the session into a structured delta pack |
| `contextgraph_resume` | Resume a session with the latest checkpoint and delta pack |
| `contextgraph_store` | Store a memory with claim extraction |
| `contextgraph_recall` | Search memories by query |
| `contextgraph_compile_context` | Compile a governed, token-budgeted context pack |

### 3. Typical session flow via MCP

```
1. contextgraph_session_start(title="Fix payment timeout", source="claude-code")
   → returns session_id

2. contextgraph_session_event(session_id, "decision", "Use connection pooling instead of per-request connections")
   contextgraph_session_event(session_id, "file_change", "src/payments/pool.py")
   contextgraph_session_event(session_id, "constraint", "Must maintain backward compatibility with REST API")
   contextgraph_session_event(session_id, "todo", "Add integration tests for new pool config")

3. contextgraph_checkpoint(session_id, reason="before_refactor")
   → returns delta pack with structured state

4. [... context compaction happens ...]

5. contextgraph_resume(session_id)
   → returns session + checkpoint + delta pack with restoration_prompt
```

## Inspecting Session State

After a checkpoint, ContextGraph syncs state to `.contextgraph/` in your workspace:

```
.contextgraph/
├── session.json              # Session metadata
├── delta_pack.json           # Full structured delta pack
├── decisions.txt             # Persistent decisions (one per line)
├── constraints.txt           # Hard constraints
├── open_tasks.txt            # Unfinished work
├── failures.txt              # Known bugs/failures
├── changed_files.txt         # Modified source files
├── restoration_prompt.txt    # Handoff instructions for the next agent turn
└── cache_metadata.json       # Branch-aware cache status
```

These files are human-readable and git-friendly. You can commit them for workflow transparency or add `.contextgraph/` to `.gitignore` if you prefer.

## Branching Sessions

When exploring alternative approaches, fork from a checkpoint:

```bash
# Start a session and checkpoint
cg session start --title "Payments refactor" --source claude-code --workspace "$PWD"
cg checkpoint --reason "baseline"

# Fork to try a different approach
cg session fork --title "grpc-branch"

# The child session inherits the parent's structured state
# New checkpoints reuse the inherited prefix (cache: prefix_hit)
```

Via the SDK:

```python
base = client.checkpoint_session(agent_id, session_id)
branch = client.fork_session(agent_id, session_id, title="grpc-branch")
# Record events on the branch...
child_pack = client.checkpoint_session(agent_id, branch["session_id"])
print(child_pack["cache_status"])  # "prefix_hit"
```

## Memory Doctor

Check session health at any time:

```bash
cg doctor-memory
```

The doctor reports:
- Total events and checkpoint count
- Unresolved tasks and known failures
- Stale and untrusted items
- Cache status and branch lineage
- Warnings and recommendations

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CG_SERVER_URL` | Yes | — | ContextGraph server URL |
| `CG_AGENT_KEY` | Yes | — | Agent API key |
| `CG_AGENT_ID` | Yes (hooks) | — | Agent identity for hook calls |
| `CG_WORKSPACE` | No | `$PWD` | Workspace path for session + memdir |
| `CG_DELTA_TOKEN_BUDGET` | No | `1600` | Token budget for delta pack checkpoints |
