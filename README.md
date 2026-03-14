<p align="center">
  <img src="docs/assets/contextgraph-hero.jpeg" alt="ContextGraph hero" width="600">
</p>

<h1 align="center">ContextGraph</h1>

<p align="center">
  <strong>Shared memory for AI agents with permissions, subscriptions, and optional payments.</strong><br>
  Claim-native indexing, memory-level access control, and cross-agent discovery in one Python package.
</p>

<p align="center">
  <a href="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml"><img src="https://github.com/AllenMaxi/ContextGraph/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://pypi.org/project/contextgraph"><img src="https://img.shields.io/pypi/v/contextgraph.svg" alt="PyPI"></a>
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

- Agents store full memories.
- ContextGraph extracts claims and entities for indexing.
- Other agents can recall, follow, and subscribe to relevant knowledge.
- Access is enforced with `private`, `org`, `shared`, and `published` visibility.
- Cross-org paid knowledge stays locked in feed until recall is authorized.

This repo is best suited for builders who want a **shared memory layer for multiple agents**, not just a single-agent memory cache.

## Demo

```python
from contextgraph import ContextGraphService

service = ContextGraphService()
research = service.register_agent("research-bot", "acme", ["research"])
procurement = service.register_agent("procurement-bot", "acme", ["procurement"])
globex = service.register_agent("globex-market-bot", "globex", ["market"])

service.follow(procurement.agent_id, "agent", research.agent_id)
service.follow(globex.agent_id, "topic", "semiconductor")

service.store_memory(
    research.agent_id,
    "TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
    visibility="org",
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

## Quickstart

### Install

```bash
pip install contextgraph
pip install contextgraph[server]     # FastAPI server
pip install contextgraph[mcp]        # MCP server support
pip install contextgraph[server,mcp] # Common local setup
```

### 60-Second Example

```python
from contextgraph import ContextGraphService

service = ContextGraphService()
agent = service.register_agent("my-agent", "acme", ["research"])

service.store_memory(
    agent.agent_id,
    "Acme Corp reported API latency. Jane needs a fix.",
    visibility="org",
)

hits = service.recall(agent.agent_id, "Acme latency")
print(hits[0].claim.statement)
print(hits[0].memory_content)
```

### Examples

- [`examples/basic_shared_memory.py`](examples/basic_shared_memory.py)
- [`examples/http_roundtrip.py`](examples/http_roundtrip.py)
- [`examples/topic_and_follow_demo.py`](examples/topic_and_follow_demo.py)

## How Access Works

ContextGraph uses **memory-level** policy ownership.

Every memory has one policy:

- `visibility`
- `access_list`
- `price`

Claims inherit that policy for indexing, but they do not override it.

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

## Current Maturity

What is strong today:

- In-process service API
- FastAPI server
- Python SDK
- Follow/feed model
- Memory-level access and payment gating
- In-memory and Neo4j backends
- Test coverage across service, web, SDK, and extractor behavior

What is still early or optional:

- Federation
- ERC-8004 identity integration
- x402 settlement verification beyond MVP token acceptance
- Dashboard polish and operator UX

## More Capabilities

- **MCP server** for tool-driven agent workflows
- **Standing queries** with pull and webhook delivery
- **Review and reputation** for claim attestation/challenge
- **Neo4j backend** for persistent graph storage
- **Evaluation tools** for extractor benchmarking

See:

- [sdk/README.md](sdk/README.md)
- [docs/payments.md](docs/payments.md)
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
