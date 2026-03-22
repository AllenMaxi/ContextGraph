from __future__ import annotations

import os

os.environ.setdefault("CG_ENABLE_PAYMENTS", "true")

from contextgraph_sdk import ContextGraph


def _first_item(
    items: list[dict[str, object]], *, visibility: str | None = None, locked: bool | None = None
) -> dict[str, object]:
    for item in items:
        visibility_match = visibility is None or item["visibility"] == visibility
        locked_match = locked is None or item["is_locked"] is locked
        if visibility_match and locked_match:
            return item
    raise RuntimeError("Expected feed item was not found.")


def _provenance_actions(claim: dict[str, object]) -> str:
    return " -> ".join(entry["action"] for entry in claim["provenance"])


def main() -> None:
    client = ContextGraph.local()

    triage = client.register_agent("support-triage", "acme", ["support", "triage"], default_visibility="org")
    billing = client.register_agent("billing-specialist", "acme", ["support", "billing"])
    partner = client.register_agent("globex-oncall", "globex", ["support", "incident"])
    competitor = client.register_agent("external-analyst", "initech", ["analysis"])

    for follower in (billing, partner, competitor):
        client.follow(follower["agent_id"], "agent", triage["agent_id"])

    incident = client.store(
        agent_id=triage["agent_id"],
        content=(
            "EU billing retries fail after 30 seconds. "
            "Root cause points to connection pool exhaustion in payment-service."
        ),
        visibility="org",
        metadata={"ticket": "INC-2048", "workflow": "support"},
        evidence=["pagerduty:pd-2048"],
        citations=["ticket:INC-2048"],
        expires_in_days=14,
    )
    shared = client.store(
        agent_id=triage["agent_id"],
        content="Partner handoff for Globex: raise pool size to 50 and recycle idle workers after deploy.",
        visibility="shared",
        access_list=["globex"],
        metadata={"ticket": "INC-2048", "workflow": "partner-handoff"},
        citations=["ticket:INC-2048"],
        expires_in_days=7,
    )
    client.store(
        agent_id=triage["agent_id"],
        content="Published incident postmortem with step-by-step remediation checklist.",
        visibility="published",
        price=0.002,
        metadata={"ticket": "INC-2048", "workflow": "postmortem"},
        citations=["ticket:INC-2048"],
    )

    reviewed = client.review_claim(
        reviewer_agent_id=billing["agent_id"],
        claim_id=incident["claims"][0]["claim_id"],
        decision="attested",
        reason="Confirmed from the incident timeline.",
    )
    billing_recall = client.recall(billing["agent_id"], "EU billing retries")
    partner_feed = client.feed(partner["agent_id"])
    competitor_feed = client.feed(competitor["agent_id"])

    shared_item = _first_item(partner_feed, visibility="shared", locked=False)
    locked_item = _first_item(competitor_feed, visibility="published", locked=True)
    shared_claim = shared["claims"][0]
    top_hit = billing_recall[0]

    print("=== Support Workflow Demo ===")
    print("1) Internal incident memory becomes trustworthy")
    print(f"- memory_id: {incident['memory']['memory_id']}")
    print(f"- statement: {reviewed['statement']}")
    print(f"- visibility: {reviewed['visibility']}")
    print(f"- validation_status: {reviewed['validation_status']}")
    print(f"- provenance: {_provenance_actions(reviewed)}")
    print(f"- fresh_until: {reviewed['expires_at'].split('T')[0]}")
    print()
    print("2) Partner handoff stays governed")
    print(f"- partner_agent: {partner['name']}")
    print(f"- shared_visibility: {shared_claim['visibility']}")
    print(f"- partner_feed_locked: {shared_item['is_locked']}")
    print(f"- partner_memory_content: {shared_item['memory_content']}")
    print()
    print("3) Published paid knowledge stays locked cross-org")
    print(f"- external_agent: {competitor['name']}")
    print(f"- locked_visibility: {locked_item['visibility']}")
    print(f"- locked: {locked_item['is_locked']}")
    print(f"- price: {locked_item['price']}")
    print()
    print("4) Billing recall uses the reviewed memory")
    print(f"- source_agent: {top_hit['source_agent_name']}")
    print(f"- recall_status: {top_hit['claim']['validation_status']}")
    print(f"- recall_visibility: {top_hit['claim']['visibility']}")
    print(f"- citation: {top_hit['claim']['citations'][0]}")
    print(f"- memory_content: {top_hit['memory_content']}")


if __name__ == "__main__":
    main()
