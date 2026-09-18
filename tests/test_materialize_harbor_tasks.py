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

    def test_task_does_not_copy_python_cache_files(self) -> None:
        source_cache = (
            Path(__file__).parents[1]
            / "src"
            / "pa_style_mock_mcp"
            / "__pycache__"
        )
        source_cache.mkdir(exist_ok=True)
        cached_file = source_cache / "materializer-test.pyc"
        cached_file.write_bytes(b"cache")
        self.addCleanup(cached_file.unlink, missing_ok=True)

        case = {"id": "example", "input": "Find it.", "expectations": {}}
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            materialize(case, root)
            copied = root / "example" / "environment" / "pa_style_mock_mcp"
            self.assertFalse((copied / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
