from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from contextgraph import eval_dataset_cli


class ContextGraphEvalDatasetCliTest(unittest.TestCase):
    def test_run_writes_fixture(self) -> None:
        source = Path("tests/fixtures/agent_trace_records.jsonl")
        stdout = StringIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "draft_cases.json"
            with (
                patch("sys.argv", ["contextgraph-eval-dataset", str(source), str(output)]),
                patch("sys.stdout", stdout),
            ):
                exit_code = eval_dataset_cli.run()

            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(payload), 2)
        self.assertIn("Wrote 2 evaluation cases", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
