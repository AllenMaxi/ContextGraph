"""Persistent identity store for ContextGraph World agents.

Keyed by ``agent_id``.  Once ``archetype`` and ``color_index`` are assigned
for a given ``agent_id`` they never change.  Rank and counters may update
on upgrade events.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import AgentArchetype, AgentRank

logger = logging.getLogger(__name__)


@dataclass
class IdentityRecord:
    agent_id: str
    name: str
    archetype: AgentArchetype
    rank: AgentRank
    color_index: int
    tools_count: int = 0
    skills_count: int = 0
    created_at: str = ""
    last_seen: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "archetype": self.archetype.value,
            "rank": self.rank.value,
            "color_index": self.color_index,
            "tools_count": self.tools_count,
            "skills_count": self.skills_count,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IdentityRecord":
        return cls(
            agent_id=d["agent_id"],
            name=d.get("name", d["agent_id"]),
            archetype=AgentArchetype(d.get("archetype", "unknown")),
            rank=AgentRank(d.get("rank", "novice")),
            color_index=int(d.get("color_index", 0)),
            tools_count=int(d.get("tools_count", 0)),
            skills_count=int(d.get("skills_count", 0)),
            created_at=d.get("created_at", ""),
            last_seen=d.get("last_seen", ""),
        )


class IdentityStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._records: dict[str, IdentityRecord] = {}

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("IdentityStore: failed to load %s: %s", self.path, exc)
            return
        for aid, raw in data.items():
            try:
                self._records[aid] = IdentityRecord.from_dict(raw)
            except (KeyError, ValueError) as exc:
                logger.warning("IdentityStore: skipping %s: %s", aid, exc)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {aid: rec.to_dict() for aid, rec in self._records.items()}
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".identities-", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(self, agent_id: str) -> IdentityRecord | None:
        return self._records.get(agent_id)

    def upsert(self, rec: IdentityRecord) -> IdentityRecord:
        existing = self._records.get(rec.agent_id)
        now = datetime.utcnow().isoformat()
        if existing is None:
            rec.created_at = rec.created_at or now
            rec.last_seen = now
            self._records[rec.agent_id] = rec
            return rec
        # Preserve archetype + color_index forever
        existing.name = rec.name or existing.name
        existing.rank = rec.rank
        existing.tools_count = rec.tools_count
        existing.skills_count = rec.skills_count
        existing.last_seen = now
        return existing

    def all(self) -> list[IdentityRecord]:
        return list(self._records.values())
