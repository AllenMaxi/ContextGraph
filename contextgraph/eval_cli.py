from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluation import evaluate_extractor, load_evaluation_cases, report_to_dict
from .extraction import RuleBasedExtractor


def run() -> None:
    parser = argparse.ArgumentParser(description="Run ContextGraph extractor evaluation.")
    parser.add_argument(
        "--fixture",
        default="tests/fixtures/claim_eval_cases.json",
        help="Path to the evaluation fixture JSON file.",
    )
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    cases = load_evaluation_cases(fixture_path)
    report = evaluate_extractor(RuleBasedExtractor(), cases)
    print(json.dumps(report_to_dict(report), indent=2))


if __name__ == "__main__":
    run()
