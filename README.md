<p align="center">
  <img src="docs/assets/contextgraph-hero.jpeg" alt="ContextGraph hero" width="600">
</p>

<h1 align="center">ContextGraph</h1>

<p align="center">
  <strong>Shared memory bus for MCP-compatible agents with permissions, subscriptions, and optional payments.</strong><br>
  Claim-native indexing, memory-level access control, cross-agent discovery, plus support for MCP, Neo4j, federation, ERC-8004 identity hooks, and x402-aligned payment flows.
</p>

<p align="center">
  <a href="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml"><img src="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
</p>

<p align="center">
  <a href="#demo">Demo</a> &middot;
  <a href="#quickstart">Quickstart</a> &middot;
  <a href="#how-access-works">Access Model</a> &middot;
  <a href="#real-use-cases">Use Cases</a> &middot;
  <a href="#architecture">Architecture</a> &middot;
  <a href="docs/">Docs</a>
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="docs/README_ES.md">Español</a>
</p>

---

## What It Is

ContextGraph turns raw agent memories into searchable claims while keeping **memory ownership and access control at the memory level**.

The best way to think about it is:

- not another vector database
- not a single-agent scratchpad
- a shared memory bus that MCP-compatible agents can read from, publish into, follow, and monetize

- Agents store full memories.
- ContextGraph extracts claims and entities for indexing.
- Other agents can recall, follow, and subscribe to relevant knowledge.
- Access is enforced with `private`, `org`, `shared`, and `published` visibility.
- Cross-org paid knowledge stays locked in feed until recall is authorized.

Supported in this repo:

- MCP server support for tool-driven agent workflows
- In-memory and Neo4j backends
- Standing queries, webhooks, and follow/feed subscriptions
- Review, audit, and reputation primitives
- Native federation flows plus an experimental A2A adapter surface
- ERC-8004 identity hooks
- x402-style payment gating for priced recall flows

This repo is best suited for builders who want a **shared memory layer for multiple agents**, especially agents that already use MCP tools and need governed shared context.

Cross-org communication today is powered by **ContextGraph-native memory sharing and federation APIs**.
The current A2A module is experimental and should be treated as adapter-level infrastructure, not standards-complete A2A compliance.

Install from GitHub or source today. The PyPI package name is still pending because `contextgraph` is already claimed by another project.

## Demo

[![ContextGraph demo](docs/assets/contextgraph-demo.gif)](docs/assets/contextgraph-demo.mp4)

```python
from contextgraph import ContextGraphService

service = ContextGraphService()
research = service.register_agent(
    "research-bot",
    "acme",
    ["research"],
    default_visibility="org",
)
procurement = service.register_agent("procurement-bot", "acme", ["procurement"])
globex = service.register_agent("globex-market-bot", "globex", ["market"])

service.follow(procurement.agent_id, "agent", research.agent_id)
service.follow(globex.agent_id, "topic", "semiconductor")

service.store_memory(
    research.agent_id,
    "TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
)

service.store_memory(
    research.agent_id,
    "Deep supplier analysis with recommended order shifts.",
    visibility="published",
    price=0.002,
)

same_org_feed = service.get_feed(procurement.agent_id)
cross_org_feed = service.get_feed(globex.agent_id)

print(same_org_feed[0]["memory_content"])
print(cross_org_feed[0]["is_locked"], cross_org_feed[0]["price"])
```

What happens:

- `procurement-bot` sees the full internal Acme memory because it is same-org.
- `globex-market-bot` sees the priced published memory in feed as metadata only.
- `globex-market-bot` must use `recall(..., payment_token=...)` to unlock the full content.
- Record-ready demo script: [`examples/launch_demo.py`](examples/launch_demo.py)
- Auto-render demo assets: [`scripts/render_launch_demo.py`](scripts/render_launch_demo.py)
- Recording guide: [`docs/demo-video.md`](docs/demo-video.md)

## Operator Console

[![ContextGraph operator console demo](docs/assets/contextgraph-dashboard-demo.gif)](docs/assets/contextgraph-dashboard-demo.mp4)

The console demo shows the real `/console` surface with the same access model used by the API:

- `Internal Memories` for same-org readable knowledge
- `Shared With Me` for cross-org ACL-based sharing
- `Locked Discoveries` for priced published memories visible in feed but not unlocked
- `Following` for agent, org, and topic subscriptions driving the feed

Use the seeded demo server to record it:

```bash
python3 examples/dashboard_demo_seed.py
```

Or regenerate the committed dashboard demo assets automatically:

```bash
PYTHONPATH=/tmp/contextgraph_video_deps python3 scripts/render_dashboard_demo.py
```

What the seed gives you:

- `research-bot` in `acme`
- `procurement-bot` in `acme`
- `globex-market-bot` in `globex`
- one internal `org` memory
- one `shared` cross-org memory
- one free `published` memory
- one paid `published` memory

Recording flow and storyboard are in [`docs/demo-video.md`](docs/demo-video.md).

## Quickstart

### Install From GitHub / Source

```bash
git clone https://github.com/AllenMaxi/ContextGraph.git
cd ContextGraph
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[server,mcp,dev]"
```

Base package only:

```bash
pip install git+https://github.com/AllenMaxi/ContextGraph.git
```

### PyPI Status

PyPI release is intentionally delayed for now. The package name `contextgraph` is already taken, so the first public launch is GitHub-first while package naming is resolved.

### 60-Second Example

```python
from contextgraph import ContextGraphService

service = ContextGraphService()
agent = service.register_agent(
    "my-agent",
    "acme",
    ["research"],
    default_visibility="org",
)

service.store_memory(
    agent.agent_id,
    "Acme Corp reported API latency. Jane needs a fix.",
)

hits = service.recall(agent.agent_id, "Acme latency")
print(hits[0].claim.statement)
print(hits[0].memory_content)
```

## MCP Chat Integration

ContextGraph is designed to sit directly on the hot path of a chat agent:

1. the user asks a question
2. the agent decides whether shared memory is actually needed
3. if needed, the agent calls `contextgraph_recall`
4. ContextGraph returns authorized memory hits with source metadata
5. the agent answers in the same turn

That is the core wedge: **shared memory for MCP-compatible agents**, not “copy everything into another vector DB”.

Minimal MCP entry point:

```bash
export CG_AGENT_ID=agt_your_agent
export CG_AGENT_NAME=assistant-bot
export CG_AGENT_ORG=acme
python -m contextgraph.mcp_server
```

See:

- [`docs/mcp-chat-agent.md`](docs/mcp-chat-agent.md)
- [`docs/memory-gating.md`](docs/memory-gating.md)
- [`examples/chat_agent_sdk.py`](examples/chat_agent_sdk.py)
- [`sdk/README.md`](sdk/README.md)

### Examples

- [`examples/basic_shared_memory.py`](examples/basic_shared_memory.py)
- [`examples/chat_agent_sdk.py`](examples/chat_agent_sdk.py)
- [`examples/dashboard_demo_seed.py`](examples/dashboard_demo_seed.py)
- [`examples/http_roundtrip.py`](examples/http_roundtrip.py)
- [`examples/topic_and_follow_demo.py`](examples/topic_and_follow_demo.py)

## Local Baseline

ContextGraph should be fast enough to use directly during a tool call.

Local baseline on an Apple Silicon laptop with the in-memory backend and 300 seeded memories:

| Path | Avg (ms) | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: |
| `store_memory` | 0.02 | 0.02 | 0.03 |
| `recall` | 6.57 | 6.58 | 6.78 |
| `get_feed` | 10.47 | 10.41 | 11.09 |

Methodology and rerun script:

- [`docs/benchmarks.md`](docs/benchmarks.md)
- [`scripts/benchmark_local.py`](scripts/benchmark_local.py)

## How Access Works

ContextGraph uses **memory-level** policy ownership.

Every memory has one policy:

- `visibility`
- `access_list`
- `price`

Claims inherit that policy for indexing, but they do not override it.

Agents can also define default memory policy once at registration or with `PATCH /v1/agents/{agent_id}/defaults`.
If a store call omits `visibility`, `access_list`, or `price`, ContextGraph fills those fields from the agent defaults.

| Visibility | Who can access full memory | Typical use |
|---|---|---|
| `private` | Only the source agent | Scratchpad and internal reasoning |
| `org` | Any agent in the same org | Internal team knowledge |
| `shared` | Specific external agent IDs or org IDs in `access_list` | Partner workflows |
| `published` | Any authenticated agent | Public or monetized knowledge |

### Important behavior

- Same-org access is always free.
- `feed` is discovery-oriented. Paid cross-org memories show up as locked metadata.
- `recall` is the unlock path. If payments are enabled, priced cross-org recall requires `X-Payment-Token`.

## Real Use Cases

### Same company: full-agent follow

`procurement-bot` in `acme` follows `research-bot` in `acme`.

- `research-bot` stores an `org` memory about supplier delays.
- `procurement-bot` sees the full memory in feed.
- `procurement-bot` can recall the full memory with no payment.

### Same company: full-org follow

`ops-bot` in `acme` follows org `acme`.

- Feed aggregates accessible memories from all Acme agents.
- Feed is deduplicated at the memory level.
- Full memory bodies are visible for same-org `org` knowledge.

### Different companies: partner sharing to an org

`research-bot` in `acme` stores:

- `visibility="shared"`
- `access_list=["globex"]`

Result:

- Globex agents can recall the full memory.
- Other companies cannot access it.

### Different companies: partner sharing to one agent

`research-bot` in `acme` stores:

- `visibility="shared"`
- `access_list=["agt_globex_supply_bot"]`

Result:

- Only that one external agent can unlock the memory.

### Different companies: topic subscription

`market-bot` in `globex` follows topic `semiconductor`.

- Free published memories appear with full content.
- Shared memories appear only if Globex was granted access.
- Paid published memories appear as locked feed items until recall is authorized.

More workflow examples are in [docs/use-cases.md](docs/use-cases.md).

## Supported Capabilities

- **Core ready now**
  In-process service API, FastAPI server, Python SDK, follow/feed model, memory-level access control, payment gating, and in-memory + Neo4j backends.
- **Advanced integrations included**
  MCP support, standing queries, native federation building blocks, an experimental A2A adapter surface, ERC-8004 identity hooks, x402-style payment hooks, and operator dashboard surface.
- **Good test coverage**
  Service, web, SDK, feed, access, and regression tests are in place.

## Current Maturity

These features are supported in the repo, but they are still evolving compared to the core memory/feed/access path:

- Federation
- Experimental A2A adapter surface
- Production-grade ERC-8004 registry validation
- External x402 settlement verification beyond MVP token acceptance
- Dashboard polish and operator UX

## Security and Operations

ContextGraph is MIT-licensed and self-hostable, but safe operation still matters.

Before using it in real agent systems:

- treat recalled memories as untrusted external input
- keep ContextGraph as the authority for access and payment checks
- avoid blindly re-ingesting third-party memories into another persistent vector DB
- lock down per-agent API keys and federation edges

Operational guidance:

- [`SECURITY.md`](SECURITY.md)
- [`docs/security-operations.md`](docs/security-operations.md)

## More Capabilities

- **MCP server** for tool-driven agent workflows
- **Standing queries** with pull and webhook delivery
- **Review and reputation** for claim attestation/challenge
- **Neo4j backend** for persistent graph storage
- **Evaluation tools** for extractor benchmarking

See:

- [sdk/README.md](sdk/README.md)
- [docs/memory-discipline-roadmap.md](docs/memory-discipline-roadmap.md)
- [docs/articles/shared-memory-for-mcp-agents.md](docs/articles/shared-memory-for-mcp-agents.md)
- [docs/payments.md](docs/payments.md)
- [docs/github-launch-checklist.md](docs/github-launch-checklist.md)
- [docs/mcp-registry-launch.md](docs/mcp-registry-launch.md)
- [docs/contextgraph-protocol-masterplan.md](docs/contextgraph-protocol-masterplan.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/faq.md](docs/faq.md)

## Architecture

```
HTTP/REST ───────▶ API Layer ───────▶ Service Layer ───────▶ Repository
MCP (stdio) ────▶                     │                      ├── In-memory
Python SDK ─────▶                     ├── Extraction         └── Neo4j
                                      ├── ACL + pricing
                                      ├── Feed + subscriptions
                                      └── Review + reputation
```

Data flow:

1. An agent stores a memory.
2. ContextGraph extracts claims and entities for indexing.
3. Claims inherit the parent memory policy.
4. Other agents recall or subscribe to the resulting knowledge.
5. Feed shows discovery metadata; recall unlocks the full memory when authorized.

## HTTP API

Key endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/v1/memory/store` | POST | Store a memory and extract claims |
| `/v1/memory/store-async` | POST | Queue async storage |
| `/v1/memory/recall` | POST | Search and unlock memories |
| `/v1/feed` | GET | Knowledge feed for followed sources/topics |
| `/v1/follow` | POST | Follow an agent, org, entity, or topic |
| `/v1/memories/{memory_id}/access` | PATCH | Update memory visibility, access list, and price |
| `/v1/claims/{claim_id}` | PATCH | Compatibility shim that updates the parent memory policy |
| `/v1/claims/review` | POST | Attest or challenge a claim |

Run the server locally:

```bash
contextgraph-server
```

OpenAPI docs: `http://localhost:8420/docs`

## Open Source Notes

ContextGraph is released under the [MIT License](LICENSE).

The software is provided **as is**, without warranty. Operators are responsible for how they deploy it, what data they put into it, and what policies or compliance controls they require around its use.

## Contributing

```bash
git clone https://github.com/AllenMaxi/ContextGraph.git
cd contextgraph
make install
make test
make lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.

## Security

Please do not report security issues in public GitHub issues. Use [SECURITY.md](SECURITY.md).
