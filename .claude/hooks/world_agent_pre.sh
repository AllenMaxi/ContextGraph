#!/usr/bin/env bash
# PreToolUse hook (matcher: Agent): spawn a sub-avatar in the World.
# Stashes the computed actor_id under ~/.contextgraph/spawns/<session>/<key>
# so the Post hook can despawn precisely.
set -u

URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"
STATE_DIR="${CG_WORLD_STATE_DIR:-$HOME/.contextgraph}"

payload="$(cat)"

parsed="$(printf '%s' "$payload" | python3 -c '
import json, sys, os, time, hashlib
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
tool = d.get("tool_name", "") or ""
if tool not in ("Agent", "Task"):
    sys.exit(0)
ti = d.get("tool_input", {}) or {}
subagent = (ti.get("subagent_type") or "general-purpose").strip() or "general-purpose"
desc = (ti.get("description") or "").strip()
session = d.get("session_id", "") or "x"
# Stable-ish key: subagent + sha1(description)[:6] + monotonic counter per session
counter_file = os.path.join(os.environ.get("STATE_DIR", "/tmp"), "spawns", f"{session}.counter")
os.makedirs(os.path.dirname(counter_file), exist_ok=True)
try:
    with open(counter_file) as f: n = int(f.read().strip() or "0")
except Exception:
    n = 0
n += 1
with open(counter_file, "w") as f: f.write(str(n))
inv = f"{n}"
print(json.dumps({
    "session": session, "subagent": subagent, "desc": desc[:120], "inv": inv,
}))
' STATE_DIR="$STATE_DIR" 2>/dev/null)"

[ -z "$parsed" ] && exit 0

session="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])' 2>/dev/null)"
subagent="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["subagent"])' 2>/dev/null)"
desc="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["desc"])' 2>/dev/null)"
inv="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["inv"])' 2>/dev/null)"

actor_id="claude.${subagent}.${inv}"

# Stash actor_id for the Post hook — keyed by session+subagent+desc hash
stash_dir="$STATE_DIR/spawns/$session"
mkdir -p "$stash_dir"
# Use a deterministic key so Post hook can find the match: sha1(subagent|desc)
key="$(printf '%s|%s' "$subagent" "$desc" | shasum | awk '{print $1}' | cut -c1-16)"
echo "$actor_id" > "$stash_dir/$key"
# Also record the newest-spawn fallback in case the exact key misses
echo "$actor_id" > "$stash_dir/_last"

body="$(python3 -c '
import json, sys
print(json.dumps({
    "parent": "claude",
    "subagent_type": sys.argv[1],
    "description": sys.argv[2],
    "invocation_id": sys.argv[3],
}))
' "$subagent" "$desc" "$inv")"

(curl -sS -m 1 -o /dev/null -X POST "$URL/v1/world/spawn" \
  -H 'Content-Type: application/json' -d "$body" >/dev/null 2>&1 &) >/dev/null 2>&1

exit 0
