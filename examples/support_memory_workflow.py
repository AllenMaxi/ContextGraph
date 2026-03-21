from __future__ import annotations

from contextgraph_sdk import ContextGraph


def main() -> None:
    client = ContextGraph.local()

    triage = client.register_agent("support-triage", "acme", ["support", "triage"], default_visibility="org")
    billing = client.register_agent("billing-specialist", "acme", ["support", "billing"])
    status_page = client.register_agent("status-page-bot", "acme", ["ops", "status"])

    client.follow(billing["agent_id"], "agent", triage["agent_id"])
    client.follow(billing["agent_id"], "agent", status_page["agent_id"])

    incident = client.store(
        agent_id=triage["agent_id"],
        content=(
            "Customer support incident: EU billing retries fail after 30 seconds. "
            "Root cause points to connection pool exhaustion in payment-service."
        ),
        visibility="org",
        metadata={"ticket": "INC-2048", "workflow": "support"},
        evidence=["pagerduty:pd-2048"],
        citations=["ticket:INC-2048"],
    )
    client.store(
        agent_id=status_page["agent_id"],
        content="Status page updated: payment-service degraded in EU region.",
        visibility="org",
        metadata={"component": "payment-service", "region": "eu"},
    )

    feed = client.feed(billing["agent_id"])
    recall = client.recall(billing["agent_id"], "EU billing retries")
    trust = client.agent_trust(billing["agent_id"], triage["agent_id"])

    print("=== Support Workflow Demo ===")
    print(f"Incident memory: {incident['memory']['memory_id']}")
    print("Feed items:")
    for item in feed:
        statement = item["claims"][0]["statement"] if item.get("claims") else "<no claims>"
        print(f"- {item['source_agent_name']}: {statement}")
    print()
    print("Top recall result:")
    if recall:
        print(f"- {recall[0]['claim']['statement']}")
        print(f"- memory_content={recall[0]['memory_content']}")
    print()
    print("Triage trust snapshot:")
    print(f"- claims={trust['total_claims']}")
    print(f"- verdicts={trust['sentinel_verdict_count']}")
    print(f"- status={trust['status']}")


if __name__ == "__main__":
    main()
