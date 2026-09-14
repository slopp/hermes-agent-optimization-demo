import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class MockMcpContainerTest(unittest.TestCase):
    def test_container_requires_runtime_token_and_runs_non_root(self) -> None:
        dockerfile = (ROOT / "deploy" / "mock-mcp" / "Dockerfile").read_text()
        self.assertIn("USER mockmcp", dockerfile)
        self.assertIn('"--require-bearer-token"', dockerfile)
        self.assertNotIn("PA_STYLE_MOCK_MCP_TOKEN=", dockerfile)
        self.assertNotIn("COPY traces", dockerfile)
