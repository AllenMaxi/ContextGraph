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

Implemented so far:

- `evidence` and `citations` on `Memory` and `Claim`
- `validated_at` on reviewed claims
- memory-level `validation_status` synchronized from sibling claims
- provenance flowing through service, HTTP API, and SDK
- console badges and filters for verified / challenged / stale / expiring claims
- console review actions for manual memory curation

Next:

- richer `validation_status`
- deeper operator workflows for stale / verified / challenged memory

## Phase 3: Expiry and Curation

Goal:

- prevent stale memory from quietly polluting prompts

Implemented so far:

- configurable expiry windows at store time
- memory-level expiry derived from claim expiry
- expiry sweeps synchronizing the parent memory state

Next:

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
