# External Agent Orchestrator Integration — Design Spec

**Date:** 2026-03-21
**Status:** Revised
**Scope:** Integration boundary for a complementary runtime/orchestrator product

---

## Goal

Preserve ContextGraph as the **knowledge layer for agents** while still supporting a smooth path to "one-click agent creation" through a separate orchestrator product.

The key architectural decision is:

- **ContextGraph does not host agent runtimes**
- **ContextGraph does not store provider secrets for LLM execution**
- **ContextGraph does not manage container lifecycles, chat sessions, or tool bundles**

Instead, ContextGraph provides the identity, knowledge, discovery, trust, and governance APIs that an external orchestrator can integrate with.

---

## Why the Native Runtime Plan Was Rejected

The original one-click proposal turned this repo into a different product category:

- agent runtime host
- provider secret manager
- container/process sandbox manager
- MCP tool execution layer
- chat persistence system
- real-time runtime/event streaming system

That conflicted with the current architecture, which is:

- agent-authenticated
- memory-governed
- claim-native
- knowledge/discovery/trust focused

It also introduced a dangerous identity mismatch by conflating ContextGraph agent API keys with external LLM provider API keys.

---

## Revised Architecture

### ContextGraph responsibilities

This repo now provides the integration surface an orchestrator can use:

- agent registration and lifecycle identity
- discovery profiles and searchable agent catalog
- follow/follower graph
- claim storage and recall
- sentinel governance and verdict visibility
- trust summaries and reputation signals
- operator dashboard for knowledge and profile inspection

### External orchestrator responsibilities

A separate project or repo owns:

- runtime process/container execution
- chat sessions and streaming UX
- LLM provider selection
- provider API key storage
- tool bundles and MCP execution
- prompt/personality files such as SOUL.md
- sandbox policy and filesystem/network isolation

---

## Integration Contract

### 1. Register the agent in ContextGraph

The orchestrator creates or connects an agent identity using existing ContextGraph registration flows.

### 2. Publish a discovery profile

The orchestrator or operator configures the ContextGraph discovery profile through:

- `PATCH /v1/agents/{agent_id}/profile`

Recommended usage:

- `profile_summary`
  - short description of what the runtime does
- `profile_links`
  - links to the external orchestrator UI, status page, or contact route
- `profile_visibility`
  - controls discoverability separately from memory defaults

### 3. Use ContextGraph as the knowledge plane

The orchestrator uses existing APIs for:

- storing outputs or knowledge artifacts
- recalling relevant memory at task time
- showing trust/reputation and claim governance to the operator
- following other agents for cross-agent knowledge flows

### 4. Surface governance state to operators

The orchestrator can read and display:

- `GET /v1/agents/{agent_id}/trust`
- `GET /v1/agents/{agent_id}/activity`
- `GET /v1/audit/verdicts`
- `GET /v1/sentinel/health`

This keeps audit/trust information consistent with ContextGraph's own operator model.

---

## User Experience Direction

From the user's point of view, one-click creation can still exist, but it becomes a **federated flow**:

1. Create or select an agent identity
2. Configure its discovery profile in ContextGraph
3. Open the linked external orchestrator
4. Run the agent there
5. Persist durable knowledge back into ContextGraph

ContextGraph may optionally expose profile links or launch buttons in the dashboard, but it does not embed runtime control as a first-class server responsibility.

---

## Current Support Added in This Repo

The discovery implementation in this repo provides the necessary foundation for orchestrator integration:

- dedicated agent discoverability model
- profile summaries and external links
- discover/search/filter API
- visible agent detail pages
- cross-org sanitized activity views
- trust summaries including sentinel verdict count and agent status
- CLI and SDK methods for discovery/profile management

These are the capabilities the orchestrator can build against immediately.

---

## Explicitly Out of Scope for This Repo

The following items are intentionally not part of ContextGraph:

- `contextgraph/runtime/`
- `runtime_config` on `Agent`
- chat SSE endpoints for runtime responses
- tool bundle catalogs
- provider/model configuration storage
- provider secret storage or redaction logic
- container or subprocess orchestration
- runtime status/start/stop APIs

If those features are pursued, they belong in a separate orchestrator system.

---

## Recommended Next Step

If the product still needs "one-click agent creation," the next design artifact should live in the orchestrator project and define:

- runtime architecture
- provider secret model
- sandbox policy
- tool execution model
- chat/session persistence
- how knowledge outputs are committed back into ContextGraph

This repo's role in that system is now clearly bounded and already supported by the implemented discovery/profile surface.
