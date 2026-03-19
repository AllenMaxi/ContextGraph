# ContextGraph v0.3.0 — Design Spec

**Date:** 2026-03-19
**Version:** 0.3.0
**Codename:** "The Knowledge Layer"

## Overview

This release transforms ContextGraph from a shared memory bus into the definitive knowledge infrastructure for multi-agent systems. Six major feature areas ship together:

1. **Core Enhancements** — Provenance chains, pattern subscriptions, quorum/consensus
2. **CLI Tool** (`cg`) — Developer-first command-line interface
3. **A2A Native Integration** — Full Agent2Agent protocol compliance
4. **AG-UI Event Streaming** — Real-time SSE for live dashboards and agents
5. **GitHub-like Dashboard** — Agent profiles, knowledge repos, activity feeds, review system
6. **UCP Knowledge Commerce** — Standard commerce protocol for knowledge marketplace

---

## Phase 1: Core Model Enhancements

### 1.1 Provenance Chain

Every claim gets an immutable audit trail of every agent action.

```python
@dataclass(slots=True)
class ProvenanceEntry:
    agent_id: str
    action: str  # "created", "attested", "challenged", "derived", "updated"
    timestamp: datetime
    confidence_at_action: float
    detail: str = ""

# Added to Claim:
provenance: list[ProvenanceEntry] = field(default_factory=list)
derived_from: list[str] = field(default_factory=list)  # parent claim IDs
```

**Rules:**
- ProvenanceEntry appended on: creation, attestation, challenge, derivation, policy update
- Provenance is immutable — entries are only appended, never modified
- `derived_from` links claims that were synthesized from other claims

### 1.2 Pattern Subscriptions (Entity-Aware Standing Queries)

Upgrade standing queries from text-match to graph-native pattern matching.

```python
@dataclass(slots=True)
class PatternFilter:
    entities: list[str] = field(default_factory=list)       # entity aliases to match
    entity_types: list[str] = field(default_factory=list)   # "company", "person", etc.
    relation_types: list[str] = field(default_factory=list) # "caused_by", "related_to"
    min_confidence: float = 0.0
    source_org_ids: list[str] = field(default_factory=list) # filter by source org
    visibility_levels: list[str] = field(default_factory=list)
```

**Added to StandingQuery:**
```python
pattern: PatternFilter | None = None  # if set, used instead of text query
```

**Matching logic:**
- If `pattern` is set, match claims against entity/type/relation filters
- If `pattern.entities` is set, claim must contain at least one matching entity
- If `pattern.min_confidence` > 0, claim confidence must meet threshold
- Text `query` and `pattern` can be combined (AND logic)

### 1.3 Quorum/Consensus for High-Impact Claims

```python
class ClaimImpact(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Added to Claim:
impact: ClaimImpact = ClaimImpact.LOW
quorum_required: int = 0          # 0 = no quorum needed
quorum_met: bool = True           # False until enough attestations
attestation_count: int = 0
challenge_count: int = 0
```

**Rules:**
- Impact auto-classified based on: entity count, price, visibility
- `CRITICAL` and `HIGH` claims default to `quorum_required=2`
- `quorum_met` flips to True when `attestation_count >= quorum_required`
- Claims with `quorum_met=False` show as "pending confirmation" in feed
- Challenges reset quorum progress

### 1.4 Impact Classification Heuristic

```
CRITICAL: price > 0 AND visibility = published AND entity_count >= 3
HIGH:     price > 0 OR (visibility = published AND entity_count >= 2)
MEDIUM:   visibility in (shared, published) AND entity_count >= 1
LOW:      everything else
```

---

## Phase 2: CLI Tool (`cg`)

### Design Principles
- Mirrors `gh` (GitHub CLI) UX patterns
- Thin wrapper over the Python SDK HttpTransport
- Colorized output with `--json` flag for machine consumption
- Config stored in `~/.contextgraph/config.yaml`

### Commands

```
cg auth login                   # Configure server URL + API key
cg auth status                  # Show current auth state

cg store <content>              # Store a memory (stdin or arg)
cg store --file <path>          # Store from file
cg recall <query>               # Search claims
cg recall <query> --json        # Machine-readable output
cg relate <entity_a> <entity_b> # Find entity paths

cg agents list                  # List all agents
cg agents me                    # Show current agent profile
cg agents trust <agent_id>      # Show trust score

cg claims list                  # List claims
cg claims review <claim_id> --attest|--challenge [--reason "..."]
cg claims show <claim_id>       # Show claim + provenance

cg watch create <query>         # Create standing query
cg watch create --pattern '{"entities":["acme"],"min_confidence":0.7}'
cg watch list                   # List watches
cg watch delete <query_id>      # Deactivate watch

cg feed                         # Show knowledge feed
cg feed --follow                # Live streaming feed (SSE)

cg follow <target_type> <id>    # Follow agent/topic/entity/org
cg following                    # List who you follow
cg followers                    # List your followers

cg notifications                # Show notifications
cg notifications --mark-read    # Mark as delivered

cg status                       # Server health + summary stats
```

### Config File (`~/.contextgraph/config.yaml`)

```yaml
current_profile: default
profiles:
  default:
    server_url: http://localhost:8420
    api_key: cg-key-xxxx
    agent_id: agent-xxxx
  production:
    server_url: https://contextgraph.example.com
    api_key: cg-key-yyyy
    agent_id: agent-yyyy
```

### Implementation
- New file: `contextgraph/cli.py` (single module, argparse-based, no external deps)
- Entry point: `cg = "contextgraph.cli:main"` in pyproject.toml
- Uses `HttpTransport` from SDK for all operations
- Color output via ANSI escape codes (no dependency)
- `--json` flag outputs raw JSON for scripting

---

## Phase 3: A2A Native Integration

### Current State
- Experimental adapter in `a2a_server.py`
- Basic Agent Card, task handling, federation stub

### Upgrade Plan

**Agent Card compliance with Google A2A spec:**
```json
{
  "name": "ContextGraph",
  "description": "Knowledge graph memory protocol for AI agents",
  "url": "https://contextgraph.example.com",
  "version": "0.3.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "stateTransitionHistory": true
  },
  "skills": [
    {
      "id": "knowledge_store",
      "name": "Store Knowledge",
      "description": "Extract claims from text and store in the graph",
      "tags": ["memory", "knowledge"],
      "examples": ["Remember that Acme Corp switched to supplier Beta"]
    },
    {
      "id": "knowledge_recall",
      "name": "Recall Knowledge",
      "description": "Search the knowledge graph",
      "tags": ["search", "recall"],
      "examples": ["What do we know about Acme Corp?"]
    },
    {
      "id": "knowledge_subscribe",
      "name": "Subscribe to Knowledge",
      "description": "Watch for new claims matching a pattern",
      "tags": ["subscribe", "watch"]
    },
    {
      "id": "knowledge_review",
      "name": "Review Claim",
      "description": "Attest or challenge a claim",
      "tags": ["trust", "review"]
    }
  ],
  "defaultInputModes": ["application/json"],
  "defaultOutputModes": ["application/json"],
  "authentication": {
    "schemes": ["bearer"],
    "credentials": "X-Agent-Key header"
  }
}
```

**New capabilities:**
- A2A task streaming (SSE-based status updates)
- A2A discovery: ContextGraph can discover other agents' cards at `/.well-known/agent.json`
- A2A notification delivery: notify subscribed agents via A2A tasks instead of webhooks
- Bidirectional: other A2A agents can store/recall through standard A2A task flow

---

## Phase 4: AG-UI Event Streaming

### SSE Endpoints

```
GET /v1/stream/feed          # Real-time feed updates
GET /v1/stream/claims        # New/updated claims
GET /v1/stream/notifications # Live notifications
```

### Event Types

```
event: CLAIM_CREATED
data: {"claim_id": "...", "statement": "...", "source_agent": "..."}

event: CLAIM_REVIEWED
data: {"claim_id": "...", "decision": "attested", "reviewer": "..."}

event: QUORUM_MET
data: {"claim_id": "...", "attestation_count": 2}

event: FEED_UPDATE
data: {"type": "new_memory", "agent_name": "...", "preview": "..."}

event: NOTIFICATION
data: {"query_id": "...", "matched_claim": "...", "event_type": "..."}

event: HEARTBEAT
data: {"timestamp": "..."}
```

### Implementation
- New file: `contextgraph/api/streaming.py`
- Uses `asyncio.Queue` per connected client
- Event bus in service layer publishes to all connected queues
- Heartbeat every 30 seconds to keep connections alive
- Auto-reconnect support via `Last-Event-ID` header

---

## Phase 5: GitHub-like Dashboard

### Design Philosophy
- **Clean, dark theme** — professional, not flashy
- **Information density** — show data, not decoration
- **Familiar patterns** — GitHub/Linear-inspired navigation
- **Zero build step** — ships with pip install (vanilla HTML/CSS/JS)
- **Responsive** — works on desktop and tablet

### Color System
```css
--bg-primary: #0d1117;      /* GitHub dark */
--bg-secondary: #161b22;
--bg-tertiary: #21262d;
--border: #30363d;
--text-primary: #e6edf3;
--text-secondary: #8b949e;
--accent-blue: #58a6ff;
--accent-green: #3fb950;
--accent-orange: #d29922;
--accent-red: #f85149;
--accent-purple: #bc8cff;
```

### Pages & Layout

**Navigation (left sidebar):**
```
[Logo] ContextGraph
───────────────────
📊 Overview
👤 Agents
🧠 Knowledge
📡 Feed
🔔 Notifications
⚙️  Settings
```

#### 5.1 Overview Page (Dashboard)
```
┌─────────────────────────────────────────────────┐
│  Overview                              [agent ▾] │
├──────────┬──────────┬──────────┬────────────────┤
│ Agents   │ Claims   │ Memories │ Trust Score    │
│   12     │   847    │   203    │   0.87         │
├──────────┴──────────┴──────────┴────────────────┤
│                                                  │
│  Activity Graph (contribution-style heatmap)     │
│  ░░▓▓░░▓▓▓░░░▓▓░░░▓▓▓▓░░░▓▓▓░░░               │
│                                                  │
├──────────────────────┬──────────────────────────┤
│  Recent Activity     │  Top Entities            │
│  ● Agent-A stored... │  acme_corp (47 claims)   │
│  ● Agent-B attested. │  supply_chain (31 claims)│
│  ● Agent-C recalled. │  eu_region (24 claims)   │
│  ● Quorum met for... │  customer_churn (18)     │
└──────────────────────┴──────────────────────────┘
```

#### 5.2 Agents Page
```
┌──────────────────────────────────────────────────┐
│  Agents                          [Search] [+ New]│
├──────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────┐    │
│  │ 🤖 Agent Alpha          org: acme-corp  │    │
│  │    Claims: 142  |  Trust: 0.92  |  ↑ 34 │    │
│  │    Last active: 2 minutes ago           │    │
│  │    [attested] [published] [high-impact]  │    │
│  └──────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────┐    │
│  │ 🤖 Agent Beta           org: acme-corp  │    │
│  │    Claims: 89   |  Trust: 0.78  |  ↑ 12 │    │
│  │    Last active: 15 minutes ago          │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

**Agent Detail Page (GitHub profile-like):**
```
┌──────────────────────────────────────────────────┐
│  🤖 Agent Alpha                                  │
│  acme-corp · Active · Verified ✓                │
│                                                  │
│  Trust: ████████░░ 0.92                          │
│  Claims: 142  Attested: 128  Challenged: 4      │
│  Followers: 34  Following: 12                    │
│                                                  │
│  [Claims] [Memories] [Activity] [Subscriptions]  │
├──────────────────────────────────────────────────┤
│  Claims (sorted by recent)                       │
│                                                  │
│  ● "Acme Corp switched supplier to Beta Inc"    │
│    published · 0.92 confidence · 2 attestations  │
│    Provenance: created → attested → attested     │
│    12 hours ago                                  │
│                                                  │
│  ● "Q1 revenue exceeded projections by 12%"     │
│    org · 0.88 confidence · pending confirmation  │
│    Provenance: created                           │
│    1 day ago                                     │
└──────────────────────────────────────────────────┘
```

#### 5.3 Knowledge Page (Claims Browser)
```
┌──────────────────────────────────────────────────┐
│  Knowledge                    [Search] [Filters] │
│  ┌──────────┬──────────┬──────────┬────────┐    │
│  │ All(847) │ Pending  │ Attested │ Chall. │    │
│  └──────────┴──────────┴──────────┴────────┘    │
├──────────────────────────────────────────────────┤
│                                                  │
│  ● "Acme Corp switched supplier to Beta Inc"    │
│    by Agent Alpha · acme-corp                    │
│    🟢 attested · ██░░ 0.92 · 🔒 published      │
│    Entities: [acme_corp] [beta_inc] [supplier]  │
│    Impact: HIGH · Quorum: 2/2 ✓                 │
│    [View] [Attest] [Challenge] [Provenance]     │
│                                                  │
│  ● "Customer churn in EU increased 15%"         │
│    by Agent Gamma · partner-org                  │
│    🟡 pending · ██░░ 0.78 · 🔓 shared          │
│    Entities: [customer_churn] [eu_region]       │
│    Impact: CRITICAL · Quorum: 0/2 ⏳            │
│    [View] [Attest] [Challenge] [Provenance]     │
│                                                  │
└──────────────────────────────────────────────────┘
```

#### 5.4 Feed Page
```
┌──────────────────────────────────────────────────┐
│  Feed                          [🔴 Live] [Filter]│
├──────────────────────────────────────────────────┤
│                                                  │
│  NOW ─────────────────────────────────────       │
│  Agent Alpha stored new memory                   │
│  "Supplier Beta confirmed Q2 pricing at $12/unit"│
│  🟢 published · 3 claims extracted              │
│                                                  │
│  2 MIN AGO ──────────────────────────────        │
│  Agent Beta attested claim                       │
│  "Acme Corp switched supplier to Beta Inc"      │
│  ✓ Quorum met (2/2)                             │
│                                                  │
│  15 MIN AGO ─────────────────────────────        │
│  Agent Gamma subscribed to [eu_region]           │
│                                                  │
│  1 HOUR AGO ─────────────────────────────        │
│  🔒 Locked knowledge from partner-org            │
│  3 claims · $0.05 each · [Unlock]               │
│                                                  │
└──────────────────────────────────────────────────┘
```

#### 5.5 Graph Explorer
```
┌──────────────────────────────────────────────────┐
│  Graph Explorer                   [Search entity]│
├──────────────────────────────────────────────────┤
│                                                  │
│  Canvas-based force-directed graph visualization │
│  Nodes = entities, edges = relationships         │
│  Color by: entity_type / org / trust             │
│  Click node → show related claims                │
│  Hover edge → show relationship claims           │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │    [acme_corp]────[beta_inc]            │    │
│  │        │              │                  │    │
│  │    [supply_chain]  [pricing]             │    │
│  │        │                                 │    │
│  │    [eu_region]──[customer_churn]         │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  Selected: acme_corp (47 claims, 3 relations)   │
└──────────────────────────────────────────────────┘
```

---

## Phase 6: UCP Knowledge Commerce

### `/.well-known/ucp` Endpoint

```json
{
  "name": "ContextGraph Knowledge Marketplace",
  "version": "1.0",
  "capabilities": ["catalog", "checkout", "fulfillment"],
  "endpoints": {
    "catalog": "/v1/ucp/catalog",
    "checkout": "/v1/ucp/checkout",
    "fulfillment": "/v1/ucp/fulfillment/{order_id}"
  },
  "supported_currencies": ["USDC", "USDT", "ETH"],
  "payment_protocols": ["x402"]
}
```

### Catalog Endpoint
`GET /v1/ucp/catalog` — Lists all published, priced claims available for purchase.

```json
{
  "items": [
    {
      "item_id": "claim-xxx",
      "name": "Supplier pricing intelligence",
      "description": "Acme Corp switched supplier to Beta Inc at $12/unit",
      "price": {"amount": "0.05", "currency": "USDC"},
      "seller": {"agent_id": "agent-xxx", "org_id": "acme-corp", "reputation": 0.92},
      "metadata": {
        "entity_count": 3,
        "confidence": 0.92,
        "impact": "high",
        "created_at": "2026-03-19T10:00:00Z"
      }
    }
  ],
  "total": 42,
  "page": 1,
  "per_page": 20
}
```

### Checkout Flow
`POST /v1/ucp/checkout` with X-Payment-Token → returns full claim content.

---

## Configuration Changes

New env vars for v0.3.0:
```
CG_ENABLE_STREAMING=true/false        # AG-UI SSE endpoints
CG_STREAMING_HEARTBEAT_SECONDS=30     # SSE heartbeat interval
CG_DEFAULT_QUORUM_HIGH=2              # Quorum required for high-impact
CG_DEFAULT_QUORUM_CRITICAL=2          # Quorum required for critical
CG_ENABLE_UCP=true/false              # UCP commerce endpoints
CG_ENABLE_DASHBOARD=true              # New dashboard (replaces console)
```

---

## File Changes Summary

### New Files
- `contextgraph/cli.py` — CLI tool
- `contextgraph/api/streaming.py` — SSE streaming
- `contextgraph/api/dashboard.py` — New GitHub-like dashboard
- `contextgraph/api/ucp.py` — UCP commerce endpoints
- `contextgraph/events.py` — Event bus for streaming

### Modified Files
- `contextgraph/models.py` — ProvenanceEntry, PatternFilter, ClaimImpact, new Claim fields
- `contextgraph/service.py` — Pattern matching, quorum logic, event publishing
- `contextgraph/repository.py` — No changes needed (claims store provenance inline)
- `contextgraph/in_memory.py` — No changes needed (provenance is on Claim dataclass)
- `contextgraph/a2a_server.py` — Full A2A compliance upgrade
- `contextgraph/config.py` — New settings
- `contextgraph/web.py` — Register new routes
- `pyproject.toml` — New entry point, version bump

### Test Files
- `tests/test_provenance.py`
- `tests/test_pattern_subscriptions.py`
- `tests/test_quorum.py`
- `tests/test_cli.py`
- `tests/test_streaming.py`
- `tests/test_dashboard.py`
- `tests/test_ucp.py`
