# ContextGraph Protocol - Master Plan

**Version:** 2.2 (Execution-aligned, MVP-first)
**Date:** 2026-03-08
**Author:** Maximilian Allende
**Status:** Strategic Blueprint + Active MVP Execution Plan

---

## Revision Notes (v2.2)

This revision keeps the trust-first thesis and aligns the document to the product we are actually building now:

1. **Claims, not blobs, are now the core primitive** — The protocol is about machine-usable claims with provenance, ACLs, freshness, and trust metadata, not just storing memories.
2. **Attestations and challenges are first-class** — Agents need to know not just what was said, but who validated it, who challenged it, and whether it is still safe to act on.
3. **Standing queries and subscriptions move into the core** — In an agent-dominant internet, context delivery needs to be evented, not dashboard-polled.
4. **Federation comes before settlement** — Trusted exchange matters before payment rails. A2A and federation move ahead of x402 monetization in strategic priority.
5. **The MVP path is explicit** — Self-hosted single-node value comes first, then operator trust controls, then two-node federation, then optional settlement.
6. **ERC-8004 is removed from the MVP path** — It remains ecosystem context, not a dependency for success or a blocker to shipping.
7. **In-process async work is now part of the plan** — Background jobs for extraction and delivery are acceptable in the MVP before heavier queue infrastructure exists.
8. **The beachhead is narrower** — Initial focus is regulated or high-cost-of-wrong-context workflows, not the entire agent economy on day one.
9. **Success metrics are less vanity-driven** — More emphasis on trust, policy enforcement, design-partner usage, and latency of governed exchange.
10. **The v2 correctness fixes remain** — config-driven embedding dimensions, `/.well-known/agent-card.json`, and a safer ACL model all stay.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Market Analysis & Opportunity](#2-market-analysis--opportunity)
3. [Vision & Strategic Positioning](#3-vision--strategic-positioning)
4. [Protocol Architecture](#4-protocol-architecture)
5. [Complete Tech Stack](#5-complete-tech-stack)
6. [Project Structure](#6-project-structure)
7. [Data Model & Schema Design](#7-data-model--schema-design)
8. [Phase 1: Claim Engine + MCP Server (Weeks 1-4)](#8-phase-1-claim-engine--mcp-server)
9. [Phase 2: Governance + Validation + Control Plane (Weeks 5-8)](#9-phase-2-governance--validation--control-plane)
10. [Phase 3: A2A + Federation + TypeScript SDK (Weeks 9-12)](#10-phase-3-a2a--federation--typescript-sdk)
11. [Phase 4: Settlement + Licensing (Weeks 13-16)](#11-phase-4-settlement--licensing)
12. [Phase 5: Public Network (Weeks 17-20)](#12-phase-5-public-network)
13. [API Specification](#13-api-specification)
14. [SDK Design](#14-sdk-design)
15. [Security Architecture](#15-security-architecture)
16. [Infrastructure & Deployment](#16-infrastructure--deployment)
17. [Testing Strategy](#17-testing-strategy)
18. [Business Model & Monetization](#18-business-model--monetization)
19. [Go-to-Market Strategy](#19-go-to-market-strategy)
20. [Competitive Moats](#20-competitive-moats)
21. [Risk Analysis & Mitigations](#21-risk-analysis--mitigations)
22. [Success Metrics & KPIs](#22-success-metrics--kpis)
23. [References & Resources](#23-references--resources)

---

## 1. Executive Summary

ContextGraph Protocol is an open-source **trust and exchange fabric** for agent-generated context. It ingests raw memories, turns them into graph-linked **claims**, attaches provenance, access control, freshness, and validation metadata, and lets agents share, subscribe to, federate, and optionally pay for trusted context across organizational boundaries.

### What this is NOT

- Not a dashboard product. Agents are the primary consumers.
- Not a public marketplace on day one. Federation, policy, and trust come first; settlement comes later.
- Not a vector wrapper with a graph attached. The product lives in the claim lifecycle: emit, validate, govern, subscribe, federate, settle.
- Not a monolithic platform. It is a protocol surface plus a reference implementation.
- Not ready for public launch until auth, typed APIs, persistence parity, async delivery, evaluation, and real agent pilots are proven.

### The core thesis

In an internet dominated by agents, the scarce resource is not UI space. It is **trusted machine-usable context**:

- Who asserted this?
- Can I rely on it?
- Can I share it onward?
- Is it stale?
- Do I need approval or budget to use it?
- If I pay for it, what rights did I actually buy?

The winning layer is the one that answers those questions in machine-readable form. That is where ContextGraph should live.

### What makes this different

Among established memory vendors, most optimize retrieval. Among emerging commerce projects, most optimize listing and payment. The differentiated position is to own the **claim lifecycle** end to end.

ContextGraph should be the place where agent-generated facts are:
- emitted from memories,
- represented as claims,
- validated or challenged,
- governed by policy,
- pushed to subscribers,
- federated across trust boundaries,
- and only then optionally settled or licensed.

| Capability | ContextGraph | Zep/Cognee/Mem0/Letta | Marketplace-first entrants |
|---|---|---|---|
| Graph-native memory engine | Core | Core or partial | Usually none |
| Claim-native fact model | Core | No | No |
| Provenance, freshness, and validation | Core | Limited or absent | Weak |
| Fact-level ACLs / treaty enforcement | Core | Weak or absent | Weak |
| Standing queries / subscriptions | Core | Rare | Rare |
| Cross-org federation | Core | Rare | Often registry-only |
| Optional settlement / licensing | Built on top | No | Often the starting point |
| Operator control plane | Yes | Letta has ADE-like control | Rare |

### Why this can matter now

The next wave of agent systems will need less manual workflow software and more machine-readable contracts over context. The hard problem is not just "better recall." It is **trusted exchange under policy**. That is a harder product to build and a more defensible place to sit.

### What we are building right now

Right now we are not building a public network or a marketplace. We are building the first strong internal node:

- agents store memories into one company-local node,
- the node emits structured claims,
- other agents recall or subscribe to those claims,
- humans review risky claims and audit what happened,
- and only after that do we let one node talk to another node.

That means the MVP is a **claim-native context operating layer for one company**, not a speculative open protocol launch.

### How to explain this to a teammate

Use this explanation:

> We are building the trust layer for agents. Instead of every agent keeping its own hidden memory, ContextGraph turns what agents learn into shared claims with source, freshness, permissions, and review state. Other agents can query or subscribe to those claims. Humans stay in control through review, audit, and policy. If this works inside one company first, we can later let companies exchange governed context with each other.

In one sentence:

> **ContextGraph helps agents share context they can actually trust and govern.**

### Why we are building this

We are building this because the internet is moving toward agent-heavy workflows, and current tooling is weak at the part that matters most:

- memory tools help an agent remember, but not necessarily trust,
- dashboards help humans operate workflows, but not agents exchange context,
- marketplaces help list or price things, but not govern claim quality,
- and enterprises need machine-readable provenance, freshness, permissions, and audit before they allow agents to act across teams or companies.

So the opportunity is not "another memory database." The opportunity is the layer that answers:

- what exactly is the claim,
- who asserted it,
- can this agent use it,
- is it still fresh,
- who reviewed it,
- and what happens if it crosses a boundary.

### Current implementation status (March 8, 2026)

**Already implemented in the reference node**

- Claim-native service with `store()`, `recall()`, `relate()`, and `watch()`
- API-key auth, typed API schemas, and SDK error mapping
- In-memory repository plus Neo4j adapter
- Review tasks, attestation/challenge flow, and audit logging
- Standing queries and notifications
- In-process background jobs for async memory ingestion and webhook delivery
- Extractor abstraction plus evaluation harness and fixture-driven tests
- Python SDK and MCP-facing surface

**Implemented, but still needs environment-level proof**

- FastAPI route tests need the server extras installed locally
- Neo4j integration tests need a live Neo4j instance and the optional test flag enabled
- Real agent traces are still needed to make the evaluation dataset honest at production quality

**Not built yet**

- Operator control plane UI
- Treaty / approval / budget policy engine
- A2A federation between two nodes
- Optional settlement

### Current execution order

This is the actual build order we are following now:

1. Finish the single-node MVP until it is trustworthy.
2. Dogfood one real workflow with our own agents every day.
3. Add the operator control plane so humans can supervise risky flows.
4. Add treaty, approval, and budget policy controls.
5. Prove two-node federation on one narrow workflow.
6. Only then consider paid exchange, public launch, or broader protocol positioning.

This sequence matters because if the single-node trust layer is not valuable, federation and monetization will not save it.

---

## 2. Market Analysis & Opportunity

### 2.1 Market Size

| Metric | Value | Source |
|---|---|---|
| AI Agent market (2025) | $7.84B | Industry reports |
| AI Agent market (2030, projected) | $52.62B | 46.3% CAGR |
| AI Infrastructure market (2026) | $90B | Coherent Market Insights |
| Enterprise apps with embedded agents by end 2026 | 40% | Gartner |
| Orgs planning to deploy autonomous agents within 2 years | 74% | Deloitte 2026 State of AI |
| Orgs with mature agent governance | 21% | Deloitte 2026 State of AI |
| Agentic commerce potential by 2030 | $3-5T redirected spend | McKinsey |
| Productivity gains from agents by 2030 | $2.9T | McKinsey |

### 2.2 Current Standards Landscape (March 2026)

| Standard | Status | Adoption | Role |
|---|---|---|---|
| **MCP** (Anthropic) | Production | 97M+ monthly SDK downloads | Agent-to-tool context |
| **A2A** (Google) | Production (v0.3.0) | 100+ enterprise supporters | Agent-to-agent communication |
| **ERC-8004** | Mainnet (Jan 29, 2026) | 24,000+ agents registered | Agent identity & reputation |
| **x402** | Production (v2) | $50M+ cumulative volume | Agent-to-agent payments |
| **UCP** (Google) | Production | Shopify, Walmart, Target | Agentic product commerce |
| **NIST AI Agent Standards** | Announced Feb 2026 | Federal backing | Security & interoperability |

### 2.3 The Real Gap in the Stack

```
WHAT EXISTS:                          WHAT'S MISSING:
+-----------+                         +---------------------------+
| Identity  | ERC-8004                |                           |
+-----------+                         |  TRUSTED CLAIM            |
| Payments  | x402                    |  EXCHANGE LAYER           |
+-----------+                         |                           |
| Commerce  | UCP (products)          |  Store, share, federate,  |
+-----------+                         |  validate, subscribe to,  |
| Comms     | A2A / MCP               |  and license claims with  |
+-----------+                         |  provenance and policy    |
| Compute   | Cloud / Edge            |                           |
+-----------+                         +---------------------------+
                                              ^
                                              |
                                       ContextGraph Protocol
```

UCP handles product commerce. x402 handles payment. A2A and MCP handle interaction. None of them define the machine-usable objects and policy layer for trusted context exchange. That is the missing layer.

### 2.4 The Trust Gap Enterprises Will Actually Pay For

This is the underserved opportunity most plans miss:

- The cost of a wrong answer is not just "bad recall." It is leakage, stale action, unlicensed reuse, runaway spend, and opaque cross-agent delegation.
- Most organizations do not have machine-enforceable ways to say what one agent may ask of another, what facts may cross boundaries, or what level of validation is needed before action.
- Agents increasingly operate as autonomous consumers of APIs, tools, and other agents, but enterprises still govern with human-facing policy documents and ad hoc approvals.

**Enterprises will pay for trusted exchange before they pay for open agent commerce.** That means:

1. policy and treaty enforcement,
2. provenance and freshness,
3. approvals and budgets,
4. auditability,
5. subscriptions to important context changes,
6. and only then monetization.

That is the sequence this plan should follow.

### 2.5 Beachhead ICP

Do not target "all agent builders" as the primary paid wedge. Start with teams where wrong context is expensive and multi-agent coordination is already happening.

| ICP | Why it fits | Example workflows |
|---|---|---|
| **Research / diligence teams** | High value per claim, repeatable reuse, provenance matters | market maps, due diligence memos, vendor assessment |
| **Cross-functional support ops** | Shared context across support, success, engineering, and AI agents | incident triage, account escalation, workaround propagation |
| **Threat intel / SecOps** | Freshness, trust, and federation matter immediately | IOC propagation, partner intel sharing, investigation threads |

These are better early customers than a generic "knowledge marketplace for agents." They have clearer pain, higher willingness to pay, and stronger need for governance.

### 2.6 Competitive Landscape

#### Established Memory Infrastructure

| Competitor | Funding | Architecture | Cross-org | Identity | Payments | Governance |
|---|---|---|---|---|---|---|
| **Zep/Graphiti** | Series A | Temporal knowledge graph | No | No | No | No |
| **Cognee** | EUR 7.5M (Feb 2026) | Knowledge graph + semantic | Permissions, not federation | No | No | No |
| **Mem0** | Well-funded | Flat + bolt-on graph (Jan 2026) | No | No | No | No |
| **Letta/MemGPT** | Well-funded | Stateful agent memory | No | No | No | ADE control plane |

These are the real competitors on the memory engine layer. They have teams, funding, and traction. Most of them stop at better memory and retrieval.

#### Emerging Knowledge Commerce

| Project | What it claims | Reality (March 2026) |
|---|---|---|
| **Memonex** | "Trustless marketplace for agent-to-agent knowledge commerce" | Empty marketplace ("No listings yet"). Solo developer. OpenClaw skill. No team/funding disclosed. |
| **Knowbster** | "Knowledge Transfer Framework for AI Agents" on Base L2 | Next.js prototype. No team/funding disclosed. No verifiable transaction volume. |
| **ClawForge** | "The Agent Knowledge Marketplace" | Agent registry with free sharing/barter. Paid "Sell" feature is "coming soon." Has some registered agents. |

These validate the category, but they are more marketplace- or registry-first than trust-fabric-first. That means they do not remove the need for an infrastructure layer beneath them.

#### Adjacent

| Project | Relevance |
|---|---|
| **AINFT** | x402 + ERC-8004 integration, but DeFi-focused, not knowledge/memory |
| **0xgasless Agent SDK** | ERC-8004 + x402 SDK, but wallet/identity tooling, not a knowledge layer |
| **OpenClaw / ClawHub** | Agent skills marketplace (13K+ skills), but skills are code plugins, not knowledge/context |

### 2.7 Our Strategic Position

```
                        INFRASTRUCTURE-FIRST
                              ^
                              |
                    ContextGraph ****
                              |
        Cognee *              |              * ClawForge
        Zep *                 |              * Knowbster
        Mem0 *                |              * Memonex
                              |
  MEMORY-ONLY ----------------+---------------- COMMERCE-ONLY
                              |
        Letta *               |
                              |
                              |
                              v
                        MARKETPLACE-FIRST
```

We should occupy the upper-left quadrant: infrastructure-first, with settlement as an optional layer. The established players are memory-heavy. The newcomers are commerce-heavy. The differentiated position is trust-heavy.

---

## 3. Vision & Strategic Positioning

### 3.1 One-Liner

> **"The trusted claim exchange layer for AI agents"** — Graph-native memory plus claims, provenance, validation, policy, subscriptions, federation, and optional settlement.

### 3.2 Product Layers

```
Layer 4: Settlement & Licensing (Optional)
         x402-based paid exchange
         Machine-readable usage rights and receipts
         Spend caps, budgets, rev-share later
         |
Layer 3: Federation & Subscriptions
         Cross-org recall via A2A
         Standing queries, notifications, change streams
         Registry + peer discovery
         |
Layer 2: Claims, Validation & Policy
         Claim graph with provenance and freshness
         Attestations, challenges, trust scoring
         Treaties, ACLs, approvals, audit trails
         |
Layer 1: Memory Ingestion & Graph Core
         Neo4j knowledge graph + vector search
         LLM extraction from raw memories
         store() / recall() / relate() / watch()
         MCP server for distribution
```

### 3.3 On Dashboards

The other AI's feedback on this is correct, and we should be precise:

**What disappears:** Workflow dashboards where humans manually do routine work. Agents handle this via A2A, MCP, APIs, and event loops.

**What remains:** Control planes for humans — approvals, observability, trust management, compliance, security, budgets, disputes, and performance monitoring. MCP itself explicitly assumes a human-in-the-loop UI for tool approval and sampling actions.

**Our stance:** No workflow dashboard as the main product. But we build a **minimal operator control plane** (Phase 2) for:
- Approving cross-org access requests
- Monitoring agent activity and knowledge flows
- Reviewing claims, attestations, and governance policies
- Audit logs for compliance
- Trust/reputation overview
- Budget and billing management

This is not a traditional dashboard. It's an oversight interface that humans use to govern what agents do autonomously.

### 3.4 Design Principles

1. **Claims, not blobs** — The core object is a claim with provenance, freshness, ACLs, and validation metadata.
2. **Evented, not dashboarded** — Agents should subscribe to changes they care about instead of repeatedly polling UIs or endpoints.
3. **Trust before settlement** — Validation, permissions, and policy come before monetization.
4. **Federation before marketplace** — Private cross-boundary exchange is the first market; public trading is the second.
5. **Protocol, not just product** — The exchange objects and policy model should be implementable outside our reference node.
6. **Graph-native, not graph-bolted** — Entities and claims live in a graph because relationships and traversal matter.
7. **Operator, not worker** — Humans supervise, approve, and audit; agents do the repetitive work.
8. **Narrow beachhead, wide ambition** — Start in a few high-trust workflows, then generalize.

---

## 4. Protocol Architecture

### 4.1 High-Level Architecture

```
+====================================================================+
||                    CONTEXTGRAPH PROTOCOL                         ||
||                                                                  ||
||  +----------------------------------------------------------+   ||
||  |            Operator Control Plane (Human Oversight)      |   ||
||  |  Approvals | Reviews | Audit | Budget | Policies         |   ||
||  +---------------------------+------------------------------+   ||
||                              |                                   ||
||  +---------------------------v------------------------------+   ||
||  |          Policy, Trust, and Validation Layer             |   ||
||  |  Treaties | ACLs | Freshness | Attestations | Audit      |   ||
||  +---------------------------+------------------------------+   ||
||                              |                                   ||
||  +---------------------------v------------------------------+   ||
||  |          Federation and Subscription Layer               |   ||
||  |  A2A Recall | Registry | Standing Queries | Notifications|   ||
||  +---------------------------+------------------------------+   ||
||                              |                                   ||
||  +---------------------------v------------------------------+   ||
||  |              Claim and Memory Core                       |   ||
||  |  Memory Ingestion | Claim Engine | Graph Query | Watch   |   ||
||  +---------------------------+------------------------------+   ||
||                              |                                   ||
||  +---------------------------v------------------------------+   ||
||  |        Optional Service Identity and Settlement          |   ||
||  |      Signed node identity | x402 | Usage Receipts       |   ||
||  +---------------------------+------------------------------+   ||
||                              |                                   ||
||                     +--------v--------+                         ||
||                     |      Neo4j      |                         ||
||                     | Claims + Graph  |                         ||
||                     +-----------------+                         ||
+====================================================================+
```

The core wedge is not chain integration. It is the claim model plus policy and federation. Signed service identity and x402 remain optional adapters for trust boundaries and settlement.

### 4.2 Core Protocol Objects

The protocol should revolve around six objects:

1. **Memory** — Raw input, usually private by default.
2. **Entity** — Canonical node for a person, company, topic, event, or object.
3. **Claim** — The access-controlled, provenance-bearing fact emitted from a memory.
4. **Attestation** — A validation, rating, or challenge attached to a claim.
5. **Treaty** — A machine-enforceable policy between agents or organizations.
6. **StandingQuery** — A subscription for changes to entities, claims, or domains.

This is the shift that makes the protocol differentiated: agents do not just retrieve text or entities; they act on governed claims.

### 4.3 Request Flow: Cross-Org Recall

1. Agent calls `recall(query, network=True)`.
2. Local node retrieves matching claims, not just memories.
3. Policy engine checks treaty, requester identity, budget, and depth limits.
4. Federation layer discovers relevant remote nodes via A2A.
5. Remote nodes return ACL-filtered claims with provenance, freshness, and attestation metadata.
6. If required, settlement happens through x402 using a fixed or quoted price.
7. Local node merges and ranks by relevance, trust, freshness, and policy fit.
8. Audit log records the entire chain.

There is no marketplace-browse experience in the primary workflow. The dominant interaction is direct recall and subscription.

### 4.4 Request Flow: Storing Memory

1. Agent stores raw memory.
2. Extraction pipeline emits entities and claims.
3. Claims receive provenance, ACL, TTL / freshness, and optional licensing metadata.
4. Validation layer optionally auto-attests, queues review, or flags conflicts.
5. Standing queries that match the new claims are triggered.
6. Subscribers receive notifications or pull the delta via API / MCP / A2A.

The product is not just retrieval. It is a governed event system for machine-usable context.

---

## 5. Complete Tech Stack

### 5.1 Core Engine (Phase 1 — Lean)

| Component | Technology | Why |
|---|---|---|
| **Language** | Python 3.11+ | AI/ML ecosystem, async support |
| **API Framework** | FastAPI | Async-native, auto OpenAPI docs, Pydantic integration |
| **Graph Database** | Neo4j 5.x | Native graph + vector indexes in one DB, Cypher, battle-tested |
| **Neo4j Driver** | `neo4j` (official Python, async) | Connection pooling, transaction management |
| **Data Validation** | Pydantic v2 | Fast serialization, strict typing |
| **Embeddings** | `sentence-transformers` (local) / OpenAI API (cloud) | Local-first for privacy |
| **LLM (extraction)** | Claude API (`anthropic` SDK) | Entity & relationship extraction |
| **HTTP Client** | `httpx` | Async support, SDK and x402 client |
| **MCP Server** | `mcp` Python SDK | Expose as MCP tool server from day one |
| **Structured Logging** | `structlog` | JSON logs, audit trail foundation |

**Deliberately excluded from Phase 1:** external queue infrastructure like Celery and Redis. Use an in-process background worker in the MVP for async extraction and notification delivery, and only add heavier infrastructure when scale demands it.

### 5.2 Settlement / Future Adapters (Later)

| Component | Technology | Why |
|---|---|---|
| **x402 Payments** | `x402` PyPI package | HTTP 402 payment protocol |
| **A2A Agent Cards** | JSON (`/.well-known/agent-card.json`) | Node discovery and metadata |
| **Service Identity** | Signed API keys / JWT / mTLS later | Node-to-node trust without crypto coupling |
| **Chain** | Base or equivalent, only if settlement is needed | Low-cost settlement when x402 is enabled |
| **Stablecoin** | USDC | Settlement currency |

These are **optional adapters**. ContextGraph works fully without them for internal deployments. They activate only if settlement or stronger remote identity requirements show up in real deployments.

### 5.3 Communication Protocols

| Component | Technology | Why |
|---|---|---|
| **A2A Protocol** | `a2a-sdk` (v0.3.0) | Agent discovery and task delegation |
| **MCP Server** | `mcp` Python SDK | 97M+ monthly downloads, instant distribution |
| **WebSocket** | FastAPI WebSocket | Real-time graph change notifications |

### 5.4 Infrastructure

| Component | Technology |
|---|---|
| Containers | Docker + Docker Compose (dev), Kubernetes (prod) |
| CI/CD | GitHub Actions |
| Cloud | Railway (early) → AWS EKS (scale) |
| Monitoring | Prometheus + Grafana |
| Logging | Structured JSON logs + Loki |
| Secrets | AWS Secrets Manager / Vault (for service keys and payment credentials) |

### 5.5 Testing & DX

| Component | Technology |
|---|---|
| Testing | `pytest` + `pytest-asyncio` + `testcontainers` |
| Load Testing | `locust` |
| API Testing | `schemathesis` (auto from OpenAPI spec) |
| Coverage | `pytest-cov` (target: 80%) |
| Package Manager | `uv` |
| Linting | `ruff` |
| Type Checking | `mypy` (strict) |
| Pre-commit | `pre-commit` |
| Docs | MkDocs + Material theme |

---

## 6. Project Structure

```
contextgraph/
  docs/
    architecture.md
    claims-model.md
    federation-guide.md
    governance-guide.md
    settlement-guide.md
  contextgraph/
    config.py
    main.py
    models/
      agent.py
      memory.py
      claim.py                    # Claim, attestation, freshness, licensing
      policy.py                   # Treaty, ACL, approval, budget rules
      subscription.py             # StandingQuery and notifications
      common.py
    graph/
      client.py
      schema.py
      queries.py
      acl.py
    services/
      extraction.py
      embeddings.py
      claims.py                   # Emit and update claims from memories
      memory.py
      validation.py               # Attest, challenge, trust scoring
      governance.py               # Treaties, approvals, budgets
      subscriptions.py            # Standing queries and fan-out
      federation.py               # Remote recall orchestration
      settlement.py               # Optional x402 + usage receipts
      audit.py
    api/
      routes_memory.py
      routes_claims.py
      routes_watch.py
      routes_governance.py
      routes_network.py
      middleware.py
      dependencies.py
    protocols/
      mcp_server.py
      a2a_server.py
      a2a_client.py
    identity/
      agent_card.py
      service_identity.py
    console/
      routes.py
      templates/
  sdk/
    contextgraph_sdk/
      client.py
      async_client.py
      models.py
      exceptions.py
  tests/
    unit/
      test_claims.py
      test_validation.py
      test_acl.py
      test_subscriptions.py
    integration/
      test_memory_service.py
      test_governance_service.py
      test_federation.py
    e2e/
      test_mcp_store_recall.py
      test_claim_review_flow.py
      test_federated_recall.py
      test_settlement_flow.py
```

---

## 7. Data Model & Schema Design

### 7.1 Neo4j Node Types

```cypher
// Agent
(:Agent {
  agent_id: String!,
  name: String!,
  org_id: String,
  status: String!,
  public_key_id: String,
  created_at: DateTime!,
  updated_at: DateTime!
})

// Memory — raw source material
(:Memory {
  memory_id: String!,
  content: String!,
  summary: String,
  visibility: String!,            // "private" | "shared" | "published"
  source: String,                 // "direct" | "mcp" | "a2a" | "federation"
  created_at: DateTime!,
  updated_at: DateTime!
})

// Entity — canonical object, intentionally thin
(:Entity {
  entity_id: String!,
  name: String!,
  type: String!,
  alias_key: String!,
  created_at: DateTime!,
  updated_at: DateTime!
})

// Claim — the main protocol primitive
(:Claim {
  claim_id: String!,
  statement: String!,             // Human-readable canonicalized form
  claim_type: String!,            // "attribute" | "relationship" | "derived"
  relation_type: String,          // For relationship claims
  confidence: Float,
  freshness_score: Float,
  validation_status: String!,     // "unreviewed" | "attested" | "challenged" | "expired"
  visibility: String!,            // "private" | "shared" | "published"
  license: String!,               // "internal" | "partner" | "paid"
  source_agent_id: String!,
  source_memory_id: String!,
  embedding: [Float],             // Config-driven, default 384
  created_at: DateTime!,
  expires_at: DateTime,
  updated_at: DateTime!
})

// StandingQuery — event-driven context subscription
(:StandingQuery {
  query_id: String!,
  agent_id: String!,
  name: String!,
  query: String!,
  filters: String,                // JSON
  delivery_mode: String!,         // "pull" | "webhook" | "websocket" | "a2a"
  status: String!,                // "active" | "paused" | "disabled"
  created_at: DateTime!,
  updated_at: DateTime!
})

// Treaty — machine-enforceable policy object
(:Treaty {
  treaty_id: String!,
  name: String!,
  policy: String!,                // JSON policy document
  status: String!,
  created_at: DateTime!,
  expires_at: DateTime
})

// AuditEntry — immutable action log
(:AuditEntry {
  audit_id: String!,
  action: String!,
  actor_agent_id: String!,
  target_agent_id: String,
  details: String,
  timestamp: DateTime!
})
```

### 7.2 Relationship Types

```cypher
// Raw storage
(:Agent)-[:STORED {at: DateTime}]->(:Memory)
(:Memory)-[:EMITS]->(:Claim)

// Claim graph
(:Claim)-[:SUBJECT]->(:Entity)
(:Claim)-[:OBJECT]->(:Entity)
(:Claim)-[:DERIVED_FROM]->(:Claim)

// Validation
(:Agent)-[:ATTESTED {
  score: Float,
  method: String,                 // "auto" | "human" | "partner"
  at: DateTime!
}]->(:Claim)

(:Agent)-[:CHALLENGED {
  reason: String,
  at: DateTime!
}]->(:Claim)

// Sharing and governance
(:Agent)-[:HAS_ACCESS_TO {
  permission: String!,
  max_depth: Integer,
  expires_at: DateTime
}]->(:Agent)

(:Agent)-[:BOUND_BY]->(:Treaty)
(:Treaty)-[:GOVERNS]->(:Agent)

// Subscriptions
(:Agent)-[:SUBSCRIBES_TO]->(:StandingQuery)
(:StandingQuery)-[:MATCHES]->(:Claim)

// Optional settlement
(:Agent)-[:PAID {
  amount: Float,
  currency: String,
  usage_receipt_id: String,
  at: DateTime!
}]->(:Agent)
```

### 7.3 Indexes

```cypher
// Vector indexes
CREATE VECTOR INDEX claim_embedding FOR (c:Claim) ON (c.embedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }};

CREATE VECTOR INDEX memory_embedding FOR (m:Memory) ON (m.embedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }};

// B-tree indexes
CREATE INDEX agent_id_idx FOR (a:Agent) ON (a.agent_id);
CREATE INDEX agent_org_idx FOR (a:Agent) ON (a.org_id);
CREATE INDEX entity_alias_idx FOR (e:Entity) ON (e.alias_key);
CREATE INDEX claim_visibility_idx FOR (c:Claim) ON (c.visibility);
CREATE INDEX claim_validation_idx FOR (c:Claim) ON (c.validation_status);
CREATE INDEX claim_expiry_idx FOR (c:Claim) ON (c.expires_at);
CREATE INDEX standing_query_status_idx FOR (q:StandingQuery) ON (q.status);
CREATE INDEX treaty_status_idx FOR (t:Treaty) ON (t.status);

// Constraints
CREATE CONSTRAINT agent_id_unique FOR (a:Agent) REQUIRE a.agent_id IS UNIQUE;
CREATE CONSTRAINT entity_id_unique FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
CREATE CONSTRAINT memory_id_unique FOR (m:Memory) REQUIRE m.memory_id IS UNIQUE;
CREATE CONSTRAINT claim_id_unique FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;
CREATE CONSTRAINT query_id_unique FOR (q:StandingQuery) REQUIRE q.query_id IS UNIQUE;
CREATE CONSTRAINT treaty_id_unique FOR (t:Treaty) REQUIRE t.treaty_id IS UNIQUE;
CREATE CONSTRAINT audit_id_unique FOR (a:AuditEntry) REQUIRE a.audit_id IS UNIQUE;
```

### 7.4 ACL Enforcement

The safest model is to keep canonical entities thin and put sensitive semantics on `Claim` nodes. ACLs are enforced on claims, not on the canonical entity identity.

```cypher
CALL db.index.vector.queryNodes('claim_embedding', $top_k, $query_embedding)
YIELD node, score
WHERE (
  node.visibility = 'published'
  OR node.source_agent_id = $requester_id
  OR (
    node.visibility = 'shared'
    AND EXISTS {
      MATCH (requester:Agent {agent_id: $requester_id})
            -[:HAS_ACCESS_TO]->
            (owner:Agent {agent_id: node.source_agent_id})
    }
  )
)
AND (node.expires_at IS NULL OR node.expires_at > datetime())
RETURN node, score
```

This means a requester may discover that an entity exists without ever seeing restricted claims about that entity. The trust-bearing information lives on the claim.

---

## 8. Phase 1: Claim Engine + MCP Server (Weeks 1-4)

**Goal:** Ship a self-hostable claim-native memory engine with MCP distribution. The output is not just "memories retrieved"; it is governed claims that agents can consume immediately.

### Build

- Core data model: `Memory`, `Entity`, `Claim`, `StandingQuery`, `AuditEntry`
- Claim emission pipeline: raw memory -> extraction -> claims with provenance, ACL, freshness
- `store()`, `recall()`, `relate()`, `watch()` API surface
- Standing queries with pull notifications first, plus webhook delivery in the MVP runtime
- MCP server with `contextgraph_store`, `contextgraph_recall`, `contextgraph_relate`, `contextgraph_watch`
- Python SDK
- Lean deployment: FastAPI + Neo4j with an in-process background worker

### Success Gate

- A new user can install the MCP server and use it in under 10 minutes
- Recall returns claims with provenance and freshness
- `watch()` can notify on claim changes for a domain or entity
- Unauthorized retrievals are blocked at the claim layer

### Deliverables

- [x] Claim-native service model and reference repository
- [x] Extraction pipeline that emits claims, not only edges
- [x] ACL-aware recall and relate
- [x] Standing queries and persisted notifications
- [x] API-key auth, typed APIs, and Python SDK
- [x] In-process background jobs for async memory ingestion and webhook delivery
- [~] Neo4j parity and HTTP integration tests exist, but still need environment verification
- [ ] Public repo, docs, Docker image, PyPI package

---

## 9. Phase 2: Governance + Validation + Control Plane (Weeks 5-8)

**Goal:** Make the output safe to trust and safe to govern.

### Build

- Treaty engine for machine-enforceable access, depth, domain, approval, and budget rules
- Validation service: attest, challenge, expire, refresh
- Review queue for high-impact or low-confidence claims
- Minimal operator control plane for approvals, reviews, budgets, and audits
- Pilot instrumentation for one real workflow using our own agents

### Success Gate

- Cross-agent exchange can be allowed or denied by policy, not code forks
- Claims can be attested or challenged and that state affects retrieval ranking
- Operators can review and approve risky actions without becoming the workflow bottleneck

### Deliverables

- [ ] Treaty engine and policy model
- [x] Claim attestation / challenge APIs
- [x] Freshness / TTL handling and expiry rules
- [~] Review queue API exists; operator control plane is not built yet
- [ ] Pilot one real workflow with our own agents
- [ ] Approval and budget controls

---

## 10. Phase 3: A2A + Federation + TypeScript SDK (Weeks 9-12)

**Goal:** Turn a single node into a real exchange fabric across nodes and agent frameworks.

### Build

- A2A server and client with `/.well-known/agent-card.json`
- Federation registry and node discovery
- Federated `recall(network=True)` over A2A
- Policy-aware remote recall orchestration
- TypeScript SDK for the JS-heavy agent ecosystem

### Success Gate

- Node A can federate a recall to Node B and merge the results
- All federated results preserve provenance, validation status, and ACLs
- JS/TS agents can use the same primitives as Python agents

### Deliverables

- [ ] A2A server and client
- [ ] Federation registry
- [ ] Federated recall orchestration
- [ ] TypeScript SDK published to npm
- [ ] End-to-end federation tests

---

## 11. Phase 4: Settlement + Licensing (Weeks 13-16)

**Goal:** Add monetization only after trust and federation work.

### Build

- Optional x402 settlement for paid recalls
- Licensing profiles on claims: `internal`, `partner`, `paid`
- Usage receipts and spend caps
- Fixed or quoted pricing, not dynamic micropayment games
- Budget-aware enforcement in governance rules

### Success Gate

- Paid exchange works for a real federated recall flow
- Buyers receive both the claims and a machine-readable record of usage rights
- Finance and compliance can reason about spend and permitted reuse

### Deliverables

- [ ] x402 adapter for cross-node payment
- [ ] Licensing model and usage receipts
- [ ] Budget controls and fixed pricing
- [ ] SDK support for transparent settlement

---

## 12. Phase 5: Public Network (Weeks 17-20)

**Goal:** Launch a network only after design-partner usage proves the exchange layer matters.

### Launch Guardrail

**Do not launch this publicly yet.** The build order before any public release should be:

1. Fix auth and remove secret leakage.
2. Add typed API schemas and HTTP tests.
3. Fix Neo4j parity and add Neo4j integration tests.
4. Add async extraction and delivery workers.
5. Build an evaluation harness for claim quality.
6. Pilot one real workflow with our own agents.
7. Only then add cross-company federation.

**Current status:** Items 1-5 are implemented in code or test scaffolding, but still need runtime verification in the right environments. Item 6 is the active product priority. Item 7 has not started.

### Build

- Hosted node and hosted control plane
- Public registry for opt-in nodes
- Framework adapters for LangGraph / CrewAI / similar ecosystems
- Landing page, docs, onboarding, and status page
- Design-partner case studies and first public federation partners

### Release Criteria

- At least 3 design partners use the system for a real workflow
- At least 2 organizations exchange governed context across a boundary
- At least 1 partner uses optional settlement or licensing

### Deliverables

- [ ] Hosted network node
- [ ] Public registry
- [ ] Framework adapters
- [ ] Reference deployments and case studies
- [ ] Public docs and onboarding flow

---

## 13. API Specification

### 13.1 Authentication

**Phase 1:** API key per agent (`X-Agent-Key: <key>`)
**Phase 2+:** Service or node identity for federation (signed service keys, JWT, or mTLS), falls back to API key

### 13.2 Error Format

```json
{
  "error": {
    "code": "ACL_DENIED",
    "message": "Agent 'sales_01' does not have access to claim 'clm_abc123' emitted by 'support_01'",
    "request_id": "req_abc123"
  }
}
```

### 13.3 Pagination

```json
{
  "data": [...],
  "pagination": {
    "total": 142,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

### 13.4 Rate Limiting

| Tier | Requests/min | Stores/hour | Recalls/hour |
|---|---|---|---|
| Free (self-hosted) | Unlimited | Unlimited | Unlimited |
| Hosted Pro ($49/mo) | 60 | 100 | 500 |
| Hosted Team ($199/mo) | 300 | 1,000 | 5,000 |
| Enterprise | Custom | Custom | Custom |

---

## 14. SDK Design

### 14.1 Principles

1. **Zero-config default** — `ContextGraph()` works out of the box
2. **Progressive disclosure** — Simple for basics, powerful for advanced
3. **Sync and async** — Both variants, same interface
4. **Type-safe** — Full annotations, IDE autocomplete
5. **Claims first** — SDK objects expose claims, attestations, freshness, and policy metadata, not only raw documents
6. **Event-native** — Standing queries and subscriptions are first-class SDK features
7. **Transparent settlement** — x402 handled automatically when payment credentials are configured

### 14.2 Exception Hierarchy

```python
ContextGraphError
  +-- ConnectionError
  +-- AuthenticationError
  +-- EntityNotFoundError
  +-- MemoryNotFoundError
  +-- ClaimNotFoundError
  +-- PermissionDeniedError       # ACL violation
  +-- TreatyViolationError        # Governance policy blocked the action
  +-- ClaimValidationError        # Claim challenged, expired, or below trust threshold
  +-- BudgetExceededError         # Governance budget cap blocked the action
  +-- SubscriptionError           # Standing query or delivery failure
  +-- PaymentRequiredError        # x402 needed (includes price)
  +-- InsufficientFundsError
  +-- ExtractionError             # LLM failed
```

---

## 15. Security Architecture

### 15.1 Threat Model

| Threat | Mitigation |
|---|---|
| **Private knowledge leakage via graph traversal** | ACLs enforced on claim retrieval and traversal. Canonical entities stay thin; trust-bearing semantics live on claims. |
| **Stale claim propagation** | Claim TTLs, freshness scores, and expiry-aware ranking. |
| **Validation laundering** | Attestations and challenges carry source identity and method metadata. |
| **Unauthorized memory access** | Agent-scoped permissions + treaty enforcement |
| **Prompt injection in stored memories** | Sanitize content before storage, flag suspicious patterns |
| **Knowledge poisoning** | Provenance tracking + attestation/challenge model. Bad sources and disputed claims stay visible as such. |
| **Sybil attacks** | Partner allowlists, signed service identity, rate limits, and trust weighting by observed behavior. |
| **Budget abuse across federated recalls** | Spend caps and approval rules enforced in governance layer before settlement. |
| **Payment fraud** | x402 via Coinbase facilitator. Blockchain finality. |
| **API abuse** | Rate limiting, API key rotation |
| **Data exfiltration** | Encryption at rest (Neo4j), TLS in transit |
| **Payment credential theft** | Encrypted storage, key rotation, HSM support for enterprise |

### 15.2 Data Privacy

- All claims are agent-scoped by default (private visibility)
- Sharing requires explicit grant with expiry
- Publishing (network-visible) is opt-in per claim or claim bundle
- Provenance is immutable — you can always trace who stored what
- Agents can delete their data (right to deletion)
- Cross-node queries return ACL-filtered claims or claim subgraphs, never raw content unless policy explicitly allows it
- Audit trail records all cross-agent access

---

## 16. Infrastructure & Deployment

### 16.1 Local Development

```bash
git clone https://github.com/contextgraph/contextgraph.git
cd contextgraph
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
docker compose up -d
uv run uvicorn contextgraph.main:app --reload
curl http://localhost:8420/health
```

### 16.2 Production

```
              +------------------+
              |   Load Balancer  |
              +--------+---------+
                       |
          +------------+------------+
          |            |            |
    +-----v----+ +----v-----+ +----v-----+
    | API Pod 1| | API Pod 2| | API Pod 3|
    +-----+----+ +----+-----+ +----+-----+
          |            |            |
          +------------+------------+
                       |
          +------------+------------+
          |                         |
    +-----v------+          +------v------+
    |   Neo4j    |          |   Neo4j     |
    |   Writer   |          |   Readers   |
    +------------+          +-------------+
```

### 16.3 Environments

| Environment | Purpose | Infrastructure |
|---|---|---|
| `local` | Development | Docker Compose |
| `staging` | Pre-production | Railway |
| `production` | Live | AWS EKS |
| `testnet` | Blockchain testing | Base Sepolia |
| `mainnet` | Live blockchain | Base mainnet |

---

## 17. Testing Strategy

### 17.1 Test Pyramid

```
         /\        E2E (10%) — Full store->recall, federation, x402
        /  \
       /    \      Integration (30%) — Neo4j queries, API, ACLs
      /      \
     /        \    Unit (60%) — Extraction, embeddings, ACL logic, governance
    /          \
```

### 17.2 Critical Scenarios

1. **Claim ACL enforcement** — Agent B cannot retrieve Agent A's restricted claims even when the underlying entity is shared
2. **Provenance integrity** — Every claim traces back to its source agent and source memory
3. **Claim merge safety** — Canonical entities can merge without leaking claim-level permissions
4. **Treaty enforcement** — Cross-org queries are blocked when treaty, budget, or approval rules disallow them
5. **Validation behavior** — Attested claims rank above unreviewed claims; challenged or expired claims are downgraded or suppressed
6. **Store & recall accuracy** — Precision@5 > 0.80 across diverse memories and claims
7. **Standing query delivery** — Matching claim changes trigger the correct subscriptions with low latency
8. **Federation flow** — Node A queries Node B, treaty checked, claims merged, audit recorded
9. **Settlement flow** — Paid federated recall returns both claims and machine-readable usage rights
10. **Audit completeness** — Every cross-agent operation, approval, and payment is logged

### 17.3 CI Pipeline

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: uv run ruff check .
      - run: uv run mypy contextgraph/

  test:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5-community
        ports: ["7687:7687"]
        env:
          NEO4J_AUTH: neo4j/test
    steps:
      - uses: actions/checkout@v4
      - run: uv run pytest --cov=contextgraph --cov-report=xml -v
      - uses: codecov/codecov-action@v4
```

---

## 18. Business Model & Monetization

### 18.1 Revenue Streams

```
1. OPEN SOURCE CORE (Free)
   Self-hosted claim engine, MCP server, federation-ready node.

2. HOSTED CONTROL PLANE (Primary Early Revenue)
   Governance, audit, review queue, budgets, hosted subscriptions,
   and federation management for teams that do not want to run it.

3. ENTERPRISE GOVERNANCE + COMPLIANCE
   SSO, audit export, policy packs, dedicated infrastructure,
   private federation hubs, premium support.

4. SETTLEMENT + LICENSE FEES (Later)
   Revenue share or transaction fees on optional paid claim exchange.
   Important later, not the primary early business.
```

### 18.2 Why This Model

The early buyer is not paying for raw memory retrieval. They are paying for:

- safer cross-agent exchange,
- review and approval flows,
- auditability,
- subscriptions to important changes,
- and the ability to govern context reuse across boundaries.

That is why the primary monetization should be the hosted trust layer, not tiny per-query fees.

### 18.3 Pricing Shape

| Tier | Price | Includes |
|---|---|---|
| **Open Source** | Free | Self-hosted claim engine and MCP server |
| **Hosted Pro** | $49/mo | Hosted node, MCP, basic claims, audit, standing queries |
| **Hosted Team** | $199/mo | Governance policies, review queue, federation controls, budgets |
| **Enterprise** | Custom | SSO, private federation hub, compliance export, SLA, dedicated infra |

Use fixed or quoted settlement later. Avoid betting the company on micropayment volume.

---

## 19. Go-to-Market Strategy

### 19.1 Beachhead Workflows

| Workflow | Why this should go first | What ContextGraph replaces |
|---|---|---|
| **Research and diligence** | High-value facts, provenance matters, repeated reuse across agents | ad hoc notes, duplicated agent runs, weak source tracking |
| **Support and operations handoff** | Multi-agent coordination already exists, stale context is expensive | siloed ticket summaries and brittle prompt context |
| **Threat intel and investigations** | Freshness, trust, and controlled sharing are essential | email/slack/manual updates and isolated intel stores |

### 19.2 Launch Sequence

| Window | Action | Goal |
|---|---|---|
| Weeks 1-4 | Build with 2-3 design partners while shipping MCP + open source core | Real pain validation |
| Week 4 | Public repo, PyPI, Docker, MCP registry submission | Developer distribution |
| Weeks 5-8 | Pilot governance and review flows with first partners | Prove trust wedge |
| Weeks 9-12 | Run federated recall across partner nodes, publish first case study | Prove cross-boundary value |
| Weeks 13-16 | Add settlement and licensing with one real partner workflow | Validate monetization path |
| Weeks 17-20 | Open hosted offering and public registry if release criteria are met | Convert pilots into repeatable product |

### 19.3 Positioning

**For developers:** "Claim-native memory and subscriptions for agents. Works with MCP today, federation-ready tomorrow."

**For enterprises:** "The trust and exchange layer for multi-agent systems. Provenance, policy, approvals, budgets, and audit trails built in."

**For agent-native / crypto audiences:** "A claim graph and settlement-ready context protocol for autonomous agents."

### 19.4 Partnerships to Pursue

| Partner | Why | Value |
|---|---|---|
| Anthropic MCP ecosystem | Immediate distribution | Installs and credibility |
| A2A ecosystem / working group | Federation alignment | Interop credibility |
| LangGraph / CrewAI / similar | Workflow distribution | Where builders already are |
| Compliance / audit vendors | Enterprise wedge | Stronger trust narrative |
| x402 / settlement ecosystem | Optional paid exchange later | Technical validation, settlement support |

---

## 20. Competitive Moats

### 20.1 Moat Depth Over Time

```
Time -->
                                                  +----------------------+
                                                  | NETWORK EFFECTS      |
                                            +-----| Nodes + claims +     |
                                            |     | subscriptions        |
                                      +-----|     +----------------------+
                                      |     |
                                +-----|     | TREATIES + POLICY CORPUS
                                |     |     | (Phase 2+)
                          +-----|     |     |
                          |     |     |     | VALIDATION GRAPH
                    +-----|     |     |     | (Phase 2)
                    |     |     |     |
              +-----|     |     |     | CLAIM MODEL + SUBSCRIPTIONS
              |     |     |     |     | (Phase 1)
        +-----|     |     |     |     |
        |     |     |     |     |     | MCP + OPEN SOURCE
        W1    W4    W8    W12   W16   W20+
```

### 20.2 Defensibility

| Moat | Strength | Why it matters |
|---|---|---|
| Claim-native data model | High | Harder to retrofit than a better retriever |
| Policy and treaty corpus | High | Encodes customer-specific trust logic and budgets |
| Validation / attestation graph | High | Improves trust and ranking over time |
| Standing queries inside workflows | High | Becomes operational plumbing, not an optional tool |
| MCP + SDK distribution | Medium | Faster adoption and switching from experiments |
| Network effects | Medium early, High later | Only matters after real federated usage exists |

---

## 21. Risk Analysis & Mitigations

| # | Risk | Prob | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **The ICP is still too broad** | Medium | High | Start with 2-3 workflows only. Do not market to the entire agent economy. |
| 2 | **Memory vendors add policy features** | Medium | High | Lean into claim-native architecture, subscriptions, and validation graph rather than generic governance slogans. |
| 3 | **Extraction quality is noisy** | Medium | High | Validation queue, attest/challenge flows, freshness decay, source-aware ranking. |
| 4 | **Subscription noise overwhelms users and agents** | Medium | Medium | Start with simple standing queries, digest modes, thresholds, and suppressions. |
| 5 | **Federation adoption is slow** | High | High | Treat single-node and two-node deployments as valuable products; do not require a public network to win. |
| 6 | **A2A / MCP spec churn** | Medium | Medium | Keep adapters isolated. Treat protocol support as versioned modules. |
| 7 | **Settlement adds complexity before demand exists** | Medium | Medium | Keep x402 optional and late. Validate paid exchange with one partner before broad rollout. |
| 8 | **Neo4j bottlenecks at scale** | Medium | Medium | Abstract graph layer and optimize claim query patterns early. |
| 9 | **Regulatory or compliance concerns slow deals** | Medium | High | Lead with audit, approvals, budgets, and licensing rather than "open marketplace" language. |
| 10 | **Team capacity / burnout** | High | Very High | Keep the roadmap narrow, design-partner-driven, and milestone-gated. |

---

## 22. Success Metrics & KPIs

### Phase 1 (Weeks 1-4)

| Metric | Target |
|---|---|
| Design partners actively testing | 2+ |
| MCP installs | 200+ |
| Time to first successful store/recall | < 10 minutes |
| Claim recall precision@5 | > 0.80 |
| Standing query notification latency | < 5 seconds local |
| Unauthorized claim retrievals blocked | 100% in test suite |

### Phase 2-3 (Weeks 5-12)

| Metric | Target |
|---|---|
| Active treaties / policy configs | 10+ |
| Claims with freshness metadata | > 90% |
| Claims with attestation or review state | > 60% in pilot workflows |
| Federated recall success rate | > 90% in partner environments |
| Weekly active SDK agents | 100+ |
| TypeScript SDK weekly downloads | 200+ |

### Phase 4-5 (Weeks 13-20)

| Metric | Target |
|---|---|
| Paying design partners | 3+ |
| Hosted MRR | $5,000+/mo |
| Organizations exchanging governed context | 2+ |
| Paid or licensed federated exchanges | 100+/month |
| Design-partner renewal intent | > 70% |
| Public network nodes | 10+ |

---

## 23. References & Resources

### Standards & Protocols

- [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004)
- [x402 Protocol](https://www.x402.org/)
- [Coinbase x402 GitHub](https://github.com/coinbase/x402)
- [A2A Specification](https://a2a-protocol.org/latest/specification/)
- [A2A Roadmap](https://a2a-protocol.org/latest/roadmap/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [MCP Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [MCP Sampling](https://modelcontextprotocol.io/specification/2025-11-25/client/sampling)

### Market and Competitor Context

- [Zep / Graphiti](https://www.getzep.com/)
- [Cognee](https://www.cognee.ai/)
- [Mem0 Graph Memory](https://docs.mem0.ai/platform/features/graph-memory)
- [Letta](https://www.letta.com/)
- [Memonex](https://www.memonex.ai/)
- [ClawForge](https://clawforge.dev/)
- [Knowbster](https://www.knowbster.com/)

### Governance, Trust, and Agentic Commerce

- [NIST AI Agent Standards Initiative](https://www.nist.gov/caisi/ai-agent-standards-initiative)
- [Google UCP](https://developers.google.com/merchant/ucp)
- [Stripe on Open Agentic Commerce Standards](https://stripe.com/blog/developing-an-open-standard-for-agentic-commerce)
- [McKinsey on Agentic Commerce](https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-agentic-commerce-opportunity-how-ai-agents-are-ushering-in-a-new-era-for-consumers-and-merchants)

---

## Appendix A: Key Decisions Log

| Decision | Choice | Rationale |
|---|---|---|
| Core primitive | `Claim` | Trust, ACL, freshness, and validation live on claims, not only memories |
| Graph DB | Neo4j | Native vector support and graph traversal in one store |
| API framework | FastAPI | Async-native, OpenAPI, Pydantic |
| Embedding default | sentence-transformers, 384 dims | Privacy-first, low dependency cost |
| LLM for extraction | Claude Sonnet 4.6 | Strong structured outputs |
| Phase 1 distribution | MCP | Fastest route into real agent workflows |
| Event model | Standing queries from day one | Agents should subscribe to context changes |
| Order of operations | Federation before settlement | Trust and usage before monetization |
| Monetization | Hosted trust layer first | Better economics than low-value micropayment fees |
| Optional adapters | x402 and signed service identity later | Useful, but not the wedge |
| Human interface | Operator control plane | Oversight, approvals, and audit rather than manual workflow UI |

## Appendix B: Environment Variables

```bash
# Core
CG_NEO4J_URI=bolt://localhost:7687
CG_NEO4J_USER=neo4j
CG_NEO4J_PASSWORD=contextgraph
CG_HOST=0.0.0.0
CG_PORT=8420
CG_DEBUG=false
CG_ENABLE_FEDERATION=false
CG_TRUST_THRESHOLD=0.65
CG_DEFAULT_CLAIM_TTL_DAYS=30

# LLM
CG_LLM_PROVIDER=anthropic
CG_ANTHROPIC_API_KEY=sk-ant-...
CG_EXTRACTION_MODEL=claude-sonnet-4-6

# Embeddings
CG_EMBEDDING_PROVIDER=local
CG_EMBEDDING_MODEL=all-MiniLM-L6-v2
CG_EMBEDDING_DIMENSIONS=384

# Async runtime
CG_ENABLE_BACKGROUND_WORKER=false
CG_BACKGROUND_WORKER_POLL_SECONDS=0.1
CG_WEBHOOK_TIMEOUT_SECONDS=5.0

# Settlement (optional)
CG_ENABLE_X402=false
CG_X402_FACILITATOR_URL=https://x402.coinbase.com
CG_PAYMENT_ADDRESS=0x...
CG_DEFAULT_QUERY_PRICE_USDC=0.002
CG_MONTHLY_BUDGET_USDC=100
```

## Appendix C: Timeline Summary

```
PHASE 1: Claim Engine + MCP                 ████████████████   Weeks 1-4
PHASE 2: Governance + Validation            ████████████████   Weeks 5-8
PHASE 3: A2A + Federation + TS SDK          ████████████████   Weeks 9-12
PHASE 4: Settlement + Licensing             ████████████████   Weeks 13-16
PHASE 5: Public Network                     ████████████████   Weeks 17-20

Total: ~5 months
Phase 1 is useful standalone.
Phase 5 should launch only if design-partner usage justifies it.
```

## Appendix D: v2 -> v2.1 Changelog

| What Changed | v2 | v2.1 | Why |
|---|---|---|---|
| Core framing | Context exchange fabric | Trust and claim exchange fabric | Clarifies the real wedge |
| Primary object | Memory + graph facts | Claim + attestation + standing query | Differentiates structurally |
| Roadmap order | Settlement before A2A | A2A/federation before settlement | Trust and exchange first |
| ICP | Broad agent economy | Narrow, high-cost-of-wrong-context workflows | Better path to PMF |
| Monetization | Generic network subscriptions | Hosted control plane and governance first | Better early economics |
| KPIs | Mix of vanity and adoption metrics | Design-partner, trust, and governed usage metrics | Better signal |
| Event model | Recall-centric | Recall + subscribe | Better fit for agent-first internet |

---

**This is the version I would execute.** The strategy is no longer "build a memory product and later add a marketplace." It is "build the trust layer for agent-generated claims, prove it in real workflows, then add federation, settlement, and network effects on top."
