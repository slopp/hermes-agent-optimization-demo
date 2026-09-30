import unittest
from pathlib import Path

import yaml


class TraceAnalystConfigTest(unittest.TestCase):
    def test_ethos_stream_uses_the_versioned_demo_operating_rules(self) -> None:
        root = Path(__file__).parents[1]
        config = yaml.safe_load((root / "configs" / "trace-analyst.yaml").read_text())
        ethos = config["evidence_streams"]["ethos_divergence"]
        ethos_path = root / ethos["ethos_path"]

        self.assertTrue(ethos_path.is_file())
        self.assertIn("permission to send", ethos_path.read_text())
        self.assertTrue(config["evidence_streams"]["anomaly_and_patterns"])
        self.assertTrue(config["evidence_streams"]["tool_issues"])


if __name__ == "__main__":
    unittest.main()
