"""Reactive Delta Compaction demo.

Shows the builder-first workflow:
- create a coding session
- record durable events
- auto-checkpoint on context pressure
- inspect resume payloads and diffs
"""

from __future__ import annotations

from contextgraph_sdk import ContextGraph


def main() -> None:
    client = ContextGraph.local()
    agent = client.register_agent("delta-coder", "acme", ["coding", "memory"])
    session = client.create_session(
        agent_id=agent["agent_id"],
        title="Reactive Delta Demo",
        source="claude-code",
        metadata={"workspace": "/tmp/demo"},
    )

    client.record_session_event(
        agent["agent_id"],
        session["session_id"],
        "decision",
        "Keep the public REST API stable while migrating internal services to gRPC.",
    )
    client.record_session_event(
        agent["agent_id"],
        session["session_id"],
        "constraint",
        "Do not break SDK compatibility for existing ContextGraph clients.",
    )
    client.record_session_event(
        agent["agent_id"],
        session["session_id"],
        "todo",
        "Add migration and resume-path regression tests.",
    )
    client.record_session_event(
        agent["agent_id"],
        session["session_id"],
        "file_change",
        "Updated contextgraph/service.py and sdk/contextgraph_sdk/client.py",
        metadata={"files": "contextgraph/service.py,sdk/contextgraph_sdk/client.py"},
    )

    auto = client.record_session_event(
        agent["agent_id"],
        session["session_id"],
        "context_pressure",
        "Only 11 percent of the context window remains before compaction.",
        metadata={"context_remaining_pct": "11"},
    )
    manual = client.checkpoint_session(
        agent["agent_id"],
        session["session_id"],
        reason="manual",
        token_budget=600,
    )
    resume = client.resume_session(agent["agent_id"], session["session_id"])
    diff = client.context_diff(agent["agent_id"], session["session_id"])

    print("=== Reactive Delta Compaction Demo ===")
    print(f"Session: {session['session_id']} :: {session['title']}")
    print(f"Auto checkpoint: {auto['checkpoint']['checkpoint_id']}")
    print(f"Manual checkpoint: {manual['checkpoint_id']}")
    print()
    print("Summary:")
    print(f"- {resume['delta_pack']['summary']}")
    print()
    print("Restoration prompt:")
    print(resume["delta_pack"]["restoration_prompt"])
    print()
    print("Context diff:")
    print(f"- {diff['summary']}")
    for bucket, items in diff["added"].items():
        print(f"- added {bucket}: {items}")


if __name__ == "__main__":
    main()
