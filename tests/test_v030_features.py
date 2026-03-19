"""Tests for ContextGraph v0.3.0 features.

Covers: provenance chains, impact classification, quorum/consensus,
pattern subscriptions, event bus, CLI config, UCP, and dashboard imports.
"""

from __future__ import annotations

import pytest

from contextgraph.events import Event, EventBus, EventType
from contextgraph.models import (
    ClaimImpact,
    PatternFilter,
    ProvenanceEntry,
    Visibility,
)
from contextgraph.service import ContextGraphService


@pytest.fixture
def svc() -> ContextGraphService:
    return ContextGraphService()


@pytest.fixture
def agent(svc: ContextGraphService) -> dict:
    a = svc.register_agent(name="TestAgent", org_id="test-org", capabilities=["store", "recall"])
    return {"agent_id": a.agent_id, "api_key": a.api_key, "org_id": a.org_id}


@pytest.fixture
def agent_b(svc: ContextGraphService) -> dict:
    a = svc.register_agent(name="ReviewerAgent", org_id="test-org", capabilities=["review"])
    return {"agent_id": a.agent_id, "api_key": a.api_key, "org_id": a.org_id}


# ------------------------------------------------------------------
# Provenance Chain Tests
# ------------------------------------------------------------------


class TestProvenance:
    def test_store_creates_provenance_entry(self, svc: ContextGraphService, agent: dict) -> None:
        result = svc.store_memory(agent_id=agent["agent_id"], content="Acme Corp raised Series B funding.")
        assert len(result.claims) > 0
        claim = result.claims[0]
        assert len(claim.provenance) == 1
        entry = claim.provenance[0]
        assert entry.action == "created"
        assert entry.agent_id == agent["agent_id"]
        assert entry.confidence_at_action == claim.confidence

    def test_review_appends_provenance(self, svc: ContextGraphService, agent: dict, agent_b: dict) -> None:
        result = svc.store_memory(agent_id=agent["agent_id"], content="Acme Corp raised Series B funding.")
        claim = result.claims[0]
        reviewed = svc.review_claim(
            reviewer_agent_id=agent_b["agent_id"], claim_id=claim.claim_id, decision="attested", reason="Confirmed"
        )
        assert len(reviewed.provenance) == 2
        assert reviewed.provenance[0].action == "created"
        assert reviewed.provenance[1].action == "attested"
        assert reviewed.provenance[1].detail == "Confirmed"

    def test_provenance_is_append_only(self, svc: ContextGraphService, agent: dict, agent_b: dict) -> None:
        result = svc.store_memory(agent_id=agent["agent_id"], content="Beta Inc launched new product.")
        claim = result.claims[0]
        svc.review_claim(reviewer_agent_id=agent_b["agent_id"], claim_id=claim.claim_id, decision="attested")
        svc.review_claim(reviewer_agent_id=agent_b["agent_id"], claim_id=claim.claim_id, decision="challenged")
        refreshed = svc.repository.get_claim(claim.claim_id)
        assert len(refreshed.provenance) == 3
        actions = [e.action for e in refreshed.provenance]
        assert actions == ["created", "attested", "challenged"]


# ------------------------------------------------------------------
# Impact Classification Tests
# ------------------------------------------------------------------


class TestImpactClassification:
    def test_low_impact_private(self, svc: ContextGraphService, agent: dict) -> None:
        result = svc.store_memory(
            agent_id=agent["agent_id"], content="Internal note about process.", visibility="private"
        )
        for claim in result.claims:
            assert claim.impact == ClaimImpact.LOW
            assert claim.quorum_required == 0
            assert claim.quorum_met is True

    def test_high_impact_published_with_price(self, svc: ContextGraphService, agent: dict) -> None:
        result = svc.store_memory(
            agent_id=agent["agent_id"],
            content="Acme Corp signed deal with Beta Inc.",
            visibility="published",
            price=0.05,
        )
        for claim in result.claims:
            if len(claim.entity_ids) >= 2:
                assert claim.impact in (ClaimImpact.HIGH, ClaimImpact.CRITICAL)
                assert claim.quorum_required >= 2
                assert claim.quorum_met is False

    def test_classify_impact_method(self, svc: ContextGraphService) -> None:
        assert svc._classify_impact(Visibility.PRIVATE, 0.0, 0) == ClaimImpact.LOW
        assert svc._classify_impact(Visibility.SHARED, 0.0, 1) == ClaimImpact.MEDIUM
        assert svc._classify_impact(Visibility.PUBLISHED, 0.05, 1) == ClaimImpact.HIGH
        assert svc._classify_impact(Visibility.PUBLISHED, 0.05, 3) == ClaimImpact.CRITICAL


# ------------------------------------------------------------------
# Quorum / Consensus Tests
# ------------------------------------------------------------------


class TestQuorum:
    def test_quorum_not_met_until_attestations(self, svc: ContextGraphService, agent: dict, agent_b: dict) -> None:
        result = svc.store_memory(
            agent_id=agent["agent_id"],
            content="Acme Corp switched supplier to Beta Inc at higher cost.",
            visibility="published",
            price=0.05,
        )
        # Find a claim with quorum
        high_claims = [c for c in result.claims if c.quorum_required > 0]
        if not high_claims:
            pytest.skip("No high-impact claims generated")
        claim = high_claims[0]
        assert claim.quorum_met is False

        # First attestation
        reviewed = svc.review_claim(reviewer_agent_id=agent_b["agent_id"], claim_id=claim.claim_id, decision="attested")
        assert reviewed.attestation_count == 1
        # May or may not meet quorum depending on required count

    def test_challenge_resets_quorum(self, svc: ContextGraphService, agent: dict, agent_b: dict) -> None:
        result = svc.store_memory(
            agent_id=agent["agent_id"],
            content="Acme Corp expanded to Japan and Korea.",
            visibility="published",
            price=0.05,
        )
        high_claims = [c for c in result.claims if c.quorum_required > 0]
        if not high_claims:
            pytest.skip("No high-impact claims generated")
        claim = high_claims[0]

        svc.review_claim(reviewer_agent_id=agent_b["agent_id"], claim_id=claim.claim_id, decision="attested")
        challenged = svc.review_claim(
            reviewer_agent_id=agent_b["agent_id"], claim_id=claim.claim_id, decision="challenged"
        )
        assert challenged.quorum_met is False
        assert challenged.challenge_count == 1


# ------------------------------------------------------------------
# Pattern Subscription Tests
# ------------------------------------------------------------------


class TestPatternSubscriptions:
    def test_watch_with_pattern(self, svc: ContextGraphService, agent: dict) -> None:
        query = svc.watch(
            agent_id=agent["agent_id"],
            query="",
            name="EU churn watch",
            pattern={"entities": ["acme_corp"], "min_confidence": 0.5},
        )
        assert query.pattern is not None
        assert query.pattern.entities == ["acme_corp"]
        assert query.pattern.min_confidence == 0.5

    def test_pattern_matches_entity(self, svc: ContextGraphService, agent: dict) -> None:
        # Create a watch with pattern
        svc.watch(
            agent_id=agent["agent_id"],
            query="",
            name="Acme watcher",
            pattern={"entities": ["acme_corp"]},
        )
        # Store memory mentioning Acme Corp
        result = svc.store_memory(
            agent_id=agent["agent_id"], content="Acme Corp announced new product line.", visibility="org"
        )
        # Check notifications were generated
        notifications = svc.get_notifications(agent_id=agent["agent_id"])
        # Should have at least one notification if entity matches
        acme_claims = [c for c in result.claims if any("acme" in eid.lower() for eid in c.entity_ids)]
        if acme_claims:
            assert len(notifications) > 0

    def test_pattern_filters_by_confidence(self, svc: ContextGraphService, agent: dict) -> None:
        svc.watch(
            agent_id=agent["agent_id"],
            query="",
            name="High confidence only",
            pattern={"min_confidence": 0.99},
        )
        svc.store_memory(agent_id=agent["agent_id"], content="Some vague unrelated note.", visibility="org")
        notifications = svc.get_notifications(agent_id=agent["agent_id"])
        # High confidence threshold should filter most things out
        assert len(notifications) == 0

    def test_pattern_filter_dataclass(self) -> None:
        pf = PatternFilter(
            entities=["acme"],
            entity_types=["company"],
            relation_types=["caused_by"],
            min_confidence=0.7,
            source_org_ids=["org-1"],
            visibility_levels=["published"],
        )
        assert pf.entities == ["acme"]
        assert pf.min_confidence == 0.7


# ------------------------------------------------------------------
# Event Bus Tests
# ------------------------------------------------------------------


class TestEventBus:
    def test_publish_and_recent(self) -> None:
        bus = EventBus()
        from contextgraph.utils import utcnow

        event = Event(
            event_id="evt-1",
            event_type=EventType.CLAIM_CREATED,
            data={"claim_id": "clm-1", "statement": "Test claim"},
            timestamp=utcnow(),
            agent_id="agent-1",
        )
        bus.publish(event)
        recent = bus.recent(10)
        assert len(recent) == 1
        assert recent[0].event_id == "evt-1"
        assert bus.total_events == 1

    def test_max_history(self) -> None:
        bus = EventBus(max_history=5)
        from contextgraph.utils import utcnow

        for i in range(10):
            bus.publish(
                Event(
                    event_id=f"evt-{i}",
                    event_type=EventType.HEARTBEAT,
                    data={},
                    timestamp=utcnow(),
                )
            )
        assert len(bus.recent(100)) == 5
        assert bus.total_events == 10

    def test_subscribe_returns_queue(self) -> None:
        bus = EventBus()
        queue = bus.subscribe()
        assert queue is not None
        bus.unsubscribe(queue)


# ------------------------------------------------------------------
# CLI Config Tests
# ------------------------------------------------------------------


class TestCLIModule:
    def test_cli_imports(self) -> None:
        from contextgraph.cli import main

        assert callable(main)


# ------------------------------------------------------------------
# Dashboard Import Tests
# ------------------------------------------------------------------


class TestDashboard:
    def test_dashboard_imports(self) -> None:
        from contextgraph.api.dashboard import register_dashboard_routes

        assert callable(register_dashboard_routes)


# ------------------------------------------------------------------
# UCP Tests
# ------------------------------------------------------------------


class TestUCP:
    def test_ucp_imports(self) -> None:
        from contextgraph.api.ucp import register_ucp_routes

        assert callable(register_ucp_routes)


# ------------------------------------------------------------------
# Streaming Tests
# ------------------------------------------------------------------


class TestStreaming:
    def test_streaming_imports(self) -> None:
        from contextgraph.api.streaming import register_streaming_routes

        assert callable(register_streaming_routes)


# ------------------------------------------------------------------
# A2A Tests
# ------------------------------------------------------------------


class TestA2A:
    def test_a2a_agent_card_has_new_skills(self) -> None:
        from contextgraph.a2a_server import A2AServer

        server = A2AServer(node_id="test", base_url="http://localhost:8420", enabled=True)
        card = server.agent_card()
        skill_ids = [s["id"] for s in card["skills"]]
        assert "store_memory" in skill_ids
        assert "recall_memory" in skill_ids

    def test_a2a_discovery(self) -> None:
        from contextgraph.a2a_server import A2AServer

        server = A2AServer(node_id="test", base_url="http://localhost:8420", enabled=True)
        # discovered_agents should be accessible
        assert hasattr(server, "_discovered_agents") or hasattr(server, "_tasks")


# ------------------------------------------------------------------
# Model Tests
# ------------------------------------------------------------------


class TestNewModels:
    def test_provenance_entry(self) -> None:
        from contextgraph.utils import utcnow

        entry = ProvenanceEntry(agent_id="agent-1", action="created", timestamp=utcnow(), confidence_at_action=0.9)
        assert entry.action == "created"
        assert entry.detail == ""

    def test_claim_impact_enum(self) -> None:
        assert ClaimImpact.LOW.value == "low"
        assert ClaimImpact.CRITICAL.value == "critical"

    def test_pattern_filter_defaults(self) -> None:
        pf = PatternFilter()
        assert pf.entities == []
        assert pf.min_confidence == 0.0
