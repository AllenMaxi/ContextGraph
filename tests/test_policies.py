from __future__ import annotations

import unittest

from contextgraph import ContextGraphService
from sdk.contextgraph_sdk import (
    ContextGraph,
    MemoryContext,
    MemoryPolicyHelper,
    SubscriptionContext,
    SubscriptionPolicyManager,
)


class ContextGraphPoliciesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService()
        self.client = ContextGraph.local(self.service)
        self.agent = self.client.register_agent("policy-agent", "alpha", ["support"])

    def tearDown(self) -> None:
        self.service.close()

    def test_memory_policy_stores_important_shared_memory(self) -> None:
        helper = MemoryPolicyHelper(self.client)

        outcome = helper.store_if_important(
            agent_id=self.agent["agent_id"],
            content="Acme Corp reported critical API latency and requested a fix today.",
            context=MemoryContext(
                workflow="support",
                task_id="ticket-123",
                task_type="incident",
                entity_names=["Acme Corp"],
                severity="critical",
                source="zendesk",
                shared_across_org=True,
                share_targets=["partner-org"],
            ),
            asynchronous=False,
        )

        self.assertTrue(outcome.decision.should_store)
        self.assertEqual(outcome.decision.visibility, "shared")
        self.assertIsNotNone(outcome.result)
        self.assertIn("memory_policy_score", outcome.decision.metadata)
        claims = self.client.claims(self.agent["agent_id"])
        self.assertGreaterEqual(len(claims), 1)
        self.assertEqual(outcome.result["memory"]["access_list"], ["partner-org"])

    def test_memory_policy_skips_duplicate_claims(self) -> None:
        helper = MemoryPolicyHelper(self.client)
        first = helper.store_if_important(
            agent_id=self.agent["agent_id"],
            content="Vendor X expanded into Germany.",
            context=MemoryContext(task_type="research"),
        )
        second = helper.store_if_important(
            agent_id=self.agent["agent_id"],
            content="Vendor X expanded into Germany.",
            context=MemoryContext(task_type="research"),
        )

        self.assertTrue(first.decision.should_store)
        self.assertFalse(second.decision.should_store)
        self.assertIn("duplicate_claim", second.decision.reasons)
        self.assertIsNotNone(second.decision.duplicate_claim_id)

    def test_memory_policy_refuses_shared_without_targets(self) -> None:
        helper = MemoryPolicyHelper(self.client)

        outcome = helper.store_if_important(
            agent_id=self.agent["agent_id"],
            content="Acme Corp reported critical API latency and requested a fix today.",
            context=MemoryContext(
                workflow="support",
                task_type="incident",
                entity_names=["Acme Corp"],
                severity="critical",
            ),
            visibility="shared",
        )

        self.assertFalse(outcome.decision.should_store)
        self.assertIn("missing_share_targets", outcome.decision.reasons)
        self.assertIsNone(outcome.result)

    def test_memory_policy_defaults_sensitive_content_to_private(self) -> None:
        helper = MemoryPolicyHelper(self.client)

        decision = helper.evaluate(
            agent_id=self.agent["agent_id"],
            content="Customer password reset token leaked in the log.",
            context=MemoryContext(task_type="support"),
        )

        self.assertEqual(decision.visibility, "private")

    def test_subscription_manager_creates_and_reuses_task_subscriptions(self) -> None:
        manager = SubscriptionPolicyManager(self.client)
        context = SubscriptionContext(
            task_id="renewal-42",
            title="Acme renewal",
            task_type="renewal",
            entity_names=["Acme"],
            topics=["pricing"],
            delivery_mode="pull",
        )

        first = manager.ensure_task_subscriptions(self.agent["agent_id"], context)
        second = manager.ensure_task_subscriptions(self.agent["agent_id"], context)

        self.assertGreaterEqual(len(first), 1)
        self.assertTrue(any(plan.created for plan in first))
        self.assertTrue(all(not plan.created for plan in second))
        active_watches = self.client.watches(self.agent["agent_id"])
        self.assertEqual(len(active_watches), len(first))

    def test_subscription_manager_can_deactivate_task_subscriptions(self) -> None:
        manager = SubscriptionPolicyManager(self.client)
        context = SubscriptionContext(
            task_id="incident-7",
            title="Acme outage",
            task_type="incident",
            entity_names=["Acme"],
            delivery_mode="pull",
        )
        manager.ensure_task_subscriptions(self.agent["agent_id"], context)

        deactivated = manager.deactivate_task_subscriptions(self.agent["agent_id"], "incident-7")
        active_watches = self.client.watches(self.agent["agent_id"])
        all_watches = self.client.watches(self.agent["agent_id"], include_inactive=True)

        self.assertGreaterEqual(len(deactivated), 1)
        self.assertEqual(active_watches, [])
        self.assertTrue(all(watch["status"] == "inactive" for watch in all_watches))


if __name__ == "__main__":
    unittest.main()
