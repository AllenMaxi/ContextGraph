# Launch Asset Guide

Use this guide to keep the public promotion of ContextGraph consistent across GitHub, LinkedIn, X, Show HN, and direct outreach.

## Primary Message

Lead with one sentence:

`ContextGraph is the memory backend for coding agents.`

The supporting line should stay close to:

`It helps coding agents survive compaction, resume from structured state, reuse governed context across branches and sessions, and materialize the latest working state into .contextgraph/.`

## What To Emphasize

Use these points repeatedly:

- coding-agent continuity under compaction pressure
- reactive delta checkpoints and branch-aware context cache
- repo-local `.contextgraph/` memory directories that make the state visible inside the workspace
- governed memory with provenance, review, freshness, and access control
- explainable context packs instead of opaque retrieval or lossy summaries
- self-hosted memory backend for Claude Code, Codex, Cline, and similar tools

## What Not To Lead With

Do not lead with these in launch copy:

- marketplace or paid discovery
- protocol ambition
- registry plans
- runtime/orchestrator breadth
- generic "AI infrastructure" wording
- "better vector database" framing

These can appear later in replies or follow-up posts, but they should not be the main message.

## GitHub About Box

Use this repository description:

`Memory backend for coding agents.`

Optional short supporting sentence for posts or bios:

`Checkpoint, resume, and branch coding-agent context with governance built in.`

## Launch Asset Order

Use the assets in this order during launch week:

1. Social preview image
   - [`docs/assets/contextgraph-social-preview.png`](./assets/contextgraph-social-preview.png)
   - Use for GitHub social preview and as the static image in LinkedIn posts if you are not using video.
2. Reactive delta compaction demo
   - [`examples/reactive_delta_compaction_demo.py`](../examples/reactive_delta_compaction_demo.py)
   - Best for showing the wedge quickly: decisions, tasks, changed files, checkpoint, resume, branch reuse, and `.contextgraph/` materialization.
3. Governed memory demo
   - [`docs/assets/contextgraph-demo.gif`](./assets/contextgraph-demo.gif)
   - [`docs/assets/contextgraph-demo.mp4`](./assets/contextgraph-demo.mp4)
   - Best for showing the second wedge: store, review, recall, visibility.
4. Dashboard demo
   - [`docs/assets/contextgraph-dashboard-demo.gif`](./assets/contextgraph-dashboard-demo.gif)
   - [`docs/assets/contextgraph-dashboard-demo.mp4`](./assets/contextgraph-dashboard-demo.mp4)
   - Best for showing operator workflow after the initial post.

## Suggested Captions Per Asset

- Social preview image:
  - `Memory backend for coding agents.`
- Reactive delta compaction demo:
  - `Checkpoint, resume, branch, and inspect coding-agent context without collapsing everything into one lossy summary.`
- Governed memory demo:
  - `Store once, review it, and let the right agents recall it with provenance and policy intact.`
- Dashboard demo:
  - `A GitHub-like interface for shared agent memory, trust signals, and visibility controls.`

## Launch Sequence

Recommended sequence for the first 7 days:

1. GitHub release post
   - Link to the repo
   - Use the social preview image or reactive delta compaction demo
2. Product walkthrough post
   - Use the reactive delta compaction demo
   - Explain the coding-agent continuity workflow
3. Governed memory post
   - Use the governed memory demo GIF/MP4
   - Explain why ContextGraph is more than a chat summary or vector memory
4. Dashboard/operator post
   - Use the dashboard demo GIF/MP4
   - Focus on explainability, review, and access controls
5. Community post
   - Adapt for Show HN, Reddit, or a relevant Slack/Discord community
   - Ask for feedback from teams building coding-agent workflows

## Landing Page Checklist

Before promoting, make sure a visitor can answer these within 30 seconds from the repo:

- What problem does ContextGraph solve?
- Who should use it first?
- Why is this not just vector memory or a chat summary?
- How does `.contextgraph/` make the memory visible in a real repo?
- What should I run first?

Current repo links that should appear in launch posts:

- quickstart: [`examples/beta_quickstart.py`](../examples/beta_quickstart.py)
- reactive delta demo: [`examples/reactive_delta_compaction_demo.py`](../examples/reactive_delta_compaction_demo.py)
- support workflow: [`examples/support_memory_workflow.py`](../examples/support_memory_workflow.py)
- production guide: [`docs/production-readiness.md`](./production-readiness.md)
- comparison guide: [`docs/contextgraph-vs-vector-memory.md`](./contextgraph-vs-vector-memory.md)
- social copy: [`docs/articles/shared-memory-launch-posts.md`](./articles/shared-memory-launch-posts.md)

## Tone Guidelines

Keep the tone:

- concrete
- trustworthy
- technical but readable
- confident without overclaiming

Prefer:

- `memory backend for coding agents`
- `reactive delta compaction`
- `branch-aware context cache`
- `repo-local .contextgraph memory directory`
- `checkpoint, resume, and branch from structured state`
- `provenance, review, freshness, and access control`
- `explainable context packs`

Avoid:

- `revolutionary`
- `game-changing`
- `world's first`
- `AGI`
- `everything platform`
