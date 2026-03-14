# ContextGraph Open-Source Launch — Design Spec

**Date:** 2026-03-12
**Author:** Maximilian Allende + Claude (AI Partner)
**Status:** Draft — Pending Review
**Timeline:** 3-4 weeks to polished launch
**Goal:** Ship the "Knowledge Layer for AI Agents" as a compelling open-source project targeting 10K+ stars

---

## 1. Positioning & Brand

### One-Liner
> **ContextGraph: The Knowledge Layer for AI Agents**

### Tagline
> **3 Lines of Code · Any Framework · Cross-Org Sharing**

### Elevator Pitch
Every AI agent today stores memory in flat text blobs, isolated from other agents. ContextGraph is a knowledge graph protocol that lets agents store, share, and trade structured knowledge — across frameworks, across teams, across companies. It's the missing piece in the agent infrastructure stack.

### Where We Fit

```
Orchestration    →  NVIDIA NemoClaw, LangGraph, CrewAI
Deployment       →  ClawCloud, Railway, Vercel
Communication    →  A2A (Google/Linux Foundation)
Tools            →  MCP (Anthropic/Linux Foundation)
Payments         →  x402 (Coinbase/Cloudflare)
Identity         →  ERC-8004 (Ethereum)
Memory/Knowledge →  ContextGraph  ← THIS IS US
```

### Brand Identity
- **Mascot:** Graph Octopus — an octopus creature whose tentacles form knowledge graph edges, connecting different agent nodes. Friendly, technical, memorable.
- **Color palette:** Deep ocean blue (#0A1628) + Electric cyan (#00D4FF) + Graph green (#00FF88) + White
- **Tone:** Technical but approachable. Like PicoClaw — confident, honest about limitations, community-first.
- **Name:** ContextGraph (domain: contextgraph.dev)

---

## 2. Target Audience (Ordered by Priority)

### Primary: AI/ML Engineers Building Multi-Agent Systems
- Use LangGraph, CrewAI, AutoGen, OpenClaw, NemoClaw
- Pain: agents forget context, can't share knowledge, framework lock-in
- Need: drop-in memory that works with their stack
- Where they are: GitHub, r/MachineLearning, HuggingFace, X/Twitter

### Secondary: Web3/Crypto Builders
- Building on ERC-8004, x402, Base chain
- Pain: agents can't monetize knowledge, no identity layer
- Need: knowledge commerce infrastructure
- Where they are: Ethereum forums, Crypto Twitter, Farcaster

### Tertiary: Platform/DevOps Engineers
- Deploying agents for their company
- Pain: agents in silos, no shared organizational memory
- Need: self-hosted knowledge layer with org scoping
- Where they are: HN, DevOps communities, Kubernetes forums

---

## 3. Competitive Comparison

| Feature | Mem0 | Zep/Graphiti | Letta (MemGPT) | Cognee | **ContextGraph** |
|---------|------|-------------|----------------|--------|-----------------|
| Storage model | Flat key-value | Knowledge graph | Stateful memory | Knowledge graph | **Knowledge graph** |
| Cross-agent sharing | No | No | No | No | **Yes (org + published)** |
| Cross-org federation | No | No | No | No | **Yes (A2A)** |
| Framework agnostic | Partial | Partial | No (own runtime) | Yes | **Yes (MCP + A2A + SDK)** |
| Agent identity | No | No | No | No | **ERC-8004 (Phase 3)** |
| Knowledge payments | No | No | No | No | **x402 (Phase 3)** |
| Standing queries | No | No | No | No | **Yes (webhook + A2A)** |
| Claim attestation | No | No | No | No | **Yes (trust scoring)** |
| Self-hostable | Cloud only | Yes | Yes | Yes | **Yes (Docker one-liner)** |
| Zero dependencies | No | No | No | No | **Yes (core)** |

---

## 4. Architecture Overview

### System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   ContextGraph Node                   │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │ REST API │  │MCP Server│  │   A2A Server       │ │
│  │ (FastAPI)│  │(Anthropic│  │ (Google Protocol)  │ │
│  │          │  │ Protocol)│  │                    │ │
│  └────┬─────┘  └────┬─────┘  └────────┬───────────┘ │
│       │              │                 │             │
│       └──────────────┼─────────────────┘             │
│                      │                               │
│              ┌───────▼────────┐                      │
│              │  Service Layer  │                      │
│              │  (Core Engine)  │                      │
│              └───────┬────────┘                      │
│                      │                               │
│       ┌──────────────┼──────────────┐               │
│       │              │              │               │
│  ┌────▼─────┐  ┌─────▼────┐  ┌─────▼──────┐       │
│  │Extraction│  │Background│  │ Delivery   │       │
│  │(LLM +   │  │ Worker   │  │ (Webhook + │       │
│  │ Rules)   │  │ (Jobs)   │  │  A2A)      │       │
│  └──────────┘  └──────────┘  └────────────┘       │
│                      │                               │
│              ┌───────▼────────┐                      │
│              │  Repository    │                      │
│              │  (Pluggable)   │                      │
│              └───────┬────────┘                      │
│                      │                               │
│          ┌───────────┼───────────┐                  │
│          │                       │                  │
│     ┌────▼─────┐          ┌─────▼──────┐          │
│     │In-Memory │          │   Neo4j    │          │
│     │(Dev/Test)│          │(Production)│          │
│     └──────────┘          └────────────┘          │
│                                                       │
└───────────────────────────────────────────────────────┘
         │                              │
         │ A2A Federation               │ A2A Federation
         ▼                              ▼
  ┌──────────────┐              ┌──────────────┐
  │ContextGraph  │              │ContextGraph  │
  │  Node (Org B)│              │  Node (Org C)│
  └──────────────┘              └──────────────┘
```

### Data Flow: Store → Extract → Share → Notify

```
Agent stores text → LLM extracts entities + relations → Claims created in graph
                                                              │
                                    ┌─────────────────────────┤
                                    │                         │
                              Standing queries            Federation
                              match & notify              replicates to
                              subscribed agents           connected nodes
```

### Core Primitives

| Primitive | Description | Example |
|-----------|-------------|---------|
| **Memory** | Raw text input from an agent | "Acme Corp reported API latency. CTO Jane wants a fix." |
| **Claim** | Extracted structured fact with provenance | `(Acme Corp) --HAS_CTO--> (Jane)` confidence: 0.9 |
| **Entity** | A node in the knowledge graph | `Acme Corp` (type: organization) |
| **Standing Query** | Subscription to future knowledge | "Notify me about anything related to Acme Corp" |
| **Attestation** | Trust signal on a claim | Agent B attests claim from Agent A → confidence rises |

---

## 5. Phase 1 Deliverables (Weeks 1-2): "Redis of Agent Memory"

### 5.1 Security Fixes (Critical)

| Fix | Current | Target |
|-----|---------|--------|
| API key generation | `uuid4().hex[:12]` (48 bits) | `secrets.token_urlsafe(32)` (256 bits) |
| Agent registration | Unauthenticated, any org | Admin bootstrap key required |
| Console auth | API key in URL query string | POST-based auth with session cookie |
| Input validation | No content length limit | 100KB max content, rate limiting |
| Webhook SSRF | No URL validation | Block private IPs (10.x, 172.x, 169.254.x) |
| CORS | Not configured | Explicit origin allowlist |

### 5.2 Open-Source Packaging

| Deliverable | Details |
|-------------|---------|
| `LICENSE` | MIT license file (matches pyproject.toml) |
| `.gitignore` | Python, Neo4j, IDE, OS files |
| `CONTRIBUTING.md` | How to contribute, code style, PR process |
| `CODE_OF_CONDUCT.md` | Contributor Covenant v2.1 |
| `CHANGELOG.md` | Keep-a-changelog format, v0.2.0 as first entry |
| `SECURITY.md` | Responsible disclosure policy |
| `.github/workflows/ci.yml` | Run tests with `.[server,dev]`, lint with ruff, type-check with mypy |
| `.github/ISSUE_TEMPLATE/` | Bug report + feature request templates |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR template with checklist |
| `Makefile` | `make test`, `make lint`, `make serve`, `make docker`, `make dev` |
| `Dockerfile` | Multi-stage build, Python 3.11-slim |
| `docker-compose.yml` | App + Neo4j + optional Redis |

### 5.3 MCP Server (Key Differentiator)

Implement a full MCP tool server so any Claude/GPT/Gemini agent can use ContextGraph as a tool.

**MCP Tools Exposed:**
- `contextgraph_store` — Store a memory with content and visibility
- `contextgraph_recall` — Query the knowledge graph
- `contextgraph_relate` — Find paths between entities
- `contextgraph_watch` — Subscribe to future knowledge
- `contextgraph_review` — Attest or challenge a claim

**Integration:** Users add ContextGraph to their `claude_desktop_config.json` or MCP client:
```json
{
  "mcpServers": {
    "contextgraph": {
      "command": "contextgraph-mcp",
      "args": ["--url", "http://localhost:8420"]
    }
  }
}
```

### 5.4 LLM-Powered Extraction (Upgrade from Rule-Based)

Replace `RuleBasedExtractor` with `LLMExtractor` as the default when an API key is configured:

- Use Claude Sonnet 4.6 (or configurable model) for entity/relation extraction
- Structured output with JSON schema for claims
- Fall back to `RuleBasedExtractor` when no LLM API key is set
- Keep `RuleBasedExtractor` as zero-dependency option

**Extraction prompt pattern:**
```
Given this text, extract:
1. Named entities (name, type: person/organization/concept/product)
2. Relationships between entities (subject, predicate, object)
3. Confidence score (0.0-1.0) for each claim

Return as structured JSON.
```

### 5.5 Structured Logging

Add `logging.getLogger(__name__)` throughout:
- Request/response logging in API layer
- Extraction results logging
- Job processing lifecycle
- Authentication events
- Correlation IDs per request via middleware

### 5.6 README Rewrite (PicoClaw-Inspired)

**Structure:**
```
1. Hero image (graph octopus mascot scene)
2. Title: "ContextGraph: The Knowledge Layer for AI Agents"
3. Tagline: "3 Lines of Code · Any Framework · Cross-Org Sharing"
4. Badges: Python 3.11+ | License MIT | CI passing | Discord | X/Twitter
5. Language links: English | Spanish | Chinese | Portuguese | Japanese
6. What is ContextGraph? (3 sentences max)
7. Comparison table (vs Mem0, Zep, Letta, Cognee)
8. Demo GIF: Agent stores memory → graph visualized → another agent recalls
9. Quickstart (4 steps, under 200 words)
10. MCP Integration (3-step setup for Claude/GPT)
11. SDK Usage (store/recall/relate in 3 lines each)
12. Architecture diagram (the stack positioning)
13. Features list (with icons)
14. Docker deployment
15. Configuration reference
16. Roadmap (phases with checkboxes)
17. Contributing
18. Community links
19. License
```

### 5.7 Hero Image & Visual Assets

- **Hero image:** Illustrated graph octopus in a futuristic control room, tentacles connecting agent nodes on screens. Style: semi-realistic digital art, dark theme matching GitHub dark mode.
- **Architecture diagram:** Clean SVG showing the stack positioning
- **Demo GIF:** Terminal recording showing store → recall → relate flow
- **Favicon/Logo:** Simplified octopus head with graph node eyes

**Image generation:** Use an AI image generator (DALL-E, Midjourney, or Flux) with prompt engineering. The hero image should be ~1200x600px, optimized for GitHub README display.

---

## 6. Phase 1.5 Deliverables (Week 3): Cross-Org & Protocols

### 6.1 A2A Integration

Implement Google's A2A protocol for agent-to-agent communication:

**Agent Card:** Each ContextGraph node publishes an A2A Agent Card at `/.well-known/agent.json`:
```json
{
  "name": "contextgraph-node-acme",
  "description": "Knowledge graph memory node for Acme Corp agents",
  "url": "https://cg.acme.com",
  "capabilities": {
    "memory_store": true,
    "memory_recall": true,
    "knowledge_federation": true
  },
  "protocols": ["contextgraph/v1", "a2a/v1", "mcp/v1"]
}
```

**A2A Tasks:**
- `knowledge/recall` — Remote agent queries this node's published knowledge
- `knowledge/subscribe` — Remote agent subscribes to knowledge matching a query
- `knowledge/attest` — Remote agent attests or challenges a claim

### 6.2 Basic Federation

Two ContextGraph nodes can connect and share `published` claims:

**Federation handshake:**
1. Node A discovers Node B via A2A Agent Card
2. Node A sends federation request with its own Agent Card
3. Node B approves (manual or policy-based)
4. Nodes exchange published claims on a configurable schedule
5. Standing queries can match federated claims

**Scope for Phase 1.5:**
- Manual peer registration via API (`POST /v1/federation/peers`)
- Pull-based sync (Node A polls Node B for new published claims)
- No conflict resolution (last-write-wins for duplicate entities)
- No payment (free federation, x402 comes in Phase 3)

### 6.3 Cross-Org Discovery

New endpoint: `GET /v1/agents/discover`
- Returns Agent Cards of federated peers
- Agents can browse available knowledge sources
- Filter by capabilities, topics, org

### 6.4 Granular Permissions

Upgrade from binary `published` to fine-grained ACLs:

| Visibility | Who Can Access |
|-----------|----------------|
| `private` | Only source agent |
| `org` | All agents in same org_id |
| `shared` | Specific agent_ids or org_ids (allowlist) |
| `published` | Any authenticated agent (including federated) |

New field on Claims: `access_list: list[str]` — agent_ids or org_ids allowed for `shared` visibility.

---

## 7. Phase 2 Deliverables (Week 4): Polish & Launch

### 7.1 Multi-Language README
- English (primary)
- Spanish (author's native context)
- Chinese (largest developer community)
- Portuguese (Brazil tech scene)
- Japanese (strong AI/ML community)

### 7.2 Landing Page
- Single-page site at contextgraph.dev
- Hero section with mascot + tagline
- Animated architecture diagram
- Live demo (embedded terminal or Replit)
- "Add to your agent in 30 seconds" CTA
- Built with Astro or plain HTML (minimal)

### 7.3 Demo GIFs / Videos
- **GIF 1:** "Store & Recall" — Agent stores text, graph appears, another agent recalls
- **GIF 2:** "Cross-Agent Sharing" — Two agents in different orgs share knowledge via federation
- **GIF 3:** "MCP Integration" — Claude Desktop using ContextGraph as a tool

### 7.4 SDK Improvements
- HTTP transport: add retry logic (3 attempts, exponential backoff)
- HTTP transport: configurable timeout (default 30s)
- Async support via `ContextGraphAsync` client
- Standalone `pip install contextgraph-sdk` package
- SDK README with independent documentation

### 7.5 Developer Experience
- `make dev` — Start local development environment (app + Neo4j via Docker)
- `make test` — Run full test suite with server dependencies
- `make lint` — ruff + mypy
- `make docs` — Generate OpenAPI spec
- Pre-commit hooks configuration (.pre-commit-config.yaml)
- `ruff.toml` + `mypy.ini` configurations

### 7.6 Additional Tests
- Cross-org `published` visibility tests
- Multi-hop `relate` traversal tests
- Empty/unicode/long input extraction tests
- Console form submission tests
- Concurrent background worker tests
- Federation handshake tests
- MCP server tool tests
- Rate limiting tests

---

## 8. Phase 3 Vision (Post-Launch, 4 weeks)

Not in scope for initial launch but documented for roadmap:

- **x402 Payments:** `POST /v1/marketplace/recall` returns HTTP 402, agent pays USDC, receives knowledge
- **ERC-8004 Identity:** On-chain agent registration, reputation scoring from attestations
- **Managed Cloud:** contextgraph.cloud — hosted nodes at $49-199/mo
- **TypeScript SDK:** For Node.js agent frameworks
- **Vector Embeddings:** sentence-transformers for semantic recall (upgrade from Jaccard)
- **Dashboard UI:** React-based operator dashboard (beyond current HTML console)
- **Multi-chain:** Support Base, Ethereum, Solana for payments

---

## 9. Success Metrics

### Launch Week
- 1,000+ GitHub stars
- 50+ forks
- README shared on HN front page, r/MachineLearning, X/Twitter
- 10+ community Discord members

### Month 1
- 5,000+ GitHub stars
- 20+ external PRs
- 3+ blog posts / tutorials by community members
- 100+ pip installs/week
- 5+ MCP integration users

### Month 3
- 10,000+ GitHub stars
- Federation between 3+ independent nodes
- Featured in NVIDIA NemoClaw or LangGraph ecosystem docs
- First x402 knowledge transaction on testnet

---

## 10. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Nobody uses federation | Phase 1 standalone value is strong enough without it |
| LLM extraction too expensive | Rule-based extractor works at zero cost |
| Competitor copies the approach | Network effects from federation create switching costs |
| Too complex for newcomers | 4-step quickstart, Docker one-liner, MCP 3-step setup |
| Security incident post-launch | SECURITY.md + responsible disclosure + 256-bit keys + rate limiting |

---

## 11. Files to Create/Modify

### New Files
```
LICENSE                              # MIT license
.gitignore                           # Python/Neo4j/IDE/OS ignores
CONTRIBUTING.md                      # Contribution guide
CODE_OF_CONDUCT.md                   # Contributor Covenant
CHANGELOG.md                         # Release history
SECURITY.md                          # Security policy
Makefile                             # Dev commands
Dockerfile                           # Multi-stage build
docker-compose.yml                   # App + Neo4j
.github/workflows/ci.yml            # CI pipeline
.github/ISSUE_TEMPLATE/bug.yml      # Bug report template
.github/ISSUE_TEMPLATE/feature.yml  # Feature request template
.github/PULL_REQUEST_TEMPLATE.md    # PR template
.pre-commit-config.yaml             # Pre-commit hooks
ruff.toml                           # Linter config
contextgraph/protocols/mcp_server.py # Full MCP implementation (replace stub)
contextgraph/protocols/a2a_server.py # A2A protocol server
contextgraph/extraction_llm.py      # LLM-powered extractor
contextgraph/federation.py          # Federation sync logic
contextgraph/middleware.py           # Rate limiting, CORS, correlation IDs
sdk/contextgraph_sdk/async_client.py # Async SDK client
sdk/README.md                       # SDK documentation
docs/README.es.md                   # Spanish README
docs/README.zh.md                   # Chinese README
docs/README.pt.md                   # Portuguese README
docs/README.ja.md                   # Japanese README
assets/hero.png                     # Hero image (generated)
assets/logo.svg                     # Logo/favicon
assets/demo-store-recall.gif        # Demo GIF 1
assets/demo-cross-agent.gif         # Demo GIF 2
assets/demo-mcp.gif                 # Demo GIF 3
```

### Modified Files
```
README.md                            # Complete rewrite (PicoClaw-inspired)
contextgraph/service.py              # Security fixes, federation, granular ACLs
contextgraph/config.py               # New settings (LLM, federation, rate limits)
contextgraph/models.py               # access_list field, federation models
contextgraph/api/routes.py           # Federation endpoints, rate limiting
contextgraph/api/dependencies.py     # Admin key auth, session cookies
contextgraph/api/console.py          # POST-based auth (remove key from URL)
contextgraph/web.py                  # Lifespan handler (replace deprecated on_event)
contextgraph/delivery.py             # SSRF protection for webhooks
contextgraph/errors.py               # Rate limit error
pyproject.toml                       # Add MCP, A2A, ruff, mypy dependencies
```

### Files to Remove
```
2026-03-07-contextgraph-design.md           # Move to docs/internal/
2026-03-07-contextgraph-implementation-plan.md  # Move to docs/internal/
```

---

## 12. README Hero Section (Draft)

```markdown
<p align="center">
  <img src="assets/hero.png" alt="ContextGraph — The Knowledge Layer for AI Agents" width="800">
</p>

<h1 align="center">ContextGraph: The Knowledge Layer for AI Agents</h1>

<h3 align="center">3 Lines of Code · Any Framework · Cross-Org Sharing</h3>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License"></a>
  <a href="#"><img src="https://img.shields.io/github/actions/workflow/status/contextgraph/contextgraph/ci.yml?label=CI" alt="CI"></a>
  <a href="#"><img src="https://img.shields.io/discord/XXXXX?label=Discord&color=7289da" alt="Discord"></a>
  <a href="#"><img src="https://img.shields.io/twitter/follow/contextgraph" alt="X/Twitter"></a>
</p>

<p align="center">
  <a href="docs/README.es.md">Espanol</a> |
  <a href="docs/README.zh.md">中文</a> |
  <a href="docs/README.pt.md">Portugues</a> |
  <a href="docs/README.ja.md">日本語</a> |
  English
</p>
```

### Quickstart Section (Draft)

```markdown
## Quickstart

### 1. Install
```bash
pip install contextgraph
```

### 2. Start the server
```bash
docker run -d --name contextgraph -p 8420:8420 contextgraph/contextgraph
```

### 3. Use it

```python
from contextgraph_sdk import ContextGraph

cg = ContextGraph.http("http://localhost:8420", api_key="your-key")

# Store knowledge
cg.store("agent-1", "Acme Corp CTO Jane reported critical API latency issues")

# Recall knowledge (from any agent in your org)
hits = cg.recall("agent-2", "What problems does Acme have?")

# Discover connections
paths = cg.relate("agent-2", "Acme Corp", "Jane")
# → (Acme Corp) --[HAS_CTO]--> (Jane) --[REPORTED]--> (API Latency)
```
```

---

*End of design spec. Ready for review.*
