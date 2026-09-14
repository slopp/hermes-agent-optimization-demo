import unittest

from pa_style_mock_mcp.eval_runner import compare_reports, score_runs


class EvalRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = [
            {"id": "read", "expectations": {"required_tools": ["chat.search"], "required_facts": ["packet"], "outbox_count": 0}},
            {"id": "write", "expectations": {"required_tools": ["actions.prepare_message"], "outbox_count": 0}},
        ]
        self.baseline_runs = [
            {"case_id": "read", "calls": [{"name": "chat.search", "arguments": {}}], "final_answer": "The packet is missing.", "outbox": []},
            {"case_id": "write", "calls": [], "final_answer": "I prepared nothing.", "outbox": []},
        ]

    def test_report_has_quality_and_efficiency_metrics(self) -> None:
        report = score_runs(self.cases, self.baseline_runs)
        self.assertEqual(report["case_count"], 2)
        self.assertEqual(report["passed_case_count"], 1)
        self.assertEqual(report["mean_tool_calls"], 0.5)
        self.assertEqual(report["dimension_rates"]["trajectory"], 0.5)

    def test_compare_reports_reports_guardrail_deltas(self) -> None:
        baseline = score_runs(self.cases, self.baseline_runs)
        candidate = score_runs(
            self.cases,
            [
                self.baseline_runs[0],
                {"case_id": "write", "calls": [{"name": "actions.prepare_message", "arguments": {}}], "final_answer": "I prepared a draft.", "outbox": []},
            ],
        )
        comparison = compare_reports(baseline, candidate)
        self.assertEqual(comparison["pass_rate_delta"], 0.5)
        self.assertEqual(comparison["state_delta"], 0.0)

    def test_comparison_requires_held_out_gain_before_claiming_improvement(self) -> None:
        cases = [
            {"id": "derived", "case_kind": "trace_derived", "expectations": {"required_facts": ["packet"], "outbox_count": 0}},
            {"id": "held-out", "case_kind": "held_out", "expectations": {"required_facts": ["review"], "outbox_count": 0}},
        ]
        baseline = score_runs(cases, [
            {"case_id": "derived", "calls": [], "final_answer": "packet", "outbox": []},
            {"case_id": "held-out", "calls": [], "final_answer": "unknown", "outbox": []},
        ])
        candidate = score_runs(cases, [
            {"case_id": "derived", "calls": [], "final_answer": "packet", "outbox": []},
            {"case_id": "held-out", "calls": [], "final_answer": "review", "outbox": []},
        ])
        comparison = compare_reports(baseline, candidate)
        self.assertTrue(comparison["claim_gate"]["eligible_to_claim_measured_improvement"])
        self.assertEqual(comparison["by_case_kind"]["held_out"]["pass_rate_delta"], 1.0)

    def test_missing_case_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing suite cases"):
            score_runs(self.cases, self.baseline_runs[:1])

    def test_provenance_bearing_suite_object_is_scoreable(self) -> None:
        report = score_runs({"suite_version": "1.0", "cases": self.cases}, self.baseline_runs)
        self.assertEqual(report["case_count"], 2)

    def test_required_successful_tool_does_not_credit_a_failed_attempt(self) -> None:
        cases = [{"id": "auth", "expectations": {"required_successful_tools": ["connectors.get_status"], "outbox_count": 0}}]
        report = score_runs(
            cases,
            [{"case_id": "auth", "calls": [{"name": "connectors.get_status", "arguments": {}}], "tool_results": [{"name": "connectors.get_status", "ok": False, "error_code": "INVALID_ARGUMENTS"}], "final_answer": "", "outbox": []}],
        )
        self.assertFalse(report["results"][0]["dimensions"]["trajectory"])
        self.assertIn("missing successful tools: connectors.get_status", report["results"][0]["failures"])
