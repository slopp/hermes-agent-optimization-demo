import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_trace_corpus import validate


def make_corpus(root: Path, *, repeated_prompt: bool = False) -> Path:
    records = []
    families = ["coverage", "read", "retry", "auth", "approval", "json"]
    for index in range(42):
        case_id = f"case-{index:02d}"
        prompt = "Repeated request" if repeated_prompt and index in {0, 1} else f"Distinct request {index}"
        trace_id = f"trace-{index:02d}"
        trace = {
            "schema_version": "ATIF-v1.7",
            "trajectory_id": trace_id,
            "extra": {"logical_case_id": case_id},
            "steps": [{"step_id": 1, "source": "user", "message": prompt}],
        }
        relpath = f"{case_id}.atif.json"
        (root / relpath).write_text(json.dumps(trace))
        records.append(
            {
                "path": relpath,
                "trace_id": trace_id,
                "logical_case_id": case_id,
                "behavior_family": families[index % len(families)],
                "prompt": prompt,
            }
        )
    index_path = root / "index.json"
    index_path.write_text(json.dumps({"schema": "enterprise-trace-corpus-v2", "traces": records}))
    return index_path


class TraceCorpusTest(unittest.TestCase):
    def test_valid_distinct_production_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(validate(make_corpus(Path(raw))), [])

    def test_duplicate_user_requests_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            errors = validate(make_corpus(Path(raw), repeated_prompt=True))
            self.assertTrue(any("prompts must be distinct" in error for error in errors))

    def test_missing_trace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            index_path = make_corpus(Path(raw))
            (Path(raw) / "case-00.atif.json").unlink()
            self.assertTrue(any("missing trace" in error for error in validate(index_path)))


if __name__ == "__main__":
    unittest.main()
