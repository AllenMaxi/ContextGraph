#!/usr/bin/env bash
# PostToolUse hook (matcher: Agent): despawn the sub-avatar emitted by the
# matching Pre hook. Also sets a short result-summary bubble on the child
# just before it fades.
set -u

URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"
STATE_DIR="${CG_WORLD_STATE_DIR:-$HOME/.contextgraph}"

payload="$(cat)"

parsed="$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
tool = d.get("tool_name", "") or ""
if tool not in ("Agent", "Task"):
    sys.exit(0)
ti = d.get("tool_input", {}) or {}
tr = d.get("tool_response", {}) or {}
subagent = (ti.get("subagent_type") or "general-purpose").strip() or "general-purpose"
desc = (ti.get("description") or "").strip()

# Pick best summary available
summary = ""
if isinstance(tr, dict):
    # Subagent results often land as a string or {"content": ...}
    summary = tr.get("result") or tr.get("summary") or ""
    if not summary:
        c = tr.get("content")
        if isinstance(c, list) and c and isinstance(c[0], dict):
            summary = c[0].get("text", "") or ""
        elif isinstance(c, str):
            summary = c
elif isinstance(tr, str):
    summary = tr

summary = summary.strip().replace("\n", " ")[:180]
print(json.dumps({
    "session": d.get("session_id", "") or "x",
    "subagent": subagent, "desc": desc[:120], "summary": summary,
}))
' 2>/dev/null)"

[ -z "$parsed" ] && exit 0

session="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])' 2>/dev/null)"
subagent="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["subagent"])' 2>/dev/null)"
desc="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["desc"])' 2>/dev/null)"
summary="$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["summary"])' 2>/dev/null)"

stash_dir="$STATE_DIR/spawns/$session"
key="$(printf '%s|%s' "$subagent" "$desc" | shasum | awk '{print $1}' | cut -c1-16)"

actor_id=""
if [ -f "$stash_dir/$key" ]; then
    actor_id="$(cat "$stash_dir/$key")"
    rm -f "$stash_dir/$key"
elif [ -f "$stash_dir/_last" ]; then
    actor_id="$(cat "$stash_dir/_last")"
    rm -f "$stash_dir/_last"
fi

[ -z "$actor_id" ] && exit 0

body="$(python3 -c '
import json, sys
print(json.dumps({"actor": sys.argv[1], "result_summary": sys.argv[2]}))
' "$actor_id" "$summary")"

(curl -sS -m 1 -o /dev/null -X POST "$URL/v1/world/despawn" \
  -H 'Content-Type: application/json' -d "$body" >/dev/null 2>&1 &) >/dev/null 2>&1

exit 0
