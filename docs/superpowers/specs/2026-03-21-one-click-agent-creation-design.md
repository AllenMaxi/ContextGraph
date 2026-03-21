# One-Click Agent Creation with Native Runtime — Design Spec

**Date:** 2026-03-21
**Sub-project:** 2 of 2 (One-Click Agent Creation). Sub-project 1: Agent Discovery Panel (separate spec).

## Goal

Enable users to create, configure, and interact with AI agents directly from the ContextGraph dashboard — with container isolation, MCP tool assignment, and full integration with ContextGraph's knowledge, sentinel, and discovery systems.

## Why Build Native (vs. Embedding Existing Claws)

Evaluated OpenClaw (248K stars, 430K lines, 1GB+ RAM), NanoClaw (~700 lines, container-isolated, Claude SDK), ZeroClaw (Rust, 3.4MB, trait-based), and NemoClaw (NVIDIA, policy guardrails). None are designed as embeddable libraries — they're standalone gateways/daemons. Embedding any would mean forking heavily or running as a sidecar with impedance mismatch.

**Patterns adopted from the ecosystem:**
- **From NanoClaw:** Container isolation, Claude Agent SDK as default runtime, ~700-line simplicity target
- **From ZeroClaw:** Trait-based provider/tool swapping, security defaults (workspace scoping, path allowlists)
- **From OpenClaw:** SOUL.md personality config, MCP skill assignment, ClawHub-compatible skill format
- **From NemoClaw:** Policy-based guardrails (maps to existing sentinel pipeline)

**ContextGraph differentiator:** Created agents get shared knowledge (recall/relate), trust scores, sentinel validation, cross-org discovery, and reputation building — things no Claw has today.

## Architecture

Three new layers:

1. **Agent Runtime** (`contextgraph/runtime/`) — Thin execution engine (~500-800 lines). Runs agents in isolated environments using Claude Agent SDK (default) or other providers. Handles container lifecycle, MCP tool loading, message routing.

2. **Agent Creation Wizard** — Dashboard UI at `/dashboard/create-agent`. Step-by-step form (name, role, tools, personality) plus optional natural language description. Generates SOUL.md, registers agent, starts runtime.

3. **Chat Interface** — Embedded chat widget on agent detail pages + dedicated `/dashboard/chat/{agent_id}` page with conversation history, tool call visibility, real-time streaming.

## Agent Runtime Engine

**`contextgraph/runtime/engine.py`** — Core execution loop per agent:

```
User Message → Context Assembly → LLM Call → Tool Execution → Response → Store Memory
```

**`AgentRuntime` class:**
- `start(agent_id)` — loads SOUL.md, initializes provider, connects MCP tools, starts isolation environment
- `send(message)` — assembles context (SOUL.md + conversation history + recalled memories), sends to LLM, executes tool calls in ReAct loop, returns response
- `stop()` — gracefully shuts down container/process, persists final state

**Context assembly** before each LLM call:
- SOUL.md (personality/goals/constraints)
- Conversation history (last N messages, default N=20, configurable via `runtime_config["context_window_messages"]`)
- Auto-recalled memories via `recall(query=user_message)` — own knowledge plus shared knowledge from followed agents
- Available MCP tools as tool definitions

**ReAct loop:** LLM responds with text or tool calls. Tool calls execute in sandbox, results feed back. Loop continues until final text response or max iterations (configurable, default 10).

**Auto-store:** After each turn, significant outputs stored via `store()`, flowing through sentinel pipeline automatically.

## LLM Provider Abstraction

**`contextgraph/runtime/providers.py`** — protocol-based (~80 lines):

```python
class LLMProvider(Protocol):
    def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse: ...

@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall]
    usage: dict[str, int]
```

**Built-in providers:**
- **`ClaudeProvider`** — default. Claude Agent SDK. Streaming support. Model configurable (sonnet default, opus for complex agents).
- **`OpenAIProvider`** — OpenAI-compatible API (covers OpenAI, Azure, OpenRouter). User provides API key + base URL.
- **`OllamaProvider`** — local models via Ollama. No API key needed.

**Provider selection:** Wizard defaults to Claude. Shows available providers based on configured API keys. Provider + model stored in agent config, changeable later.

**API key management:** Platform-level keys via env vars (existing pattern). Per-agent overrides stored encrypted. Keys never exposed in dashboard UI or API responses.

## Container Isolation

**`contextgraph/runtime/isolation.py`** — sandboxed execution:

**Docker mode (default when available):**
- Each agent gets own container (`python:3.12-slim` + Claude Agent SDK)
- Workspace mounted read-write at `/workspace`
- MCP servers started inside container
- Network access: allowed by default (for LLM API calls), configurable deny-list
- Container lifecycle tied to agent: created on `start()`, removed on `stop()`
- Resource limits: configurable CPU/memory (default 1 CPU, 512MB RAM)

**Process mode (fallback):**
- Subprocess with workspace scoping (inspired by ZeroClaw)
- Filesystem restricted to `~/.contextgraph/agents/{agent_id}/`
- Blocked paths: `~/.ssh`, `~/.gnupg`, `~/.aws`, `/etc` (configurable)
- Allowed commands whitelist (default: python, node, git, curl)
- Path canonicalization — no symlink escape

**Isolation levels per agent:** `docker` | `process` | `none` (dev only, explicit opt-in)

**Auto-detection:** Check Docker availability on startup. Default to `docker` if available, `process` fallback with dashboard warning.

## MCP Tool System

**`contextgraph/runtime/tools.py`** — tool loading and bundles:

**Pre-configured bundles** (defined in `contextgraph/runtime/bundles.json`):

| Bundle | MCP Servers | Use Case |
|--------|------------|----------|
| Developer | filesystem, shell, git, github | Coding agents |
| Research | web-search, browser, fetch | Research/analysis |
| Data | sqlite, postgres, csv-reader | Data agents |
| Communication | slack, email, calendar | Assistants |
| Minimal | filesystem (read-only) | Restricted agents |

**Manual MCP server assignment:** User provides name, command, args, env vars. Compatible with standard MCP server format.

**Tool loading at startup:**
1. Read assigned bundle + manual tools from config
2. Start MCP servers as subprocesses (inside container if Docker mode)
3. Discover tools via MCP `tools/list`
4. Convert to LLM tool definitions
5. Route tool calls via MCP `tools/call`

**Tool permissions per agent:**
- `auto` — agent uses freely
- `confirm` — requires user approval in chat before execution
- Dangerous tools (shell, filesystem-write) default to `confirm` for new agents

## Agent Creation Wizard

Dashboard page `/dashboard/create-agent` — 4 steps, server-side rendered in `dashboard.py` following the existing pure HTML/CSS/JS pattern (same as all other dashboard pages and Sub-project 1).

**Step 1: Identity** — name, role label (dropdown: assistant/researcher/developer/analyst/custom — stored as a string in `runtime_config["role_label"]`, separate from the system-level `AgentRole` enum which stays as `agent`/`sentinel`), emoji/avatar, org (pre-filled)

**Step 2: Tools & Capabilities** — bundle selector (cards), "Add more tools" with MCP server checkboxes, tool permission toggles (auto/confirm), isolation level selector

**Step 3: Personality** — two paths:
- **Quick setup:** personality trait dropdowns (tone, verbosity, caution) + goals text + constraints checklist
- **Describe your agent:** free-text, LLM generates SOUL.md
- Preview of generated SOUL.md with edit button

**Step 4: Review & Create** — summary card, provider/model selector, visibility selector (private/org/shared/published), "Create Agent" button

**On creation flow (uses existing + new endpoints):**
1. Call existing `POST /v1/agents/register` to create the agent
2. Call `POST /v1/agents/{id}/generate-soul` (if natural language path) or construct SOUL.md from wizard fields
3. Call `PATCH /v1/agents/{id}/runtime-config` to save runtime_config (provider, tools, isolation, soul_md)
4. Call `POST /v1/agents/{id}/start` to start the runtime
5. Redirect to agent detail page with chat widget ready

**Alternative entry:** "Describe your agent in one sentence" link → chat-like interface, LLM asks follow-ups, auto-fills wizard → user reviews before creation

## Chat Interface

**Chat widget (agent detail page):**
- Collapsible panel at bottom-right of agent detail
- Simple input + scrollable history (last 10 messages)
- "View full chat" link
- Real-time streaming via SSE
- Compact tool call indicators (expandable)

**Full chat page (`/dashboard/chat/{agent_id}`):**
- Left sidebar: conversation list (sessions, create new)
- Center: message thread with streaming
- Right panel (collapsible): agent info, active tools, runtime status

**Message rendering:**
- User: right-aligned bubbles
- Agent: left-aligned, markdown rendered
- Tool calls: inline collapsible blocks (tool name, input, output)
- System: centered, muted
- Streaming via SSE (existing infrastructure)

**Conversation persistence:**
- Messages stored as ContextGraph memories with metadata `{type: "conversation", session_id: "..."}`
- Recallable via normal `recall()` — part of knowledge graph
- Visible in agent's Activity tab (from Sub-project 1)

**Status indicators:** green (ready), yellow (processing), red (stopped/error). Start/Stop button in chat header.

## Data Model

**New field on Agent model in `contextgraph/models.py`:**
```python
runtime_config: dict[str, Any] = field(default_factory=dict)
```

Contents:
```python
{
    "provider": "claude",
    "model": "claude-sonnet-4-6",
    "isolation": "docker",
    "soul_md": "...",
    "bundles": ["developer"],
    "manual_tools": [...],
    "tool_permissions": {"shell": "confirm", "filesystem": "auto"},
    "resource_limits": {"cpu": 1, "memory_mb": 512},
    "auto_store": true
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/agents/{id}/start` | Start agent runtime |
| `POST` | `/v1/agents/{id}/stop` | Stop agent runtime |
| `GET` | `/v1/agents/{id}/status` | Runtime status (running/stopped/error) |
| `POST` | `/v1/agents/{id}/chat` | Send message, SSE streaming response |
| `GET` | `/v1/agents/{id}/conversations` | List conversation sessions |
| `GET` | `/v1/agents/{id}/conversations/{session}` | Get conversation messages |
| `GET` | `/v1/tools/bundles` | List available tool bundles |
| `GET` | `/v1/tools/available` | List available MCP servers |
| `POST` | `/v1/agents/{id}/generate-soul` | Generate SOUL.md from natural language (uses platform ANTHROPIC_API_KEY) |
| `PATCH` | `/v1/agents/{id}/runtime-config` | Update runtime configuration |

**`AgentResponse` schema update:** Add `runtime_config` field to `AgentResponse` in `schemas.py`. API keys inside `runtime_config` must be redacted (replaced with `"***"`) before serialization.

**Chat SSE:** `POST /v1/agents/{id}/chat` returns `Content-Type: text/event-stream`. The POST body contains the user message; the response streams SSE events (`data: {"type": "text", "content": "..."}` for tokens, `data: {"type": "tool_call", ...}` for tool usage, `data: {"type": "done"}` for completion).

## SDK & CLI

### SDK Methods (on `ContextGraph` client)

- `start_agent()` → starts the agent's runtime
- `stop_agent()` → stops the agent's runtime
- `agent_status()` → returns runtime status (running/stopped/error)
- `chat(message)` → sends message, returns streaming response
- `list_conversations(agent_id)` → list conversation sessions
- `get_conversation(agent_id, session_id)` → get messages in a conversation
- `list_tool_bundles()` → list available tool bundles
- `list_available_tools()` → list available MCP servers
- `generate_soul(description)` → generate SOUL.md from natural language
- `update_runtime_config(config)` → update runtime configuration

### LocalTransport & HttpTransport

Both transports implement matching methods following existing patterns.

### CLI Commands

- `cg agents create --name <name> --role <role> --bundle <bundle>` — create agent with defaults
- `cg agents start <agent_id>` — start agent runtime
- `cg agents stop <agent_id>` — stop agent runtime
- `cg agents status <agent_id>` — check runtime status
- `cg agents chat <agent_id>` — interactive chat session in terminal
- `cg tools bundles` — list available tool bundles
- `cg tools list` — list available MCP servers

## ContextGraph Integration

Created agents are **first-class ContextGraph citizens:**

- **Memory:** `recall()` searches full knowledge graph (own + shared/followed). Outputs auto-stored via `store()` through normal claim extraction pipeline.
- **Sentinel validation:** All claims go through sentinel pipeline. New agents get `full` audit depth. Audit depth reduces as reputation grows (existing graduated trust).
- **Discovery:** Agents appear in discover panel based on `default_visibility`. Wizard defaults to `ORG`.
- **Trust building:** Reputation starts at 0.0, builds through validated/attested claims. High-reputation agents get scoring bonuses in recall.
- **Cross-agent knowledge:** Follow other agents → recall includes their shared knowledge. Configurable auto-follow via standing queries.

## Error Handling & Security

**Security:**
- API keys encrypted at rest, never exposed via API/dashboard
- Container agents: non-root, read-only rootfs except workspace
- Process agents: strict path canonicalization (no symlink escape)
- `confirm` permission blocks dangerous tools until user approves
- Agent creation requires authenticated session
- Rate limiting on chat endpoint (existing API limits)

**Resource management:**
- Max agents per org (configurable, default 10)
- Idle timeout: agents auto-stop after 30min inactivity, auto-restart on next chat
- Docker containers cleaned up on stop
- Process agents: SIGTERM → 5s → SIGKILL

**Error handling:**
- LLM provider errors → clear message in chat, agent stays running
- Container crash → auto-restart once, then stop with error + notification
- MCP tool crash → mark unavailable, agent continues without it, dashboard warning
- SOUL.md generation failure → fall back to default template

**Edge cases:**
- Recursive agent creation → blocked
- Agent modifying own SOUL.md → blocked (owner changes via dashboard)
- Concurrent chat → sequential message queue per agent
- No Docker available → wizard shows process-mode only
- Agent deleted while runtime active → `stop()` called automatically before deletion
- Conversation history on agent deletion → conversations preserved as orphaned memories (immutable audit trail)
- `generate-soul` rate limiting → max 5 calls per minute per org (expensive LLM operation)

## Testing Strategy

~25-30 new tests:

- **Runtime:** start/stop lifecycle, context assembly, ReAct loop with mock provider, auto-store, max iterations
- **Providers:** ClaudeProvider formatting/parsing, provider selection, API key errors
- **Isolation:** Docker create/cleanup (integration, skip if no Docker), process workspace scoping, fallback, resource limits
- **MCP tools:** bundle loading, manual tool addition, permission enforcement, crash recovery
- **Creation API:** full flow (register + config + start), SOUL.md generation, validation errors
- **Chat:** send/receive, conversation persistence/retrieval, concurrent queuing, SSE streaming
- **Integration:** auto-store through sentinels, recall includes followed agents, discover panel listing, reputation updates
