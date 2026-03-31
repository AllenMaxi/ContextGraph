"""Reactive Delta Compaction demo.

Shows the builder-first workflow:
- create a coding session
- record durable events
- auto-checkpoint on context pressure
- fork a branch from a checkpoint
- reuse the shared checkpoint prefix on the branch
- inspect resume payloads and diffs
"""

from __future__ import annotations

from tempfile import TemporaryDirectory

from contextgraph_sdk import ContextGraph


def main() -> None:
    with TemporaryDirectory(prefix="contextgraph-demo-") as workspace:
        client = ContextGraph.local()
        agent = client.register_agent("delta-coder", "acme", ["coding", "memory"])
        session = client.create_session(
            agent_id=agent["agent_id"],
            title="Reactive Delta Demo",
            source="claude-code",
            metadata={"workspace": workspace},
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
        branch = client.fork_session(
            agent["agent_id"],
            session["session_id"],
            from_checkpoint_id=manual["checkpoint_id"],
            title="Reactive Delta Branch",
        )
        client.record_session_event(
            agent["agent_id"],
            branch["session_id"],
            "resolved",
            "Add migration and resume-path regression tests.",
        )
        branched = client.checkpoint_session(agent["agent_id"], branch["session_id"], reason="manual", token_budget=600)
        resume = client.resume_session(agent["agent_id"], session["session_id"])
        branch_resume = client.resume_session(agent["agent_id"], branch["session_id"])
        diff = client.context_diff(agent["agent_id"], session["session_id"])
        memdir = client.sync_memory_directory(agent["agent_id"], branch["session_id"], workspace_path=workspace)

        print("=== Reactive Delta Compaction Demo ===")
        print(f"Session: {session['session_id']} :: {session['title']}")
        print(f"Auto checkpoint: {auto['checkpoint']['checkpoint_id']}")
        print(f"Manual checkpoint: {manual['checkpoint_id']}")
        print(f"Branch session: {branch['session_id']} :: {branch['title']}")
        print(f"Branch checkpoint: {branched['checkpoint_id']} ({branched['cache_status']})")
        print()
        print("Summary:")
        print(f"- {resume['delta_pack']['summary']}")
        print()
        print("Branch cache metadata:")
        print(f"- cache base checkpoint: {branched['cache_base_checkpoint_id'] or '<none>'}")
        print(f"- reused events: {branched['reused_event_count']}")
        print(f"- recomputed events: {branched['recomputed_event_count']}")
        print()
        print("Repo-local memory directory:")
        print(f"- path: {memdir['directory_path']}")
        print(f"- files written: {len(memdir['files_written'])}")
        print()
        print("Restoration prompt:")
        print(resume["delta_pack"]["restoration_prompt"])
        print()
        print("Branch restoration summary:")
        print(f"- {branch_resume['delta_pack']['summary']}")
        print()
        print("Context diff:")
        print(f"- {diff['summary']}")
        for bucket, items in diff["added"].items():
            print(f"- added {bucket}: {items}")


if __name__ == "__main__":
    main()
