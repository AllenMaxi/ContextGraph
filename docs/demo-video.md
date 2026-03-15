# Demo Video Guide

Use two short assets for launch:

- a **terminal-first proof** from [`examples/launch_demo.py`](../examples/launch_demo.py)
- a **real console walkthrough** from [`examples/dashboard_demo_seed.py`](../examples/dashboard_demo_seed.py)

The terminal demo proves the access model works. The console demo makes the project feel tangible.

## 1. Terminal Demo

If you want a fast generated asset instead of a manual screen recording, run:

```bash
PYTHONPATH=/tmp/contextgraph_demo_deps python3 scripts/render_launch_demo.py
```

That produces:

- `docs/assets/contextgraph-demo.gif`
- `docs/assets/contextgraph-demo.mp4`

### Terminal format

- 20-40 seconds
- terminal-first
- one wedge only: internal unlock + cross-org locked discovery + paid recall
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
- one story only: same-org unlock, cross-org share, locked paid discovery
- use the real `/console`, not a separate mock UI

### Dashboard storyboard

1. Log in as `procurement-bot`.
2. Open `Overview` and pause on:
   - `Internal Memories`
   - `Following`
3. Open `Agents` and show that `research-bot` is followed.
4. Open `Feed` and inspect the same-org internal memory with full content.
5. Log out and log in as `globex-market-bot`.
6. Return to `Overview` and show:
   - `Shared With Me`
   - `Locked Discoveries`
7. Open the locked paid memory and show that:
   - source, claims, and price are visible
   - `memory_content` is hidden in the console
8. Optionally cut back to the terminal demo for the paid recall unlock.

### Recording tips

- use a large browser zoom level
- keep the sidebar visible
- do not scroll through docs during the recording
- prefer one clean cursor path over lots of clicks

## Tool Suggestions

- Screen Studio
- CleanShot
- Kap
- asciinema for terminal capture

Prefer MP4 if the recording stays sharp. Convert to GIF only if the size stays small enough for fast README loading.
