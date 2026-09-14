import unittest

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


if __name__ == "__main__":
    unittest.main()
