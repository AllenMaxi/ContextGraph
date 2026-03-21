# Agent Lifecycle & Audit Orchestration — Design Spec

**Date:** 2026-03-20
**Status:** Implemented
**Scope:** Agent sleep/wake lifecycle, sentinel audit pipeline, graduated claim lifecycle, operator-visible governance surfaces

---

## 1. Problem Statement

ContextGraph agents are records in a database, not running processes. An idle agent making zero API calls costs nothing in compute. However, the **background work the system does on behalf of idle agents** is expensive:

- Standing queries (watches) are evaluated against every new claim for every active agent
- Feed generation runs for agents that never read
- Notification delivery fires for agents that aren't listening
- Claim expiry sweeps scan claims for agents that don't care

Additionally, there is no automated quality control on stored knowledge. Any agent can store any content. The existing review system is manual — review tasks are created for low-confidence claims, but someone has to act on them. Bad knowledge degrades the entire graph.

**Goals:**
1. Auto-suspend idle agents to eliminate wasted background work
2. Transparently wake agents on first API call (virtual actor pattern)
3. Validate every piece of stored knowledge automatically via built-in sentinel agents
4. Graduate claims through a trust lifecycle: pending → validated → trusted
5. Zero configuration required — works out of the box

---

## 2. Agent Lifecycle

### 2.1 Status Enum

```
ACTIVE ──────► SUSPENDED ──────► ACTIVE       (auto or manual wake)
   │               │
   ▼               ▼
DELETED        DELETED                        (soft-delete, irreversible)
```

| Status | Behavior |
|--------|----------|
| `active` | Full functionality, all background work runs |
| `suspended` | Identity preserved, API calls rejected (403), watches don't fire, notifications don't deliver, feed not built |
| `deleted` | Soft-delete. Exists for audit trail, can never authenticate. Claims/memories remain attributed. |

### 2.2 New Agent Fields

| Field | Type | Purpose |
|-------|------|---------|
| `last_activity_at` | `datetime` | Updated on every authenticated API call |
| `suspension_reason` | `str \| None` | `"idle"`, `"manual"`, `"policy_violation"` |
| `suspended_at` | `datetime \| None` | When suspension occurred |
| `role` | `str` | `"agent"` (default) or `"sentinel"` |

### 2.3 Auto-Sleep

New background job type: `SWEEP_IDLE_AGENTS`

- Runs every `agent_idle_scan_interval_hours` (default: 24)
- Finds all `active` agents where `last_activity_at < now - agent_idle_threshold_days`
- Transitions to `suspended` with `suspension_reason="idle"`
- Audits each transition
- Emits `AGENT_SUSPENDED` event on event bus

### 2.4 Auto-Wake (Transparent)

When a suspended agent authenticates:
- If `suspension_reason == "idle"`: transparently reactivate, update `last_activity_at`, audit `"auto_reactivation"`, process request normally. Caller never knows.
- If `suspension_reason != "idle"` (manual/policy): reject with `403 "Agent suspended: {reason}. Contact your admin."`

### 2.5 Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `POST /v1/agents/{id}/suspend` | POST | Same-org or admin | Manual suspend with reason |
| `POST /v1/agents/{id}/reactivate` | POST | Same-org or admin | Manual reactivate |
| `DELETE /v1/agents/{id}` | DELETE | Same-org or admin | Soft-delete |
| `GET /v1/agents?status=...` | GET | Authenticated | Filter agents by status |

### 2.6 SDK + CLI

```python
client.suspend_agent(agent_id, reason="decommissioned")
client.reactivate_agent(agent_id)
client.delete_agent(agent_id)
```

```bash
cg agents suspend agt_xxx --reason "decommissioned"
cg agents wake agt_xxx
cg agents delete agt_xxx
cg agents list --status suspended
```

---

## 3. Claim Lifecycle

### 3.1 Graduated Validation States

```
PENDING ──► VALIDATED ──► TRUSTED
   │            │             │
   │            ▼             ▼
   │        DISPUTED ──► REJECTED
   │            │
   ▼            ▼
REJECTED    PENDING        (dispute resolved, back to review)
```

| State | Meaning | Access | Entry Condition |
|-------|---------|--------|-----------------|
| `pending` | Stored, awaiting validation | All authorized (with badge) | Default on store |
| `validated` | Passed sentinel audit | All authorized | Sentinel quorum approves |
| `trusted` | Long-standing + multiple independent confirmations | All authorized (highest recall priority) | Auto-promoted: validated 7+ days, 2+ attestations, 0 disputes |
| `disputed` | Conflicting evidence found | All authorized (with warning) | Any challenge or sentinel conflict detection |
| `rejected` | Failed validation | Audit log + source agent only | Sentinel quorum rejects or operator action |
| `expired` | TTL reached | Unchanged | Expiry sweep (unchanged) |

### 3.2 Backward Compatibility

| Old Value | New Value | Migration |
|-----------|-----------|-----------|
| `UNREVIEWED` | `PENDING` | Rename |
| `ATTESTED` | `VALIDATED` | Rename |
| `CHALLENGED` | `DISPUTED` | Rename |
| `EXPIRED` | `EXPIRED` | No change |

### 3.3 Trust Promotion

Background job `PROMOTE_TRUSTED_CLAIMS` runs every `trust_promotion_scan_interval_hours` (default: 24):
- Finds `validated` claims where `validated_at` is `trust_promotion_min_age_days`+ ago
- Requires `attestation_count >= trust_promotion_min_attestations` from different agents
- Requires `challenge_count == 0` since last validation
- Promotes to `trusted`, audits the promotion

### 3.4 Recall Scoring Impact

| Status | Score Modifier |
|--------|---------------|
| `trusted` | +0.25 |
| `validated` | +0.15 |
| `pending` | +0.0 |
| `disputed` | -0.2 |
| `rejected` | -1.0 (excluded from recall by default) |
| `expired` | -1.0 (unchanged) |

---

## 4. Sentinel Agent Framework

### 4.1 Architecture

```
Agent stores memory
       │
       ▼
┌──────────────┐     ┌──────────────────────┐
│  Pre-Store   │────►│  Fast Gate (< 50ms)  │
│  Pipeline    │     │  - Duplicate check    │
│              │     │  - Format validation  │
└──────────────┘     └──────────┬───────────┘
                               │
                 ┌─────────────┼─────────────┐
                 │ PASS        │ BLOCK        │
                 ▼             ▼
           Store with    Return 400 with
           status=PENDING  clear reason
                 │
                 ▼
┌─────────────────────────────────┐
│     Post-Store Audit Queue       │
│  (background, target < 5 min)    │
└────────────┬────────────────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
┌──────────┐    ┌──────────┐
│ Sentinel │    │ Sentinel │   (independent)
│ Conflict │    │ Quality  │
│ Checker  │    │ Scorer   │
└────┬─────┘    └────┬─────┘
     └───────┬───────┘
             ▼
┌─────────────────────┐
│  Verdict Aggregator  │
│  (reputation-weighted│
│   quorum)            │
└──────────┬──────────┘
           │
  ┌────────┼────────┐
  ▼        ▼        ▼
VALIDATED DISPUTED REJECTED
```

### 4.2 Built-in Sentinels

**Duplicate Sentinel** (`sentinel_duplicate`)
- Phase: pre-store (synchronous)
- Method: Jaccard similarity against recent claims from same agent
- Threshold: 0.88
- Verdict: `BLOCK` if duplicate, `PASS` otherwise

**Conflict Sentinel** (`sentinel_conflict`)
- Phase: post-store (async)
- Method: Recalls claims for same entities, detects contradiction patterns:
  - Negation: "X is Y" vs "X is not Y"
  - Numeric: "revenue $10M" vs "revenue $5M"
  - Temporal: "deadline March" vs "deadline April"
- Verdict: `DISPUTE` with pointer to conflicting claim, or `PASS`

**Quality Sentinel** (`sentinel_quality`)
- Phase: post-store (async)
- Scoring matrix:

| Signal | Points |
|--------|--------|
| Has 1+ entities | +2 |
| Confidence > 0.6 | +1 |
| Source reputation > 0.5 | +1 |
| Content > 10 words | +1 |
| Has evidence/citations | +2 |
| Source agent < 5 claims | -1 |
| Sensitive keywords detected | -1 |

- Score >= 4 → `VALIDATE`
- Score 2-3 → `NEEDS_REVIEW` (creates review task)
- Score < 2 → `REJECT`

### 4.3 Verdict Aggregation

```python
if any sentinel says BLOCK/REJECT:
    → claim stays PENDING, review task created
    → if 2+ sentinels reject → auto-REJECTED
if all sentinels say VALIDATE:
    → claim promoted to VALIDATED
if any sentinel says DISPUTE:
    → claim marked DISPUTED with conflicting_claim_id
    → notification sent to source agent
```

### 4.4 Risk-Proportional Audit Depth

| Source Agent Profile | Pre-Store | Post-Store | Depth |
|---------------------|-----------|------------|-------|
| New (< 5 claims) | Duplicate + format | All 3 sentinels | Full |
| Established (reputation > 0.6) | Duplicate only | Quality only | Light |
| Trusted (reputation > 0.8, 20+ attested) | Duplicate only | 10% sampling | Minimal |
| Suspended/reactivated | Duplicate + format | All 3 sentinels for 10 stores | Probation |

Configurable via `sentinel_audit_depth` (auto/full/light/off) and `sentinel_bypass_reputation_threshold`.

### 4.5 SentinelVerdict Model

```python
@dataclass(slots=True)
class SentinelVerdict:
    verdict_id: str
    sentinel_agent_id: str
    claim_id: str
    memory_id: str
    decision: str           # "pass", "validate", "dispute", "reject", "needs_review"
    confidence: float
    reason: str
    conflicting_claim_id: str | None
    details: dict[str, str]
    timestamp: datetime
```

### 4.6 Canary Injection

- Runs every `sentinel_canary_interval_hours` (default: 24)
- Injects a known-bad claim (contradiction or low quality)
- Verifies at least one sentinel catches it
- If canary passes undetected → operator notification
- Canary claims tagged `_sentinel_canary: true`, auto-cleaned after verification

### 4.7 Sentinel Registration

On `ContextGraphService.__init__` when `sentinel_enabled=True`:
1. Register `sentinel_duplicate`, `sentinel_conflict`, `sentinel_quality` in `_system` org
2. Idempotent — skip if already registered
3. Schedule background jobs: `SWEEP_IDLE_AGENTS`, `PROMOTE_TRUSTED_CLAIMS`, `SENTINEL_CANARY`

---

## 5. Configuration

```python
# Agent Lifecycle
agent_idle_threshold_days: int = 30
agent_idle_scan_interval_hours: int = 24

# Sentinel Pipeline
sentinel_enabled: bool = True
sentinel_audit_depth: str = "auto"
sentinel_bypass_reputation_threshold: float = 0.8
sentinel_new_agent_claim_threshold: int = 5
sentinel_canary_interval_hours: int = 24
sentinel_post_store_timeout_seconds: int = 300

# Trust Promotion
trust_promotion_enabled: bool = True
trust_promotion_min_age_days: int = 7
trust_promotion_min_attestations: int = 2
trust_promotion_scan_interval_hours: int = 24
```

---

## 6. API Additions

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /v1/agents/{id}/suspend` | POST | Manual suspend |
| `POST /v1/agents/{id}/reactivate` | POST | Manual reactivate |
| `DELETE /v1/agents/{id}` | DELETE | Soft-delete |
| `GET /v1/agents?status=...` | GET | Filter by status |
| `GET /v1/audit/verdicts` | GET | List sentinel verdicts |
| `GET /v1/sentinel/health` | GET | Sentinel system status |

---

## 7. SDK Additions

```python
# Agent lifecycle
client.suspend_agent(agent_id, reason="...")
client.reactivate_agent(agent_id)
client.delete_agent(agent_id)

# Sentinel (operator)
client.sentinel_verdicts(claim_id="clm_xxx")
client.sentinel_health()
```

---

## 8. CLI Additions

```bash
cg agents suspend <id> --reason "..."
cg agents wake <id>
cg agents delete <id>
cg agents list --status suspended

cg sentinel health
cg sentinel verdicts --claim clm_xxx
cg sentinel verdicts --status dispute
```

---

## 9. Repository Protocol Additions

```python
# Agent lifecycle
def update_agent_status(agent_id: str, status: str, reason: str | None) -> Agent
def list_agents_by_status(status: str) -> list[Agent]
def list_idle_agents(threshold: datetime) -> list[Agent]

# Sentinel verdicts
def save_sentinel_verdict(verdict: SentinelVerdict) -> SentinelVerdict
def list_verdicts_for_claim(claim_id: str) -> list[SentinelVerdict]
def list_verdicts(limit: int, status: str | None) -> list[SentinelVerdict]
```

Both `InMemoryRepository` and `Neo4jRepository` implement all methods.

---

## 10. New Event Types

- `AGENT_SUSPENDED` — agent auto-suspended or manually suspended
- `AGENT_REACTIVATED` — agent woke up
- `AGENT_DELETED` — agent soft-deleted
- `CLAIM_VALIDATED` — sentinel pipeline validated a claim
- `CLAIM_DISPUTED` — sentinel or reviewer disputed a claim
- `CLAIM_REJECTED` — claim rejected by sentinels
- `CLAIM_PROMOTED` — claim promoted to trusted
- `SENTINEL_CANARY_FAILED` — canary passed undetected (alert)

---

## 11. Files to Modify/Create

| File | Action |
|------|--------|
| `contextgraph/models.py` | Edit — new enum values, SentinelVerdict, Agent fields |
| `contextgraph/config.py` | Edit — new settings |
| `contextgraph/service.py` | Edit — lifecycle methods, sentinel pipeline integration, trust promotion |
| `contextgraph/sentinel.py` | Create — sentinel logic (duplicate, conflict, quality, aggregator, canary) |
| `contextgraph/repository.py` | Edit — new protocol methods |
| `contextgraph/in_memory.py` | Edit — implement new methods |
| `contextgraph/graph/neo4j_repository.py` | Edit — implement new methods |
| `contextgraph/api/routes.py` | Edit — new endpoints |
| `contextgraph/api/schemas.py` | Edit — new request/response models |
| `contextgraph/api/dependencies.py` | Edit — auth changes for auto-wake |
| `contextgraph/events.py` | Edit — new event types |
| `sdk/contextgraph_sdk/client.py` | Edit — new SDK methods |
| `sdk/contextgraph_sdk/_local.py` | Edit — new LocalTransport methods |
| `contextgraph/cli.py` | Edit — new CLI commands |
| `tests/test_agent_lifecycle.py` | Create |
| `tests/test_sentinel.py` | Create |
| `tests/test_claim_lifecycle.py` | Create |

---

## 12. Testing Strategy

**test_agent_lifecycle.py (~12 tests):**
- Active → suspended → reactivated round-trip
- Auto-suspend on idle (mock time)
- Auto-wake for idle-suspended agents
- Manual suspend blocks auto-wake
- Soft-delete is irreversible
- Suspended agent can't authenticate
- last_activity_at updates on API calls

**test_sentinel.py (~15 tests):**
- Duplicate sentinel blocks exact duplicates
- Duplicate sentinel allows distinct claims
- Conflict sentinel detects negation contradictions
- Conflict sentinel detects numeric contradictions
- Quality sentinel scoring (each signal)
- Verdict aggregation: all pass → validated
- Verdict aggregation: any reject → review task
- Verdict aggregation: dispute → links conflicting claim
- Risk-proportional depth by agent profile
- Canary injection and detection

**test_claim_lifecycle.py (~12 tests):**
- Store → pending (default)
- Sentinel pass → validated
- Validated + time + attestations → trusted (auto-promotion)
- Challenge → disputed
- Rejected excluded from recall
- Backward compat: existing enum values parse correctly
- Recall scoring weights by status

**Target: 188 existing tests pass + ~39 new tests.**

---

## 13. Future Extensions (Not in Scope)

- **Escrow services** for knowledge commerce (hold payment until claim validated)
- **LLM-based sentinels** (swap rule-based conflict detection for semantic understanding)
- **Custom sentinel registration** (orgs register their own domain-specific sentinels)
- **Cross-org sentinel federation** (shared sentinel infrastructure between orgs)
