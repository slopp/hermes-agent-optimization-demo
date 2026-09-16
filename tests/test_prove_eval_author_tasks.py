from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prove_eval_author_tasks", ROOT / "scripts" / "prove_eval_author_tasks.py"
)
assert SPEC and SPEC.loader
PROOF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROOF)


class ProofRunnerTests(unittest.TestCase):
    @patch.object(PROOF.subprocess, "run")
    def test_no_network_preflight_uses_selected_context(self, run) -> None:
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        ]

        PROOF._check_no_network_support(Path("/venv/python"), "colima")

        self.assertEqual(run.call_args_list[0].args[0][:3], ["docker", "--context", "colima"])
        self.assertEqual(
            run.call_args_list[1].args[0], ["/venv/python", "-c", PROOF.HARBOR_NETWORK_PROBE]
        )
        self.assertEqual(run.call_args_list[1].kwargs["env"]["DOCKER_CONTEXT"], "colima")

    @patch.object(PROOF.subprocess, "run")
    def test_no_network_preflight_explains_docker_desktop_workaround(self, run) -> None:
        run.side_effect = [
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 1, "", ""),
        ]

        with self.assertRaisesRegex(RuntimeError, "start Colima"):
            PROOF._check_no_network_support(Path("/venv/python"), "default")

    @patch.object(PROOF.concurrent.futures, "ThreadPoolExecutor")
    @patch.object(PROOF, "_run")
    def test_prove_creates_shared_jobs_directory(self, run, executor) -> None:
        executor.return_value.__enter__.return_value.submit.return_value.result.return_value = None
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary) / "task"
            task_dir.mkdir()

            PROOF.prove(
                task_dir,
                helper=Path("helper.py"),
                harbor_python=Path("python"),
                harbor=Path("harbor"),
                docker_context="colima",
                workers=1,
            )

            self.assertTrue((task_dir / "private" / "jobs").is_dir())


if __name__ == "__main__":
    unittest.main()
