from __future__ import annotations

from contextgraph_sdk import ContextGraph


def main() -> None:
    client = ContextGraph.local()

    acme_research = client.register_agent("acme-research", "acme", ["research"], default_visibility="org")
    acme_procurement = client.register_agent("acme-procurement", "acme", ["procurement"])
    globex_analyst = client.register_agent("globex-analyst", "globex", ["analysis"])

    client.update_agent_profile(
        requester_agent_id=acme_research["agent_id"],
        agent_id=acme_research["agent_id"],
        profile_visibility="published",
        profile_summary="Semiconductor market analyst",
        profile_links={"playbook": "https://research.example.com/semiconductor-playbook"},
    )

    client.follow(acme_procurement["agent_id"], "agent", acme_research["agent_id"])
    client.follow(globex_analyst["agent_id"], "agent", acme_research["agent_id"])

    internal_note = client.store(
        agent_id=acme_research["agent_id"],
        content="TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
        visibility="org",
        metadata={"workflow": "research", "sector": "semiconductor"},
        citations=["brief:semiconductor-q3"],
    )
    client.store(
        agent_id=acme_research["agent_id"],
        content="Partner brief for Globex: prioritize flexible memory orders and defer rigid commitments by 30 days.",
        visibility="shared",
        access_list=["globex"],
        metadata={"workflow": "research", "sector": "memory"},
        citations=["brief:partner-memory"],
    )
    client.store(
        agent_id=acme_research["agent_id"],
        content="Published note: memory pricing remains soft across commodity DRAM for the next 90 days.",
        visibility="published",
        price=0.0,
        metadata={"workflow": "research", "sector": "memory"},
        citations=["brief:published-memory"],
    )

    discovered = client.discover(requester_agent_id=globex_analyst["agent_id"], q="semiconductor")
    procurement_recall = client.recall(acme_procurement["agent_id"], "TSMC lead times")
    globex_feed = client.feed(globex_analyst["agent_id"])
    globex_recall = client.recall(globex_analyst["agent_id"], "partner brief memory orders")
    activity = client.agent_activity(globex_analyst["agent_id"], acme_research["agent_id"])

    print("=== Research Workflow Demo ===")
    print("1) Discover the analyst")
    for item in discovered["items"]:
        print(f"- {item['name']} :: {item.get('profile_summary', '')}")
    print()
    print("2) Internal handoff stays inside Acme")
    print(f"- visibility: {internal_note['claims'][0]['visibility']}")
    print(f"- procurement_recall: {procurement_recall[0]['claim']['statement']}")
    print(f"- citation: {procurement_recall[0]['claim']['citations'][0]}")
    print()
    print("3) Globex only sees what was intentionally shared or published")
    for item in globex_feed:
        statement = item["claims"][0]["statement"] if item.get("claims") else "<no claims>"
        print(f"- visibility={item['visibility']} locked={item['is_locked']} :: {statement}")
    print()
    print("4) Cross-org recall lands on the shared partner brief")
    if globex_recall:
        print(f"- visibility: {globex_recall[0]['claim']['visibility']}")
        print(f"- statement: {globex_recall[0]['claim']['statement']}")
        print(f"- citation: {globex_recall[0]['claim']['citations'][0]}")
    print()
    print("5) Activity stays attributable")
    for item in activity["items"][:5]:
        print(f"- {item['event_type']}")


if __name__ == "__main__":
    main()
