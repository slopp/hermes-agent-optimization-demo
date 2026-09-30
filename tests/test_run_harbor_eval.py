import os
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_harbor_eval import ROOT, main


class RunHarborEvalTest(unittest.TestCase):
    def invoke(self, run, split: str, arm: str) -> int:
        run.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as raw:
            suite = Path(raw) / "suite.json"
            suite.write_text(
                json.dumps(
                    {
                        "cases": [
                            {"id": "dev-1", "case_kind": "development"},
                            {"id": "hold-1", "case_kind": "held_out"},
                        ]
                    }
                )
            )
            argv = [
                "run_harbor_eval.py",
                "--arm",
                arm,
                "--split",
                split,
                "--suite",
                str(suite),
                "--harbor",
                "/tmp/harbor",
            ]
            with patch.object(sys, "argv", argv):
                return main()

    @patch("scripts.run_harbor_eval.subprocess.run")
    def test_custom_agent_is_importable_from_clean_shell(self, run) -> None:
        run.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as raw:
            suite = Path(raw) / "suite.json"
            suite.write_text(json.dumps({"cases": [{"id": "dev-1", "case_kind": "development"}]}))
            argv = [
                "run_harbor_eval.py", "--arm", "candidate", "--split", "development",
                "--suite", str(suite), "--harbor", "/tmp/harbor",
                "--provider-base-url", "https://inference.example.test/v1",
            ]
            with patch.object(sys, "argv", argv), patch.dict(os.environ, {"PYTHONPATH": "prior"}):
                self.assertEqual(main(), 0)

        _, kwargs = run.call_args
        self.assertEqual(kwargs["cwd"], Path(ROOT))
        self.assertEqual(kwargs["env"]["PYTHONPATH"], f"{ROOT}{os.pathsep}prior")
        command = run.call_args.args[0]
        self.assertIn(
            "harbor_agents.openshell_hermes:OpenShellHermesFlywheel", command
        )
        self.assertIn("openshell_image=hermes-flywheel-openshell:0.3", command)
        self.assertIn(
            "provider_base_url=https://inference.example.test/v1", command
        )

    @patch("scripts.run_harbor_eval.subprocess.run")
    def test_direct_runtime_remains_available(self, run) -> None:
        run.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as raw:
            suite = Path(raw) / "suite.json"
            suite.write_text(json.dumps({"cases": [{"id": "hold-1", "case_kind": "held_out"}]}))
            argv = ["run_harbor_eval.py", "--arm", "baseline", "--split", "held-out", "--runtime", "direct", "--suite", str(suite)]
            with patch.object(sys, "argv", argv):
                self.assertEqual(main(), 0)

        command = run.call_args.args[0]
        self.assertIn("harbor_agents.hermes_flywheel:HermesFlywheel", command)
        self.assertFalse(any(str(arg).startswith("openshell_image=") for arg in command))


if __name__ == "__main__":
    unittest.main()
