from __future__ import annotations

from pathlib import Path
import unittest

from contextgraph.evaluation import EvaluationCase, ExpectedClaim, evaluate_extractor, load_evaluation_cases
from contextgraph.extraction import ExtractedClaim, ExtractedEntity, RuleBasedExtractor, canonicalize_statement


class StaticExtractor:
    def __init__(self, claims: list[ExtractedClaim]) -> None:
        self._claims = claims

    def extract(self, content: str) -> list[ExtractedClaim]:
        return list(self._claims)


class ContextGraphEvaluationTest(unittest.TestCase):
    def test_evaluate_extractor_scores_expected_matches(self) -> None:
        case = EvaluationCase(
            case_id="case_1",
            name="Exact match",
            content="Acme Corp reported API latency.",
            expected_claims=[
                ExpectedClaim(
                    statement="Acme Corp reported API latency",
                    entities=["Acme Corp"],
                    relation_type="REPORTED",
                    claim_type="attribute",
                )
            ],
        )
        extractor = StaticExtractor(
            [
                ExtractedClaim(
                    statement="Acme Corp reported API latency",
                    claim_type="attribute",
                    relation_type="REPORTED",
                    confidence=0.9,
                    entities=[ExtractedEntity(name="Acme Corp", entity_type="company")],
                )
            ]
        )

        report = evaluate_extractor(extractor, [case])

        self.assertEqual(report.case_count, 1)
        self.assertEqual(report.statement_precision, 1.0)
        self.assertEqual(report.statement_recall, 1.0)
        self.assertEqual(report.entity_precision, 1.0)
        self.assertEqual(report.entity_recall, 1.0)
        self.assertEqual(report.relation_accuracy, 1.0)

    def test_load_fixture_and_evaluate_rule_based_extractor(self) -> None:
        fixture_path = Path("tests/fixtures/claim_eval_cases.json")

        cases = load_evaluation_cases(fixture_path)
        report = evaluate_extractor(RuleBasedExtractor(), cases)

        self.assertEqual(len(cases), 4)
        self.assertEqual(report.case_count, 4)
        self.assertGreaterEqual(report.statement_precision, 0.0)
        self.assertLessEqual(report.statement_precision, 1.0)
        self.assertGreaterEqual(report.statement_recall, 0.0)
        self.assertLessEqual(report.statement_recall, 1.0)

    def test_canonicalize_statement_strips_trailing_punctuation(self) -> None:
        self.assertEqual(canonicalize_statement(" Acme Corp reported API latency. "), "Acme Corp reported API latency")


if __name__ == "__main__":
    unittest.main()
