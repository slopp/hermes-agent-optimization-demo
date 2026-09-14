import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("check_provisioning", ROOT / "scripts" / "check_provisioning.py")
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)


class ProvisioningCheckTest(unittest.TestCase):
    def test_https_url_requires_https_and_host(self) -> None:
        self.assertTrue(CHECKER.present_https_url("https://mock.example.test/mcp"))
        self.assertFalse(CHECKER.present_https_url("http://mock.example.test/mcp"))
        self.assertFalse(CHECKER.present_https_url("https:///mcp"))

    def test_platform_reports_presence_without_retaining_secret_values(self) -> None:
        env = {
            "NMP_BASE_URL": "https://platform.example.test",
            "NEMO_DEFAULT_MODEL": "demo/default",
            "NEMO_FAST_MODEL": "demo/fast",
            "NVIDIA_API_KEY": "a-secret-that-must-not-be-rendered",
        }
        results = CHECKER.requirements_for("platform", env, {"nemo"}, Path("/unused"))
        self.assertTrue(all(result.present for result in results))
        self.assertNotIn(env["NVIDIA_API_KEY"], repr(results))

    def test_nemoclaw_requires_public_endpoint_and_dedicated_token(self) -> None:
        env = {"NEMOCLAW_SANDBOX_NAME": "fictional-demo", "PA_STYLE_MOCK_MCP_URL": "http://localhost:8000/mcp"}
        results = CHECKER.requirements_for("nemoclaw", env, {"docker", "nemohermes"}, Path("/unused"))
        states = {result.name: result.present for result in results}
        self.assertFalse(states["public HTTPS mock MCP URL"])
        self.assertFalse(states["mock MCP bearer token"])

    def test_hub_key_is_distinct_from_build_key(self) -> None:
        results = CHECKER.requirements_for("hub", {"NVIDIA_API_KEY": "build-only"}, set(), Path("/unused"))
        self.assertFalse(results[0].present)
        results = CHECKER.requirements_for("hub", {"INFERENCE_HUB_API_KEY": "hub-only"}, set(), Path("/unused"))
        self.assertTrue(results[0].present)
