from __future__ import annotations

from dataclasses import dataclass

from sdk.contextgraph_sdk import ContextGraph, SharedMemoryHelper, SharedMemoryQueryContext


@dataclass(slots=True)
class AgentAnswer:
    user_query: str
    strategy: str
    response: str
    source_agent: str = ""
    source_memory_id: str = ""
    source_claim: str = ""
    citations: list[str] | None = None


class StarChatAgent:
    def __init__(self, client: ContextGraph, helper: SharedMemoryHelper, agent_id: str) -> None:
        self.client = client
        self.helper = helper
        self.agent_id = agent_id

    def answer(self, user_query: str, *, context: SharedMemoryQueryContext | None = None) -> AgentAnswer:
        outcome = self.helper.recall_if_needed(
            agent_id=self.agent_id,
            user_query=user_query,
            context=context,
            limit=3,
        )
        if not outcome.decision.should_consult:
            return AgentAnswer(
                user_query=user_query,
                strategy="direct",
                response=(
                    "This question does not need shared memory. "
                    "Answer from general model knowledge or the current conversation."
                ),
            )
        if not outcome.hits:
            return AgentAnswer(
                user_query=user_query,
                strategy="consulted_no_reliable_hit",
                response=(
                    "Shared memory was consulted, but no reliable hit passed the threshold. "
                    "Do not hallucinate. Ask for clarification or say no reliable memory was found."
                ),
            )

        top_hit = outcome.hits[0]
        claim = top_hit["claim"]
        return AgentAnswer(
            user_query=user_query,
            strategy="shared_memory",
            response=top_hit["memory_content"],
            source_agent=top_hit["source_agent_name"] or claim["source_agent_id"],
            source_memory_id=claim["memory_id"],
            source_claim=claim["statement"],
            citations=claim.get("citations") or [],
        )


def seed_demo(client: ContextGraph) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
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
    partner = client.register_agent(
        name="globex-lane-bot",
        org_id="globex",
        capabilities=["logistics"],
        default_visibility="shared",
        default_access_list=["acme"],
    )

    client.store(
        agent_id=research["agent_id"],
        content="TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
        evidence=["meeting:research-weekly"],
        citations=["doc:tsmc-q3-brief"],
    )
    client.store(
        agent_id=partner["agent_id"],
        content="Globex lane note: prioritize the Hsinchu lane for urgent semiconductor shipments this month.",
        evidence=["partner-call:globex-logistics"],
        citations=["ticket:GLOBEX-42"],
    )

    return research, assistant, partner


def print_answer(answer: AgentAnswer) -> None:
    print(f"User question: {answer.user_query}")
    print(f"Strategy: {answer.strategy}")
    print(f"Response: {answer.response}")
    if answer.source_agent:
        print(f"Source agent: {answer.source_agent}")
    if answer.source_memory_id:
        print(f"Source memory: {answer.source_memory_id}")
    if answer.source_claim:
        print(f"Supporting claim: {answer.source_claim}")
    if answer.citations:
        print("Citations:")
        for item in answer.citations:
            print(f"  - {item}")


def main() -> None:
    client = ContextGraph.local()
    helper = SharedMemoryHelper(client, default_min_score=0.55)
    research, assistant, partner = seed_demo(client)
    chat_agent = StarChatAgent(client, helper, assistant["agent_id"])

    general = chat_agent.answer("What is MCP?")
    same_org = chat_agent.answer(
        "Should we shift orders away from TSMC this quarter?",
        context=SharedMemoryQueryContext(
            task_type="research",
            entity_names=["TSMC", "Samsung"],
            topics=["semiconductor", "supply-chain"],
        ),
    )
    cross_org = chat_agent.answer(
        "What did Globex share about the Hsinchu lane for urgent shipments?",
        context=SharedMemoryQueryContext(
            task_type="operations",
            entity_names=["Globex", "Hsinchu"],
            topics=["logistics", "semiconductor"],
            source_agent_names=[partner["name"]],
        ),
    )

    print("=== General Question ===")
    print_answer(general)
    print()
    print("=== Same-org Shared Memory ===")
    print_answer(same_org)
    print()
    print("=== Cross-org Shared Memory ===")
    print_answer(cross_org)


if __name__ == "__main__":
    main()
