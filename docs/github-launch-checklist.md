# GitHub Launch Checklist

Use this checklist to finish the repo settings that do not live in git.

Last verified: March 21, 2026

## Current Public Status

- `Latest published release`: legacy
  - `v0.2.1` is published: <https://github.com/AllenMaxi/ContextGraph/releases/tag/v0.2.1>
- `Next release target`: `v0.4.0`
  - align packaging, docs, and release notes before promotion
- `Social preview image`: asset ready, GitHub setting still needs manual upload
  - Use [`docs/assets/contextgraph-social-preview.png`](./assets/contextgraph-social-preview.png)
- `Topics`: not configured yet
- `Discussions`: disabled
- `MCP Registry`: not listed yet

Supporting launch docs now available in-repo:

- release notes: [`docs/releases/0.4.0.md`](./releases/0.4.0.md)
- beta plan: [`docs/launch-plan.md`](./launch-plan.md)
- launch asset guide: [`docs/launch-assets.md`](./launch-assets.md)
- social copy: [`docs/articles/shared-memory-launch-posts.md`](./articles/shared-memory-launch-posts.md)
- production guide: [`docs/production-readiness.md`](./production-readiness.md)
- design partner program: [`docs/design-partner-program.md`](./design-partner-program.md)

## Recommended Public Repo Description

Use this as the GitHub repository description:

`Governed shared memory for AI agents.`

This wording is tighter for the current beta and keeps the lead message on the main wedge instead of the broader platform surface.

## Recommended Topics

Set these topics on the repository:

- `mcp`
- `model-context-protocol`
- `mcp-server`
- `ai-agents`
- `agent-memory`
- `agentic-rag`
- `multi-agent-systems`
- `knowledge-graph`
- `python`
- `neo4j`

These are chosen for discoverability around MCP, agent systems, and the repo's actual implementation.

## GitHub Settings To Update

### 1. Upload the social preview image

In GitHub:

1. Open `Settings`
2. Open `General`
3. Scroll to `Social preview`
4. Upload [`docs/assets/contextgraph-social-preview.png`](./assets/contextgraph-social-preview.png)

This asset is already sized for GitHub social sharing at `1280x640`.

### 2. Update the repo description and topics

If you prefer the GitHub UI:

1. Open the repository homepage
2. Click the settings icon beside `About`
3. Update the description
4. Add the topics above

If you prefer GitHub CLI and are authenticated:

```bash
gh repo edit AllenMaxi/ContextGraph \
  --description "Governed shared memory for AI agents." \
  --add-topic mcp \
  --add-topic model-context-protocol \
  --add-topic mcp-server \
  --add-topic ai-agents \
  --add-topic agent-memory \
  --add-topic agentic-rag \
  --add-topic multi-agent-systems \
  --add-topic knowledge-graph \
  --add-topic python \
  --add-topic neo4j
```

### 3. Enable Discussions

In GitHub:

1. Open `Settings`
2. Open `General`
3. Scroll to `Features`
4. Enable `Discussions`

Or with GitHub CLI:

```bash
gh repo edit AllenMaxi/ContextGraph --enable-discussions
```

Suggested starter categories:

- `Announcements`
- `Ideas`
- `Q&A`
- `Show and tell`

## MCP Registry Readiness

ContextGraph is not listed in the official MCP Registry yet.

The current blocker is not packaging. It is transport shape:

- the repo already has an MCP server over `stdio`
- the official registry is best suited to published remote servers or installable packages
- for a GitHub-first launch, the clean next step is a public `streamable-http` MCP endpoint

Use [`docs/mcp-registry-launch.md`](./mcp-registry-launch.md) and [`registry/contextgraph.server.template.json`](../registry/contextgraph.server.template.json) to prepare the listing.

## Verification Script

Run this before and after the next public release:

```bash
# Check the currently published public state
python3 scripts/check_public_launch.py --repo AllenMaxi/ContextGraph --release-tag v0.2.1

# After publishing the next release
python3 scripts/check_public_launch.py --repo AllenMaxi/ContextGraph --release-tag v0.4.0
```
