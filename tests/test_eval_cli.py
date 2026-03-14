from __future__ import annotations

from io import StringIO
import json
import unittest
from unittest.mock import patch

from contextgraph import eval_cli


class ContextGraphEvalCliTest(unittest.TestCase):
    def test_run_prints_json_report(self) -> None:
        stdout = StringIO()

        with patch("sys.argv", ["contextgraph-eval"]), patch("sys.stdout", stdout):
            eval_cli.run()

        payload = json.loads(stdout.getvalue())
        self.assertIn("extractor_name", payload)
        self.assertIn("case_count", payload)
        self.assertEqual(payload["case_count"], 4)


if __name__ == "__main__":
    unittest.main()
