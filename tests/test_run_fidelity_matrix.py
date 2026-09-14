import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("run_fidelity_matrix", ROOT / "scripts" / "run_fidelity_matrix.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


class FidelityMatrixRunnerTest(unittest.TestCase):
    def matrix(self) -> dict:
        return {
            "scenarios": [
                {"id": "first", "prompt": "fictional one"},
                {"id": "second", "prompt": "fictional two"},
            ],
            "go_no_go": {"baseline_trials_per_scenario": 5},
        }

    def test_builds_one_real_run_job_per_trial(self) -> None:
        jobs = RUNNER.build_jobs(RUNNER.select_scenarios(self.matrix(), {"second"}), 2, "baseline")
        self.assertEqual(
            jobs,
            [
                {"scenario_id": "second", "trial": 1, "case_id": "second-trial-01", "prompt": "fictional two", "arm": "baseline"},
                {"scenario_id": "second", "trial": 2, "case_id": "second-trial-02", "prompt": "fictional two", "arm": "baseline"},
            ],
        )

    def test_rejects_unknown_scenario(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown scenario IDs"):
            RUNNER.select_scenarios(self.matrix(), {"not-present"})

    def test_manifest_does_not_include_prompt_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            matrix_path = Path(temp) / "matrix.json"
            matrix_path.write_text(json.dumps(self.matrix()))
            manifest_path = Path(temp) / "manifest.json"
            RUNNER.write_manifest(
                manifest_path,
                matrix_path,
                "baseline",
                1,
                "extended",
                "build",
                "nvidia",
                "nvidia/test-model",
                180,
                "collection-001",
                Path(temp) / "run-root",
                [{"scenario_id": "first", "trial": 1, "case_id": "first-trial-01", "exit_code": 0}],
            )
            manifest = json.loads(manifest_path.read_text())
        self.assertNotIn("prompt", json.dumps(manifest))
        self.assertEqual(manifest["records"][0]["case_id"], "first-trial-01")
        self.assertEqual(manifest["tool_catalog"], "extended")
        self.assertEqual(manifest["inference_route"], "build")
        self.assertEqual(manifest["wall_timeout_seconds"], 180)
        self.assertEqual(manifest["collection_id"], "collection-001")

    def test_refuses_to_mix_runs_in_a_nonempty_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "existing.json").write_text("old trace marker")
            with self.assertRaisesRegex(ValueError, "not empty"):
                RUNNER.require_empty_run_root(root)
