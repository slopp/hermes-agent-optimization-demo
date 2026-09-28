import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_harbor_eval import ROOT, main


class RunHarborEvalTest(unittest.TestCase):
    @patch("scripts.run_harbor_eval.subprocess.run")
    def test_custom_agent_is_importable_from_clean_shell(self, run) -> None:
        run.return_value.returncode = 0
        argv = [
            "run_harbor_eval.py",
            "--arm",
            "candidate",
            "--split",
            "development",
            "--harbor",
            "/tmp/harbor",
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
        self.assertIn("openshell_image=hermes-flywheel-openshell:0.2", command)

    @patch("scripts.run_harbor_eval.subprocess.run")
    def test_direct_runtime_remains_available(self, run) -> None:
        run.return_value.returncode = 0
        argv = [
            "run_harbor_eval.py",
            "--arm",
            "baseline",
            "--split",
            "held-out",
            "--runtime",
            "direct",
        ]
        with patch.object(sys, "argv", argv):
            self.assertEqual(main(), 0)

        command = run.call_args.args[0]
        self.assertIn("harbor_agents.hermes_flywheel:HermesFlywheel", command)
        self.assertFalse(any(str(arg).startswith("openshell_image=") for arg in command))


if __name__ == "__main__":
    unittest.main()
