import tempfile
import unittest
from pathlib import Path

from scripts.prepare_hermes_run import prepare


class PrepareHermesRunTest(unittest.TestCase):
    def test_writes_isolated_profile_with_extended_mock_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = prepare(
                Path(temp),
                demo_root=Path("/fictional/demo"),
                model="nvidia/test-model",
                system_prompt="Use the fictional fixture only.",
            )
            config = config_path.read_text()
        self.assertIn('provider: "nvidia"', config)
        self.assertIn('default: "nvidia/test-model"', config)
        self.assertIn('system_prompt: "Use the fictional fixture only."', config)
        self.assertIn("tool_search:\n    enabled: off", config)
        self.assertIn("observability/nemo_relay", config)
        self.assertIn("PA_STYLE_TOOL_CATALOG: extended", config)
        self.assertIn('PYTHONPATH: "/fictional/demo/src"', config)

    def test_custom_endpoint_is_written_without_a_credential(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config_path = prepare(
                Path(temp),
                provider="custom",
                base_url="https://inference-api.nvidia.com/v1",
            )
            config = config_path.read_text()
        self.assertIn('provider: "custom"', config)
        self.assertIn('base_url: "https://inference-api.nvidia.com/v1"', config)
        self.assertNotIn("api_key", config)

    def test_writes_requested_focused_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = prepare(Path(temp), tool_catalog="focused").read_text()
        self.assertIn("PA_STYLE_TOOL_CATALOG: focused", config)
