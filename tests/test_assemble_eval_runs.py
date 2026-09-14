import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("assemble_eval_runs", ROOT / "scripts" / "assemble_eval_runs.py")
ASSEMBLER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ASSEMBLER)


class AssembleEvalRunsTest(unittest.TestCase):
    def write_run(self, directory: Path, name: str, case_id: str) -> None:
        (directory / name).write_text(
            json.dumps({"case_id": case_id, "calls": [], "final_answer": "fictional", "outbox": []})
        )

    def test_assembles_and_sorts_extracted_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.write_run(directory, "second.json", "z-case")
            self.write_run(directory, "first.json", "a-case")
            runs = ASSEMBLER.assemble_runs(directory)
        self.assertEqual([run["case_id"] for run in runs], ["a-case", "z-case"])

    def test_rejects_duplicate_case_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.write_run(directory, "one.json", "same")
            self.write_run(directory, "two.json", "same")
            with self.assertRaisesRegex(ValueError, "duplicate case_id"):
                ASSEMBLER.assemble_runs(directory)

    def test_rejects_incomplete_run_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "bad.json").write_text(json.dumps({"case_id": "missing-fields"}))
            with self.assertRaisesRegex(ValueError, "calls"):
                ASSEMBLER.assemble_runs(directory)
