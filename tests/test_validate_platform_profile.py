import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
STAGER_SPEC = importlib.util.spec_from_file_location("stage_platform_profile_for_validator", ROOT / "scripts" / "stage_platform_profile.py")
STAGER = importlib.util.module_from_spec(STAGER_SPEC)
assert STAGER_SPEC.loader is not None
sys.modules[STAGER_SPEC.name] = STAGER
STAGER_SPEC.loader.exec_module(STAGER)
VALIDATOR_SPEC = importlib.util.spec_from_file_location("validate_platform_profile", ROOT / "scripts" / "validate_platform_profile.py")
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
sys.modules[VALIDATOR_SPEC.name] = VALIDATOR
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


class ValidatePlatformProfileTest(unittest.TestCase):
    def test_accepts_staged_profile_with_matching_relay_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            STAGER.stage(directory, "Hermes-PA-style-mock", "fictional-demo")
            self.assertEqual(VALIDATOR.validate(directory, "Hermes-PA-style-mock"), [])

    def test_rejects_relay_agent_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            STAGER.stage(directory, "Hermes-PA-style-mock", "fictional-demo")
            errors = VALIDATOR.validate(directory, "different-agent")
            self.assertTrue(any("does not match Relay" in error for error in errors))

    def test_rejects_spec_that_does_not_name_the_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            STAGER.stage(directory, "Hermes-PA-style-mock", "fictional-demo")
            (directory / "AGENT-SPEC.md").write_text("# Generic spec\n")
            errors = VALIDATOR.validate(directory)
            self.assertIn("AGENT-SPEC.md must state the exact normalized agent_name", errors)
