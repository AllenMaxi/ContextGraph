# ContextGraph vs Vector Memory

## The Short Version

Use ContextGraph when multiple agents need to reuse context with provenance, review, freshness, and visibility controls.

Do not use ContextGraph when you only need a single agent's personal memory or a generic vector retrieval layer.

## What Problem ContextGraph Solves

Most memory stacks answer one question:

- "What text is relevant to this query?"

ContextGraph is built to answer the harder operational questions:

- who asserted this?
- has anyone reviewed it?
- is it still fresh enough to trust?
- who is allowed to see it?
- should another agent act on it?

That is why the current beta is aimed at support operations, research handoffs, and internal multi-agent platforms where wrong context is expensive.

## Category Comparison

| Need | Vector DB + per-agent memory | Temporal/context-graph engine | ContextGraph |
| --- | --- | --- | --- |
| One agent remembers prior facts | Good fit | Good fit | Overkill |
| Search relevant text quickly | Good fit | Good fit | Good fit |
| Time-aware fact evolution | Weak by default | Strong | Good today, deeper temporal history still evolving |
| Provenance and citations attached to recall | Usually custom work | Often partial | Built in |
| Review and trust workflow before reuse | Usually custom work | Usually custom work | Built in |
| Org, shared, and published visibility | Usually custom work | Usually custom work | Built in |
| Feed, follow, and discovery between agents | Rare | Rare | Built in |
| Operator-facing governance workflow | Rare | Rare | Built in for the beta wedge |

## Choose ContextGraph If

- two or more agents need to reuse the same operational context
- one team's memory must stay visible while another team's memory must stay private
- recalled memory needs provenance, evidence, citations, or review state
- you want support or research workflows to share context without copying it into separate stores

## Choose a Simpler Memory Stack If

- you are building a single chatbot
- you only need private user preferences or notes
- you mainly want embeddings plus semantic search
- there is no trust, freshness, or visibility problem to solve

## Choose a Temporal Graph Engine If

- your primary problem is time-aware fact modeling inside one application
- you want to build your own governance, policy, and operator layers around the graph
- you care more about temporal graph construction than cross-agent operational workflow

## What ContextGraph Intentionally Optimizes For

The beta is not trying to be the broadest memory product.

It is optimizing for one pain point:

- agents sharing context they can actually trust and govern

That means the strongest current story is:

1. store a memory once
2. review it when needed
3. recall it from another agent with provenance and policy intact
4. share outward only on purpose

## Not the Right Tool Yet If

- you need enterprise IAM, SSO, and a hosted multi-tenant control plane today
- you want a finished public federation network today
- you want a marketplace-first product before the core trust workflow is proven
