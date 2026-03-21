# Production Readiness Guide

ContextGraph is ready for internal deployment, design-partner pilots, and self-hosted beta usage. It is not yet a finished hosted enterprise platform.

This guide explains the recommended production posture with the current codebase.

## Recommended Deployment Topology

Minimum serious deployment:

- reverse proxy / TLS terminator
- one or more ContextGraph server instances
- Neo4j as the repository backend
- persistent volume snapshots for Neo4j data

Recommended environment baseline:

```bash
CG_REPOSITORY_BACKEND=neo4j
CG_ADMIN_KEY=change-this
CG_ENABLE_BACKGROUND_WORKER=true
CG_RATE_LIMIT_PER_MINUTE=60
```

For development, in-memory is fine. For production, do not rely on the memory backend if you care about durability.

## Current Auth and Admin Model

Today the system uses:

- agent API keys for authenticated traffic
- optional `CG_ADMIN_KEY` to gate agent registration

Current limitations:

- no SSO
- no RBAC control plane for human users
- dashboard auth is still agent-based, not user-account based

Operational recommendation:

- create separate operator agents
- rotate API keys on a schedule
- keep `CG_ADMIN_KEY` only in trusted automation or operator environments

## Backups and Export

What exists today:

- durable storage through Neo4j
- repository snapshots for counts and health visibility

What does not exist yet:

- first-class export API
- one-click backup/restore tooling in the app itself

Recommended current posture:

- use Neo4j volume snapshots or managed Neo4j backups
- snapshot before upgrades or schema-affecting changes
- treat export/backup automation as deployment-layer responsibility for now

## Observability

Minimum recommended signals:

- reverse proxy access logs
- application logs from the API/server
- health checks via `/health`
- operator checks via `/v1/sentinel/health`
- queue and repository counts via server health and dashboard/operator surfaces

Track at least:

- request rate and error rate
- recall latency
- store latency
- background worker backlog
- sentinel verdict volume
- suspended/deleted agent counts

## Governance Posture

Current governance strengths:

- sentinel verdict pipeline
- claim review flow
- trust scoring
- lifecycle controls
- audit entry recording

Current gaps you should explain honestly to customers:

- no full audit alerts/reports control plane
- no enterprise approval workflow UI
- no hosted multi-tenant admin console yet

## Hosted Beta Path

The commercial path should be:

- open source for self-hosted developer adoption
- hosted beta for design partners who want managed infrastructure

The hosted beta should promise:

- managed deployment
- managed Neo4j/backend
- backups
- support
- configuration help

Do not promise:

- full enterprise IAM
- compliance exports
- multi-region SaaS

unless those are actually built.

## Before Calling It Production

Before broad company rollout, tighten these areas:

- migration strategy and upgrade notes
- backup/restore runbooks
- structured logging and dashboards
- deployment examples for cloud providers
- user-facing status page / incident process
- clearer support and SLA expectations

See also:

- [`docs/security-operations.md`](./security-operations.md)
- [`docs/launch-plan.md`](./launch-plan.md)
- [`docs/roadmap.md`](./roadmap.md)
