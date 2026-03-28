"""Memory OS v1 — Context Pack Demo

Demonstrates the core context compiler feature:
- Ingest diverse memories from multiple agents
- Compile governed, token-budgeted context packs
- Show three agents receiving different packs from the same corpus
- Show conflict detection, source provenance, and explanations
"""

from __future__ import annotations

from contextgraph_sdk import ContextGraph


def main() -> None:
    client = ContextGraph.local()

    # --- Register agents across two orgs ---
    lead = client.register_agent("eng-lead", "acme", ["engineering", "architecture"])
    oncall = client.register_agent("oncall-bot", "acme", ["operations", "monitoring"])
    partner = client.register_agent("partner-agent", "globex", ["integration"])

    # --- Ingest a corpus of diverse memories ---

    # Engineering lead stores architecture decisions (org-visible)
    client.store(
        agent_id=lead["agent_id"],
        content=(
            "Architecture decision: the payment service migrates from REST to gRPC "
            "for internal service-to-service communication. REST remains for external APIs. "
            "Target completion: end of Q2."
        ),
        visibility="org",
    )

    client.store(
        agent_id=lead["agent_id"],
        content=(
            "The authentication service uses JWT tokens with RS256 signing. "
            "Token lifetime is 15 minutes with refresh tokens valid for 7 days. "
            "All tokens are validated by the API gateway before reaching backend services."
        ),
        visibility="org",
    )

    # Oncall bot stores incident reports (published for cross-org visibility)
    client.store(
        agent_id=oncall["agent_id"],
        content=(
            "Incident INC-2024-042: payment service latency spike to 2.3s p99 "
            "caused by connection pool exhaustion. Root cause: gRPC migration "
            "introduced incompatible keepalive settings. Mitigated by rolling back "
            "to REST endpoints. Permanent fix pending."
        ),
        visibility="published",
    )

    client.store(
        agent_id=oncall["agent_id"],
        content=(
            "Incident INC-2024-043: authentication token validation failures "
            "affecting 3% of requests. Caused by clock skew between API gateway "
            "and auth service after NTP misconfiguration. Resolved within 45 minutes."
        ),
        visibility="published",
    )

    # Oncall bot stores a private postmortem
    client.store(
        agent_id=oncall["agent_id"],
        content=(
            "Internal postmortem: the gRPC migration was rushed without load testing. "
            "Connection pool defaults were insufficient for production traffic patterns. "
            "Recommendation: mandatory load testing gate for all protocol migrations."
        ),
        visibility="private",
    )

    # Partner stores external integration context (published)
    client.store(
        agent_id=partner["agent_id"],
        content=(
            "Globex integration status: REST webhook delivery from Acme payment service "
            "has been reliable at 99.97% over the past quarter. No gRPC endpoint "
            "is currently available for partner integrations."
        ),
        visibility="published",
    )

    print("=" * 72)
    print("MEMORY OS v1 — CONTEXT PACK DEMO")
    print("=" * 72)

    # --- Demo 1: Same query, three agents, three different packs ---
    query = "payment service architecture incidents"
    budget = 2000

    print(f"\nQuery: '{query}'")
    print(f"Token budget: {budget}")
    print("-" * 72)

    for agent_name, agent in [("eng-lead (acme)", lead), ("oncall-bot (acme)", oncall), ("partner (globex)", partner)]:
        pack = client.compile_context(
            agent_id=agent["agent_id"],
            query=query,
            token_budget=budget,
            include_explanations=True,
        )

        included = pack["included_claims"]
        conflicts = pack["conflicting_claims"]
        excluded = pack["excluded_claims"]
        sources = pack["sources"]
        explanation = pack["explanation"]

        print(f"\n  Agent: {agent_name}")
        print(f"  Pack ID: {pack['pack_id']}")
        print(f"  Included claims: {len(included)}")
        print(f"  Conflicting claims: {len(conflicts)}")
        print(f"  Excluded claims: {len(excluded)}")
        print(f"  Sources: {len(sources)}")
        print(f"  Tokens used: {pack['tokens_used']} / {pack['token_budget']}")

        if included:
            print("  Top claims:")
            for claim in included[:3]:
                status = claim["validation_status"]
                locked = " [LOCKED]" if claim["locked"] else ""
                print(
                    f"    - [{status}] {claim['statement'][:80]}...{locked}"
                    if len(claim["statement"]) > 80
                    else f"    - [{status}] {claim['statement']}{locked}"
                )

        if conflicts:
            print("  Conflicts:")
            for claim in conflicts[:2]:
                print(f"    ! {claim['statement'][:80]}...")

        if explanation and explanation.get("filter_counts"):
            print(f"  Filters applied: {explanation['filter_counts']}")

        locked_count = sum(1 for c in excluded if c.get("locked"))
        if locked_count:
            print(f"  Locked (paid) claims: {locked_count}")

    # --- Demo 2: Tight budget shows truncation ---
    print("\n" + "=" * 72)
    print("TIGHT BUDGET DEMO (100 tokens)")
    print("=" * 72)

    tight_pack = client.compile_context(
        agent_id=lead["agent_id"],
        query="payment service gRPC migration",
        token_budget=100,
        include_explanations=True,
    )
    print(f"\n  Included: {len(tight_pack['included_claims'])} claims")
    print(f"  Excluded: {len(tight_pack['excluded_claims'])} claims")
    print(f"  Tokens: {tight_pack['tokens_used']} / {tight_pack['token_budget']}")
    if tight_pack["summary"]:
        print(f"  Summary: {tight_pack['summary'][:120]}...")
    if tight_pack["explanation"] and tight_pack["explanation"].get("filter_counts"):
        print(f"  Filters: {tight_pack['explanation']['filter_counts']}")

    # --- Demo 3: Retrieve and explain a pack ---
    print("\n" + "=" * 72)
    print("PACK RETRIEVAL AND EXPLANATION")
    print("=" * 72)

    full_pack = client.compile_context(
        agent_id=lead["agent_id"],
        query="authentication JWT tokens",
        token_budget=4000,
        include_explanations=True,
    )
    retrieved = client.get_context_pack(full_pack["pack_id"])
    print(f"\n  Retrieved pack: {retrieved['pack_id']}")
    print(f"  Query: {retrieved['query']}")
    print(f"  Claims: {len(retrieved['included_claims'])}")

    explained = client.explain_context_pack(full_pack["pack_id"])
    explanation = explained["explanation"]
    if explanation:
        if explanation.get("included_reasons"):
            print(f"  Included reasons for {len(explanation['included_reasons'])} claims:")
            for claim_id, reasons in list(explanation["included_reasons"].items())[:3]:
                print(f"    {claim_id}: {reasons}")
        if explanation.get("excluded_reasons"):
            print(f"  Excluded reasons for {len(explanation['excluded_reasons'])} claims:")
            for claim_id, reasons in list(explanation["excluded_reasons"].items())[:3]:
                print(f"    {claim_id}: {reasons}")

    print("\n" + "=" * 72)
    print("DEMO COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()
