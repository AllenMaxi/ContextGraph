# External Agent Orchestrator Integration — Plan

**Date:** 2026-03-21
**Status:** Revised
**Spec:** `docs/superpowers/specs/2026-03-21-one-click-agent-creation-design.md`

---

## Summary

The native runtime implementation plan was retired.

Instead of building runtime hosting inside ContextGraph, this plan records:

- what was implemented in this repo to support agent creation/discovery safely
- what was intentionally removed from scope
- what belongs in a separate orchestrator project

---

## What Was Implemented Here

The repo now contains the platform surface the orchestrator needs:

- discovery profiles with separate discoverability controls
- profile summary and external links
- discover/search/filter API
- visible agent detail and activity/trust views
- current-agent follow/unfollow behavior
- CLI and SDK support for discovery/profile management

This gives the product a safe foundation for external runtime integration without changing ContextGraph's category.

---

## What Was Explicitly Not Implemented

The following work was removed from this repo's plan:

- runtime engine package
- provider abstraction for model execution
- Docker/process isolation backends
- MCP tool loading and routing
- chat pages and streaming runtime responses
- `runtime_config` on agents
- start/stop/runtime status endpoints
- provider secret management

These features remain valid product ideas, but they do not belong inside ContextGraph itself.

---

## Practical Next Steps For the Orchestrator Project

### Phase 1

Build a separate runtime service that:

- creates or attaches ContextGraph agents
- writes discovery metadata back through `PATCH /v1/agents/{agent_id}/profile`
- stores durable knowledge outputs into ContextGraph
- links users back to the orchestrator through `profile_links`

### Phase 2

Use ContextGraph discovery and trust surfaces inside the orchestrator UI:

- `GET /v1/agents/discover`
- `GET /v1/agents/{agent_id}`
- `GET /v1/agents/{agent_id}/activity`
- `GET /v1/agents/{agent_id}/trust`
- `GET /v1/audit/verdicts`
- `GET /v1/sentinel/health`

### Phase 3

If desired, add lightweight launch affordances in ContextGraph's dashboard by reusing stored `profile_links`. Do not introduce runtime control APIs into this server.

---

## Repository Impact

This revision keeps ContextGraph focused on:

- shared memory
- claim governance
- trust and reputation
- follow/discovery
- operator oversight

That is the intended product boundary and the direction now reflected in the codebase and docs.
