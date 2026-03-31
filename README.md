<p align="center">
  <img src="docs/assets/contextgraph-hero.jpeg" alt="ContextGraph hero" width="600">
</p>

<h1 align="center">ContextGraph</h1>

<p align="center">
  <strong>Stop losing agent context.</strong><br>
  ContextGraph is the memory backend for coding agents and multi-agent teams.<br>
  Capture durable facts, compile trusted context packs, and survive compaction with reactive delta checkpoints.
</p>

<p align="center">
  <a href="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml"><img src="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <img src="https://img.shields.io/badge/version-0.4.0-blue.svg" alt="Version 0.4.0">
</p>

<p align="center">
  <a href="#reactive-delta-compaction">Reactive Delta</a> &middot;
  <a href="#context-compiler">Context Compiler</a> &middot;
  <a href="#use-cases">Use Cases</a> &middot;
  <a href="#demo">Demo</a> &middot;
  <a href="#quickstart">Quickstart</a> &middot;
  <a href="#python-sdk">SDK</a> &middot;
  <a href="#cli-tool">CLI</a> &middot;
  <a href="#real-use-cases">More Use Cases</a> &middot;
  <a href="docs/">Docs</a>
</p>

<p align="center">
  <a href="README.md">English</a> &middot; <a href="docs/README_ES.md">Espa&ntilde;ol</a>
</p>

---

## Why It Stands Out

Most agent memory tools either store raw text in a vector database or replace long sessions with one lossy summary.

ContextGraph is built for the gap between those two:

- **governed shared memory** so agents can reuse facts without losing provenance, freshness, or access control
- **context packs** so agents get token-budgeted, explainable context instead of opaque recall results
- **reactive delta compaction** so coding agents can checkpoint decisions, open tasks, blockers, and changed files before the context window collapses

If you want memory that is inspectable, team-safe, and useful during real work, this is the wedge.

## Start Here

The fastest path to understand the repo is:

1. run the 2-minute setup in [`examples/beta_quickstart.py`](examples/beta_quickstart.py)
2. run the coding-agent continuity demo in [`examples/reactive_delta_compaction_demo.py`](examples/reactive_delta_compaction_demo.py)
3. run the governed retrieval demo in [`examples/context_pack_demo.py`](examples/context_pack_demo.py)
4. skim the hook protocol in [`docs/reactive-delta-compaction.md`](docs/reactive-delta-compaction.md)
5. check the production notes in [`docs/production-readiness.md`](docs/production-readiness.md)

Public API note: use `ContextGraph` from `contextgraph_sdk` in user code and examples. `ContextGraphService` is the in-process server/service API used for internal embedding, tests, and implementation work.

## Use Cases

- coding agents that need to survive `/compact`, `/resume`, or context-window pressure without losing the plot
- support and incident agents that need trusted shared memory across handoffs
- research and analyst flows where provenance and freshness matter as much as retrieval quality
- internal agent platforms where ACLs, review state, and explainability must live in the memory layer
- teams that want a self-hosted memory backend instead of wiring brittle prompt glue around a vector store

## Where It Wins

- **better than vector-only memory** when freshness, provenance, and access control matter
- **better than plain chat summaries** when coding agents need to resume from structured state
- **better than prompt glue** when multiple agents or teams need one shared memory backend

## Not The Right Fit

- you only need personal memory for one chatbot
- you want a hosted agent runtime or enterprise IAM today
- you mainly want a vector database or generic RAG pipeline

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()
agent = client.register_agent("my-agent", "acme", ["research"])
client.store(agent["agent_id"], "Acme Corp reported 3x latency in EU region.")
hits = client.recall(agent["agent_id"], "latency EU")
print(hits[0]["claim"]["statement"])
# "Acme Corp reported 3x latency in EU region."
```

## What Ships Today

- **reactive delta compaction**: checkpoint coding sessions from structured events and restore them across compaction boundaries
- **context compiler**: compile governed, token-budgeted context packs from mixed agent memory
- **governed shared memory**: store and recall claims with provenance, freshness, review state, and ACLs
- **explainable retrieval**: inspect why a claim was included, excluded, locked, or filtered
- **Anthropic Memory Tool adapter**: use ContextGraph as the governed backend for Claude's API memory tool, with versioned memory snapshots and archival delete semantics
- **developer surfaces**: dashboard, CLI, Python SDK, HTTP API, and MCP server
- **self-hosted backends**: in-memory local mode and Neo4j persistence

Broader roadmap note: federation, payments, and protocol positioning remain part of the long-term direction, but the current beta is focused on governed shared memory inside real team workflows.

---

## Reactive Delta Compaction

Reactive Delta Compaction is the flagship feature for coding agents.

Instead of collapsing a long session into one fragile summary, ContextGraph records structured events and compiles **delta packs** with:

- decisions
- constraints
- open tasks
- failures and resolved items
- changed files and important artifacts
- restoration prompts and instructions

This makes compaction feel more like `git diff` for agent context than “rewrite the whole conversation and hope.”

**Real use case: payment-service refactor**

During a live session, the agent records events like:

- decision: "Keep the public REST API stable"
- constraint: "Do not break SDK compatibility"
- file change: `contextgraph/service.py`
- failure: "resume-path regression is failing"
- todo: "add migration tests"

When context pressure appears, ContextGraph emits a delta pack instead of a vague summary.

The next turn or next day can resume from:

- the decision that must still hold
- the files that changed
- the test failure that is still open
- the unresolved task list
- a restoration prompt and instructions for the next agent

That is why it feels like `git diff` for working context, not “summarize and hope.”

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()
agent = client.register_agent("delta-coder", "acme", ["coding"])
session = client.create_session(agent["agent_id"], title="Payments refactor", source="claude-code")

client.record_session_event(agent["agent_id"], session["session_id"], "decision", "Keep the REST API stable.")
result = client.record_session_event(
    agent["agent_id"],
    session["session_id"],
    "context_pressure",
    "Only 10 percent of the context window remains.",
    metadata={"context_remaining_pct": "10"},
)

print(result["checkpoint"]["checkpoint_id"])
print(result["delta_pack"]["restoration_prompt"])
```

Hook adapters and the JSON protocol are documented in [`docs/reactive-delta-compaction.md`](docs/reactive-delta-compaction.md).

---

## Context Compiler

The context compiler is the hero feature of Memory OS v1. It takes many memories and claims across agents and orgs, and compiles a **governed, explainable, token-budgeted context pack** tailored to the requesting agent's permissions.

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()
agent = client.register_agent("ops-bot", "acme", ["operations"])

# Store diverse memories
client.store(agent["agent_id"], "Payment service migrating from REST to gRPC for Q2.")
client.store(agent["agent_id"], "Incident: payment latency spike caused by connection pool exhaustion.")

# Compile a context pack
pack = client.compile_context(
    agent_id=agent["agent_id"],
    query="payment service issues",
    token_budget=1000,
    include_explanations=True,
)

print(f"Summary: {pack['summary']}")
print(f"Claims: {len(pack['included_claims'])} included, {len(pack['conflicting_claims'])} conflicts")
print(f"Tokens: {pack['tokens_used']} / {pack['token_budget']}")
```

**What the compiler does:**

1. Retrieves candidate claims via repository-native BM25 search
2. Applies ACL, freshness, trust, curation, and payment filters per agent
3. Deduplicates near-exact claims (Jaccard >= 0.88)
4. Detects conflicts using existing sentinel dispute signals
5. Truncates to fit the token budget (word_count * 1.3 estimation)
6. Builds an extractive summary from top claims
7. Returns different packs to different agents from the same corpus

**Three agents, same corpus, different packs:**

```python
# Alice (owner) sees private + org + published claims
# Carol (same org) sees org + published claims
# Bob (other org) sees only published claims
alice_pack = client.compile_context(alice_id, "project status", 4000)
carol_pack = client.compile_context(carol_id, "project status", 4000)
bob_pack   = client.compile_context(bob_id,   "project status", 4000)
# alice_pack has >= carol_pack has >= bob_pack claims
```

**Paid claims appear as locked references:**

Cross-org priced claims appear in the pack with `locked=True` and empty statements. The agent knows the claim exists and can choose to purchase it, but content is not leaked.

Run the full demo: `python3 examples/context_pack_demo.py`

---

## What's New in v0.5.0

### Memory OS v1 — Context Compiler
ContextGraph now ships a **context compiler** that assembles governed, token-budgeted context packs from mixed agent memory. This is the first release of the Memory OS vision: not a bigger vector DB, but the first governed memory OS for agents.

- **`compile_context()`**: compile a context pack from all accessible memories, respecting ACL, freshness, trust, and payment gates
- **Token budget enforcement**: packs are truncated to fit a caller-specified token budget using deterministic estimation (word_count * 1.3)
- **Near-exact deduplication**: claims with Jaccard similarity >= 0.88 are deduplicated automatically
- **Conflict detection**: claims with existing sentinel dispute/reject verdicts are separated into `conflicting_claims`
- **Locked paid claims**: cross-org priced claims appear as references with `locked=True` and empty statements
- **Extractive summaries**: top claim statements are stitched into a `summary` field within 20% of the token budget
- **Full explanations**: `include_explanations=True` returns inclusion/exclusion reasons, conflict pairs, and filter counts
- **Immutable snapshots**: compiled packs are persisted and retrievable via `get_context_pack()` and `explain_context_pack()`
- **REST, SDK, and MCP**: available as `POST /v1/context/compile`, `client.compile_context()`, and `contextgraph_compile_context` MCP tool

### Extended Memory Model
- **Memory** gains optional `source_type`, `source_uri`, `source_label`, `section_refs`, and `ingest_metadata` fields for richer source tracking
- **Claim** gains optional `source_memory_section` for section-level provenance
- All extensions are additive-only with null defaults — no migration needed, existing data remains valid

### Anthropic Memory Tool Adapter
ContextGraph can now act as the **governed backend for Anthropic's Claude API Memory tool**.

This lets teams keep Claude-compatible memory operations while upgrading the storage layer underneath:

- **Versioned memory snapshots**: each `/memories/...` file is stored as a ContextGraph memory revision instead of a mutable blob
- **Archival delete semantics**: deletes map to curation/archive so provenance is preserved
- **Adapter-native provenance**: Anthropic-backed memories carry `source_type`, `source_uri`, `source_label`, and ingestion metadata for traceability
- **Public SDK surface**: the integration uses `store()`, `memories()`, `memory()`, and `update_memory_curation()` so it works with both local and HTTP clients
- **Claude-compatible file operations**: create, view, insert, replace, rename, and delete stay available through a virtual `/memories` filesystem

See the integration guide: [`docs/anthropic-memory-tool.md`](docs/anthropic-memory-tool.md)  
Run the example: [`examples/anthropic_memory_tool.py`](examples/anthropic_memory_tool.py)

### New API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/v1/context/compile` | POST | Compile a governed context pack |
| `/v1/context/{pack_id}` | GET | Retrieve a compiled context pack |
| `/v1/context/{pack_id}/explain` | GET | Retrieve a pack with full explanation |

```python
# SDK
pack = client.compile_context(agent_id, "query", token_budget=2000, include_explanations=True)
retrieved = client.get_context_pack(pack["pack_id"])
explained = client.explain_context_pack(pack["pack_id"])
```

```bash
# MCP tool
contextgraph_compile_context(query="deployment status", token_budget=4000)
```

---

## What's New in v0.4.0

### Explainable Recall + Repository-Native Retrieval
Recall now exposes a first-class explanation path and uses repository-backed candidate retrieval instead of scanning the full claim set on every query.

- **Explainable recall**: inspect hits, score breakdowns, and filtered reasons via `client.explain_recall(...)` or `POST /v1/memory/recall/explain`
- **Repository-native candidate search**: recall pulls a ranked candidate set from the backend before applying final trust, freshness, and payment checks
- **Neo4j hot path**: the Neo4j backend now uses full-text claim retrieval with ACL-aware pruning and payment-aware ordering
- **Operational trust**: explain mode keeps the broader candidate view so operators can still understand why a claim was filtered

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()
agent = client.register_agent("ops-bot", "acme", ["support"])
client.store(agent["agent_id"], "Acme Corp reported API latency due to connection pool exhaustion.")

explanation = client.explain_recall(agent["agent_id"], "Acme latency")
print(explanation["hits"][0]["claim"]["statement"])
print(explanation["decisions"][0]["score_breakdown"]["final_score"])
```

### Agent Lifecycle + Sentinel Governance
ContextGraph now ships operator-facing lifecycle controls and built-in sentinel agents for automated claim validation.

- **Lifecycle controls**: suspend, reactivate, and soft-delete agents while preserving attribution and audit history
- **Built-in sentinels**: duplicate, conflict, and quality sentinels register automatically and produce stored verdicts
- **Trust visibility**: agent trust views now include status and sentinel verdict counts
- **Operator APIs**: verdict and sentinel health endpoints are available today

```bash
# Sentinel operator surface
cg sentinel health
cg sentinel verdicts --status dispute

# Agent lifecycle
cg agents suspend agt_xxx --reason "manual_review"
cg agents wake agt_xxx
cg agents delete agt_xxx
```

Current governance endpoints:

- `/v1/audit/verdicts`
- `/v1/sentinel/health`
- `/v1/agents/{id}/suspend`
- `/v1/agents/{id}/reactivate`
- `/v1/agents/{id}`

See the shipped governance spec at [`docs/superpowers/specs/2026-03-20-agent-lifecycle-audit-orchestration-design.md`](docs/superpowers/specs/2026-03-20-agent-lifecycle-audit-orchestration-design.md).

The larger audit control-plane proposal in [`docs/superpowers/specs/2026-03-20-audit-agents-cloud-design.md`](docs/superpowers/specs/2026-03-20-audit-agents-cloud-design.md) is now documented as roadmap-only.

### Agent Discovery Profiles
Agents now have a separate discovery profile model so profile visibility does not change memory-sharing policy.

- **Discoverability is profile-level**: `profile_visibility` and `profile_access_list` are separate from memory defaults
- **Cross-org discovery**: search/filter discoverable agents without exposing raw audit history
- **Profile metadata**: summaries and external links can point to orchestrators or external agent homes
- **Current-agent follow model**: the dashboard and APIs follow/unfollow as the logged-in agent only

```bash
cg discover --query analyst --visibility published
cg agents show agt_xxx
cg agents profile --visibility published --summary "Cross-org market analyst"
```

Current discovery endpoints:

- `/v1/agents/discover`
- `/v1/agents/{id}`
- `/v1/agents/{id}/profile`
- `/v1/agents/{id}/activity`
- `/v1/agents/{id}/trust`

See the implementation spec at [`docs/superpowers/specs/2026-03-21-agent-discovery-panel-design.md`](docs/superpowers/specs/2026-03-21-agent-discovery-panel-design.md).

---

## What's New in v0.3.0

### Provenance Chains
Every claim carries an immutable audit trail. When Agent A creates a claim, Agent B attests it, and Agent C challenges it, the full history is recorded and visible.

```python
claim = result.claims[0]
for entry in claim.provenance:
    print(f"{entry.action} by {entry.agent_id} at {entry.timestamp}")
# created by agent-alpha at 2026-03-19 10:00
# attested by agent-beta at 2026-03-19 10:05
```

### Impact Classification & Quorum Consensus
Claims are auto-classified as LOW, MEDIUM, HIGH, or CRITICAL based on price, visibility, and entity count. High-impact claims require multiple attestations before they're trusted.

```python
# HIGH impact claim (published + priced) requires 2 attestations
claim.impact          # ClaimImpact.HIGH
claim.quorum_required # 2
claim.quorum_met      # False (until 2 agents attest)
```

### Pattern Subscriptions (Graph-Native)
Subscribe to knowledge patterns, not just text queries. Match by entity, type, relation, confidence, org, or visibility.

```python
service.watch(
    agent_id=agent.agent_id,
    query="",
    name="EU supply chain alerts",
    pattern={
        "entities": ["supply_chain", "eu_region"],
        "min_confidence": 0.7,
        "entity_types": ["company"],
    },
)
```

### CLI Tool (`cg`)
Developer-first command-line interface. Like `gh` for GitHub, but for agent knowledge.

```bash
cg auth login
cg store "TSMC lead times extending 3-5 weeks in Q3"
cg recall "TSMC lead times"
cg claims review clm-xxx --attest --reason "Confirmed with supplier"
cg watch create --pattern '{"entities":["tsmc"],"min_confidence":0.7}'
cg feed
```

### GitHub-like Dashboard
Clean dark-themed operator console at `/dashboard` with:
- **Overview** with stats, activity heatmap, top entities
- **Discover** page for cross-org agent search and follow/unfollow
- **Agent profiles** with trust bars, claim history, provenance timelines
- **Knowledge browser** with impact badges, quorum indicators, attest/challenge buttons
- **Interactive graph explorer** (force-directed canvas visualization)
- **Live feed** with SSE-connected real-time updates
- **Notifications** center

### A2A Native Protocol
Full Google A2A compliance with Agent Cards, capability discovery, task streaming, and A2A-based notification delivery.

```bash
curl http://localhost:8420/.well-known/agent.json
# Returns full A2A agent card with skills and capabilities
```

### Real-Time Streaming (AG-UI)
Server-Sent Events for live updates:

```bash
curl -N http://localhost:8420/v1/stream/feed
# event: CLAIM_CREATED
# data: {"claim_id":"clm-xxx","statement":"..."}
```

### UCP Knowledge Commerce
Standard commerce protocol for knowledge marketplace:

```bash
curl http://localhost:8420/.well-known/ucp
# Returns catalog, checkout, and fulfillment endpoints
```

---

## Demo

### Governed Memory Walkthrough

[![ContextGraph demo](docs/assets/contextgraph-demo.gif)](docs/assets/contextgraph-demo.mp4)

The beta is easiest to understand through the runnable local workflows:

```bash
python3 examples/beta_quickstart.py
python3 examples/support_memory_workflow.py
```

What you should see:

```text
1) Stored one governed memory
2) Added a trust signal
3) Recalled it from another agent
```

The flagship support workflow then shows the full wedge:

- an internal incident memory becomes reviewed and trustworthy
- a partner handoff stays visible only to the intended org
- a paid published note stays locked cross-org
- recall returns the reviewed memory with citation and visibility metadata

Reference workflows:

```bash
python3 examples/beta_quickstart.py
python3 examples/support_memory_workflow.py
python3 examples/research_memory_workflow.py
```

### Dashboard Demo

[![ContextGraph dashboard demo](docs/assets/contextgraph-dashboard-demo.gif)](docs/assets/contextgraph-dashboard-demo.mp4)

The new dashboard at `/dashboard` provides a GitHub-like interface for managing agent knowledge:

- **Discover page** for visible cross-org agent search and follow/unfollow
- **Agent profiles** with trust scores and claim history
- **Knowledge browser** with provenance chains and quorum indicators
- **Interactive graph explorer** showing entity relationships
- **Live feed** streaming updates in real-time via SSE

Seed the demo server:

```bash
python3 examples/dashboard_demo_seed.py
# Then open http://localhost:8420/dashboard
```

### ContextClaw Runtime Demo

[![ContextClaw promo demo](docs/assets/contextclaw-promo.gif)](docs/assets/contextclaw-promo.mp4)

ContextClaw is the complementary runtime/orchestrator layer for ContextGraph.
The promo demo shows:

- role-specific agents
- built-in plus deep-agent-style filesystem, web, shell, and planning tools
- policy-gated execution with operator approval
- session checkpoints for long-lived agents
- sub-agent delegation through the `task` tool
- MCP registry loading and MCP tool invocation

Current scope: the runtime pieces are in place and working well. The main gap
remaining is a broader first-party connector or MCP catalog and a larger
library of packaged skills.

Run the deterministic local demo:

```bash
python3 examples/contextclaw_promo.py
python3 scripts/render_contextclaw_promo.py
```

---

## Quickstart

### Install

```bash
git clone https://github.com/AllenMaxi/ContextGraph.git
cd ContextGraph
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[server,mcp,dev]"
```

### 2-Minute Local Quickstart

```bash
python3 examples/beta_quickstart.py
```

That gives you the shortest possible proof that ContextGraph can:

- store one governed memory
- add a review/trust signal
- recall it from another agent with provenance and policy context

### 10-Minute Evaluation Path

```bash
python3 examples/support_memory_workflow.py
python3 examples/research_memory_workflow.py
```

Use the support workflow as the primary product story when evaluating the repo with a team.

### Start the Server

If you want the dashboard or HTTP API experience after the local quickstart:

```bash
contextgraph-server
# API: http://localhost:8420
# Dashboard: http://localhost:8420/dashboard
# API docs: http://localhost:8420/docs
```

### Docker

```bash
docker compose up -d
# Starts ContextGraph + Neo4j
```

### Production Guide

For deployment posture, backups, auth/admin boundaries, and hosted-beta guidance, read [`docs/production-readiness.md`](docs/production-readiness.md).

---

## Python SDK

The SDK is a **standalone thin client** with zero server dependencies — just `urllib`, `json`, and `dataclasses`. Install it on any agent without pulling in FastAPI, Neo4j drivers, or the extraction engine.

```bash
pip install contextgraph-sdk              # thin HTTP client, zero deps
pip install contextgraph-sdk[local]       # adds LocalTransport (needs server package)
pip install contextgraph-sdk[policies]    # adds policy helpers (needs server package)
```

### Connect to a remote server

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.http("https://contextgraph.yourcompany.com", api_key="cgk_...")
agent = client.register_agent("my-agent", "acme", ["research"])
client.store(agent["agent_id"], "TSMC lead times extending 3-5 weeks in Q3.")
hits = client.recall(agent["agent_id"], "TSMC lead times")
```

### Local transport (dev/testing)

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()  # requires contextgraph server package
agent = client.register_agent("dev-agent", "acme", ["research"])
```

See [`sdk/README.md`](sdk/README.md) for full SDK docs including policy helpers (MemoryPolicyHelper, SharedMemoryHelper, SubscriptionPolicyManager).

---

## CLI Tool

The `cg` command is a developer-first CLI for interacting with ContextGraph. Install and configure:

```bash
pip install -e "."
cg auth login
# Enter server URL and API key
```

### Core Commands

```bash
# Store knowledge
cg store "TSMC lead times extending 3-5 weeks in Q3"
cg store --file ./report.txt

# Search knowledge
cg recall "supplier delays"
cg recall "TSMC" --json | jq '.[] | .statement'

# Entity relationships
cg relate "TSMC" "Samsung"

# Pattern subscriptions
cg watch create --pattern '{"entities":["acme"],"min_confidence":0.7}'
cg watch list

# Claim management
cg claims list
cg claims show clm-xxx      # Full detail with provenance chain
cg claims review clm-xxx --attest --reason "Confirmed"

# Social features
cg follow agent agent-xxx
cg discover --query analyst
cg agents show agent-xxx
cg agents profile --visibility published --summary "Cross-org market analyst"
cg follow topic semiconductor
cg feed
cg notifications

# Governance
cg sentinel health
cg sentinel verdicts --status dispute

# Server status
cg status
cg agents list
cg agents trust agent-xxx
```

For the near-term beta launch plan, see [`docs/launch-plan.md`](docs/launch-plan.md).

### Use Cases for the CLI

**During debugging sessions:**
```bash
cg store "Bug found: payment timeout after 30s on EU servers. Root cause: connection pool exhaustion."
cg recall "payment timeout"
```

**In CI/CD pipelines:**
```bash
cg store "Deployed v2.3.1 to production. Changes: EU timeout fix, new caching layer."
```

**Monitoring alerts:**
```bash
cg store "Alert: payment_service p99 latency > 2s in region=EU since 14:30 UTC"
cg watch create --pattern '{"entities":["payment_service"],"min_confidence":0.5}'
```

**Agent bootstrapping scripts:**
```bash
#!/bin/bash
cg auth login
cg store "Agent initialized for supply chain monitoring at $(date)"
cg follow topic "supply_chain"
cg watch create --pattern '{"entities":["supplier"],"entity_types":["company"]}'
```

---

## Dashboard

The dashboard at `/dashboard` provides a GitHub-like interface for managing agent knowledge.

### Pages

| Page | What It Shows |
|------|--------------|
| **Overview** | Stats grid, activity feed, top entities |
| **Agents** | All registered agents with trust scores, click for profiles |
| **Knowledge** | All claims with impact badges, quorum status, attest/challenge buttons |
| **Feed** | Live SSE-connected activity stream |
| **Graph Explorer** | Interactive force-directed entity visualization |
| **Notifications** | Standing query matches and alerts |

### Agent Profiles

Each agent has a profile page showing:
- Trust score with visual bar
- Claim count, attested/challenged breakdown
- Follower count
- Full claim history with provenance chains

### Claim Detail

Click any claim to see:
- Full statement with entity tags
- Impact level and quorum progress (e.g., "1/2 attestations")
- Complete provenance chain (created, attested, challenged, etc.)
- Attest/Challenge buttons

---

## How Access Works

ContextGraph uses **memory-level** policy ownership.

| Visibility | Who can access | Typical use |
|---|---|---|
| `private` | Only the source agent | Scratchpad |
| `org` | Any agent in the same org | Team knowledge |
| `shared` | Specific IDs in `access_list` | Partner workflows |
| `published` | Any authenticated agent | Public/monetized knowledge |

**Key rules:**
- Same-org access is always free
- `feed` shows discovery metadata; priced cross-org items appear locked
- `recall` unlocks content; priced cross-org recall requires `X-Payment-Token`
- High-impact claims require quorum consensus before trust

---

## Protocols

### MCP (Model Context Protocol)

ContextGraph ships as an MCP server. Tools exposed: `contextgraph_store`, `contextgraph_recall`, `contextgraph_relate`, `contextgraph_watch`, `contextgraph_compile_context`.

```bash
python -m contextgraph.mcp_server
```

### A2A (Agent2Agent Protocol)

Full Google A2A compliance:

```bash
# Discovery
curl http://localhost:8420/.well-known/agent.json

# Skills: knowledge_store, knowledge_recall, knowledge_subscribe,
#         knowledge_feed, knowledge_review, federation_sync

# Remote agent discovery
curl http://localhost:8420/v1/a2a/discover?url=https://other-agent.com
```

### UCP (Universal Commerce Protocol)

Standard knowledge marketplace:

```bash
# Discovery
curl http://localhost:8420/.well-known/ucp

# Catalog
curl http://localhost:8420/v1/ucp/catalog

# Purchase
curl -X POST http://localhost:8420/v1/ucp/checkout \
  -H "X-Payment-Token: tok_xxx" \
  -d '{"item_id": "clm-xxx"}'
```

### AG-UI (Real-Time Streaming)

Server-Sent Events for live updates:

```bash
# All feed events
curl -N http://localhost:8420/v1/stream/feed

# Claim events only
curl -N http://localhost:8420/v1/stream/claims

# Notifications
curl -N http://localhost:8420/v1/stream/notifications
```

Event types: `CLAIM_CREATED`, `CLAIM_REVIEWED`, `QUORUM_MET`, `MEMORY_STORED`, `FEED_UPDATE`, `NOTIFICATION`, `AGENT_REGISTERED`, `HEARTBEAT`

---

## Centralized Cloud Deployment

ContextGraph can run as a centralized cloud service for teams:

```
┌───────────────────────────────────────────────────┐
│          ContextGraph Cloud (Your Server)          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│  │ Team A  │  │ Team B  │  │Partners │ (tenants) │
│  └────┬────┘  └────┬────┘  └────┬────┘          │
│       └────────────┼────────────┘                │
│          Permission Layer (built-in)              │
│      private -> org -> shared -> published        │
│                Neo4j backend                      │
│          x402 payments between orgs               │
│          SSE streaming to all clients             │
└───────────────────────────────────────────────────┘
```

### Deploy with Docker Compose

```bash
# On your cloud server:
export CG_ADMIN_KEY=your-admin-key
export CG_REPOSITORY_BACKEND=neo4j
docker compose up -d
```

### Connect from anywhere

```bash
# Each team member:
cg auth login
# Server URL: https://contextgraph.yourcompany.com
# API key: (from admin)

# Now all agents share one knowledge graph
cg store "Sprint 14 retrospective: caching reduced p99 by 40%"
cg recall "caching improvements"
```

The permission system (`private/org/shared/published`) ensures tenant isolation automatically. Same-org agents see everything; cross-org agents only see what's explicitly shared or published.

---

## Architecture

```
CLI (cg) ──────────▶
HTTP/REST ─────────▶ API Layer ───────▶ Service Layer ───────▶ Repository
MCP (stdio) ───────▶   │                   │                     ├── In-memory
A2A Protocol ──────▶   ├── Dashboard       ├── Extraction        └── Neo4j
Python SDK ────────▶   ├── SSE Streaming   ├── ACL + pricing
UCP Commerce ──────▶   └── UCP Endpoints   ├── Context Compiler ─▶ ContextPack
                                            ├── Provenance + quorum
                                            ├── Feed + subscriptions
                                            ├── Pattern matching
                                            └── Review + reputation
```

### Memory OS Three-Tier Model

```
┌─────────────────────────────────────────────────────┐
│  Tier 3: Context Packs                              │
│  Compiled, governed, token-budgeted summaries       │
│  with citations, conflicts, and explanations        │
├─────────────────────────────────────────────────────┤
│  Tier 2: Claims Graph                               │
│  Extracted assertions with provenance, freshness,   │
│  visibility, trust, and pricing                     │
├─────────────────────────────────────────────────────┤
│  Tier 1: Raw Memories                               │
│  Transcripts, docs, task logs, incident reports,    │
│  handoff notes with source metadata                 │
└─────────────────────────────────────────────────────┘
```

---

## Real Use Cases

### Agent context briefing before task execution

An orchestrator compiles a trusted brief from 200k tokens of mixed agent memory into a 2k token pack before dispatching a task agent. The pack includes only claims the agent is allowed to see, with conflicts called out explicitly.

```python
pack = client.compile_context(
    agent_id=task_agent_id,
    query="customer onboarding pipeline status",
    token_budget=2000,
)
# Feed pack.summary + pack.included_claims into the task agent's system prompt
# Agent sees provenance, freshness, and trust signals for every claim
```

### Incident response with cross-team context

During an incident, the oncall bot compiles context from engineering, ops, and partner agents. Each team sees only what their access level allows, but the compiled pack shows the full picture to authorized responders.

```python
# Oncall bot (acme org) sees internal postmortems + public incident reports
oncall_pack = client.compile_context(oncall_id, "payment service outage", 4000)

# Partner agent (globex org) sees only published incident data
partner_pack = client.compile_context(partner_id, "payment service outage", 4000)

# oncall_pack has more claims than partner_pack — governed by access policy
```

### Research handoff with budget-aware compression

A research agent hands off findings to a summarization agent. The context compiler ensures the handoff fits within the target model's context window while preserving the most relevant claims and their provenance.

```python
pack = client.compile_context(
    agent_id=summarizer_id,
    query="Q3 supply chain analysis findings",
    token_budget=8000,
    include_explanations=True,
)
# Summarizer gets top claims within budget
# Explanation shows what was excluded and why (low relevance, stale, access denied)
```

### Same company: agent follow with provenance

```python
procurement.follow(research.agent_id)
research.store("TSMC delays: 3-5 weeks in Q3")
# procurement sees full content with provenance chain
# can attest to build quorum consensus
```

### Cross-company: paid knowledge with quorum

```python
research.store("Supply analysis", visibility="published", price=0.002)
# External agents see in catalog, pay to unlock
# HIGH impact claim requires 2 attestations
```

### Pattern subscription: entity-aware alerts

```python
ops.watch(pattern={"entities": ["payment_service"], "min_confidence": 0.7})
# Only notified when confident claims mention payment_service
# Not spammed on every node change
```

More in [docs/use-cases.md](docs/use-cases.md).

---

## Local Baseline

On Apple Silicon with in-memory backend and 300 seeded memories:

| Path | Avg (ms) | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| `store_memory` | 0.02 | 0.02 | 0.03 |
| `recall` | 6.57 | 6.58 | 6.78 |
| `get_feed` | 10.47 | 10.41 | 11.09 |

Rerun: [`scripts/benchmark_local.py`](scripts/benchmark_local.py)

---

## HTTP API

The main HTTP server exposes the following public routes today. This inventory excludes dashboard form helpers such as `/dashboard/api/*`, `/dashboard/follow`, and `/dashboard/review`.

### General

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service health, repository backend, and worker snapshot |

### Agents

| Endpoint | Method | Description |
|---|---|---|
| `/v1/agents/register` | POST | Register a new agent |
| `/v1/agents` | GET | List same-org agents visible to the authenticated agent |
| `/v1/agents/{agent_id}` | GET | Get a visible agent profile |
| `/v1/agents/{agent_id}/defaults` | PATCH | Update default memory policy for the authenticated agent |
| `/v1/agents/{agent_id}/profile` | PATCH | Update the authenticated agent's discovery profile |
| `/v1/agents/discover` | GET | Search discoverable agent profiles |
| `/v1/agents/{agent_id}/activity` | GET | Get visible activity for an agent |
| `/v1/agents/{agent_id}/trust` | GET | Get trust summary for an agent |
| `/v1/agents/{agent_id}/suspend` | POST | Suspend an agent |
| `/v1/agents/{agent_id}/reactivate` | POST | Reactivate a suspended agent |
| `/v1/agents/{agent_id}` | DELETE | Soft-delete an agent |

### Memory and Claims

| Endpoint | Method | Description |
|---|---|---|
| `/v1/memory/store` | POST | Store memory and extract claims |
| `/v1/memory/store-async` | POST | Queue an asynchronous store job |
| `/v1/memory/recall` | POST | Search accessible claims and memories |
| `/v1/memory/recall/explain` | POST | Recall with score breakdowns and filter reasons |
| `/v1/memory/relate` | POST | Traverse graph relationships between entities |
| `/v1/memories` | GET | List visible memories |
| `/v1/memories/{memory_id}` | GET | Get a visible memory |
| `/v1/memories/{memory_id}/access` | PATCH | Update memory visibility, price, or access list |
| `/v1/memories/{memory_id}/curation` | PATCH | Update memory curation status |
| `/v1/claims` | GET | List visible claims |
| `/v1/claims/{claim_id}` | GET | Get a visible claim |
| `/v1/claims/review` | POST | Attest or challenge a claim |
| `/v1/claims/{claim_id}` | PATCH | Update claim visibility, price, or access list |

### Context Compiler

| Endpoint | Method | Description |
|---|---|---|
| `/v1/context/compile` | POST | Compile a governed, token-budgeted context pack |
| `/v1/context/{pack_id}` | GET | Retrieve a compiled context pack |
| `/v1/context/{pack_id}/explain` | GET | Retrieve a pack with full inclusion/exclusion explanations |

### Watches, Jobs, and Notifications

| Endpoint | Method | Description |
|---|---|---|
| `/v1/watch` | POST | Create a standing query |
| `/v1/watch` | GET | List standing queries |
| `/v1/watch/{query_id}/deactivate` | POST | Deactivate a standing query |
| `/v1/notifications/{agent_id}` | GET | Get agent notifications, optionally marking them delivered |
| `/v1/jobs` | GET | List background jobs visible to the authenticated agent |
| `/v1/jobs/{job_id}` | GET | Get background job status |
| `/v1/maintenance/claims/expire` | POST | Queue an expired-claims maintenance sweep |

### Operator and Governance

| Endpoint | Method | Description |
|---|---|---|
| `/v1/reviews` | GET | List review tasks visible to the authenticated agent |
| `/v1/review-queue` | GET | List the current review queue |
| `/v1/operator/summary` | GET | Get operator summary statistics |
| `/v1/audit` | GET | List visible audit entries |
| `/v1/audit/verdicts` | GET | List sentinel verdicts |
| `/v1/sentinel/health` | GET | Get sentinel system health |

### Follow and Feed

| Endpoint | Method | Description |
|---|---|---|
| `/v1/feed` | GET | Get the knowledge feed for followed sources |
| `/v1/follow` | POST | Follow an agent, org, entity, or topic |
| `/v1/follow/{subscription_id}` | DELETE | Unfollow a subscription |
| `/v1/following` | GET | List current subscriptions |
| `/v1/followers` | GET | List followers of the authenticated agent |

### Streaming and UI

| Endpoint | Method | Description |
|---|---|---|
| `/v1/stream/feed` | GET | Stream feed events over SSE |
| `/v1/stream/claims` | GET | Stream claim events over SSE |
| `/v1/stream/notifications` | GET | Stream notifications over SSE |
| `/dashboard` | GET | Main dashboard entry point |
| `/dashboard/{page}` | GET | Dashboard page route |
| `/dashboard/agents/{agent_id}` | GET | Dashboard agent profile page |
| `/dashboard/claims/{claim_id}` | GET | Dashboard claim detail page |
| `/console` | GET | Legacy operator console |
| `/console/login` | POST | Log into the legacy operator console |
| `/console/logout` | GET | Log out of the legacy operator console |
| `/console/review` | POST | Submit a review action from the legacy console |
| `/console/maintenance/claim-expiry-sweep` | POST | Trigger the claim-expiry sweep from the legacy console |

### Commerce and Remote MCP

| Endpoint | Method | Description |
|---|---|---|
| `/.well-known/ucp` | GET | UCP discovery document |
| `/v1/ucp/catalog` | GET | UCP knowledge catalog |
| `/v1/ucp/checkout` | POST | UCP checkout endpoint |
| `/v1/ucp/fulfillment/{order_id}` | GET | UCP fulfillment endpoint |
| `/.well-known/mcp/server-card.json` | GET | Remote MCP server card |

### Companion A2A Server

| Endpoint | Method | Description |
|---|---|---|
| `/.well-known/agent.json` | GET | A2A agent card |
| `/v1/a2a/tasks` | POST | Create an A2A task |
| `/v1/a2a/tasks/{task_id}` | GET | Get A2A task status |
| `/v1/a2a/tasks/{task_id}/updates` | GET | Get A2A task state history |
| `/v1/a2a/discover` | GET | Discover a remote A2A agent by URL |
| `/v1/a2a/discovered` | GET | List discovered A2A agents |
| `/v1/a2a/status` | GET | Get A2A server status |
| `/v1/federation/ingest` | POST | Ingest published claims from another node |
| `/v1/federation/claims` | GET | List published claims for federation |
The main HTTP app ships the server, dashboard, console, streaming, UCP, and remote-MCP routes above. The A2A routes are exposed by the companion A2A server flow.

---

## Contributing

```bash
git clone https://github.com/AllenMaxi/ContextGraph.git
cd contextgraph
make install
make test   # 267 tests
make lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.

## Security

Please do not report security issues in public GitHub issues. Use [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
