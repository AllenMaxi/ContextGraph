from __future__ import annotations

from sdk.contextgraph_sdk import ContextGraph


def main() -> None:
    # Start the server first:
    #   contextgraph-server
    client = ContextGraph.http("http://localhost:8420")

    agent = client.register_agent("http-demo-agent", "acme", ["research"])
    client_with_key = ContextGraph.http("http://localhost:8420", api_key=agent["api_key"])

    client_with_key.store(
        agent["agent_id"],
        "Acme Corp reported API latency during the morning batch.",
        visibility="org",
    )
    hits = client_with_key.recall(agent["agent_id"], "API latency")

    print("Agent:", agent["agent_id"])
    print("Top claim:", hits[0]["claim"]["statement"])
    print("Memory:", hits[0]["memory_content"])


if __name__ == "__main__":
    main()
