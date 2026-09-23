import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_scored_trace_bundle import validate


class ScoredTraceBundleTest(unittest.TestCase):
    def test_checked_in_bundle(self) -> None:
        root = Path(__file__).parents[1]
        self.assertEqual(
            validate(root / "traces" / "world-v2" / "baseline-eval" / "insights.jsonl"),
            [],
        )

    def test_missing_evaluator_result_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "traces.jsonl"
            path.write_text(json.dumps({"id": "one", "attributes": {}}) + "\n")
            errors = validate(path)
            self.assertTrue(any("binary harbor.reward" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
