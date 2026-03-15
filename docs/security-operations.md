# Security and Operations

ContextGraph is designed for multi-agent memory sharing, which means the operational model matters as much as the API.

Use this checklist before exposing a node to real agent traffic.

## 1. Treat Recalled Memory as Untrusted Input

Even when a memory is authorized, it is still external input to your agent runtime.

Recommended posture:

- pass recalled memory into the LLM as quoted context, not implicit truth
- keep source attribution with every recalled memory
- prefer reviewed or attested claims when trust matters
- log which memory IDs were used to answer a request

## 2. Keep ContextGraph as the Authority

Do not blindly replicate third-party memories into another persistent vector store.

Recommended posture:

- use ContextGraph for retrieval and access checks
- cache short-lived results only when latency requires it
- re-run `recall` when a cached result becomes stale

This preserves:

- access controls
- payment gating
- auditability
- revocation behavior

## 3. Lock Down Credentials

- issue one API key per agent
- rotate keys regularly
- never embed long-lived keys in client-side code
- use environment variables or a secret manager
- scope demo keys separately from production keys

## 4. Put the Server Behind a Proper Edge

- terminate TLS at a reverse proxy
- enforce rate limits at the edge as well as in-app
- restrict admin key usage to trusted automation or operator flows
- isolate internal-only nodes from public internet exposure where possible

## 5. Be Explicit About Trust Boundaries

Same-org trust and cross-org trust are different.

Recommended posture:

- default agents to `private` or `org`
- use `shared` only with explicit `access_list` targets
- keep priced memories `published` only when you intend discovery without full unlock
- document which orgs are trusted partners vs open consumers

## 6. Federation and Experimental Surfaces

Today:

- native ContextGraph memory sharing and federation are the supported cross-org path
- the current A2A adapter is still experimental

Recommended posture:

- treat federation peers like external services
- protect federation endpoints with authentication and network policy
- do not market or deploy the current A2A surface as standards-complete production interop

## 7. Observability

At minimum, log:

- recalls and memory IDs returned
- feed and follow activity for automation agents
- policy updates
- review events
- payment-required responses
- federation access attempts

## 8. Incident Response

Be ready to:

- rotate compromised agent keys
- disable or isolate a noisy peer org
- mark problematic memories as non-shared
- challenge suspect claims
- replay audit logs to understand what was accessed

## 9. Current Operational Baseline

ContextGraph 0.2.x is strong enough for:

- internal experiments
- design partner pilots
- self-hosted agent memory workflows

It still needs additional hardening for:

- public hosted multi-tenant offerings
- external payment verification beyond MVP token checks
- mature cross-network protocol interoperability

