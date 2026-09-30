import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.validate_artifact_chain import digest, validate

REPO = Path(__file__).resolve().parents[1]


class ArtifactChainTest(unittest.TestCase):
    def prepare(self, root):
        paths = {
            "production_corpus": "traces/world-v3/production/index.json",
            "production_insights": "results/production-insights.yml",
            "eval_suite": "evals/flywheel-eval-set-v3.json",
            "baseline_development_traces": "traces/world-v3/baseline-development/insights.jsonl",
            "baseline_development_insights": "results/baseline-development-insights.yml",
            "candidate_proposal": "results/candidate-proposal.md",
            "candidate_profile": "profiles/candidate-soul.md",
        }
        extra = ("results/experiment-freeze.json", "profiles/baseline-soul.md", "openshell/policy.yaml",
                 "fixtures/world-v2.json", "src/pa_style_mock_mcp/tools.py", "src/pa_style_mock_mcp/world.py")
        for relative in (*paths.values(), *extra):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((REPO / relative).read_bytes())
        suite = json.loads((root / paths["eval_suite"]).read_text())
        measured = {"schema": "hermes-harbor-ab-comparison-v3", "attempts_per_task_per_arm": 3,
                    "acceptance": {"both_splits_improve": True}}
        for split in ("development", "held_out"):
            ids = {case["id"] for case in suite["cases"] if case["case_kind"] == split}
            measured[split] = {
                "tasks": len(ids), "attempts_per_task_per_arm": 3,
                "candidate_improved": True, "regressed_tasks": [],
                **{arm: {"trials": len(ids) * 3, "passed": len(ids) * passed, "exceptions": 0,
                         "per_task": {task_id: {"passed": passed, "trials": 3} for task_id in ids}}
                   for arm, passed in (("baseline", 0), ("candidate", 3))},
            }
        paths["measured_ab"] = "results/measured-ab-v3.json"
        (root / paths["measured_ab"]).write_text(json.dumps(measured))
        paths.pop("measured_ab")
        for split in ("development", "held_out"):
            ids = {case["id"] for case in suite["cases"] if case["case_kind"] == split}
            for task_id in ids:
                relative = f"evals/task-proofs/{task_id}/result.json"
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((REPO / relative).read_bytes())
            for arm, reward in (("baseline", 0), ("candidate", 1)):
                fingerprint = {
                    "schema": "hermes-runtime-fingerprint-v1", "arm": arm,
                    "requested_model": "nvidia/example", "harness_config_sha256": "shared-config",
                    "profile_sha256": digest(root / f"profiles/{arm}-soul.md"),
                    "policy_sha256": digest(root / "openshell/policy.yaml"),
                    "fixture_sha256": digest(root / "fixtures/world-v2.json"),
                    "mcp_implementation_sha256": {name: digest(root / "src/pa_style_mock_mcp" / name)
                                                  for name in ("tools.py", "world.py")},
                }
                trials = []
                for task_id in ids:
                    proof = json.loads((root / f"evals/task-proofs/{task_id}/result.json").read_text())
                    for k in range(3):
                        trials.append({"task": f"suite/{task_id}", "trial": f"{task_id}-{k}",
                                       "reward": reward, "exception": None, "arm": arm,
                                       "task_checksum": proof["technical_validation"]["task_checksum"],
                                       "verifier_environment_mode": "separate",
                                       "requested_model": "nvidia/example", "relay_atof": True,
                                       "relay_atif": True, "runtime_fingerprint": fingerprint})
                summary = {"job_finished_at": "done", "runtime": {"name": "openshell-hermes-flywheel"},
                           "trials": trials, "counts": {"passed": len(trials) * reward}}
                relative = f"results/{arm}-{split}-summary.json"
                (root / relative).write_text(json.dumps(summary))
                paths[f"{arm}_{split}_run"] = relative
        paths["measured_ab"] = "results/measured-ab-v3.json"
        chain = {
            "schema": "hermes-agent-optimization-artifact-chain-v3",
            "runtime": {"agent_sandbox": "OpenShell", "mcp": {
                "location": "host_outside_sandbox", "transport": "streamable-http",
                "host": "host.openshell.internal", "ports": [8765]}},
            "stages": [{"id": name, "path": relative, "sha256": digest(root / relative),
                        "consumes": []} for name, relative in paths.items()],
        }
        (root / "results/artifact-chain.json").write_text(json.dumps(chain))
        return chain, measured

    def check(self, root, *, require_review=False):
        # Exact-tree controls are tested independently in test_task_products.
        with patch("scripts.validate_artifact_chain.validate_task_products", return_value=[]), \
                contextlib.redirect_stdout(io.StringIO()):
            validate(root, require_review=require_review)

    def test_experimental_integrity_does_not_establish_human_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.prepare(root)
            self.check(root)
            with self.assertRaisesRegex(SystemExit, "human task/split review"):
                self.check(root, require_review=True)

    def test_frozen_candidate_drift_is_rejected_even_with_updated_stage_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain, _ = self.prepare(root)
            path = root / "profiles/candidate-soul.md"
            path.write_text(path.read_text() + "\nChanged after holdout\n")
            for stage in chain["stages"]:
                if stage["id"] == "candidate_profile":
                    stage["sha256"] = digest(path)
            (root / "results/artifact-chain.json").write_text(json.dumps(chain))
            with self.assertRaisesRegex(SystemExit, "frozen design"):
                self.check(root)

    def test_task_regression_is_rejected_despite_aggregate_improvement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain, measured = self.prepare(root)
            measured["held_out"]["regressed_tasks"] = ["approval-reviewable-launch-draft"]
            path = root / "results/measured-ab-v3.json"
            path.write_text(json.dumps(measured))
            chain["stages"][-1]["sha256"] = digest(path)
            (root / "results/artifact-chain.json").write_text(json.dumps(chain))
            with self.assertRaisesRegex(SystemExit, "per-task regressions"):
                self.check(root)

    def test_frozen_evaluation_contract_cannot_drift_with_stage_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain, _ = self.prepare(root)
            path = root / "evals/flywheel-eval-set-v3.json"
            suite = json.loads(path.read_text())
            suite["cases"][0]["input"] = "Changed evaluation request"
            path.write_text(json.dumps(suite))
            for stage in chain["stages"]:
                if stage["id"] == "eval_suite":
                    stage["sha256"] = digest(path)
            (root / "results/artifact-chain.json").write_text(json.dumps(chain))
            with self.assertRaisesRegex(SystemExit, "evaluation contract differs"):
                self.check(root)

    def test_reported_pass_count_must_match_retained_rewards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain, measured = self.prepare(root)
            measured["development"]["candidate"]["passed"] = 5
            path = root / "results/measured-ab-v3.json"
            path.write_text(json.dumps(measured))
            chain["stages"][-1]["sha256"] = digest(path)
            (root / "results/artifact-chain.json").write_text(json.dumps(chain))
            with self.assertRaisesRegex(SystemExit, "aggregate differs from Harbor rewards"):
                self.check(root)


if __name__ == "__main__":
    unittest.main()
