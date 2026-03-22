from __future__ import annotations

from contextgraph_sdk import ContextGraph


def _provenance_actions(claim: dict[str, object]) -> str:
    return " -> ".join(entry["action"] for entry in claim["provenance"])


def main() -> None:
    client = ContextGraph.local()

    triage = client.register_agent("support-triage", "acme", ["support", "triage"], default_visibility="org")
    billing = client.register_agent("billing-specialist", "acme", ["support", "billing"])

    client.follow(billing["agent_id"], "agent", triage["agent_id"])

    stored = client.store(
        agent_id=triage["agent_id"],
        content=(
            "EU billing retries fail after 30 seconds. "
            "Root cause points to connection pool exhaustion in payment-service."
        ),
        metadata={"ticket": "INC-2048", "workflow": "support"},
        evidence=["pagerduty:pd-2048"],
        citations=["ticket:INC-2048"],
        expires_in_days=14,
    )
    first_claim = stored["claims"][0]

    reviewed = client.review_claim(
        reviewer_agent_id=billing["agent_id"],
        claim_id=first_claim["claim_id"],
        decision="attested",
        reason="Confirmed from the incident timeline.",
    )
    hits = client.recall(agent_id=billing["agent_id"], query="EU billing retries")
    top_hit = hits[0]

    print("=== ContextGraph Beta Quickstart ===")
    print("1) Stored one governed memory")
    print(f"- memory_id: {stored['memory']['memory_id']}")
    print(f"- visibility: {first_claim['visibility']}")
    print(f"- validation_status: {first_claim['validation_status']}")
    print(f"- fresh_until: {first_claim['expires_at'].split('T')[0]}")
    print(f"- citation: {first_claim['citations'][0]}")
    print()
    print("2) Added a trust signal")
    print(f"- reviewed_by: {billing['name']}")
    print(f"- validation_status: {reviewed['validation_status']}")
    print(f"- provenance: {_provenance_actions(reviewed)}")
    print()
    print("3) Recalled it from another agent")
    print(f"- source_agent: {top_hit['source_agent_name']}")
    print(f"- statement: {top_hit['claim']['statement']}")
    print(f"- recall_visibility: {top_hit['claim']['visibility']}")
    print(f"- recall_status: {top_hit['claim']['validation_status']}")
    print(f"- memory_content: {top_hit['memory_content']}")
    print()
    print("Next step: python3 examples/support_memory_workflow.py")


if __name__ == "__main__":
    main()
