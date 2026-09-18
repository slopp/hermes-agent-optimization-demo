import unittest
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.ensure_nemoclaw_mcp import ensure_mcp, healthy_status, tunnel_url


class EnsureNemoClawMcpTests(unittest.TestCase):
    def test_extracts_newest_quick_tunnel_url(self) -> None:
        output = "old https://first-one.trycloudflare.com\nnew https://second-two.trycloudflare.com"
        self.assertEqual(tunnel_url(output), "https://second-two.trycloudflare.com")

    def test_requires_success_and_exact_tool_count(self) -> None:
        output = "tool discovery: successful\ntools discovered: 15\n"
        self.assertTrue(healthy_status(output, 15))
        self.assertFalse(healthy_status(output, 14))
        self.assertFalse(healthy_status("tool discovery: FAILED\ntools discovered: 15", 15))

    @patch.dict("os.environ", {"DEMO_TOKEN": "secret"}, clear=False)
    @patch(
        "scripts.ensure_nemoclaw_mcp._start_tunnel", return_value="https://new.trycloudflare.com"
    )
    @patch("scripts.ensure_nemoclaw_mcp._run")
    def test_replaces_preserved_provider_after_failed_discovery(self, run, start_tunnel) -> None:
        failed = CompletedProcess([], 0, "tool discovery: FAILED\ntools discovered: 0\n", "")
        succeeded = CompletedProcess(
            [], 0, "tool discovery: successful\ntools discovered: 15\n", ""
        )
        run.side_effect = [
            failed,
            CompletedProcess([], 0, "", ""),
            CompletedProcess([], 0, "", ""),
            CompletedProcess([], 0, "", ""),
            succeeded,
        ]
        with TemporaryDirectory() as raw_root:
            url = ensure_mcp(
                sandbox="demo",
                name="enterprise-world",
                runtime_dir=Path(raw_root),
                local_url="http://127.0.0.1:8000",
                credential_env="DEMO_TOKEN",
                expected_tools=15,
            )

        self.assertEqual(url, "https://new.trycloudflare.com")
        start_tunnel.assert_called_once()
        self.assertEqual(
            run.call_args_list[1].args[0],
            ["nemoclaw", "demo", "mcp", "remove", "enterprise-world", "--force"],
        )
        self.assertEqual(
            run.call_args_list[2].args[0],
            ["openshell", "provider", "delete", "demo-mcp-enterprise-world"],
        )
        self.assertNotIn("secret", repr(run.call_args_list))


if __name__ == "__main__":
    unittest.main()
