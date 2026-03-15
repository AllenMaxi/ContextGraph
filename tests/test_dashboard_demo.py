from __future__ import annotations

import unittest

from contextgraph.config import Settings
from contextgraph.demo import seed_dashboard_demo
from contextgraph.service import ContextGraphService


class DashboardDemoSeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ContextGraphService(
            app_settings=Settings(enable_payments=True, enable_claim_expiry_sweeps=False)
        )

    def tearDown(self) -> None:
        self.service.close()

    def test_seed_creates_internal_shared_and_locked_feed_items(self) -> None:
        demo = seed_dashboard_demo(self.service)

        procurement_feed = self.service.get_feed(demo.procurement_agent_id)
        globex_feed = self.service.get_feed(demo.globex_agent_id)
        procurement_following = self.service.list_following(demo.procurement_agent_id)
        globex_following = self.service.list_following(demo.globex_agent_id)

        self.assertGreaterEqual(len(procurement_feed), 2)
        self.assertGreaterEqual(len(globex_feed), 3)
        self.assertTrue(any(item["source_org_id"] == "acme" and item["memory_content"] for item in procurement_feed))
        self.assertTrue(
            any(
                item["visibility"] == "shared"
                and item["source_org_id"] == "acme"
                and not item["is_locked"]
                and item["memory_content"]
                for item in globex_feed
            )
        )
        self.assertTrue(any(item["is_locked"] and item["memory_content"] == "" for item in globex_feed))
        self.assertEqual({sub.target_type.value for sub in procurement_following}, {"agent", "org"})
        self.assertEqual({sub.target_type.value for sub in globex_following}, {"agent", "topic"})
        self.assertTrue(demo.recording_steps)


if __name__ == "__main__":
    unittest.main()
