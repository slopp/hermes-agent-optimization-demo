import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "assemble_insights_corpus", ROOT / "scripts" / "assemble_insights_corpus.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AssembleInsightsCorpusTests(unittest.TestCase):
    def test_combines_unique_records(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            output = root / "out.jsonl"
            first.write_text(json.dumps({"id": "one"}) + "\n")
            second.write_text(json.dumps({"id": "two"}) + "\n")
            self.assertEqual(MODULE.assemble([first, second], output), 2)
            self.assertEqual([json.loads(line)["id"] for line in output.read_text().splitlines()], ["one", "two"])

    def test_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            path = Path(raw_temp) / "traces.jsonl"
            path.write_text(json.dumps({"id": "same"}) + "\n" + json.dumps({"id": "same"}) + "\n")
            with self.assertRaisesRegex(ValueError, "duplicate trace id"):
                MODULE.assemble([path], Path(raw_temp) / "out.jsonl")

    def test_valid_only_excludes_infrastructure_failures(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            source = root / "source.jsonl"
            output = root / "out.jsonl"
            source.write_text(
                json.dumps({"id": "ok", "attributes": {"infrastructure_valid": True}})
                + "\n"
                + json.dumps({"id": "bad", "attributes": {"infrastructure_valid": False}})
                + "\n"
            )

            self.assertEqual(MODULE.assemble([source], output, valid_only=True), 1)
            self.assertEqual(json.loads(output.read_text())["id"], "ok")
