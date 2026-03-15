# Memory Discipline Roadmap

This roadmap turns ContextGraph into a stronger shared-memory layer for MCP-compatible agents.

## Phase 1: Query Shared Memory Only When Needed

Goal:

- avoid unnecessary retrieval on generic questions
- use other agents' memory when it prevents hallucination

Implemented in this phase:

- `SharedMemoryHelper` in the SDK
- configurable minimum recall score
- example chat-agent loop with conditional retrieval
- memory-gating documentation

## Phase 2: Add Evidence and Validation

Goal:

- make memories safer to trust and easier to audit

Planned:

- `evidence` / `citations` on memories or claims
- `validated_at`
- richer `validation_status`
- stronger UI for stale / verified / challenged memory

## Phase 3: Expiry and Curation

Goal:

- prevent stale memory from quietly polluting prompts

Planned:

- configurable expiry windows
- manual curation in the operator console
- downgrade or suppression of stale memories during recall

## Phase 4: Remote MCP Distribution

Goal:

- publish ContextGraph as a real remote MCP server

Planned:

- `streamable-http` transport
- public deployment target
- official MCP Registry listing

## Product Principle

ContextGraph should not behave like "memory always on".

It should behave like:

- shared memory when needed
- provenance when used
- policy enforcement at retrieval time
