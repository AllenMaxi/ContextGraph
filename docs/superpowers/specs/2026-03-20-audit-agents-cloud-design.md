# ContextGraph v0.4.0 — Audit Agents + Centralized Cloud Architecture

**Date:** 2026-03-20
**Status:** Proposed

---

## Part 1: Answering the Teammate's Question

> "Todos los clientes tienen que tener esto instalado para que puedan compartir la
> memoria? Y si hubiese un sitio central donde guardar la memoria? Pero siempre
> con cada permiso, que esté en la nube o en algún lugar."

### Short Answer

**No, clients don't need to install anything.** ContextGraph already supports a
centralized cloud model today. Here's how it works:

```
┌─────────────────────────────────────────────────────────────┐
│                  CENTRALIZED CLOUD                          │
│                                                             │
│   ┌───────────────────────────────────────────────┐         │
│   │         ContextGraph Server (v0.3.0)          │         │
│   │  ┌──────────┐  ┌──────────┐  ┌────────────┐  │         │
│   │  │ REST API  │  │ EventBus │  │ Dashboard  │  │         │
│   │  │ /v1/*     │  │ SSE      │  │ /dashboard │  │         │
│   │  └──────────┘  └──────────┘  └────────────┘  │         │
│   │       │              │              │         │         │
│   │  ┌──────────────────────────────────────┐     │         │
│   │  │         Permission Engine            │     │         │
│   │  │  private | org | shared | published  │     │         │
│   │  └──────────────────────────────────────┘     │         │
│   │                    │                          │         │
│   │  ┌──────────────────────────────────────┐     │         │
│   │  │        Neo4j Graph Database          │     │         │
│   │  │  (all memory stored here centrally)  │     │         │
│   │  └──────────────────────────────────────┘     │         │
│   └───────────────────────────────────────────────┘         │
│                                                             │
└────────┬──────────────┬───────────────┬─────────────────────┘
         │              │               │
    HTTPS + API Key     │          HTTPS + API Key
         │              │               │
   ┌─────┴─────┐  ┌────┴────┐   ┌──────┴──────┐
   │  Org: Acme │  │Org: Beta│   │ Org: Globex │
   │            │  │         │   │             │
   │ Agent-1    │  │ Agent-3 │   │ Agent-5     │
   │ Agent-2    │  │ Agent-4 │   │ Agent-6     │
   └────────────┘  └─────────┘   └─────────────┘
     Any server       Laptop       AWS Lambda
     anywhere         locally      serverless
```

### What Already Works Today

| Capability | How It Works | Config |
|---|---|---|
| **Central server** | `docker-compose up` deploys ContextGraph + Neo4j | `docker-compose.yml` |
| **Remote agent connection** | SDK's `HttpTransport` connects via HTTPS | `ContextGraph.http(url, api_key)` |
| **Org isolation** | Each agent belongs to an org; visibility enforced per-request | `register_agent(name, org_id, ...)` |
| **Permission model** | 4 levels: private, org, shared, published | Set per memory at store time |
| **Admin-gated registration** | `CG_ADMIN_KEY` env var blocks open registration | `.env` |
| **CLI remote access** | `cg auth login --url https://cloud.example.com --key <key>` | `~/.contextgraph/config.json` |
| **Cross-org commerce** | x402 payment gate for published+priced memories | `CG_ENABLE_PAYMENTS=true` |

### Deployment Options for Centralized Cloud

**Option A: Single Docker instance (simplest)**
```bash
# On any cloud VM (AWS EC2, GCP Compute, DigitalOcean, etc.)
git clone https://github.com/AllenMaxi/ContextGraph.git
cd ContextGraph
CG_ADMIN_KEY=your-secret-admin-key docker-compose up -d
```
Agents connect from anywhere:
```python
from contextgraph_sdk import ContextGraph
cg = ContextGraph.http("https://contextgraph.yourcompany.com", api_key="key-xyz")
cg.store(agent_id="agt_1", content="Market analysis Q3...")
```

**Option B: Managed Kubernetes (production scale)**
```yaml
# Helm chart or K8s manifests
# ContextGraph server: 2+ replicas behind a load balancer
# Neo4j: Causal cluster (3 nodes) for HA
# TLS termination at ingress
```

**Option C: Serverless (Google Cloud Run / AWS Fargate)**
```bash
# Build and push the Docker image
docker build -t contextgraph:0.3.0 .
# Deploy to Cloud Run with Neo4j Aura as managed graph DB
```

### What's Missing for Production Cloud

The current architecture handles multi-tenancy through org-based isolation, but
for a true SaaS-grade cloud deployment, we should add:

1. **Audit Agents** — built-in governance agents that monitor claim integrity
2. **Org-level API key rotation** — admin can rotate keys without re-registering
3. **Usage quotas per org** — rate limits + storage limits per tenant
4. **Backup/export API** — orgs can export their own data

This spec focuses on item #1: Audit Agents.

---

## Part 2: Audit Agent Design

### Motivation

From Google DeepMind's "Intelligent AI Delegation" paper (Feb 2026):
- Multi-agent systems need **process-level monitoring**, not just outcome checking
- **Reputation-based circuit breakers** should freeze agents whose trust drops
- **Provenance chain integrity** must be cryptographically verifiable
- All of this must be **auditable and policy-driven**

ContextGraph already has provenance chains, reputation scores, quorum consensus,
and an event bus. The missing piece is an **active agent** that ties these together
into a governance system.

### What Is an Audit Agent?

An audit agent is a **built-in, opt-in ContextGraph agent** that:
- Runs inside the ContextGraph server process (no external deployment needed)
- Subscribes to the EventBus and reacts to claim/agent events in real-time
- Enforces configurable rules (anomaly detection, quorum verification, etc.)
- Can take actions: flag claims, freeze agents, emit alerts
- Exposes audit reports via API and the dashboard

```
┌──────────────────────────────────────────────────────────┐
│                  ContextGraph Server                     │
│                                                          │
│  ┌─────────┐   events    ┌──────────────────────┐       │
│  │ EventBus │────────────▶│    Audit Agent       │       │
│  │          │             │                      │       │
│  │ CLAIM_   │             │  ┌────────────────┐  │       │
│  │ CREATED  │             │  │ Rule Engine    │  │       │
│  │          │             │  │                │  │       │
│  │ CLAIM_   │             │  │ • provenance   │  │       │
│  │ REVIEWED │             │  │   integrity    │  │       │
│  │          │             │  │ • confidence   │  │       │
│  │ AGENT_   │             │  │   anomaly      │  │       │
│  │ TRUST_   │             │  │ • quorum       │  │       │
│  │ CHANGED  │             │  │   compliance   │  │       │
│  │          │             │  │ • reputation   │  │       │
│  │ MEMORY_  │             │  │   circuit      │  │       │
│  │ STORED   │             │  │   breaker      │  │       │
│  └─────────┘             │  │ • cross-org    │  │       │
│                           │  │   access       │  │       │
│                           │  │   patterns     │  │       │
│  ┌─────────┐             │  └────────────────┘  │       │
│  │ Service  │◀────actions──│                      │       │
│  │          │             │  Actions:             │       │
│  │ freeze   │             │  • flag_claim         │       │
│  │ claim    │             │  • freeze_agent       │       │
│  │          │             │  • emit_alert         │       │
│  │ suspend  │             │  • downgrade_trust    │       │
│  │ agent    │             │  • generate_report    │       │
│  └─────────┘             └──────────────────────┘       │
│                                                          │
│  ┌──────────────────────────────────────────────┐       │
│  │              Audit API + Dashboard            │       │
│  │  GET /v1/audit/reports                        │       │
│  │  GET /v1/audit/alerts                         │       │
│  │  GET /v1/audit/agent/{id}/history             │       │
│  │  GET /dashboard/audit                         │       │
│  └──────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────┘
```

### Audit Rules (Built-in)

Each rule is independently toggleable. Orgs can enable/disable per their needs.

#### Rule 1: Provenance Integrity Check
**Trigger:** CLAIM_CREATED, CLAIM_REVIEWED
**Logic:** Verify that every claim has a non-empty provenance chain, the first
entry is "created", entries are chronologically ordered, and agent_ids in the
chain are valid registered agents.
**Action on violation:** Flag claim as `audit_flagged`, emit AUDIT_ALERT event.

#### Rule 2: Confidence Anomaly Detection
**Trigger:** CLAIM_REVIEWED
**Logic:** If a claim's confidence changes by more than a configurable threshold
(default: 0.3) in a single review, flag it. Also flag if an agent consistently
attests claims that later get challenged.
**Action:** Emit AUDIT_ALERT, optionally downgrade reviewer's trust score.

#### Rule 3: Quorum Compliance
**Trigger:** MEMORY_STORED (for claims with quorum_required > 0)
**Logic:** Track claims that have been pending quorum for longer than a
configurable window (default: 72 hours). Alert the org that high-impact claims
are unverified.
**Action:** Emit AUDIT_ALERT with list of stale unverified claims.

#### Rule 4: Reputation Circuit Breaker
**Trigger:** AGENT_TRUST_CHANGED (new event type)
**Logic:** If an agent's reputation_score drops below a threshold (default: 0.3)
or drops by more than 0.2 in a 24-hour window, freeze the agent's write access.
Require admin intervention to unfreeze.
**Action:** Suspend agent (set `active=False`), emit AUDIT_ALERT, log to report.

#### Rule 5: Cross-Org Access Pattern Monitor
**Trigger:** MEMORY_RECALLED (new event type)
**Logic:** Track cross-org recall patterns. If an agent from Org-B is recalling
an unusually high volume of Org-A's published memories (configurable threshold),
flag it as potential data harvesting.
**Action:** Emit AUDIT_ALERT, rate-limit the agent's recall for that org.

#### Rule 6: Claim Volume Spike
**Trigger:** CLAIM_CREATED
**Logic:** If an agent creates more than N claims (default: 100) within a
configurable window (default: 1 hour), flag it as potential spam or
misconfiguration.
**Action:** Emit AUDIT_ALERT, optionally throttle the agent.

### Data Model

```python
@dataclass(slots=True)
class AuditAlert:
    alert_id: str              # "aud_<random>"
    rule_id: str               # "provenance_integrity", "confidence_anomaly", etc.
    severity: str              # "info", "warning", "critical"
    agent_id: str | None       # Agent that triggered the alert (if applicable)
    claim_id: str | None       # Claim involved (if applicable)
    org_id: str                # Org context
    message: str               # Human-readable description
    details: dict[str, Any]    # Rule-specific metadata
    action_taken: str          # "flagged", "suspended", "alert_only", "throttled"
    created_at: datetime
    acknowledged: bool = False # Admin can acknowledge/dismiss

@dataclass(slots=True)
class AuditReport:
    report_id: str
    org_id: str
    period_start: datetime
    period_end: datetime
    total_claims: int
    total_reviews: int
    alerts_by_severity: dict[str, int]   # {"info": 5, "warning": 2, "critical": 0}
    alerts_by_rule: dict[str, int]       # {"provenance_integrity": 1, ...}
    top_flagged_agents: list[dict]       # [{agent_id, alert_count, ...}]
    quorum_compliance_rate: float        # 0.0 - 1.0
    created_at: datetime
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/audit/alerts` | List alerts (filterable by org, severity, rule, date) |
| GET | `/v1/audit/alerts/{id}` | Get alert detail |
| POST | `/v1/audit/alerts/{id}/acknowledge` | Admin acknowledges an alert |
| GET | `/v1/audit/reports` | List generated reports |
| GET | `/v1/audit/reports/{id}` | Get full report |
| POST | `/v1/audit/reports/generate` | Generate a report for a time window |
| GET | `/v1/audit/agent/{id}/history` | Audit trail for a specific agent |
| GET | `/v1/audit/config` | Current audit configuration |
| PUT | `/v1/audit/config` | Update audit rules (admin only) |

### Configuration

```bash
# .env
CG_ENABLE_AUDIT=true                          # Master switch (default: false)
CG_AUDIT_PROVENANCE_CHECK=true                # Rule 1
CG_AUDIT_CONFIDENCE_THRESHOLD=0.3             # Rule 2: max delta
CG_AUDIT_QUORUM_STALE_HOURS=72                # Rule 3: hours before alert
CG_AUDIT_REPUTATION_FLOOR=0.3                 # Rule 4: freeze threshold
CG_AUDIT_REPUTATION_DROP_THRESHOLD=0.2        # Rule 4: 24h drop threshold
CG_AUDIT_CROSS_ORG_RECALL_LIMIT=50            # Rule 5: per hour per org-pair
CG_AUDIT_CLAIM_SPIKE_LIMIT=100                # Rule 6: per hour per agent
CG_AUDIT_REPORT_AUTO_INTERVAL_HOURS=24        # Auto-generate daily reports
```

### Dashboard Page: Audit

New page at `/dashboard/audit` with:

1. **Alert feed** — real-time list of audit alerts, color-coded by severity
2. **Alert detail** — click to see full context, acknowledge button
3. **Agent risk scores** — agents ranked by alert frequency
4. **Quorum health** — % of high-impact claims with quorum met
5. **Report viewer** — browse and download audit reports
6. **Rule config** — toggle rules on/off, adjust thresholds (admin only)

### CLI Commands

```bash
cg audit alerts                    # List recent alerts
cg audit alerts --severity critical
cg audit alerts --agent <agent-id>
cg audit acknowledge <alert-id>    # Acknowledge an alert
cg audit report                    # Generate a report for last 24h
cg audit report --from 2026-03-01 --to 2026-03-20
cg audit config                    # Show current audit config
cg audit config --set reputation_floor=0.4
```

---

## Part 3: Implementation Plan

### Phase 1: Core Audit Engine
**Files:** `contextgraph/audit.py` (new)

- [ ] `AuditAlert` and `AuditReport` dataclasses in `models.py`
- [ ] `AuditRule` base class with `evaluate(event) -> AuditAlert | None`
- [ ] 6 built-in rule implementations
- [ ] `AuditEngine` class:
  - Subscribes to EventBus on startup
  - Routes events to matching rules
  - Stores alerts in repository
  - Takes actions (flag claim, suspend agent) via service
- [ ] `AuditConfig` dataclass for runtime rule toggling
- [ ] New EventTypes: `AUDIT_ALERT`, `AGENT_TRUST_CHANGED`, `MEMORY_RECALLED`

### Phase 2: Repository + API
**Files:** `contextgraph/audit.py`, `contextgraph/api/audit.py` (new)

- [ ] Repository methods: `store_alert()`, `list_alerts()`, `get_alert()`,
      `acknowledge_alert()`, `store_report()`, `list_reports()`
- [ ] REST endpoints (see table above)
- [ ] Admin-only gating for config endpoints (uses `X-Admin-Key`)
- [ ] Wire routes in `web.py` (conditional on `CG_ENABLE_AUDIT`)

### Phase 3: Dashboard + CLI
**Files:** `contextgraph/api/dashboard.py`, `contextgraph/cli.py`

- [ ] New dashboard page: `/dashboard/audit`
- [ ] Alert feed with severity badges and acknowledge action
- [ ] Quorum health widget and agent risk table
- [ ] CLI `cg audit` subcommands

### Phase 4: Auto-Reports + Event Enrichment
**Files:** `contextgraph/audit.py`, `contextgraph/service.py`

- [ ] Background task to auto-generate periodic reports
- [ ] Emit `AGENT_TRUST_CHANGED` events when trust is modified
- [ ] Emit `MEMORY_RECALLED` events on recall (for cross-org monitoring)
- [ ] Report generation logic with aggregation queries

### Phase 5: Tests
**Files:** `tests/test_audit.py` (new)

- [ ] Test each rule independently with mock events
- [ ] Test circuit breaker (agent gets suspended)
- [ ] Test alert lifecycle (create → acknowledge)
- [ ] Test report generation
- [ ] Test API endpoints
- [ ] Test audit is fully disabled when `CG_ENABLE_AUDIT=false`

### Phase 6: Config + Docs
- [ ] Add audit settings to `config.py`
- [ ] Add audit section to `.env.example`
- [ ] Update README with audit agent section
- [ ] Update demo scripts to optionally show audit features

---

## Design Decisions

**Why built-in, not external?**
External audit agents would need to poll the API. Built-in agents subscribe to
the EventBus directly — zero latency, zero network overhead, and they can take
immediate action (freeze an agent in milliseconds, not seconds).

**Why opt-in?**
Small teams and dev environments don't need compliance overhead. The audit agent
adds zero cost when disabled (`CG_ENABLE_AUDIT=false`, the default).

**Why per-org isolation?**
Audit alerts and reports are scoped to an org. Org-A's admin cannot see Org-B's
audit alerts. This maintains the same isolation guarantees as the rest of
ContextGraph.

**Why not use an LLM for audit?**
Deterministic rules are auditable themselves. If the audit agent used an LLM
to decide what's suspicious, you'd need an audit agent for the audit agent.
Rules are transparent, fast, and reproducible.
