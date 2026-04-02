from __future__ import annotations

import unittest
from datetime import datetime

from contextgraph.graph.neo4j_repository import Neo4jRepository
from contextgraph.models import (
    Claim,
    ClaimImpact,
    CompactionCheckpoint,
    ContextPack,
    ContextPackClaim,
    ContextPackExplanation,
    ContextPackSource,
    DeliveryMode,
    DeltaPack,
    DeltaPackDiff,
    Memory,
    PatternFilter,
    ProvenanceEntry,
    Session,
    SessionEvent,
    SessionStateEntry,
    StandingQuery,
    Subscription,
    SubscriptionTarget,
    ValidationStatus,
    Visibility,
)


class Neo4jRepositoryRoundTripTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = object.__new__(Neo4jRepository)
        self.now = datetime(2026, 3, 31, 12, 0, 0)

    def test_memory_and_claim_round_trip_preserves_extended_fields(self) -> None:
        memory = Memory(
            memory_id="mem_1",
            agent_id="agt_1",
            content="API latency came from pool exhaustion.",
            visibility=Visibility.ORG,
            validation_status=ValidationStatus.ATTESTED,
            license="MIT",
            metadata={"ticket": "INC-123"},
            created_at=self.now,
            updated_at=self.now,
            access_list=["agt_1", "org_acme"],
            evidence=["incident review"],
            citations=["https://example.com/incidents/123"],
            source_type="incident_report",
            source_uri="https://example.com/incidents/123",
            source_label="INC-123",
            section_refs=["root-cause", "timeline"],
            ingest_metadata={"importer": "notion"},
        )
        claim = Claim(
            claim_id="clm_1",
            memory_id=memory.memory_id,
            source_agent_id=memory.agent_id,
            statement="Pool exhaustion caused the API latency spike.",
            claim_type="fact",
            relation_type=None,
            confidence=0.92,
            freshness_score=0.88,
            validation_status=ValidationStatus.ATTESTED,
            visibility=Visibility.ORG,
            license="MIT",
            entity_ids=["ent_1"],
            created_at=self.now,
            expires_at=None,
            updated_at=self.now,
            review_reasons=["confirmed by SRE"],
            source_org_id="acme",
            access_list=["agt_1", "org_acme"],
            evidence=["incident review"],
            citations=["https://example.com/incidents/123"],
            validated_at=self.now,
            provenance=[
                ProvenanceEntry(
                    agent_id="agt_reviewer",
                    action="attested",
                    timestamp=self.now,
                    confidence_at_action=0.92,
                    detail="confirmed by incident review",
                )
            ],
            derived_from=["clm_parent"],
            source_memory_section="root-cause",
            impact=ClaimImpact.HIGH,
            quorum_required=2,
            quorum_met=False,
            attestation_count=1,
            challenge_count=0,
        )

        serialized_memory = self.repo._serialize(memory)
        serialized_claim = self.repo._serialize(claim)
        round_trip_memory = self.repo._memory_from_node(serialized_memory)
        round_trip_claim = self.repo._claim_from_record({"c": serialized_claim, "entity_ids": ["ent_1"]})

        self.assertIsInstance(serialized_memory["metadata"], str)
        self.assertIsInstance(serialized_memory["ingest_metadata"], str)
        self.assertIsInstance(serialized_claim["provenance"], str)
        self.assertEqual(round_trip_memory.source_type, "incident_report")
        self.assertEqual(round_trip_memory.source_label, "INC-123")
        self.assertEqual(round_trip_memory.section_refs, ["root-cause", "timeline"])
        self.assertEqual(round_trip_memory.ingest_metadata["importer"], "notion")
        self.assertEqual(round_trip_claim.source_memory_section, "root-cause")
        self.assertEqual(round_trip_claim.impact, ClaimImpact.HIGH)
        self.assertEqual(round_trip_claim.quorum_required, 2)
        self.assertFalse(round_trip_claim.quorum_met)
        self.assertEqual(round_trip_claim.derived_from, ["clm_parent"])
        self.assertEqual(round_trip_claim.provenance[0].detail, "confirmed by incident review")

    def test_context_pack_round_trip_preserves_nested_fields(self) -> None:
        pack = ContextPack(
            pack_id="cpk_1",
            agent_id="agt_1",
            query="payment outage",
            included_claims=[
                ContextPackClaim(
                    claim_id="clm_1",
                    statement="Pool exhaustion caused the outage.",
                    source_memory_id="mem_1",
                    source_agent_id="agt_1",
                    confidence=0.91,
                    freshness_score=0.87,
                    validation_status="attested",
                    score=2.4,
                    source_memory_section="root-cause",
                    source_label="INC-123",
                    visibility=Visibility.ORG.value,
                    staleness_warning="Verify against the latest incident review.",
                )
            ],
            sources=[
                ContextPackSource(
                    memory_id="mem_1",
                    agent_id="agt_1",
                    source_type="incident_report",
                    source_label="INC-123",
                    source_uri="https://example.com/incidents/123",
                    claim_count=1,
                )
            ],
            token_budget=1200,
            tokens_used=280,
            generated_at=self.now,
            summary="One confirmed claim included.",
            session_id="ses_1",
            base_pack_id="cpk_base",
            delta_from_pack_id="dpk_1",
            checkpoint_reason="context_pressure",
            restoration_prompt="Resume from the payment outage checkpoint.",
            restoration_instructions=["Re-check the root cause before editing more files."],
            excluded_claims=[
                ContextPackClaim(
                    claim_id="clm_2",
                    statement="",
                    source_memory_id="mem_2",
                    source_agent_id="agt_2",
                    confidence=0.5,
                    freshness_score=0.4,
                    validation_status="unreviewed",
                    score=0.7,
                    visibility=Visibility.PUBLISHED.value,
                    locked=True,
                )
            ],
            conflicting_claims=[],
            explanation=ContextPackExplanation(
                included_reasons={"clm_1": ["fresh", "reviewed"]},
                excluded_reasons={"clm_2": ["paid claim"]},
                conflict_pairs=[("clm_1", "clm_3")],
                filter_counts={"priced": 1},
            ),
        )

        serialized = self.repo._serialize(pack)
        round_trip = self.repo._context_pack_from_node(serialized)

        self.assertIsInstance(serialized["included_claims"], str)
        self.assertIsInstance(serialized["explanation"], str)
        self.assertEqual(round_trip.session_id, "ses_1")
        self.assertEqual(round_trip.base_pack_id, "cpk_base")
        self.assertEqual(round_trip.delta_from_pack_id, "dpk_1")
        self.assertEqual(round_trip.sources[0].source_uri, "https://example.com/incidents/123")
        self.assertTrue(round_trip.excluded_claims[0].locked)
        self.assertEqual(round_trip.included_claims[0].visibility, Visibility.ORG.value)
        self.assertEqual(
            round_trip.included_claims[0].staleness_warning,
            "Verify against the latest incident review.",
        )
        self.assertEqual(round_trip.excluded_claims[0].visibility, Visibility.PUBLISHED.value)
        self.assertEqual(round_trip.explanation.conflict_pairs, [("clm_1", "clm_3")])

    def test_session_delta_and_subscription_round_trip(self) -> None:
        session = Session(
            session_id="ses_1",
            agent_id="agt_1",
            title="Payments refactor",
            source="claude-code",
            status="active",
            metadata={"workspace": "/tmp/project"},
            created_at=self.now,
            updated_at=self.now,
            parent_session_id="ses_parent",
            forked_from_checkpoint_id="chk_parent",
            latest_checkpoint_id="chk_1",
            latest_delta_pack_id="dpk_1",
            checkpoint_count=2,
            event_count=9,
        )
        event = SessionEvent(
            event_id="evt_1",
            session_id="ses_1",
            agent_id="agt_1",
            event_type="context_pressure",
            content="Only 10 percent remains.",
            created_at=self.now,
            metadata={"context_remaining_pct": "10"},
            sequence=9,
            important=True,
        )
        delta = DeltaPack(
            delta_pack_id="dpk_1",
            checkpoint_id="chk_1",
            session_id="ses_1",
            agent_id="agt_1",
            sequence=2,
            checkpoint_reason="context_pressure",
            generated_at=self.now,
            token_budget=800,
            tokens_used=220,
            summary="Resume from the latest checkpoint.",
            base_pack_id="dpk_base",
            delta_from_pack_id="dpk_0",
            decisions=["Keep the public API stable."],
            constraints=["Do not break SDK compatibility."],
            open_tasks=["Ship resume hooks."],
            failures=["pytest is failing on the context pack suite."],
            changed_files=["contextgraph/service.py"],
            commands=["pytest -q"],
            notes=["Need to checkpoint before more edits."],
            stale_items=["Old TODO"],
            untrusted_items=["Third-party benchmark"],
            dropped_items=["Obsolete task"],
            restoration_prompt="Restore the session state before editing.",
            restoration_instructions=["Start with the changed files."],
            included_event_ids=["evt_1"],
            event_count=9,
            cache_status="prefix_hit",
            cache_base_checkpoint_id="chk_parent",
            reused_event_count=8,
            recomputed_event_count=1,
            invalidated_reasons=["snapshot_version_mismatch"],
            state_snapshot={
                "decisions": [SessionStateEntry(value="Keep the public API stable.", observed_at=self.now)],
                "open_tasks": [SessionStateEntry(value="Ship resume hooks.", observed_at=self.now)],
                "untrusted_items": [SessionStateEntry(value="Third-party benchmark", observed_at=self.now)],
            },
            state_snapshot_version="rdc_state_v1",
            state_snapshot_event_count=9,
            diff=DeltaPackDiff(
                added={"open_tasks": ["Ship resume hooks."]},
                dropped={"resolved_items": ["Old TODO"]},
            ),
        )
        checkpoint = CompactionCheckpoint(
            checkpoint_id="chk_1",
            session_id="ses_1",
            agent_id="agt_1",
            sequence=2,
            reason="context_pressure",
            created_at=self.now,
            delta_pack_id="dpk_1",
            base_checkpoint_id="chk_0",
            event_count=9,
            restoration_prompt="Restore the session state before editing.",
            restoration_instructions=["Start with the changed files."],
            summary="Resume from the latest checkpoint.",
        )
        query = StandingQuery(
            query_id="qry_1",
            agent_id="agt_1",
            name="watch incidents",
            query="payment outage",
            filters={"visibility": "org"},
            delivery_mode=DeliveryMode.PULL,
            status="active",
            created_at=self.now,
            updated_at=self.now,
            pattern=PatternFilter(entities=["payment"], min_confidence=0.7),
        )
        subscription = Subscription(
            subscription_id="sub_1",
            follower_agent_id="agt_1",
            target_type=SubscriptionTarget.AGENT,
            target_id="agt_2",
            created_at=self.now,
            active=True,
        )

        session_round_trip = self.repo._session_from_node(self.repo._serialize(session))
        event_round_trip = self.repo._session_event_from_node(self.repo._serialize(event))
        delta_round_trip = self.repo._delta_pack_from_node(self.repo._serialize(delta))
        checkpoint_round_trip = self.repo._compaction_checkpoint_from_node(self.repo._serialize(checkpoint))
        query_round_trip = self.repo._query_from_node(self.repo._serialize(query))
        subscription_round_trip = self.repo._subscription_from_node(self.repo._serialize(subscription))

        self.assertEqual(session_round_trip.metadata["workspace"], "/tmp/project")
        self.assertEqual(session_round_trip.parent_session_id, "ses_parent")
        self.assertEqual(session_round_trip.forked_from_checkpoint_id, "chk_parent")
        self.assertEqual(event_round_trip.metadata["context_remaining_pct"], "10")
        self.assertEqual(delta_round_trip.diff.added["open_tasks"], ["Ship resume hooks."])
        self.assertEqual(delta_round_trip.cache_status, "prefix_hit")
        self.assertEqual(delta_round_trip.cache_base_checkpoint_id, "chk_parent")
        self.assertEqual(delta_round_trip.reused_event_count, 8)
        self.assertEqual(delta_round_trip.recomputed_event_count, 1)
        self.assertEqual(delta_round_trip.invalidated_reasons, ["snapshot_version_mismatch"])
        self.assertEqual(delta_round_trip.state_snapshot_version, "rdc_state_v1")
        self.assertEqual(delta_round_trip.state_snapshot_event_count, 9)
        self.assertEqual(delta_round_trip.state_snapshot["decisions"][0].value, "Keep the public API stable.")
        self.assertEqual(checkpoint_round_trip.base_checkpoint_id, "chk_0")
        self.assertIsNotNone(query_round_trip.pattern)
        self.assertEqual(query_round_trip.pattern.entities, ["payment"])
        self.assertEqual(subscription_round_trip.target_type, SubscriptionTarget.AGENT)


if __name__ == "__main__":
    unittest.main()
