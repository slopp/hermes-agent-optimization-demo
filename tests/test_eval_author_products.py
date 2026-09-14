import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_eval_author_products import _task_tree_sha256, validate


class EvalAuthorProductValidationTest(unittest.TestCase):
    def _product(self, root: Path) -> dict:
        product_dir = root / "evals" / "products" / "case-1"
        product_dir.mkdir(parents=True)
        result = {
            "schema": "nemo.eval_author.trace_environment_product.v3",
            "task_id": "case-1",
            "status": "candidate",
            "environment": {
                "status": "unproven",
                "review_status": "unreviewed",
                "technical_status": "passed",
                "verifier_environment_mode": "separate",
            },
            "technical_validation": {
                "task_tree_sha256": "sha256:abc",
                "runs": {
                    "nop": [{"reward": 0.0, "exception_present": False}] * 2,
                    "oracle": [{"reward": 1.0, "exception_present": False}] * 2,
                    "negative": [{"reward": 0.0, "exception_present": False}],
                },
            },
        }
        candidate = {
            "schema": "nemo.eval_author.trace_environment_candidate.v2",
            "status": "candidate",
            "instruction": "Do the thing.\n\nWrite the artifact.",
        }
        reproducibility = {
            "schema": "nemo.eval_author.trace_environment_reproducibility.v3",
            "task_tree_sha256": "pending",
            "network": {"agent": "no-network", "verifier": "no-network"},
            "contamination": {"passed": True},
        }
        for name, value in (
            ("result.json", result),
            ("candidate.json", candidate),
            ("reproducibility.json", reproducibility),
        ):
            (product_dir / name).write_text(json.dumps(value))
        tree_digest = _task_tree_sha256(product_dir / "task")
        result["technical_validation"]["task_tree_sha256"] = tree_digest
        reproducibility["task_tree_sha256"] = tree_digest
        (product_dir / "result.json").write_text(json.dumps(result))
        (product_dir / "reproducibility.json").write_text(json.dumps(reproducibility))
        return {
            "cases": [
                {
                    "id": "case-1",
                    "case_kind": "trace_derived",
                    "input": "Do the thing.",
                    "provenance": {"eval_author_product_ref": "evals/products/case-1/result.json"},
                }
            ]
        }

    def test_accepts_technically_proven_product_with_human_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(validate(self._product(root), root), [])

    def test_rejects_oracle_that_does_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite = self._product(root)
            result_path = root / "evals/products/case-1/result.json"
            result = json.loads(result_path.read_text())
            result["technical_validation"]["runs"]["oracle"][0]["reward"] = 0.0
            result_path.write_text(json.dumps(result))
            self.assertIn(
                "case case-1 proof rewards do not match the required matrix",
                validate(suite, root),
            )


if __name__ == "__main__":
    unittest.main()
