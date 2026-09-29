import json
import tempfile
import unittest
from pathlib import Path

from harbor_agents.openshell_utils import final_answer, sandbox_name

try:
    from harbor_agents.openshell_hermes import OpenShellHermesFlywheel
except (ImportError, ModuleNotFoundError):  # Harbor/Python 3.12 are optional here.
    OpenShellHermesFlywheel = None


class OpenShellHelpersTest(unittest.TestCase):
    def test_sandbox_name_is_dns_safe_bounded_and_stable(self) -> None:
        first = sandbox_name("Source_Coverage__LONG/unsafe value" * 3, "candidate")
        second = sandbox_name("Source_Coverage__LONG/unsafe value" * 3, "candidate")
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 19)
        self.assertRegex(first, r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

    def test_final_answer_reads_export_and_skips_tool_call_messages(self) -> None:
        session = json.dumps(
            {
                "messages": [
                    {"role": "assistant", "content": "searching", "tool_calls": [{}]},
                    {"role": "tool", "content": "result"},
                    {"role": "assistant", "content": "grounded answer"},
                ]
            }
        )
        self.assertEqual(final_answer(session), "grounded answer")


@unittest.skipIf(OpenShellHermesFlywheel is None, "Harbor is not installed")
class OpenShellRuntimeTest(unittest.TestCase):
    def test_runtime_contains_arm_mcp_relay_and_no_api_key(self) -> None:
        import yaml

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            agent = OpenShellHermesFlywheel(
                logs_dir=root / "logs",
                model_name="nvidia/nvidia/nemotron-3-ultra-550b-a55b",
                arm="candidate",
            )
            self.assertEqual(agent.version(), "0.21.3")
            runtime = root / "run"
            agent._write_runtime(runtime, 'Summarize the "launch" evidence.')

            config_text = (runtime / "hermes" / "config.yaml").read_text()
            config = yaml.safe_load(config_text)
            self.assertEqual(config["agent"]["max_turns"], 12)
            self.assertEqual(config["toolsets"], ["skills"])
            self.assertEqual(config["tools"]["tool_search"]["enabled"], "auto")
            enterprise = config["mcp_servers"]["enterprise-world"]
            self.assertEqual(
                enterprise["url"], "http://host.openshell.internal:8765/mcp"
            )
            self.assertEqual(
                enterprise["headers"]["Authorization"], "Bearer test-token"
            )
            self.assertFalse((runtime / "world.json").exists())
            self.assertEqual(
                (runtime / "instruction.txt").read_text(),
                'Summarize the "launch" evidence.',
            )
            all_text = "\n".join(
                path.read_text(errors="ignore")
                for path in runtime.rglob("*")
                if path.is_file()
            )
            self.assertNotIn("NVIDIA_API_KEY=", all_text)
            self.assertIn("HERMES_NEMO_RELAY_PLUGINS_TOML", all_text)
            # A CLI --toolsets override becomes an MCP server-name allowlist in
            # Hermes 0.21.3. Keep arm toolsets in config so enterprise-world
            # remains discoverable.
            self.assertNotIn("--toolsets", (runtime / "run.sh").read_text())

    def test_provider_base_url_is_an_optional_runtime_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            agent = OpenShellHermesFlywheel(
                logs_dir=root / "logs",
                model_name="nvidia/nvidia/nemotron-3-ultra-550b-a55b",
                arm="baseline",
                provider_base_url="https://inference.example.test/v1/",
            )
            runtime = root / "run"
            agent._write_runtime(runtime, "Find launch evidence.")
            script = (runtime / "run.sh").read_text()
            self.assertIn(
                "export NVIDIA_BASE_URL=https://inference.example.test/v1", script
            )

    def test_baseline_eagerly_exposes_mcp_tools(self) -> None:
        import yaml

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            agent = OpenShellHermesFlywheel(
                logs_dir=root / "logs",
                model_name="nvidia/nvidia/nemotron-3-ultra-550b-a55b",
                arm="baseline",
            )
            runtime = root / "run"
            agent._write_runtime(runtime, "Find launch evidence.")
            config = yaml.safe_load(
                (runtime / "hermes" / "config.yaml").read_text()
            )
            self.assertEqual(config["tools"]["tool_search"]["enabled"], "off")


if __name__ == "__main__":
    unittest.main()
