from __future__ import annotations

from sdk.contextgraph_sdk import ContextGraph


def build_shared_memory_context(client: ContextGraph, agent_id: str, user_query: str) -> str:
    hits = client.recall(agent_id=agent_id, query=user_query, limit=3)
    if not hits:
        return "No shared memory hits."

    sections: list[str] = []
    for idx, hit in enumerate(hits, start=1):
        claim = hit["claim"]["statement"]
        memory = hit["memory_content"]
        source = hit["source_agent_name"] or hit["claim"]["source_agent_id"]
        sections.append(f"[Hit {idx}] Source: {source}\nClaim: {claim}\nMemory: {memory}")
    return "\n\n".join(sections)


def main() -> None:
    client = ContextGraph.local()

    research = client.register_agent(
        name="research-bot",
        org_id="acme",
        capabilities=["research"],
        default_visibility="org",
    )
    assistant = client.register_agent(
        name="assistant-bot",
        org_id="acme",
        capabilities=["assistant"],
    )

    client.store(
        agent_id=research["agent_id"],
        content="TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
    )

    user_query = "Should we adjust our semiconductor orders this quarter?"
    memory_context = build_shared_memory_context(client, assistant["agent_id"], user_query)

    prompt = f"""You are assistant-bot.

Answer the user using the shared memory context when it is relevant.
If the memory context does not answer the question, say what is missing.

User question:
{user_query}

Shared memory context:
{memory_context}
"""

    print(prompt)


if __name__ == "__main__":
    main()
