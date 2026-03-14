# ContextGraph Protocol — Team Summary

**Date:** 2026-03-07
**Author:** Maximilian Allende
**For:** Team review & alignment

---

## What Are We Building?

ContextGraph is an **open-source protocol** that gives AI agents a shared knowledge graph memory — and lets them **buy and sell knowledge** from each other using crypto payments.

Think of it as **"The Graph, but for agent memory."**

Today, AI agents store memories as flat text chunks in isolated databases. They can't share what they learn, they can't discover what other agents know, and they can't trade knowledge. We fix all of that.

---

## Why Now?

Four things just happened that make this the right moment:

| What | When | Why It Matters |
|---|---|---|
| **ERC-8004** went live on Ethereum | Jan 29, 2026 | AI agents now have verifiable on-chain identities. 24,000+ already registered. |
| **x402** hit $50M+ in volume | Q1 2026 | Agents can pay each other instantly via HTTP. The payment rails work. |
| **A2A protocol** SDK released | Feb 20, 2026 | Google's agent-to-agent communication standard is now easy to integrate. |
| **NIST** announced AI Agent Standards | Feb 17, 2026 | The US government is backing agent interoperability. Regulatory tailwind. |

The infrastructure stack is forming: Identity (ERC-8004) + Payments (x402) + Communication (A2A/MCP) + **??? (Knowledge Layer)**

That missing layer is what we're building.

---

## The Problem

Every competitor in the agent memory space has the same limitation:

| Competitor | Funding | What They Do | What They Don't Do |
|---|---|---|---|
| **Cognee** | EUR 7.5M (Feb 2026) | Knowledge graphs for internal agent memory | No cross-org sharing, no payments, no network |
| **Mem0** | Well-funded | Flat memory with bolt-on graph | No identity, no monetization |
| **Zep / Graphiti** | Open source | Real-time knowledge graphs | No identity, no payments, no marketplace |
| **Letta (MemGPT)** | Well-funded | Stateful agent memory | Locked to their runtime |
| **AINFT** | Crypto-backed | x402 + ERC-8004 integration | DeFi-focused, no knowledge graphs |

**Nobody is combining knowledge graphs + agent identity + programmatic payments.**

---

## How It Works

### For a Single Team (Phase 1 — Open Source)

```
Your Agent A                    ContextGraph                     Your Agent B
     |                              |                                 |
     | store("Acme Corp reported    |                                 |
     |  API latency issues. Their   |                                 |
     |  CTO Jane wants a fix")      |                                 |
     | ---------------------------> |                                 |
     |                              |                                 |
     |    Extracts entities:        |                                 |
     |    (Acme Corp) --CTO--> (Jane)                                 |
     |    (Acme Corp) --HAS_ISSUE--> (API Latency)                    |
     |    Stores as knowledge graph |                                 |
     |                              |                                 |
     |                              |    recall("Acme Corp problems") |
     |                              | <-------------------------------|
     |                              |                                 |
     |                              |    Returns: Acme Corp → Jane,   |
     |                              |    API Latency, CTO relationship|
     |                              | ------------------------------->|
```

Agents store raw text. ContextGraph uses an LLM to extract entities and relationships, stores them as a knowledge graph in Neo4j, and lets any authorized agent query with semantic search + graph traversal.

### For the Agent Economy (Phase 3+ — The Network)

```
Agent A (Buyer)                  ContextGraph Network              Agent B (Seller)
     |                                   |                               |
     | "Who knows about RWA risks?"      |                               |
     | --------------------------------> |                               |
     |                                   | Agent B has relevant knowledge|
     | <-------------------------------- |                               |
     |                                   |                               |
     | recall("RWA risks in EU")         |                               |
     | --------------------------------> | Forward to Agent B ---------->|
     |                                   |                               |
     |                                   | HTTP 402: Pay $0.002 USDC <---|
     |                                   |                               |
     | x402 payment (USDC on Base) ----> | Settle payment -------------->|
     |                                   |                               |
     | Knowledge subgraph returned <---- | Return knowledge <------------|
     |                                   |                               |
     | rate(Agent B, score=5) ---------> | Update ERC-8004 reputation    |
```

Agents discover knowledge they need, pay for it instantly via x402, receive structured knowledge graphs, and rate the transaction on-chain.

---

## Tech Stack

### Core Engine

| Component | Technology | Why This One |
|---|---|---|
| Language | **Python 3.11+** | AI/ML ecosystem, async support |
| API | **FastAPI** | Async, auto OpenAPI docs, x402 middleware support |
| Graph DB | **Neo4j 5.x** | Native graph + vector search in one DB |
| LLM (extraction) | **Claude Sonnet 4.6** | Best structured output for entity extraction |
| Embeddings | **sentence-transformers** (local) | Privacy-first, no API dependency |
| Cache / Queue | **Redis + Celery** | Caching, rate limiting, background jobs |
| Package Manager | **uv** | Fastest Python dependency management |

### Blockchain / Web3

| Component | Technology | Why This One |
|---|---|---|
| Agent Identity | **ERC-8004** via web3.py | On-chain identity + reputation for agents |
| Payments | **x402** Python SDK | HTTP-native micropayments, USDC |
| Target Chain | **Base** (Coinbase L2) | Low gas, where x402 + 8004 activity lives |
| Metadata Storage | **IPFS** | Decentralized agent card hosting |

### Agent Protocols

| Component | Technology | Why This One |
|---|---|---|
| Agent-to-Agent | **A2A SDK** (Google, v0.3.0) | Industry standard for agent communication |
| Agent-to-Tool | **MCP** (Anthropic) | 97M+ monthly downloads, Claude-native |

### Infrastructure

| Component | Technology |
|---|---|
| Containers | Docker + Docker Compose (dev), Kubernetes (prod) |
| CI/CD | GitHub Actions |
| Cloud | AWS EKS or Railway (early stage) |
| Monitoring | Prometheus + Grafana |
| Testing | pytest, testcontainers, locust (load) |
| Linting | ruff + mypy |

---

## Product Layers

```
Layer 3: THE NETWORK (Public Knowledge Marketplace)
         Agents across organizations discover & trade knowledge
         Revenue: 3% fee on x402 transactions
         THIS IS THE BUSINESS
         |
Layer 2: THE PROTOCOL (Cross-Agent Sharing + Identity)
         ERC-8004 identity for every agent
         x402 payments for knowledge access
         A2A/MCP for interoperability
         |
Layer 1: THE ENGINE (Open Source Core)
         Neo4j knowledge graph + vector search
         LLM entity extraction
         store() / recall() / relate()
         Self-hostable, MIT licensed
         THIS BUILDS THE COMMUNITY
```

---

## API Overview

### Core Endpoints

```
POST   /v1/memory/store         Store a memory (LLM extracts entities → graph)
POST   /v1/memory/recall        Query memories (vector search + graph traversal)
POST   /v1/memory/relate        Find paths between two entities
POST   /v1/agents/register      Register a new agent
```

### Marketplace Endpoints (Phase 3)

```
POST   /v1/marketplace/publish  Publish knowledge for sale
GET    /v1/marketplace/listings Browse available knowledge
POST   /v1/marketplace/recall   Buy knowledge (x402 payment required)
POST   /v1/marketplace/rate     Rate a transaction (→ ERC-8004 reputation)
```

### SDK Usage

```python
from contextgraph import ContextGraph

cg = ContextGraph(url="http://localhost:8420")

# Store a memory
cg.store("my_agent", "Acme Corp reported API latency. CTO Jane wants a fix by Friday.")

# Recall with graph traversal
results = cg.recall("my_agent", "What problems does Acme have?", depth=2)

# Find connections
paths = cg.relate("Acme Corp", "Jane")
# Returns: (Acme Corp) --[HAS_CTO]--> (Jane) --[REPORTED]--> (API Latency)

# Buy knowledge from another agent (Phase 3)
knowledge = cg.buy("my_agent", seller="research_01", query="RWA risks in EU")
```

---

## Roadmap

```
PHASE 1   Core Engine               Weeks 1-6     ████████████████████
PHASE 2   ERC-8004 Identity         Weeks 7-10    ████████████
PHASE 3   x402 Payments             Weeks 11-14   ████████████
PHASE 4   A2A/MCP Integration       Weeks 15-17   ████████
PHASE 5   Public Network Launch     Weeks 18-22   ████████████████
PHASE 6   TS SDK + Multi-chain      Weeks 23-28   ████████████████████
```

| Phase | What We Ship | Value |
|---|---|---|
| **Phase 1** | Knowledge graph memory engine + Python SDK + Docker Compose | Usable open-source product, community building |
| **Phase 2** | On-chain agent identity via ERC-8004, reputation system | Differentiator vs every competitor |
| **Phase 3** | x402 micropayments, knowledge marketplace, dynamic pricing | Revenue starts, agents can trade knowledge |
| **Phase 4** | A2A server/client, MCP tool server | Any agent framework can plug in |
| **Phase 5** | Public network, discovery index, node federation | The marketplace goes live |
| **Phase 6** | TypeScript SDK, multi-chain (Base, ETH, Solana), framework adapters | Full ecosystem reach |

**Key point:** Phase 1 alone is a competitive open-source product. Each phase adds value independently.

---

## Business Model

### Revenue Streams

1. **Network Transaction Fees (Primary)** — 3% on every x402 knowledge transaction on the public network
2. **Managed Cloud** — Hosted ContextGraph nodes for teams ($49-199/mo)
3. **Enterprise** — Multi-tenant, SSO, SLAs, custom integrations (custom pricing)
4. **Open Source Core** — Free forever. Builds community and adoption.

### Unit Economics

- Cost per recall: ~$0.0003
- Cost per store: ~$0.002
- Average transaction: $0.002-0.01
- Network fee: 3%
- Break-even: ~100K monthly transactions

---

## Market Numbers

| Metric | Value |
|---|---|
| AI Agent market by 2030 | $52.62B (46.3% CAGR) |
| Enterprise apps with agents by end 2026 | 40% (Gartner) |
| x402 transaction volume (Q1 2026) | $50M+ |
| ERC-8004 registered agents | 24,000+ |
| MCP SDK monthly downloads | 97M+ |
| Productivity gains from agents by 2030 | $2.9T (McKinsey) |

---

## Competitive Advantage

**Why we win:**

1. **First mover in knowledge commerce** — Nobody else combines knowledge graphs + identity + payments
2. **Built on winning standards** — ERC-8004, x402, A2A, MCP are all converging. We're the glue layer.
3. **Network effects** — Every agent that joins makes the network more valuable for everyone
4. **Open source core** — Builds trust and community. Competitors can't replicate the network.
5. **No dashboards needed** — 100% agent-native. Built for the future, not the past.

---

## Key Risks

| Risk | How We Handle It |
|---|---|
| Competitors add similar features | We ship faster. Our architecture is designed for this, not bolted on. |
| Cold start (no knowledge to buy) | Seed with open datasets. Incentivize early publishers. |
| ERC-8004 or x402 don't get adoption | Both already have significant traction. Identity module is swappable. |
| Solo founder burnout | Scope aggressively. Each phase is independently valuable. Find co-builders early. |

---

## What We Need to Start

| Item | Status |
|---|---|
| Anthropic API key (Claude for extraction) | Required for Phase 1 |
| Neo4j (Docker, free community edition) | Ready |
| Python 3.11+ environment | Ready |
| GitHub repo (public, MIT) | To create |
| Base Sepolia testnet ETH + USDC | Required for Phase 2-3 testing |
| IPFS account (Pinata or similar) | Required for Phase 2 agent cards |
| Domain: contextgraph.dev | To register |

---

## Next Steps

1. Review this document as a team
2. Align on timeline and resource allocation
3. Set up the GitHub repo and project scaffolding
4. Begin Phase 1, Task 1.1 (Project Scaffolding)

**Full technical plan with day-by-day breakdown:** `docs/contextgraph-protocol-masterplan.md`

---

*Questions? Let's discuss and align before we start building.*
