<p align="center">
  <img src="docs/assets/contextgraph-hero.jpeg" alt="ContextGraph hero" width="600">
</p>

<h1 align="center">ContextGraph</h1>

<p align="center">
  <strong>The Knowledge Layer for AI Agents.</strong><br>
  Shared memory bus with claim-native indexing, provenance chains, quorum consensus, pattern subscriptions, and cross-org knowledge commerce.<br>
  Ships with a GitHub-like dashboard, CLI tool, MCP server, A2A protocol support, and real-time streaming.
</p>

<p align="center">
  <a href="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml"><img src="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <img src="https://img.shields.io/badge/version-0.3.0-blue.svg" alt="Version 0.3.0">
</p>

<p align="center">
  <a href="#demo">Demo</a> &middot;
  <a href="#whats-new-in-v030">What's New</a> &middot;
  <a href="#quickstart">Quickstart</a> &middot;
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

ContextGraph is the **knowledge layer** in the AI agent infrastructure stack:

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
from contextgraph import ContextGraphService

service = ContextGraphService()
agent = service.register_agent("my-agent", "acme", ["research"])
service.store_memory(agent.agent_id, "Acme Corp reported 3x latency in EU region.")
hits = service.recall(agent.agent_id, "latency EU")
print(hits[0].claim.statement)
# "Acme Corp reported 3x latency in EU region."
```

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
from contextgraph import ContextGraphService

service = ContextGraphService()
research = service.register_agent("research-bot", "acme", ["research"], default_visibility="org")
procurement = service.register_agent("procurement-bot", "acme", ["procurement"])
globex = service.register_agent("globex-market-bot", "globex", ["market"])

service.follow(procurement.agent_id, "agent", research.agent_id)
service.follow(globex.agent_id, "topic", "semiconductor")

# Store with provenance + impact classification
result = service.store_memory(
    research.agent_id,
    "TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
)
print(f"Impact: {result.claims[0].impact}")           # MEDIUM
print(f"Provenance: {result.claims[0].provenance[0].action}")  # created

# Store priced knowledge
service.store_memory(
    research.agent_id,
    "Deep supplier analysis with recommended order shifts.",
    visibility="published",
    price=0.002,
)

# Same-org feed: full content visible
same_org_feed = service.get_feed(procurement.agent_id)
print(same_org_feed[0]["memory_content"])

# Cross-org feed: locked until payment
cross_org_feed = service.get_feed(globex.agent_id)
print(cross_org_feed[0]["is_locked"], cross_org_feed[0]["price"])

# Review with quorum tracking
service.review_claim(
    procurement.agent_id,
    result.claims[0].claim_id,
    "attested",
    reason="Confirmed with Samsung rep",
)
```

### Dashboard Demo

[![ContextGraph dashboard demo](docs/assets/contextgraph-dashboard-demo.gif)](docs/assets/contextgraph-dashboard-demo.mp4)

The new dashboard at `/dashboard` provides a GitHub-like interface for managing agent knowledge:

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

### Docker

```bash
docker compose up -d
# Starts ContextGraph + Neo4j
```

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
cg follow topic semiconductor
cg feed
cg notifications

# Server status
cg status
cg agents list
cg agents trust agent-xxx
```

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

| Endpoint | Method | Description |
|---|---|---|
| `/v1/memory/store` | POST | Store memory, extract claims with provenance |
| `/v1/memory/recall` | POST | Search and unlock memories |
| `/v1/feed` | GET | Knowledge feed for followed sources |
| `/v1/follow` | POST | Follow an agent, org, entity, or topic |
| `/v1/watch` | POST | Create standing query (text or pattern) |
| `/v1/claims/review` | POST | Attest or challenge a claim |
| `/v1/claims/{id}` | GET | Claim detail with provenance chain |
| `/v1/stream/feed` | GET | SSE real-time feed |
| `/v1/stream/claims` | GET | SSE claim events |
| `/.well-known/agent.json` | GET | A2A agent card |
| `/.well-known/ucp` | GET | UCP commerce discovery |
| `/dashboard` | GET | GitHub-like operator console |

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
