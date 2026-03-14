from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .evaluation import ExpectedClaim
from .extraction import Extractor


@dataclass(slots=True)
class AgentTraceRecord:
    case_id: str
    name: str
    content: str
    expected_claims: list[ExpectedClaim] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


def load_agent_trace_records(path: str | Path) -> list[AgentTraceRecord]:
    source = Path(path)
    if source.suffix == ".jsonl":
        payload = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Agent trace source must contain a list of records.")
    return [_parse_trace_record(item, index=index) for index, item in enumerate(payload, start=1)]


def build_evaluation_cases_from_traces(
    records: list[AgentTraceRecord],
    extractor: Extractor,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for record in records:
        expected_claims = record.expected_claims or _draft_expected_claims(record.content, extractor)
        metadata = dict(record.metadata)
        metadata.setdefault("review_status", "provided" if record.expected_claims else "draft")
        metadata.setdefault("draft_generated", "false" if record.expected_claims else "true")
        cases.append(
            {
                "case_id": record.case_id,
                "name": record.name,
                "content": record.content,
                "expected_claims": [
                    {
                        "statement": claim.statement,
                        "entities": list(claim.entities),
                        "relation_type": claim.relation_type,
                        "claim_type": claim.claim_type,
                    }
                    for claim in expected_claims
                ],
                "tags": list(record.tags),
                "metadata": metadata,
            }
        )
    return cases


def write_evaluation_cases(path: str | Path, cases: list[dict[str, Any]]) -> Path:
    target = Path(path)
    target.write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    return target


def _parse_trace_record(payload: Any, *, index: int) -> AgentTraceRecord:
    if not isinstance(payload, dict):
        raise ValueError("Each agent trace record must be an object.")
    case_id = str(payload.get("case_id") or payload.get("trace_id") or payload.get("id") or f"trace-{index}")
    name = str(payload.get("name") or payload.get("title") or payload.get("summary") or case_id)
    content = payload.get("content") or payload.get("text") or payload.get("memory") or payload.get("message")
    if not content:
        raise ValueError(f"Trace record '{case_id}' is missing content/text/memory/message.")
    expected_claims_raw = payload.get("expected_claims", [])
    if not isinstance(expected_claims_raw, list):
        raise ValueError(f"Trace record '{case_id}' has invalid expected_claims.")
    expected_claims = [
        ExpectedClaim(
            statement=str(item["statement"]),
            entities=[str(entity) for entity in item.get("entities", [])],
            relation_type=str(item["relation_type"]) if item.get("relation_type") is not None else None,
            claim_type=str(item["claim_type"]) if item.get("claim_type") is not None else None,
        )
        for item in expected_claims_raw
    ]
    tags = [str(tag) for tag in payload.get("tags", [])]
    metadata = {
        key: str(value)
        for key, value in payload.items()
        if key
        not in {
            "case_id",
            "trace_id",
            "id",
            "name",
            "title",
            "summary",
            "content",
            "text",
            "memory",
            "message",
            "expected_claims",
            "tags",
        }
        and value is not None
    }
    return AgentTraceRecord(
        case_id=case_id,
        name=name,
        content=str(content),
        expected_claims=expected_claims,
        tags=tags,
        metadata=metadata,
    )


def _draft_expected_claims(content: str, extractor: Extractor) -> list[ExpectedClaim]:
    return [
        ExpectedClaim(
            statement=claim.statement,
            entities=[entity.name for entity in claim.entities],
            relation_type=claim.relation_type,
            claim_type=claim.claim_type,
        )
        for claim in extractor.extract(content)
    ]
