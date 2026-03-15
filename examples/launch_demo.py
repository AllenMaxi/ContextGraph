from __future__ import annotations

from contextgraph import ContextGraphService
from contextgraph.config import Settings
from contextgraph.errors import PaymentRequiredError


def main() -> None:
    service = ContextGraphService(app_settings=Settings(enable_payments=True, enable_claim_expiry_sweeps=False))
    try:
        research = service.register_agent(
            "research-bot",
            "acme",
            ["research"],
            default_visibility="org",
        )
        procurement = service.register_agent("procurement-bot", "acme", ["procurement"])
        globex = service.register_agent("globex-market-bot", "globex", ["market"])

        service.follow(procurement.agent_id, "agent", research.agent_id)
        service.follow(globex.agent_id, "agent", research.agent_id)

        service.store_memory(
            research.agent_id,
            "TSMC lead times are extending 3-5 weeks in Q3. Shift flexible orders to Samsung.",
        )
        priced = service.store_memory(
            research.agent_id,
            "Deep supplier analysis with recommended order shifts.",
            visibility="published",
            price=0.002,
        )

        same_org_feed = service.get_feed(procurement.agent_id)
        cross_org_feed = service.get_feed(globex.agent_id)

        print("$ register research-bot with default_visibility=org")
        print("agent_id:", research.agent_id)
        print()
        print("$ store internal memory without repeating policy")
        print("same-org feed content:", same_org_feed[0]["memory_content"])
        print()
        print("$ store published priced memory")
        print("priced memory id:", priced.memory.memory_id)
        print("cross-org feed locked:", cross_org_feed[0]["is_locked"])
        print("cross-org feed price:", cross_org_feed[0]["price"])
        print("cross-org feed content:", repr(cross_org_feed[0]["memory_content"]))
        print()
        print("$ cross-org recall without payment")
        try:
            service.recall(globex.agent_id, "supplier analysis")
        except PaymentRequiredError as exc:
            print("payment required:", str(exc))
        print()
        print("$ cross-org recall with payment token")
        paid_hits = service.recall(globex.agent_id, "supplier analysis", payment_token="x402_test_token")
        print("unlocked memory:", paid_hits[0].memory_content)
    finally:
        service.close()


if __name__ == "__main__":
    main()
