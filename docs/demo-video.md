# Demo Video Guide

Use [`examples/launch_demo.py`](../examples/launch_demo.py) as the single source for the README and launch-video walkthrough.

## Recommended format

- 20-40 seconds
- terminal-first
- one wedge only: internal unlock + cross-org locked discovery + paid recall
- no voiceover needed

## Recording flow

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

## Tool suggestions

- Screen Studio
- CleanShot
- Kap
- asciinema if you prefer terminal-native recording

Prefer MP4 if the recording stays sharp. Convert to GIF only if the size stays small enough for fast README loading.
