"""Tests for agent identity, archetype, rank assignment."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from contextgraph.world.models import (
    AgentArchetype,
    AgentRank,
    AgentVisual,
    GameEventType,
    rank_for_counts,
)


# ── Task 1: AgentArchetype ───────────────────────────────────────────

def test_archetype_enum_values():
    assert AgentArchetype.ARCHMAGE == "archmage"
    assert AgentArchetype.SCOUT == "scout"
    assert AgentArchetype.ORACLE == "oracle"
    assert AgentArchetype.SCRIBE == "scribe"
    assert AgentArchetype.APPRENTICE == "apprentice"
    assert AgentArchetype.ARTIFICER == "artificer"
    assert AgentArchetype.SAGE == "sage"
    assert AgentArchetype.USER == "user"
    assert AgentArchetype.UNKNOWN == "unknown"


def test_archetype_count():
    assert len(AgentArchetype) == 9


# ── Task 2: AgentRank + rank_for_counts ──────────────────────────────

def test_rank_enum_values():
    assert AgentRank.NOVICE == "novice"
    assert AgentRank.ADEPT == "adept"
    assert AgentRank.MAGE == "mage"
    assert AgentRank.HIGH_MAGE == "high_mage"
    assert AgentRank.AVATAR == "avatar"


@pytest.mark.parametrize("total,expected", [
    (0, AgentRank.NOVICE),
    (5, AgentRank.NOVICE),
    (6, AgentRank.ADEPT),
    (15, AgentRank.ADEPT),
    (16, AgentRank.MAGE),
    (30, AgentRank.MAGE),
    (31, AgentRank.HIGH_MAGE),
    (60, AgentRank.HIGH_MAGE),
    (61, AgentRank.AVATAR),
    (999, AgentRank.AVATAR),
])
def test_rank_for_counts(total, expected):
    tools = total // 2
    skills = total - tools
    assert rank_for_counts(tools, skills) == expected


# ── Task 3: AgentVisual identity fields ──────────────────────────────

def test_agent_visual_identity_fields_default():
    v = AgentVisual(agent_id="claude", name="Claude", color_index=0)
    assert v.archetype == AgentArchetype.UNKNOWN
    assert v.rank == AgentRank.NOVICE
    assert v.parent_agent_id is None
    assert v.tools_count == 0
    assert v.skills_count == 0


def test_agent_visual_to_dict_includes_identity():
    v = AgentVisual(
        agent_id="claude.Explore.1",
        name="Scout",
        color_index=2,
        archetype=AgentArchetype.SCOUT,
        rank=AgentRank.ADEPT,
        parent_agent_id="claude",
        tools_count=8,
        skills_count=4,
    )
    d = v.to_dict()
    assert d["archetype"] == "scout"
    assert d["rank"] == "adept"
    assert d["parent_agent_id"] == "claude"
    assert d["tools_count"] == 8
    assert d["skills_count"] == 4


# ── Task 4: New event types ──────────────────────────────────────────

def test_new_event_types():
    assert GameEventType.AGENT_UPGRADE == "agent_upgrade"
    assert GameEventType.HANDOFF_ORB == "handoff_orb"
