from __future__ import annotations

import json
import os

from _hook_common import build_client, ensure_session


def main() -> None:
    client = build_client()
    agent_id = os.environ["CG_AGENT_ID"]
    workspace = os.environ.get("CG_WORKSPACE", os.getcwd())
    session_id = ensure_session(client, agent_id=agent_id, tool_name="claude-code", workspace=workspace)
    resume = client.resume_session(agent_id, session_id)
    print(json.dumps(resume, indent=2))


if __name__ == "__main__":
    main()
