# ContextGraph Playground — Design Spec

## Overview

A zero-friction interactive demo page at `/playground` on the existing ContextGraph server. Visitors type a query, pick a token budget, and see three agents receive different governed context packs from the same pre-seeded corpus — in one glance.

**Goal:** Convert visitors into GitHub stars by making the "same query, three agents, three different packs" moment land visually in under 10 seconds.

## Architecture

The playground is a new page in the existing dashboard route system. It follows the same pattern as the dashboard: server-side rendered HTML/CSS/JS in Python, no build step, no frontend framework. The page calls the existing `compile_context` API internally (server-side, no CORS issues) and renders the three results.

**Route:** `GET /playground`  
**Style:** Matches the existing dashboard dark theme (same CSS variables)  
**Data:** Pre-seeded on first visit via a `_seed_playground_corpus()` function that creates 3 agents and 6 memories if they don't already exist.

## Page Layout

### Top Bar
- Left: "ContextGraph Playground" with diamond icon
- Right: "Pre-seeded with 6 memories across 3 agents" label + "GitHub" external link

### Query Bar (sticky)
- Text input for the query (prefilled with "payment service architecture incidents")
- Token budget slider (range 100–8000, default 2000, shows current value)
- Green "Compile" button
- Form submits as GET with query params: `?q=...&budget=...`

### Three-Column Results
Three equal columns, one per agent. Each column contains:

1. **Agent header:** colored dot + name + role label + org
   - Alice (green) — "owner · acme"
   - Carol (yellow) — "teammate · acme"  
   - Bob (red) — "external · globex"

2. **Stats badges row:**
   - Claim count (green)
   - Conflict count (red, only if > 0)
   - Locked count (gray, only if > 0)
   - Compression ratio (blue)
   - Token usage (gray: "148 / 2000 tok")

3. **Summary block:** Bordered left with agent color. Extractive summary text.

4. **Claims list:** Top 3 claims shown with colored dots:
   - Green dot: normal included claim
   - Yellow dot: private or stale claim (with label)
   - Red lock icon: locked paid claim (statement replaced with "Paid claim — locked")
   - "+N more claims" expandable link (JavaScript toggle)

5. **Warnings footer:** Below claims, separated by border:
   - Conflict warning (red)
   - Staleness warning (yellow)
   - Locked claim notice (red)
   - "No private claims visible" (gray, when applicable)

### Page Footer
- Left: "Same query. Same corpus. Three different governed packs."
- Right: "View raw JSON" (toggles JSON view) + "Copy API call" (copies curl command) + "Star on GitHub" (external link)

## Pre-Seeded Corpus

The `_seed_playground_corpus()` function creates:

**Agents:**
1. Alice (org: "acme") — the owner who stores memories
2. Carol (org: "acme") — teammate in same org
3. Bob (org: "globex") — external partner

**Memories stored by Alice's agent:**
1. Architecture decision about REST→gRPC migration (visibility: org)
2. JWT authentication details (visibility: org)
3. Private postmortem about rushed gRPC migration (visibility: private)

**Memories stored by the oncall bot (acme org):**
4. Incident report INC-2024-042 about latency spike (visibility: published)
5. Auth token validation failures incident (visibility: published)

**Memories stored by Bob's partner agent:**
6. Integration status report with pricing (visibility: published, price: 5.0)

This corpus demonstrates: private access, org-level access, published access, paid/locked claims, and content that produces meaningful search results for queries about "payment service."

**Idempotency:** The seed function checks if playground agents already exist (by name pattern "playground-*") and skips creation if found. This prevents duplicate seeding on server restart.

## Server-Side Flow

1. `GET /playground` → render form with default query and budget
2. `GET /playground?q=...&budget=...` → for each of the 3 playground agents:
   - Call `service.compile_context(agent_id, query, token_budget, include_explanations=True)`
   - Collect the three ContextPack results
3. Render the three-column HTML with the pack data
4. No JavaScript API calls — everything is server-rendered on form submit

## Interactive Elements (JavaScript)

Minimal JS, no framework:
- **Token budget slider:** Updates the displayed number as user drags
- **"+N more claims" toggle:** Shows/hides overflow claims per column
- **"View raw JSON" toggle:** Shows/hides a `<pre>` block with the raw pack JSON below each column
- **"Copy API call" button:** Copies a `curl` command to clipboard that reproduces the compile_context call

## Seeding Lifecycle

- Playground agents are created with names `playground-alice`, `playground-carol`, `playground-bob` and a fourth `playground-oncall` for incident reports
- On first `/playground` visit, `_seed_playground_corpus()` is called lazily (not on server startup, to avoid slowing boot)
- All playground data uses org IDs `playground-acme` and `playground-globex` to avoid collisions with real data
- No cleanup needed — playground data is harmless and serves as demo content

## Files

| File | Purpose |
|---|---|
| `contextgraph/api/playground.py` | New file: route handler, seed function, HTML rendering |
| `contextgraph/web.py` | Add `register_playground_routes(app, service)` call |
| `tests/test_playground.py` | Seed function test, route smoke test |

## What Is NOT In Scope

- User registration or login on the playground page
- Storing custom memories (compile-only for v1)
- Mobile-responsive layout (desktop-first, acceptable on tablet)
- Analytics or tracking
- Rate limiting beyond the existing server-wide rate limiter
