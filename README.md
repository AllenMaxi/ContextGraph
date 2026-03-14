<p align="center">
  <img src="docs/assets/contextgraph-hero.jpeg" alt="ContextGraph — The Knowledge Layer for AI Agents" width="600">
</p>

<h1 align="center">ContextGraph</h1>

<p align="center">
  <strong>The Knowledge Layer for AI Agents</strong><br>
  Store memories. Extract claims. Share knowledge across agents.<br>
  <em>Private by default. Paid when you want. Verified on-chain.</em>
</p>

<p align="center">
  <a href="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml"><img src="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://pypi.org/project/contextgraph"><img src="https://img.shields.io/pypi/v/contextgraph.svg" alt="PyPI"></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-8A2BE2.svg" alt="MCP Compatible"></a>
  <a href="https://www.x402.org"><img src="https://img.shields.io/badge/x402-payments-orange.svg" alt="x402 Payments"></a>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> &middot;
  <a href="#features">Features</a> &middot;
  <a href="#architecture">Architecture</a> &middot;
  <a href="#comparison">Comparison</a> &middot;
  <a href="docs/">Docs</a> &middot;
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="docs/README_ES.md">Español</a>
</p>

---

## News

- **2026-03-14** — ContextGraph v0.1.0 released with MCP server, x402 payments, ERC-8004 identity, A2A federation
- **2026-03-14** — Full BM25 scoring engine replaces Jaccard similarity
- **2026-03-14** — LLM-powered extraction with Claude Sonnet 4.6

---

## What is ContextGraph?

ContextGraph is an **open-source knowledge graph protocol** that gives AI agents persistent, shared memory with built-in trust, permissions, and payments.

Agents produce knowledge. ContextGraph captures it as **structured claims** with provenance, confidence scores, and expiry dates — then makes it discoverable across agents, organizations, and platforms.

```
Your Agent                    ContextGraph                    Other Agents
    │                              │                              │
    │── store("Acme reported       │                              │
    │   API latency. Jane needs    │                              │
    │   a fix.")                   │                              │
    │                              │── Extract claims:            │
    │                              │   "Acme reported latency"    │
    │                              │   "Jane needs a fix"         │
    │                              │── Extract entities:          │
    │                              │   Acme Corp, Jane            │
    │                              │── Build graph relations      │
    │                              │                              │
    │                              │   recall("Acme issues") ◄────│
    │                              │── Permission check           │
    │                              │── Payment gate (x402)        │
    │                              │── BM25 + freshness scoring   │
    │                              │── Return ranked claims ─────►│
```

### Where ContextGraph Fits

| Layer | Protocol | What it does |
|-------|----------|-------------|
| **Orchestration** | LangGraph, CrewAI | Task routing and agent coordination |
| **Communication** | A2A Protocol | Cross-agent discovery and messaging |
| **Tools** | MCP (Model Context Protocol) | Tool and resource integration |
| **Payments** | x402 Protocol | HTTP-native micropayments |
| **Identity** | ERC-8004 | On-chain agent identity |
| **Knowledge** | **ContextGraph** | **Persistent shared memory with trust** |

ContextGraph is the **missing knowledge layer** — it integrates with all the protocols above so your agents can remember, share, and monetize what they know.

---

## Features

### Claim-Native Memory

Raw text goes in. Structured claims come out. Every memory is decomposed into **claims** (facts), **entities** (people, companies, concepts), and **relations** (connections between entities) — powered by BM25 scoring and optional LLM extraction via Claude.

```python
result = service.store_memory(
    agent_id=agent.agent_id,
    content="Jane from Acme Corp reported critical API latency on March 10.",
    visibility="org",
)
# result.claims  → [Claim("Acme Corp reported critical API latency"), ...]
# result.entities → [Entity("Jane", type="person"), Entity("Acme Corp", type="company")]
```

### Granular Permissions (4-Tier)

Agents choose who sees their knowledge:

| Visibility | Who can access | Use case |
|-----------|---------------|----------|
| `private` | Only the source agent | Internal reasoning, scratch notes |
| `org` | Any agent in the same organization | Team knowledge, shared context |
| `shared` | Specific agents/orgs via `access_list` | Partner sharing, cross-org collaboration |
| `published` | Everyone (including federated nodes) | Public knowledge, monetized claims |

```python
# Share with specific partners
service.store_memory(
    agent_id=agent.agent_id,
    content="Q4 revenue projection: $2.3M",
    visibility="shared",
    access_list=["partner-agent-id", "org-partner-corp"],
)
```

### x402 Payments — Monetize Your Knowledge

Price your claims. Other agents pay with the [x402 protocol](https://www.x402.org/) (HTTP 402) to access premium knowledge. Same-org agents never pay each other. Supports any currency — USDC, USDT, ETH, BTC, or fiat.

```python
# Price your knowledge
service.store_memory(
    agent_id=agent.agent_id,
    content="Market analysis: semiconductor supply chain disruptions expected Q3.",
    visibility="published",
    price=0.002,  # Per recall, in configured currency (default: USDC)
)

# Other agents pay to access
hits = service.recall(
    agent_id=other_agent.agent_id,
    query="semiconductor supply chain",
    payment_token="x402_token_...",
)

# Same-org agents always access for free — no payment needed
```

> **[Full payments guide](docs/payments.md)** — setup, verifiers, supported currencies, and examples.
```

### ERC-8004 Agent Identity

Verify agent identity on-chain using the [ERC-8004 standard](https://eips.ethereum.org/EIPS/eip-8004). Verified agents get higher trust scores.

```python
agent = service.register_agent(
    name="research-agent",
    org_id="acme",
    capabilities=["research"],
    erc8004_address="0x1234567890abcdef1234567890abcdef12345678",
)
# agent.identity_verified = True (after on-chain verification)
```

### MCP Server — Use with Claude & GPT

ContextGraph ships as an [MCP server](https://modelcontextprotocol.io/) so Claude, GPT, and other MCP-compatible agents can use it directly as a tool.

<details>
<summary><strong>Claude Desktop / Claude Code setup</strong></summary>

Add to your MCP config (`claude_desktop_config.json` or `.mcp.json`):

```json
{
  "mcpServers": {
    "contextgraph": {
      "command": "python",
      "args": ["-m", "contextgraph.mcp_server"],
      "env": { "CG_AGENT_ID": "my-agent" }
    }
  }
}
```

</details>

<details>
<summary><strong>Available MCP tools</strong></summary>

| Tool | Description |
|------|------------|
| `contextgraph_store` | Store a memory and extract claims |
| `contextgraph_recall` | Search claims by semantic query |
| `contextgraph_relate` | Find entity relationship paths |
| `contextgraph_watch` | Subscribe to topics |
| `contextgraph_notifications` | Get pending notifications |
| `contextgraph_review` | Attest or challenge a claim |

</details>

### Federation & A2A Protocol

Share published knowledge across ContextGraph nodes. Each node exposes an [A2A agent card](https://google.github.io/A2A/) at `/.well-known/agent.json` for cross-agent discovery.

```bash
# Enable federation
CG_ENABLE_FEDERATION=true
CG_FEDERATION_PEERS=https://partner-node.example.com
CG_ENABLE_A2A=true
```

### Trust & Governance

Claims go through review workflows with attestation and challenge cycles:

- **Attestation** — other agents vouch for a claim's accuracy
- **Challenge** — agents flag disputed claims
- **Expiry** — claims automatically expire based on TTL
- **Confidence scoring** — BM25 + freshness + validation status

### Standing Queries & Notifications

Subscribe to topics and get notified when matching claims arrive — via pull, webhook, or A2A delivery:

```python
service.watch(
    agent_id=agent.agent_id,
    query="Acme latency",
    delivery_mode="webhook",
    filters={"webhook_url": "https://my-agent.example.com/notify"},
)
```

---

## Quickstart

### Install

```bash
pip install contextgraph
# With server (FastAPI + Uvicorn):
pip install contextgraph[server]
# With MCP support:
pip install contextgraph[mcp]
# Everything:
pip install contextgraph[server,mcp]
```

### 5 Lines to Shared Agent Memory

```python
from contextgraph import ContextGraphService

service = ContextGraphService()
agent = service.register_agent("my-agent", "my-org", ["research"])
service.store_memory(agent.agent_id, "Acme Corp reported API latency.", visibility="org")
hits = service.recall(agent.agent_id, "Acme latency")
print(hits[0].claim.statement)  # "Acme Corp reported API latency"
```

### HTTP API

<details>
<summary><strong>Register, store, and recall via curl</strong></summary>

```bash
# Start the server
contextgraph-server

# Register an agent
curl -X POST http://localhost:8420/v1/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name":"my-agent","org_id":"acme","capabilities":["research"]}'

# Store a memory (use api_key from registration response)
curl -X POST http://localhost:8420/v1/memory/store \
  -H "Content-Type: application/json" \
  -H "X-Agent-Key: <api_key>" \
  -d '{"content":"Acme Corp reported API latency.","visibility":"org"}'

# Recall claims
curl -X POST http://localhost:8420/v1/memory/recall \
  -H "Content-Type: application/json" \
  -H "X-Agent-Key: <api_key>" \
  -d '{"query":"Acme latency"}'
```

Full OpenAPI docs at `http://localhost:8420/docs`.

</details>

### Docker

```bash
docker compose up
```

Starts ContextGraph + Neo4j. API at `http://localhost:8420`, docs at `http://localhost:8420/docs`.

### Python SDK

```python
from sdk.contextgraph_sdk import ContextGraph

# Local (in-process, no server needed)
client = ContextGraph.local()

# HTTP (connects to running server)
client = ContextGraph.http("http://localhost:8420", api_key="cgk_...")

agent = client.register_agent("sdk-agent", "acme", ["research"])
client.store(agent["agent_id"], "Important finding about market trends.", visibility="org")
hits = client.recall(agent["agent_id"], "market trends")
```

See [sdk/README.md](sdk/README.md) for full SDK documentation.

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              ContextGraph                    │
                    │                                             │
  HTTP/REST ───────▶│  ┌─────────┐  ┌───────────┐  ┌──────────┐ │
  MCP (stdio) ─────▶│  │ API     │  │ Service   │  │ Graph    │ │
  A2A Protocol ────▶│  │ Layer   │──│ Layer     │──│ Backend  │ │
  Python SDK ──────▶│  └─────────┘  └───────────┘  └──────────┘ │
                    │       │            │               │        │
                    │  ┌────┴────┐  ┌────┴─────┐  ┌─────┴──────┐│
                    │  │Auth     │  │Extraction│  │In-Memory   ││
                    │  │Rate Lim │  │BM25 Score│  │Neo4j       ││
                    │  │x402 Pay │  │LLM/Rules │  │            ││
                    │  │ERC-8004 │  │Federation│  │            ││
                    │  └─────────┘  └──────────┘  └────────────┘│
                    └─────────────────────────────────────────────┘
```

### Data Model

```
Agent ──stores──▶ Memory ──extracts──▶ Claims ──reference──▶ Entities
                                         │                      │
                                         ├── confidence score    ├── aliases
                                         ├── freshness score     ├── type
                                         ├── validation status   └── relations
                                         ├── visibility (4-tier)
                                         ├── access_list
                                         ├── price (x402)
                                         └── expires_at (TTL)
```

---

## Comparison

| Feature | ContextGraph | Mem0 | Zep | LangMem |
|---------|:---:|:---:|:---:|:---:|
| Structured claims (not just text) | **Yes** | No | No | No |
| Granular permissions (4-tier) | **Yes** | No | Basic | No |
| Cross-org sharing | **Yes** | No | No | No |
| x402 knowledge payments | **Yes** | No | No | No |
| On-chain identity (ERC-8004) | **Yes** | No | No | No |
| MCP server | **Yes** | No | No | No |
| A2A protocol | **Yes** | No | No | No |
| Federation | **Yes** | No | No | No |
| Trust/attestation model | **Yes** | No | No | No |
| Standing queries & webhooks | **Yes** | No | Partial | No |
| Neo4j graph backend | **Yes** | No | No | No |
| BM25 + LLM extraction | **Yes** | Partial | Partial | Partial |
| Open source | **MIT** | Partial | Partial | Yes |

---

## Configuration

All settings via environment variables. See [`.env.example`](.env.example) for the complete list.

| Variable | Default | Description |
|----------|---------|-------------|
| `CG_REPOSITORY_BACKEND` | `memory` | `memory` or `neo4j` |
| `CG_ENABLE_PAYMENTS` | `false` | Enable x402 payment gate |
| `CG_ENABLE_IDENTITY` | `false` | Enable ERC-8004 verification |
| `CG_ENABLE_FEDERATION` | `false` | Enable cross-node federation |
| `CG_ENABLE_A2A` | `false` | Enable A2A protocol server |
| `CG_LLM_API_KEY` | _(empty)_ | Anthropic API key for LLM extraction |
| `CG_LLM_MODEL` | `claude-sonnet-4-6` | Model for claim extraction |
| `CG_ADMIN_KEY` | _(empty)_ | Require admin key for agent registration |
| `CG_RATE_LIMIT_PER_MINUTE` | `60` | API rate limit per key |
| `CG_CORS_ORIGINS` | `*` | Allowed CORS origins |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/v1/agents/register` | POST | Register a new agent |
| `/v1/agents` | GET | List agents in your org |
| `/v1/memory/store` | POST | Store memory and extract claims |
| `/v1/memory/store-async` | POST | Async memory storage (background job) |
| `/v1/memory/recall` | POST | Search claims by query |
| `/v1/memory/relate` | POST | Find entity relation paths |
| `/v1/watch` | POST/GET | Create or list standing queries |
| `/v1/claims` | GET | List claims |
| `/v1/claims/{id}` | GET | Get a specific claim |
| `/v1/claims/review` | POST | Attest or challenge a claim |
| `/v1/review-queue` | GET | Claims needing review |
| `/v1/notifications/{id}` | GET | Get pending notifications |
| `/v1/operator/summary` | GET | Org-level dashboard |
| `/v1/audit` | GET | Audit log |
| `/v1/jobs/{id}` | GET | Background job status |
| `/.well-known/agent.json` | GET | A2A agent card |
| `/v1/federation/claims` | GET | Federated claim list |

Full interactive docs at `http://localhost:8420/docs` (Swagger UI).

---

## Evaluation

Built-in extractor evaluation framework:

```bash
contextgraph-eval                              # Run evaluator
contextgraph-eval --fixture custom.json        # Custom fixtures
contextgraph-eval-dataset traces.jsonl out.json # Build from agent traces
```

## Operator Console

Web UI for reviewing claims, monitoring jobs, and viewing audit logs:

```
http://localhost:8420/console
```

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

```bash
git clone https://github.com/AllenMaxi/ContextGraph.git
cd contextgraph
make install    # Install dev dependencies
make test       # Run test suite (90+ tests)
make lint       # Run linter
make format     # Auto-format code
```

## Security

For security vulnerabilities, please see [SECURITY.md](SECURITY.md). **Do not open public issues for security bugs.**

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  Built for the agent economy.<br>
  <strong>ContextGraph</strong> — because agents deserve memory that's structured, trusted, and shared.
</p>
