from __future__ import annotations

from contextgraph import ContextGraphService


def main() -> None:
    service = ContextGraphService()
    research = service.register_agent("research-bot", "acme", ["research"])
    procurement = service.register_agent("procurement-bot", "acme", ["procurement"])

    service.follow(procurement.agent_id, "agent", research.agent_id)
    service.store_memory(
        research.agent_id,
        "TSMC lead times are extending 3-5 weeks; shift flexible orders to Samsung.",
        visibility="org",
    )

    feed = service.get_feed(procurement.agent_id)
    hits = service.recall(procurement.agent_id, "TSMC lead times")

    print("Feed items:", len(feed))
    print("Feed preview:", feed[0]["memory_content"])
    print("Top recall claim:", hits[0].claim.statement)
    print("Unlocked memory:", hits[0].memory_content)


if __name__ == "__main__":
    main()
