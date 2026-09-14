import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_collection_review", ROOT / "scripts" / "prepare_collection_review.py")
DOSSIER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = DOSSIER
SPEC.loader.exec_module(DOSSIER)


class PrepareCollectionReviewTest(unittest.TestCase):
    def test_dossier_joins_coverage_without_copying_trace_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"scenarios": [{"id": "case", "signals": ["connectors.get_status"]}]}))
            runs = root / "runs"
            runs.mkdir()
            runs.joinpath("fidelity-collection-manifest.json").write_text(json.dumps({
                "schema_version": "fidelity-collection-manifest-v1",
                "arm": "baseline",
                "trials_per_scenario": 1,
                "records": [{"case_id": "case-trial-01"}],
            }))
            atif_dir = runs / "case-trial-01" / "relay" / "atif"
            atif_dir.mkdir(parents=True)
            atif_dir.joinpath("trace.json").write_text(json.dumps({
                "schema_version": "ATIF-v1.7",
                "session_id": "session-1",
                "steps": [{
                    "tool_calls": [{"function_name": "mcp__pa_style_enterprise__connectors_get_status", "arguments": {"secret": "no-copy"}}],
                    "message": "Fictional answer must not be copied",
                }],
            }))
            dossier = DOSSIER.prepare(runs, matrix, 1, "baseline")
        encoded = json.dumps(dossier)
        self.assertTrue(dossier["signal_coverage"]["all_expected_signals_matched"])
        self.assertIn("connectors.get_status", encoded)
        self.assertNotIn("Fictional answer must not be copied", encoded)
        self.assertNotIn("no-copy", encoded)

    def test_dossier_rejects_a_case_directory_absent_from_collector_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.joinpath("fidelity-collection-manifest.json").write_text(json.dumps({
                "schema_version": "fidelity-collection-manifest-v1",
                "arm": "baseline",
                "trials_per_scenario": 1,
                "records": [],
            }))
            root.joinpath("extra-case").mkdir()
            matrix = root / "matrix.json"
            matrix.write_text(json.dumps({"scenarios": []}))
            with self.assertRaisesRegex(ValueError, "absent from collector manifest"):
                DOSSIER.prepare(root, matrix, 1, "baseline")
