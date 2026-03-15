# Launch Posts for ContextGraph

These posts are aligned to the current product wedge:

**ContextGraph is a shared memory bus for MCP-compatible agents.**

Use the variants below as copy-paste starting points for launch day and follow-up posts.

## LinkedIn

I just open-sourced ContextGraph.

It is a shared memory bus for MCP-compatible agents with permissions, subscriptions, provenance, and optional paid discovery.

The problem we wanted to solve is simple:

- one agent learns something another agent should be able to use
- that memory should not be copied everywhere
- and it should not lose attribution, policy, or freshness on the way

ContextGraph stores full memories, extracts claims for retrieval, and enforces access at the memory level.

That gives agent systems a way to:

- share memory within the same org
- share memory across orgs when explicitly allowed
- follow agents, orgs, and topics
- expose paid discoveries without leaking the full body
- use shared memory only when the question actually needs it

We also added a stricter memory discipline layer inspired by what serious memory systems get right:

- evidence and citations
- validation state
- expiry for stale memory
- memory lookup only when needed

GitHub:
https://github.com/AllenMaxi/ContextGraph

Release:
https://github.com/AllenMaxi/ContextGraph/releases/tag/v0.2.1

If you are building MCP-native agents, multi-agent systems, or governed retrieval, I would love your feedback.

## X Short Post

Open-sourced ContextGraph.

Shared memory bus for MCP-compatible agents:
- memory-level permissions
- follow agents, orgs, and topics
- cross-org sharing
- optional paid discovery
- evidence, validation, and expiry

The goal is not another vector DB.
The goal is shared memory that agents can trust and use only when needed.

GitHub: https://github.com/AllenMaxi/ContextGraph

## X Thread

1/ Open-sourced ContextGraph: a shared memory bus for MCP-compatible agents.

GitHub: https://github.com/AllenMaxi/ContextGraph

2/ Most agent memory systems solve single-agent recall.
The harder problem is shared memory:
- across agents
- across teams
- across org boundaries
- without losing policy or provenance

3/ ContextGraph stores full memories, extracts claims for retrieval, and enforces access at the memory level:
- private
- org
- shared
- published

4/ Agents can:
- follow agents
- follow orgs
- follow topics
- discover memories
- unlock only what they are allowed to read

5/ We also started adding stricter memory discipline:
- evidence
- citations
- validation state
- expiry

6/ And the important part:
shared memory should not be queried on every turn.
It should be pulled into the loop only when the question actually needs external memory.

7/ That makes the wedge much clearer:
not another vector DB
not just chat history
but shared memory infrastructure for MCP-native agent systems

8/ Would love feedback from anyone building:
- MCP servers
- agent runtimes
- multi-agent workflows
- governed RAG systems

Release: https://github.com/AllenMaxi/ContextGraph/releases/tag/v0.2.1

## Show HN

### Title

Show HN: ContextGraph – Shared memory bus for MCP-compatible agents

### Body

I built and open-sourced ContextGraph.

It is a shared memory layer for MCP-compatible agents with:

- memory-level permissions
- follow and feed semantics
- cross-org sharing
- optional paid discovery
- evidence, validation, and expiry metadata

The goal is not to be another generic vector database.
The goal is to let agents publish, recall, and share memory with policy and provenance intact.

One product principle we care about a lot:
shared memory should only be used when the question actually needs it.
If the agent can answer directly, it should.
If another agent holds relevant memory, ContextGraph should help retrieve it without hallucinating or bypassing access controls.

Repo:
https://github.com/AllenMaxi/ContextGraph

Release:
https://github.com/AllenMaxi/ContextGraph/releases/tag/v0.2.1

There are both terminal and operator console demos in the README.

I would especially appreciate feedback from people building MCP-native agents, multi-agent systems, or retrieval systems with real trust boundaries.
