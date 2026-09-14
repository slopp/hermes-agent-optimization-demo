import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("stage_platform_profile", ROOT / "scripts" / "stage_platform_profile.py")
STAGER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(STAGER)


class StagePlatformProfileTest(unittest.TestCase):
    def test_stages_profile_aligned_to_relay_agent_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            optimizer, spec = STAGER.stage(Path(temporary), "Hermes-PA-style-mock", "fictional-demo")
            self.assertEqual(
                optimizer.read_text(),
                "agent: Hermes-PA-style-mock\nworkspace: fictional-demo\nagent_spec: AGENT-SPEC.md\n",
            )
            content = spec.read_text()
            self.assertIn("normalized `agent_name` is\n`Hermes-PA-style-mock`", content)
            self.assertNotIn("NVIDIA_API_KEY", content)

    def test_refuses_to_replace_profile_without_explicit_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            STAGER.stage(directory, "agent", "workspace")
            with self.assertRaises(FileExistsError):
                STAGER.stage(directory, "agent", "workspace")
