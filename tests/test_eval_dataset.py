from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contextgraph import build_evaluation_cases_from_traces, load_agent_trace_records, write_evaluation_cases
from contextgraph.extraction import RuleBasedExtractor


FIXTURE_PATH = Path("tests/fixtures/agent_trace_records.jsonl")


class ContextGraphEvalDatasetTest(unittest.TestCase):
    def test_load_agent_trace_records_supports_jsonl(self) -> None:
        records = load_agent_trace_records(FIXTURE_PATH)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].case_id, "trace-1")
        self.assertEqual(records[1].expected_claims[0].statement, "Vendor X expanded into Germany")

    def test_build_evaluation_cases_drafts_missing_claims(self) -> None:
        records = load_agent_trace_records(FIXTURE_PATH)

        cases = build_evaluation_cases_from_traces(records, RuleBasedExtractor())

        self.assertEqual(len(cases), 2)
        self.assertEqual(cases[0]["metadata"]["review_status"], "draft")
        self.assertEqual(cases[0]["metadata"]["source_agent"], "support-agent")
        self.assertGreaterEqual(len(cases[0]["expected_claims"]), 1)
        self.assertEqual(cases[1]["metadata"]["review_status"], "provided")

    def test_write_evaluation_cases_outputs_json(self) -> None:
        records = load_agent_trace_records(FIXTURE_PATH)
        cases = build_evaluation_cases_from_traces(records, RuleBasedExtractor())

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "draft_cases.json"
            write_evaluation_cases(output_path, cases)
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["case_id"], "trace-1")


if __name__ == "__main__":
    unittest.main()
