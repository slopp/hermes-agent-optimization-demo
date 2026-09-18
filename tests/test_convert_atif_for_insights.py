import tempfile
import unittest
from pathlib import Path

from scripts.convert_atif_for_insights import _files, _harbor_case_id


class ConvertAtifForInsightsTest(unittest.TestCase):
    def test_finds_corpus_and_native_relay_names_without_other_job_json(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            corpus = root / "corpus.atif.json"
            relay = root / "trial" / "artifacts" / "relay" / "atif" / "trajectory-1.json"
            unrelated = root / "trial" / "result.json"
            relay.parent.mkdir(parents=True)
            corpus.write_text("{}")
            relay.write_text("{}")
            unrelated.write_text("{}")

            self.assertEqual(_files([root]), [corpus, relay])

            unrelated.write_text('{"task_name": "hermes-flywheel/source-coverage"}')
            self.assertEqual(_harbor_case_id(relay), "source-coverage")


if __name__ == "__main__":
    unittest.main()
