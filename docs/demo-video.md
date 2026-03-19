# Demo Video Guide — v0.3.0

Use two short assets for launch:

- a **terminal-first proof** from [`examples/launch_demo.py`](../examples/launch_demo.py)
- a **real console walkthrough** from [`examples/dashboard_demo_seed.py`](../examples/dashboard_demo_seed.py)

The terminal demo proves the access model and v0.3.0 features work. The console demo makes the project feel tangible.

## 1. Terminal Demo

If you want a fast generated asset instead of a manual screen recording, run:

```bash
PYTHONPATH=/tmp/contextgraph_demo_deps python3 scripts/render_launch_demo.py
```

That produces:

- `docs/assets/contextgraph-demo.gif`
- `docs/assets/contextgraph-demo.mp4`

### Terminal format

- 30-50 seconds
- terminal-first
- covers: access model, provenance, impact/quorum, pattern subscriptions, payment gate
- no voiceover needed

### Terminal flow

1. Open a clean terminal with a large monospace font.
2. Run:

   ```bash
   python3 examples/launch_demo.py
   ```

3. Keep only the following moments in the final cut:
   - agent registration with `default_visibility="org"`
   - internal memory stored without repeating policy
   - same-org full memory access
   - **provenance chain** created on claim
   - **impact classification** (HIGH) and quorum requirement
   - **attestation** by procurement-bot growing the provenance chain
   - **pattern subscription** for TSMC with notification delivery
   - priced published memory appearing locked cross-org
   - `402`-style payment gate on recall
   - successful unlock with payment token

## 2. Dashboard Console Demo

Run the seeded local console:

```bash
python3 examples/dashboard_demo_seed.py
```

If you want to regenerate the committed dashboard assets automatically instead of recording manually, run:

```bash
PYTHONPATH=/tmp/contextgraph_video_deps python3 scripts/render_dashboard_demo.py
```

That produces:

- `docs/assets/contextgraph-dashboard-demo.mp4`
- `docs/assets/contextgraph-dashboard-demo.gif`

The script prints:

- the local console URL
- API keys for `procurement-bot`, `globex-market-bot`, and `research-bot`
- the recommended recording order
- seeded memory IDs for the internal, shared, free published, and paid published memories

### Dashboard format

- 30-45 seconds
- no voiceover needed
- one story: same-org unlock, cross-org share, locked paid discovery
- show the new v0.3.0 dashboard pages
- use the real `/dashboard`, not a separate mock UI

### Dashboard storyboard

1. Log in as `procurement-bot`.
2. Open **Overview** and pause on:
   - `Internal Memories`
   - `Following`
3. Open **Knowledge** and show:
   - Claim impact badges (LOW / HIGH / CRITICAL)
   - Provenance chain on a claim detail
   - Quorum status (met / not met)
4. Open **Agents** and show that `research-bot` is followed.
5. Open **Feed** and inspect the same-org internal memory with full content.
6. Open **Graph Explorer** and show the force-directed entity graph.
7. Log out and log in as `globex-market-bot`.
8. Open **Notifications** and show pattern subscription alerts.
9. Return to **Overview** and show:
   - `Shared With Me`
   - `Locked Discoveries`
10. Open the locked paid memory and show that:
    - source, claims, and price are visible
    - `memory_content` is hidden in the dashboard
11. Optionally cut back to the terminal demo for the paid recall unlock.

### Recording tips

- use a large browser zoom level
- keep the sidebar visible
- do not scroll through docs during the recording
- prefer one clean cursor path over lots of clicks

## 3. CLI Demo (NEW in v0.3.0)

Record a third terminal clip showing the CLI tool:

```bash
# Login
cg auth login --url http://localhost:8000 --key <api-key>

# Store and recall
cg store "TSMC lead times extending 3-5 weeks"
cg recall "TSMC supplier"

# Inspect claims with provenance
cg claims list
cg claims show <claim-id>

# Review a claim
cg claims review <claim-id> --decision attested --reason "Confirmed"

# Pattern watch
cg watch create "TSMC alerts" --entity tsmc --min-confidence 0.5
cg notifications

# Live feed
cg feed
```

### CLI format

- 20-30 seconds
- show store → recall → claims → review → watch → notifications flow
- use `--json` flag once to show machine-readable output

## Tool Suggestions

- Screen Studio
- CleanShot
- Kap
- asciinema for terminal capture

Prefer MP4 if the recording stays sharp. Convert to GIF only if the size stays small enough for fast README loading.
