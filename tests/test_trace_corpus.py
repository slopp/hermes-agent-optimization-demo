import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_trace_corpus import EXPECTED_CASES, validate


class TraceCorpusTest(unittest.TestCase):
    def test_checked_in_corpus(self) -> None:
        root = Path(__file__).parents[1]
        self.assertEqual(
            validate(root / "traces" / "world-v2" / "corpus" / "index.json"), []
        )

    def test_missing_trace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            records = [
                {
                    "path": f"{case}.atif.json",
                    "trace_id": case,
                    "logical_case_id": case,
                    "collection": "test",
                }
                for case in EXPECTED_CASES
            ]
            (root / "index.json").write_text(
                json.dumps({"schema": "enterprise-trace-corpus-v1", "traces": records})
            )
            errors = validate(root / "index.json", per_case=1)
            self.assertTrue(any("missing trace" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
