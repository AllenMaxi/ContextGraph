from __future__ import annotations

import json

from _hook_common import emit_hook_event, read_hook_payload


def main() -> None:
    payload = read_hook_payload()
    remaining = str(payload.get("context_remaining_pct", payload.get("remaining_pct", "12")))
    content = payload.get(
        "summary",
        "Claude Code is approaching compaction and needs a resumable delta checkpoint.",
    )
    result = emit_hook_event(
        tool_name="claude-code",
        event_type="context_pressure",
        content=content,
        metadata={"context_remaining_pct": remaining},
        auto_checkpoint=True,
        checkpoint_reason="context_pressure",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
