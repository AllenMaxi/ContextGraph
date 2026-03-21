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

        # ------------------------------------------------------------------
        # 1. Store & access model (original demo)
        # ------------------------------------------------------------------
        print("=" * 60)
        print("  ContextGraph v0.3.0 — Full Demo")
        print("=" * 60)
        print()

        print("$ register research-bot with default_visibility=org")
        print("agent_id:", research.agent_id)
        print()

        result = service.store_memory(
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

        print("$ store internal memory without repeating policy")
        print("same-org feed content:", same_org_feed[0]["memory_content"])
        print()
        print("$ store published priced memory")
        print("priced memory id:", priced.memory.memory_id)
        print("cross-org feed locked:", cross_org_feed[0]["is_locked"])
        print("cross-org feed price:", cross_org_feed[0]["price"])
        print("cross-org feed content:", repr(cross_org_feed[0]["memory_content"]))
        print()

        # ------------------------------------------------------------------
        # 2. Provenance chains (NEW in v0.3.0)
        # ------------------------------------------------------------------
        print("-" * 60)
        print("  Provenance Chains")
        print("-" * 60)
        print()

        claim = result.claims[0]
        print(f"$ claim '{claim.claim_id}' created with provenance:")
        for entry in claim.provenance:
            print(f"  [{entry.action}] by {entry.agent_id} @ confidence {entry.confidence_at_action:.2f}")
        print()

        # ------------------------------------------------------------------
        # 3. Impact classification & quorum (NEW in v0.3.0)
        # ------------------------------------------------------------------
        print("-" * 60)
        print("  Impact Classification & Quorum")
        print("-" * 60)
        print()

        priced_claim = priced.claims[0]
        print(f"$ priced claim impact: {priced_claim.impact.value}")
        print(f"  quorum required: {priced_claim.quorum_required}")
        print(f"  quorum met: {priced_claim.quorum_met}")
        print()

        # Review the claim — provenance grows
        reviewed = service.review_claim(
            reviewer_agent_id=procurement.agent_id,
            claim_id=priced_claim.claim_id,
            decision="attested",
            reason="Confirmed from internal data",
        )
        print("$ procurement-bot attested the claim")
        print(f"  attestation count: {reviewed.attestation_count}")
        print(f"  provenance chain ({len(reviewed.provenance)} entries):")
        for entry in reviewed.provenance:
            detail = f" — {entry.detail}" if entry.detail else ""
            print(f"    [{entry.action}] by {entry.agent_id}{detail}")
        print(f"  quorum met: {reviewed.quorum_met}")
        print()

        # ------------------------------------------------------------------
        # 4. Pattern subscriptions (NEW in v0.3.0)
        # ------------------------------------------------------------------
        print("-" * 60)
        print("  Pattern Subscriptions")
        print("-" * 60)
        print()

        watch = service.watch(
            agent_id=globex.agent_id,
            query="",
            name="TSMC supply chain alerts",
            pattern={"entities": ["tsmc"], "min_confidence": 0.5},
        )
        print("$ globex-market-bot created pattern watch:")
        print(f"  name: {watch.name}")
        print(f"  pattern entities: {watch.pattern.entities}")
        print(f"  pattern min_confidence: {watch.pattern.min_confidence}")
        print()

        # Store something that matches the pattern
        service.store_memory(
            research.agent_id,
            "TSMC capacity utilization dropped to 78% amid weak demand signals.",
            visibility="shared",
            access_list=[globex.agent_id],
        )
        notifications = service.get_notifications(agent_id=globex.agent_id)
        print("$ new memory stored mentioning TSMC")
        print(f"  globex-market-bot notifications: {len(notifications)}")
        print()

        # ------------------------------------------------------------------
        # 5. Payment gate (original demo)
        # ------------------------------------------------------------------
        print("-" * 60)
        print("  x402 Payment Gate")
        print("-" * 60)
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
        print()

        print("=" * 60)
        print("  Demo complete — all v0.3.0 features working")
        print("=" * 60)
    finally:
        service.close()


if __name__ == "__main__":
    main()
