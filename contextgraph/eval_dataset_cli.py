from __future__ import annotations

import argparse
from pathlib import Path

from .eval_dataset import build_evaluation_cases_from_traces, load_agent_trace_records, write_evaluation_cases
from .extraction import RuleBasedExtractor


def run() -> int:
    parser = argparse.ArgumentParser(description="Build a draft evaluation fixture from agent trace records.")
    parser.add_argument("source", help="Path to a JSON or JSONL file with agent trace records.")
    parser.add_argument("output", help="Path to write the evaluation fixture JSON.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output file if it already exists.")
    args = parser.parse_args()

    output_path = Path(args.output)
    if output_path.exists() and not args.overwrite:
        parser.error(f"Output file already exists: {output_path}")

    records = load_agent_trace_records(args.source)
    cases = build_evaluation_cases_from_traces(records, RuleBasedExtractor())
    write_evaluation_cases(output_path, cases)
    print(f"Wrote {len(cases)} evaluation cases to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
