#!/usr/bin/env bash
# Stop hook: post Claude's final assistant message as a speech bubble on
# the Claude avatar. Reads the transcript JSONL and finds the last
# assistant text block.
set -u

URL="${CG_WORLD_URL:-http://127.0.0.1:8420}"

payload="$(cat)"

text="$(printf '%s' "$payload" | python3 -c '
import json, os, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

path = d.get("transcript_path") or d.get("transcript") or ""
if not path or not os.path.isfile(path):
    sys.exit(0)

last = ""
# Walk the JSONL; keep the most recent assistant text
try:
    with open(path, "rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        # Read the tail — transcripts can be long; 64 KiB is plenty for the final turn
        tail_bytes = min(size, 65536)
        fh.seek(size - tail_bytes)
        chunk = fh.read().decode("utf-8", errors="replace")
except Exception:
    sys.exit(0)

for line in chunk.splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        ev = json.loads(line)
    except Exception:
        continue
    # Accept several shapes
    msg = ev.get("message") or ev
    if not isinstance(msg, dict):
        continue
    role = msg.get("role") or ev.get("role") or ""
    if role != "assistant":
        continue
    content = msg.get("content") or ev.get("content") or ""
    if isinstance(content, str):
        last = content
    elif isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
        if parts:
            last = " ".join(parts)

print(last.strip().replace("\n", " ")[:180])
' 2>/dev/null)"

[ -z "$text" ] && exit 0

body="$(python3 -c '
import json, sys
print(json.dumps({"actor": "claude", "role": "assistant", "text": sys.argv[1]}))
' "$text")"

(curl -sS -m 1 -o /dev/null -X POST "$URL/v1/world/message" \
  -H 'Content-Type: application/json' -d "$body" >/dev/null 2>&1 &) >/dev/null 2>&1

exit 0
