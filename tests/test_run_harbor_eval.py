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


if __name__ == "__main__":
    unittest.main()
