import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.score_insights_traces import score_trace


class ScoreInsightsTraceTests(unittest.TestCase):
    def test_failed_turn_cannot_pass_even_when_required_tool_was_called(self) -> None:
        trace = {
            "id": "trace-1",
            "root_spans": [
                {"tool_name": "mcp__pa_style_enterprise__chat_search"},
                {"tool_name": "mcp__pa_style_enterprise__chat_search"},
            ],
            "attributes": {
                "final_answer": "I will search now.",
                "turn_outcome": "failed",
                "metrics": {},
            },
        }
        case = {
            "id": "retry",
            "expectations": {"required_tools": ["chat.search", "chat.search"]},
        }

        result = score_trace(trace, case)

        self.assertTrue(result["trajectory_pass"])
        self.assertFalse(result["answer_pass"])
        self.assertEqual(result["terminal_failure"], "turn_outcome:failed")

    def test_preserves_infrastructure_validity_for_report_filtering(self) -> None:
        trace = {
            "id": "trace-1",
            "root_spans": [],
            "attributes": {"final_answer": "ok", "infrastructure_valid": False},
        }
        case = {"id": "case", "expectations": {}}

        result = score_trace(trace, case)

        self.assertFalse(result["infrastructure_valid"])

    def test_scores_walkthrough_mcp_server_prefix(self) -> None:
        trace = {
            "id": "trace-1",
            "root_spans": [{"tool_name": "mcp__enterprise_world__chat_search"}],
            "attributes": {"final_answer": "found it"},
        }
        case = {"id": "case", "expectations": {"required_tools": ["chat.search"]}}

        self.assertTrue(score_trace(trace, case)["trajectory_pass"])

    def test_cli_caps_valid_trials_and_reports_excess(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            suite = root / "suite.json"
            traces = root / "traces.jsonl"
            output = root / "report.json"
            suite.write_text(
                json.dumps({"cases": [{"id": "case", "expectations": {}}]})
            )
            records = [
                {
                    "id": f"trace-{index}",
                    "root_spans": [],
                    "attributes": {
                        "logical_case_id": "case",
                        "final_answer": "ok",
                        "infrastructure_valid": index != 0,
                    },
                }
                for index in range(5)
            ]
            traces.write_text("".join(json.dumps(record) + "\n" for record in records))

            subprocess.run(
                [
                    sys.executable,
                    "scripts/score_insights_traces.py",
                    "--valid-only",
                    "--trials-per-case",
                    "3",
                    "--suite",
                    str(suite),
                    "--arm",
                    f"test={traces}",
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            arm = json.loads(output.read_text())["arms"]["test"]
            self.assertEqual(arm["trace_count"], 3)
            self.assertEqual(arm["excluded_infrastructure_trace_count"], 1)
            self.assertEqual(arm["excluded_excess_valid_trace_count"], 1)


if __name__ == "__main__":
    unittest.main()
