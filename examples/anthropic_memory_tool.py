from __future__ import annotations

import os

from contextgraph_sdk import ContextGraph

from contextgraph import ContextGraphAnthropicMemoryTool


def main() -> None:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - example guard
        raise SystemExit(
            'Install the Anthropic SDK first: pip install anthropic or pip install -e ".[anthropic]"'
        ) from exc

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY before running this example.")

    client = ContextGraph.local()
    agent = client.register_agent(
        name="claude-memory-demo",
        org_id="acme",
        capabilities=["assistant", "memory"],
        default_visibility="private",
    )
    memory_tool = ContextGraphAnthropicMemoryTool(
        client,
        agent["agent_id"],
        namespace="demo",
        default_visibility="private",
    )

    anthropic_client = anthropic.Anthropic(api_key=api_key)
    runner = anthropic_client.beta.messages.tool_runner(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        betas=["memory-tool-2025-08-18"],
        tools=[memory_tool],
        messages=[
            {
                "role": "user",
                "content": (
                    "Create a memory file for this project, store the current milestone goals, "
                    "then update the file with a short progress note."
                ),
            }
        ],
    )

    for message in runner:
        print(message)

    final_message = runner.until_done()
    print("\nFinal response:")
    print(final_message)
    print("\nCurrent memory directory:")
    print(memory_tool.view(type("ViewCommand", (), {"path": "/memories", "view_range": None})()))


if __name__ == "__main__":
    main()
