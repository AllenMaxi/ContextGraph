#!/usr/bin/env bash
# PostToolUse hook: push Claude Code tool activity into the ContextGraph World.
# Fire-and-forget — never blocks the tool.
set -u

URL="${CG_WORLD_ACTIVITY_URL:-http://127.0.0.1:8420/v1/world/activity}"
ACTOR="${CG_WORLD_ACTOR:-claude}"
NAME="${CG_WORLD_ACTOR_NAME:-Claude}"

# Read the hook JSON payload from stdin
payload=$(cat)

# Extract tool_name with a minimal jq-free parser (Python is reliable + installed)
tool_name=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get("tool_name", "") or "")
except Exception:
    print("")
' 2>/dev/null)

if [ -z "$tool_name" ]; then
  exit 0
fi

# Map tool to action
case "$tool_name" in
  Read|Glob|Grep|NotebookRead)        action="read" ;;
  Edit|Write|NotebookEdit|MultiEdit)  action="edit" ;;
  Bash)                                action="bash" ;;
  WebSearch|WebFetch)                  action="search" ;;
  Agent|Task)                          action="think" ;;
  TodoWrite|TaskCreate|TaskUpdate)     action="review" ;;
  *)                                   action="idle" ;;
esac

# Bubble = short label of what was done
bubble="$tool_name"

# Build JSON body safely (export → python reads env)
body=$(ACTOR="$ACTOR" NAME="$NAME" ACTION="$action" BUBBLE="$bubble" python3 -c 'import json, os; print(json.dumps({"actor": os.environ["ACTOR"], "name": os.environ["NAME"], "action": os.environ["ACTION"], "bubble": os.environ["BUBBLE"]}))' 2>/dev/null)

if [ -z "$body" ]; then
  exit 0
fi

# Fire-and-forget POST, 1s timeout, swallow output
(curl -sS -m 1 -o /dev/null -X POST "$URL" \
  -H 'Content-Type: application/json' \
  -d "$body" >/dev/null 2>&1 &) >/dev/null 2>&1

exit 0
