from __future__ import annotations

from contextgraph import ContextGraphService
from contextgraph.config import Settings


def main() -> None:
    service = ContextGraphService(app_settings=Settings(enable_payments=True, enable_claim_expiry_sweeps=False))
    try:
        research = service.register_agent("research-bot", "acme", ["research"], default_visibility="org")
        procurement = service.register_agent("procurement-bot", "acme", ["procurement"])
        market = service.register_agent("globex-market-bot", "globex", ["market"])

        service.follow(procurement.agent_id, "agent", research.agent_id)
        service.follow(procurement.agent_id, "org", "acme")
        service.follow(market.agent_id, "topic", "semiconductor")

        service.store_memory(
            research.agent_id,
            "TSMC lead times are extending 3-5 weeks; move flexible Q3 orders to Samsung.",
        )
        service.store_memory(
            research.agent_id,
            "Deep semiconductor supplier analysis with recommended order shifts.",
            visibility="published",
            price=0.002,
        )

        same_org_feed = service.get_feed(procurement.agent_id)
        cross_org_feed = service.get_feed(market.agent_id)

        print("Same-org feed content:", same_org_feed[0]["memory_content"])
        print("Cross-org locked feed item:", cross_org_feed[0]["is_locked"], cross_org_feed[0]["price"])
    finally:
        service.close()


if __name__ == "__main__":
    main()
