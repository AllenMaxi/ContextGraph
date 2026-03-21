# ContextGraph Beta Launch Plan

**Date:** 2026-03-21
**Goal:** turn ContextGraph into a credible developer beta that can attract real pilots from teams and companies

## Positioning

Do not market ContextGraph as "everything for all agents."

Launch with one clear wedge:

- shared governed memory for multi-agent systems
- provenance, review, and trust built in
- follow/discovery for agents and organizations

Recommended short description:

`Governed shared memory and discovery layer for AI agents.`

## Ideal Early Users

Prioritize teams already building agent workflows and feeling pain around:

- duplicated memory across agents
- lack of provenance on shared outputs
- weak access control on memory reuse
- no trust/review layer across collaborating agents

Best first design partners:

- support automation teams
- market/research agent teams
- internal platform teams experimenting with MCP-based workflows

## 30-Day Execution Plan

### Week 1: Launch hardening

- align versions and public release metadata
- make README onboarding fast and concrete
- ensure CLI, SDK, dashboard, and docs tell the same product story
- keep the product boundary explicit: knowledge layer, not runtime host

### Week 2: Opinionated demos

- publish one support-memory walkthrough
- publish one research/market-intel walkthrough
- record short demo clips for CLI plus dashboard discover/trust flow

### Week 3: Production trust

- improve deployment and operator docs
- document backups, admin keys, and Neo4j deployment guidance
- add a clear "what is production-ready vs experimental" matrix

### Week 4: Pilot outreach

- recruit 3-5 design partners
- onboard them on a narrow use case
- track what they store, recall, review, and share
- refine the product based on repeated friction, not one-off requests

## Success Criteria

The beta is succeeding when:

- 3 teams use ContextGraph weekly on a real workflow
- at least 1 company runs it outside a toy demo
- users can get value in under 10 minutes
- the README and dashboard explain the product without a founder call

## What Not To Do Right Now

- do not add a native agent runtime to this repo
- do not broaden the message to cover every agent architecture
- do not lead with speculative federation or standards support
- do not optimize for stars over pilot usage

## Next Repo Priorities

- better quickstarts and seeded demos
- production deployment guidance
- startup diagnostics and migrations
- polished discover/profile dashboard UX
- hosted beta planning

Use these supporting docs while executing the plan:

- [`docs/releases/0.4.0.md`](./releases/0.4.0.md)
- [`docs/design-partner-program.md`](./design-partner-program.md)
- [`docs/pilot-checklist.md`](./pilot-checklist.md)
- [`docs/production-readiness.md`](./production-readiness.md)
