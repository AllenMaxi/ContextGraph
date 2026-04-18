#!/usr/bin/env bash
# SessionStart hook: ensure the World server is running and register
# base identities (Claude + User). Fire-and-forget — non-blocking.
set -u

REPO_ROOT="/Users/maximilianoallende/ContextGraph/ContextGraph"
URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"
STATE_DIR="${CG_WORLD_STATE_DIR:-$HOME/.contextgraph}"

mkdir -p "$STATE_DIR/spawns"

# Reset per-session counter (best-effort — payload on stdin is JSON w/ session_id)
payload="$(cat 2>/dev/null || true)"
session_id="$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin); print(d.get("session_id", "") or "")
except Exception: print("")
' 2>/dev/null)"
[ -n "$session_id" ] && : > "$STATE_DIR/spawns/$session_id.counter"

# 1. Ensure world is running
"$REPO_ROOT/bin/cg-world" ensure >/dev/null 2>&1 || true

# 2. Register Claude (main) identity — archmage by default
curl -sS -m 2 -o /dev/null -X POST "$URL/v1/world/identity" \
  -H 'Content-Type: application/json' \
  -d '{"actor":"claude","name":"Claude","archetype":"archmage","tools_count":20,"skills_count":10}' \
  >/dev/null 2>&1 || true

# 3. Register User identity (presence — shown on first prompt)
curl -sS -m 2 -o /dev/null -X POST "$URL/v1/world/identity" \
  -H 'Content-Type: application/json' \
  -d '{"actor":"user","name":"You","archetype":"user","tools_count":0,"skills_count":0}' \
  >/dev/null 2>&1 || true

exit 0
