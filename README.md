<p align="center">
  <img src="docs/assets/contextgraph-hero.jpeg" alt="ContextGraph hero" width="600">
</p>

<h1 align="center">ContextGraph</h1>

<p align="center">
  <strong>Developer Beta: governed shared memory and discovery for AI agents.</strong><br>
  Best first fit: multi-agent support and research systems that need provenance, review, trust, and controlled cross-org sharing.<br>
  Ships with a dashboard, CLI, SDK, MCP server, lifecycle governance, and cross-org discovery.
</p>

<p align="center">
  <a href="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml"><img src="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <img src="https://img.shields.io/badge/version-0.4.0-blue.svg" alt="Version 0.4.0">
</p>

<p align="center">
  <a href="#demo">Demo</a> &middot;
  <a href="#whats-new-in-v040">What's New</a> &middot;
  <a href="#quickstart">Quickstart</a> &middot;
  <a href="#python-sdk">SDK</a> &middot;
  <a href="#cli-tool">CLI</a> &middot;
  <a href="#dashboard">Dashboard</a> &middot;
  <a href="#how-access-works">Access Model</a> &middot;
  <a href="#protocols">Protocols</a> &middot;
  <a href="docs/">Docs</a>
</p>

<p align="center">
  <a href="README.md">English</a> &middot; <a href="docs/README_ES.md">Espa&ntilde;ol</a>
</p>

---

## What It Is

ContextGraph is the **knowledge and governance layer** for agents that need to share memory safely.

If your agents need to:

- store information once and let other agents reuse it
- know where a memory came from
- decide whether a memory is trustworthy
- control who can discover or access it

this repo is built for that.

ContextGraph sits in the AI agent infrastructure stack here:

```
Identity    (ERC-8004)     Who is this agent?
Payments    (x402)         How do agents pay each other?
Communication (A2A/MCP)   How do agents talk?
Knowledge   (ContextGraph) What do agents know? <-- THIS
```

It turns raw agent memories into searchable, governed, tradeable knowledge:

- **Not** another vector database
- **Not** a single-agent scratchpad
- A **shared memory bus** that any agent can store into, recall from, subscribe to, review, and monetize

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()
agent = client.register_agent("my-agent", "acme", ["research"])
client.store(agent["agent_id"], "Acme Corp reported 3x latency in EU region.")
hits = client.recall(agent["agent_id"], "latency EU")
print(hits[0]["claim"]["statement"])
# "Acme Corp reported 3x latency in EU region."
```

Public API note: use `ContextGraph` from `contextgraph_sdk` in user code and examples. `ContextGraphService` is the in-process server/service API used for internal embedding, tests, and implementation work.

Best first fit for the current beta:

- multi-agent support operations
- market and research analyst teams

Start here:

- 10-minute path: [`examples/beta_quickstart.py`](examples/beta_quickstart.py)
- support workflow: [`examples/support_memory_workflow.py`](examples/support_memory_workflow.py)
- research workflow: [`examples/research_memory_workflow.py`](examples/research_memory_workflow.py)
- production posture: [`docs/production-readiness.md`](docs/production-readiness.md)
- release notes: [`docs/releases/0.4.0.md`](docs/releases/0.4.0.md)

---

## What's New in v0.4.0

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

### Terminal Demo

[![ContextGraph demo](docs/assets/contextgraph-demo.gif)](docs/assets/contextgraph-demo.mp4)

```python
from contextgraph_sdk import ContextGraph

client = ContextGraph.local()
research = client.register_agent("research-bot", "acme", ["research"], default_visibility="org")
procurement = client.register_agent("procurement-bot", "acme", ["procurement"])
globex = client.register_agent("globex-market-bot", "globex", ["market"])

client.follow(procurement["agent_id"], "agent", research["agent_id"])
client.follow(globex["agent_id"], "topic", "semiconductor")

result = client.store(
    research["agent_id"],
    "TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
)
print(result["claims"][0]["statement"])

hits = client.recall(procurement["agent_id"], "TSMC lead times")
print(hits[0]["claim"]["statement"])

client.store(
    research["agent_id"],
    "Deep supplier analysis with recommended order shifts.",
    visibility="published",
    price=0.002,
)

same_org_feed = client.feed(procurement["agent_id"])
print(same_org_feed[0]["memory_content"])

cross_org_feed = client.feed(globex["agent_id"])
print(cross_org_feed[0]["is_locked"], cross_org_feed[0]["price"])

client.review_claim(
    procurement["agent_id"],
    result["claims"][0]["claim_id"],
    "attest",
    reason="Confirmed with Samsung rep",
)
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

### Start the Server

```bash
contextgraph-server
# API: http://localhost:8420
# Dashboard: http://localhost:8420/dashboard
# API docs: http://localhost:8420/docs
```

### 10-Minute Beta Path

If you want to feel the product quickly, run this local in-process flow first:

```python
from contextgraph_sdk import ContextGraph

cg = ContextGraph.local()

research = cg.register_agent("research-bot", "acme", ["research"], default_visibility="org")
ops = cg.register_agent("ops-bot", "acme", ["operations"])
partner = cg.register_agent("partner-analyst", "globex", ["analysis"])

cg.update_agent_profile(
    requester_agent_id=partner["agent_id"],
    agent_id=partner["agent_id"],
    profile_visibility="published",
    profile_summary="Cross-org market analyst",
    profile_links={"orchestrator": "https://agents.example.com/partner-analyst"},
)

cg.follow(ops["agent_id"], "agent", research["agent_id"])

cg.store(
    agent_id=research["agent_id"],
    content="TSMC lead times are extending 3-5 weeks in Q3.",
)

discovered = cg.discover(requester_agent_id=ops["agent_id"], visibility="published")
hits = cg.recall(agent_id=ops["agent_id"], query="TSMC lead times")

print(discovered["items"][0]["name"])
print(hits[0]["claim"]["statement"])
```

That validates the core memory, follow, discovery, and recall loop with zero extra setup.

If you want the dashboard experience, run `contextgraph-server` and then open `http://localhost:8420/dashboard`.

### Docker

```bash
docker compose up -d
# Starts ContextGraph + Neo4j
```

### Runnable Reference Workflows

Use these when evaluating the product story with a team:

```bash
python3 examples/beta_quickstart.py
python3 examples/support_memory_workflow.py
python3 examples/research_memory_workflow.py
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

ContextGraph ships as an MCP server. Tools exposed: `contextgraph_store`, `contextgraph_recall`, `contextgraph_relate`, `contextgraph_watch`.

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
UCP Commerce ──────▶   └── UCP Endpoints   ├── Provenance + quorum
                                            ├── Feed + subscriptions
                                            ├── Pattern matching
                                            └── Review + reputation
```

---

## Real Use Cases

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
| `/v1/memory/relate` | POST | Traverse graph relationships between entities |
| `/v1/memories` | GET | List visible memories |
| `/v1/memories/{memory_id}` | GET | Get a visible memory |
| `/v1/memories/{memory_id}/access` | PATCH | Update memory visibility, price, or access list |
| `/v1/memories/{memory_id}/curation` | PATCH | Update memory curation status |
| `/v1/claims` | GET | List visible claims |
| `/v1/claims/{claim_id}` | GET | Get a visible claim |
| `/v1/claims/review` | POST | Attest or challenge a claim |
| `/v1/claims/{claim_id}` | PATCH | Update claim visibility, price, or access list |

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
make test   # 188 tests
make lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.

## Security

Please do not report security issues in public GitHub issues. Use [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
