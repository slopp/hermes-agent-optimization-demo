import json
import tempfile
import unittest
from pathlib import Path

from scripts.materialize_harbor_tasks import materialize


class MaterializeHarborTasksTest(unittest.TestCase):
    def test_task_uses_real_mcp_and_separate_verifier(self) -> None:
        case = {
            "id": "example",
            "input": "Find the evidence.",
            "expectations": {
                "required_tools": ["chat.search"],
                "required_facts": ["evidence"],
            },
        }
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            materialize(case, root)
            task = root / "example"
            task_toml = (task / "task.toml").read_text()
            dockerfile = (task / "environment" / "Dockerfile").read_text()
            expected = json.loads((task / "tests" / "expected.json").read_text())

            self.assertIn('name = "enterprise-world"', task_toml)
            self.assertIn('environment_mode = "separate"', task_toml)
            self.assertIn('network_mode = "no-network"', task_toml)
            self.assertNotIn("enterprise-query", task_toml)
            self.assertIn("hermes-agent", dockerfile)
            self.assertEqual(expected["required_tools"], ["chat.search"])


if __name__ == "__main__":
    unittest.main()
