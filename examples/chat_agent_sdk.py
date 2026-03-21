from __future__ import annotations

from contextgraph_sdk import ContextGraph, SharedMemoryHelper, SharedMemoryQueryContext


def answer_question(
    client: ContextGraph,
    helper: SharedMemoryHelper,
    agent_id: str,
    user_query: str,
    *,
    context: SharedMemoryQueryContext | None = None,
) -> str:
    outcome = helper.recall_if_needed(
        agent_id=agent_id,
        user_query=user_query,
        context=context,
        limit=3,
    )
    if not outcome.decision.should_consult:
        return (
            f"User question: {user_query}\n"
            "Decision: answer directly without shared memory.\n"
            "Reason: the question looks general enough that external memory is unnecessary."
        )
    if not outcome.hits:
        return (
            f"User question: {user_query}\n"
            "Decision: shared memory was consulted, but no hit passed the relevance threshold.\n"
            "Response policy: do not hallucinate; ask for clarification or say no reliable memory was found."
        )

    top_hit = outcome.hits[0]
    source = top_hit["source_agent_name"] or top_hit["claim"]["source_agent_id"]
    return (
        f"User question: {user_query}\n"
        "Decision: use shared memory.\n"
        f"Source: {source}\n"
        f"Claim: {top_hit['claim']['statement']}\n"
        f"Memory: {top_hit['memory_content']}"
    )


def main() -> None:
    client = ContextGraph.local()
    helper = SharedMemoryHelper(client, default_min_score=0.55)

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
    client.store(
        agent_id=research["agent_id"],
        content="Public industry note: semiconductor wafer prices increased this quarter.",
        visibility="published",
    )

    general_question = "What is MCP?"
    org_question = "Should we adjust our semiconductor orders this quarter?"

    print(answer_question(client, helper, assistant["agent_id"], general_question))
    print()
    print(
        answer_question(
            client,
            helper,
            assistant["agent_id"],
            org_question,
            context=SharedMemoryQueryContext(
                task_type="research",
                entity_names=["TSMC", "Samsung"],
                topics=["semiconductor", "supply"],
            ),
        )
    )


if __name__ == "__main__":
    main()
