from __future__ import annotations

import json

from _hook_common import emit_hook_event, read_hook_payload


def main() -> None:
    payload = read_hook_payload()
    result = emit_hook_event(
        tool_name="cline",
        event_type=str(payload.get("event_type", "note")),
        content=str(payload.get("content", "Cline hook event")),
        metadata={str(key): str(value) for key, value in dict(payload.get("metadata", {})).items()},
        auto_checkpoint=bool(payload.get("auto_checkpoint", False)),
        checkpoint_reason=str(payload.get("checkpoint_reason", "")).strip() or None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
