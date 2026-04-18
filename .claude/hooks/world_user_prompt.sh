#!/usr/bin/env bash
# UserPromptSubmit hook: show the user's prompt as a speech bubble on the
# User avatar. If the user avatar does not yet exist, /v1/world/message will
# auto-spawn it.
set -u

URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"

payload="$(cat)"

prompt="$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
p = d.get("prompt") or d.get("user_message") or ""
if isinstance(p, list):
    # Rare shape — join text parts
    parts = []
    for x in p:
        if isinstance(x, dict) and x.get("type") == "text":
            parts.append(x.get("text", ""))
        elif isinstance(x, str):
            parts.append(x)
    p = " ".join(parts)
print(str(p).strip().replace("\n", " ")[:180])
' 2>/dev/null)"

[ -z "$prompt" ] && exit 0

body="$(python3 -c '
import json, sys
print(json.dumps({"actor": "user", "role": "user", "text": sys.argv[1]}))
' "$prompt")"

(curl -sS -m 1 -o /dev/null -X POST "$URL/v1/world/message" \
  -H 'Content-Type: application/json' -d "$body" >/dev/null 2>&1 &) >/dev/null 2>&1

exit 0
