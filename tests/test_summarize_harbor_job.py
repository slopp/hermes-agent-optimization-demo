import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class SummarizeHarborJobTest(unittest.TestCase):
    def test_reports_rewards_calls_and_relay(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            trial = root / "case__trial"
            (trial / "verifier").mkdir(parents=True)
            artifact = trial / "artifacts" / "logs" / "artifacts" / "relay"
            (artifact / "atof").mkdir(parents=True)
            (artifact / "atif").mkdir()
            (trial / "result.json").write_text(
                json.dumps(
                    {
                        "task_name": "suite/case",
                        "trial_name": "case__trial",
                        "agent_info": {
                            "name": "hermes-flywheel",
                            "model_info": {"name": "example/model", "provider": "example"},
                        },
                        "verifier_result": {"rewards": {"reward": 1.0}},
                    }
                )
            )
            (trial / "verifier" / "report.json").write_text(
                json.dumps({"tool_calls": ["chat.search", "chat.read_thread"]})
            )
            (artifact / "atof" / "events.jsonl").write_text("{}\n")
            (artifact / "atif" / "trace.atif.json").write_text("{}\n")

            result = subprocess.run(
                ["python3", str(ROOT / "scripts" / "summarize_harbor_job.py"), str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(result.stdout)
            self.assertEqual(summary["counts"]["passed"], 1)
            self.assertEqual(summary["counts"]["relay_complete"], 1)
            self.assertEqual(summary["tool_calls"]["mean_per_trial"], 2)
            self.assertEqual(summary["runtime"]["model_info"]["name"], "example/model")


if __name__ == "__main__":
    unittest.main()
