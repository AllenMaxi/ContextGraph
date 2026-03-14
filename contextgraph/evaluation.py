from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from .extraction import ExtractedClaim, Extractor, canonicalize_statement
from .utils import normalize_alias


@dataclass(slots=True)
class ExpectedClaim:
    statement: str
    entities: list[str] = field(default_factory=list)
    relation_type: str | None = None
    claim_type: str | None = None


@dataclass(slots=True)
class EvaluationCase:
    case_id: str
    name: str
    content: str
    expected_claims: list[ExpectedClaim]
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvaluationCaseResult:
    case_id: str
    name: str
    extracted_claim_count: int
    expected_claim_count: int
    statement_precision: float
    statement_recall: float
    entity_precision: float
    entity_recall: float
    relation_accuracy: float
    missing_statements: list[str] = field(default_factory=list)
    unexpected_statements: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvaluationReport:
    extractor_name: str
    case_count: int
    statement_precision: float
    statement_recall: float
    entity_precision: float
    entity_recall: float
    relation_accuracy: float
    cases: list[EvaluationCaseResult] = field(default_factory=list)


def load_evaluation_cases(path: str | Path) -> list[EvaluationCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Evaluation fixture must contain a list of cases.")

    cases: list[EvaluationCase] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Each evaluation case must be an object.")
        expected_raw = item.get("expected_claims", [])
        if not isinstance(expected_raw, list):
            raise ValueError("expected_claims must be a list.")
        expected_claims = [
            ExpectedClaim(
                statement=str(claim["statement"]),
                entities=[str(entity) for entity in claim.get("entities", [])],
                relation_type=str(claim["relation_type"]) if claim.get("relation_type") is not None else None,
                claim_type=str(claim["claim_type"]) if claim.get("claim_type") is not None else None,
            )
            for claim in expected_raw
        ]
        cases.append(
            EvaluationCase(
                case_id=str(item["case_id"]),
                name=str(item["name"]),
                content=str(item["content"]),
                expected_claims=expected_claims,
                tags=[str(tag) for tag in item.get("tags", [])],
            )
        )
    return cases


def evaluate_extractor(extractor: Extractor, cases: list[EvaluationCase]) -> EvaluationReport:
    case_results = [_evaluate_case(extractor, case) for case in cases]
    if not case_results:
        return EvaluationReport(
            extractor_name=extractor.__class__.__name__,
            case_count=0,
            statement_precision=0.0,
            statement_recall=0.0,
            entity_precision=0.0,
            entity_recall=0.0,
            relation_accuracy=0.0,
            cases=[],
        )

    return EvaluationReport(
        extractor_name=extractor.__class__.__name__,
        case_count=len(case_results),
        statement_precision=_average(result.statement_precision for result in case_results),
        statement_recall=_average(result.statement_recall for result in case_results),
        entity_precision=_average(result.entity_precision for result in case_results),
        entity_recall=_average(result.entity_recall for result in case_results),
        relation_accuracy=_average(result.relation_accuracy for result in case_results),
        cases=case_results,
    )


def report_to_dict(report: EvaluationReport) -> dict[str, Any]:
    return {
        "extractor_name": report.extractor_name,
        "case_count": report.case_count,
        "statement_precision": report.statement_precision,
        "statement_recall": report.statement_recall,
        "entity_precision": report.entity_precision,
        "entity_recall": report.entity_recall,
        "relation_accuracy": report.relation_accuracy,
        "cases": [
            {
                "case_id": case.case_id,
                "name": case.name,
                "extracted_claim_count": case.extracted_claim_count,
                "expected_claim_count": case.expected_claim_count,
                "statement_precision": case.statement_precision,
                "statement_recall": case.statement_recall,
                "entity_precision": case.entity_precision,
                "entity_recall": case.entity_recall,
                "relation_accuracy": case.relation_accuracy,
                "missing_statements": case.missing_statements,
                "unexpected_statements": case.unexpected_statements,
            }
            for case in report.cases
        ],
    }


def _evaluate_case(extractor: Extractor, case: EvaluationCase) -> EvaluationCaseResult:
    extracted = extractor.extract(case.content)

    expected_statement_map = {
        canonicalize_statement(item.statement).lower(): item for item in case.expected_claims
    }
    extracted_statement_map = {
        canonicalize_statement(item.statement).lower(): item for item in extracted
    }

    expected_statements = set(expected_statement_map)
    extracted_statements = set(extracted_statement_map)
    matched_statements = expected_statements & extracted_statements

    expected_entities = _collect_expected_entities(case.expected_claims)
    extracted_entities = _collect_extracted_entities(extracted)

    matched_entities = expected_entities & extracted_entities
    missing_statements = sorted(expected_statements - extracted_statements)
    unexpected_statements = sorted(extracted_statements - expected_statements)

    relation_total = len(case.expected_claims)
    relation_hits = 0
    for statement_key in matched_statements:
        expected = expected_statement_map[statement_key]
        actual = extracted_statement_map[statement_key]
        if expected.relation_type is None or expected.relation_type == actual.relation_type:
            relation_hits += 1

    return EvaluationCaseResult(
        case_id=case.case_id,
        name=case.name,
        extracted_claim_count=len(extracted),
        expected_claim_count=len(case.expected_claims),
        statement_precision=_safe_ratio(len(matched_statements), len(extracted_statements)),
        statement_recall=_safe_ratio(len(matched_statements), len(expected_statements)),
        entity_precision=_safe_ratio(len(matched_entities), len(extracted_entities)),
        entity_recall=_safe_ratio(len(matched_entities), len(expected_entities)),
        relation_accuracy=_safe_ratio(relation_hits, relation_total),
        missing_statements=missing_statements,
        unexpected_statements=unexpected_statements,
    )


def _collect_expected_entities(expected_claims: list[ExpectedClaim]) -> set[str]:
    return {normalize_alias(entity) for claim in expected_claims for entity in claim.entities}


def _collect_extracted_entities(claims: list[ExtractedClaim]) -> set[str]:
    return {normalize_alias(entity.name) for claim in claims for entity in claim.entities}


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _average(values: Any) -> float:
    items = list(values)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)
