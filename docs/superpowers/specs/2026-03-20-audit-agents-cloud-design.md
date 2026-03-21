# Audit Agents in Cloud Deployments — Roadmap Note

**Date:** 2026-03-20
**Status:** Roadmap / superseded as an implementation spec

---

## Why This File Changed

This document originally described a large audit control plane with alert feeds, report generation, dedicated audit APIs, and a dashboard page that are **not implemented in this repo**.

ContextGraph already supports centralized cloud deployment, but the shipped governance surface is narrower and should be documented accurately:

- agent lifecycle controls
- built-in sentinel agents
- sentinel verdict storage and visibility
- trust summaries and claim promotion behavior

The control-plane features from the original draft remain possible future work, but they are not the current API contract.

---

## What Is Shipped Today

The current governance implementation is defined by the lifecycle/sentinel design and the codebase itself.

### Built-in sentinel system

ContextGraph ships with built-in sentinel agents that participate in claim validation:

- `sentinel_duplicate`
- `sentinel_conflict`
- `sentinel_quality`

They generate `SentinelVerdict` records and influence claim state through the existing claim lifecycle.

### Agent lifecycle controls

The service supports:

- suspend agent
- reactivate agent
- soft-delete agent
- idle suspension / wake behavior

### Operator-visible governance surface

Actual API endpoints:

- `GET /v1/audit/verdicts`
- `GET /v1/sentinel/health`
- `POST /v1/agents/{id}/suspend`
- `POST /v1/agents/{id}/reactivate`
- `DELETE /v1/agents/{id}`

Actual CLI commands:

- `cg sentinel health`
- `cg sentinel verdicts --claim <claim_id>`
- `cg sentinel verdicts --status <decision>`
- `cg agents suspend <agent_id> --reason "..."`
- `cg agents wake <agent_id>`
- `cg agents delete <agent_id>`

Discovery and trust surfaces now also expose governance-relevant signals:

- sentinel verdict counts in agent trust summaries
- agent lifecycle status in trust responses
- sentinel verdict summaries in visible agent activity feeds

---

## What Is Not Shipped

The following items from the original audit-agent concept are **not implemented** and should be treated as roadmap only:

- `GET /v1/audit/alerts`
- `GET /v1/audit/reports`
- `GET /v1/audit/agent/{id}/history`
- `GET/PUT /v1/audit/config`
- `/dashboard/audit`
- `cg audit ...` command group
- stored audit alerts and acknowledgements
- generated audit reports

---

## Recommended Source of Truth

For the current shipped governance model, use:

- `docs/superpowers/specs/2026-03-20-agent-lifecycle-audit-orchestration-design.md`
- the implemented API/CLI surface in the codebase

This file should now be read as a **future cloud governance concept**, not as the current feature spec.

---

## Future Direction

If the broader audit control plane is revived later, it should be designed as an expansion on top of the shipped sentinel/lifecycle foundation rather than as a separate parallel model.

That future design should explicitly answer:

- where alerts and reports are stored
- how org-level authorization works
- which governance signals are cross-org visible
- how it integrates with discovery and trust views
- which APIs are operator-only vs agent-visible
