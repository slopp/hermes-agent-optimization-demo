import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("check_fidelity_coverage", ROOT / "scripts" / "check_fidelity_coverage.py")
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)


class FidelityCoverageTest(unittest.TestCase):
    def test_signal_sequence_allows_unrelated_tools(self) -> None:
        self.assertTrue(
            CHECKER.is_subsequence(
                ["chat.search", "chat.read_thread", "calendar.list_events"],
                ["people.search", "chat.search", "knowledge.search", "chat.read_thread", "calendar.list_events"],
            )
        )

    def test_signal_sequence_requires_order_and_repeat(self) -> None:
        self.assertFalse(CHECKER.is_subsequence(["chat.search", "chat.search"], ["chat.search"]))
        self.assertFalse(CHECKER.is_subsequence(["chat.search", "chat.read_thread"], ["chat.read_thread", "chat.search"]))

    def test_all_source_coverage_allows_a_valid_different_retrieval_order(self) -> None:
        expected = ["chat.search", "chat.read_thread", "calendar.list_events"]
        observed = ["calendar.list_events", "chat.search", "chat.read_thread"]
        self.assertTrue(CHECKER.signals_match(expected, observed, "all"))
        self.assertFalse(CHECKER.signals_match(expected, observed[:-1], "all"))
        self.assertFalse(CHECKER.signals_match(["chat.search", "chat.search"], ["chat.search"], "all"))

    def test_unknown_signal_match_mode_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported signal_match_mode"):
            CHECKER.signals_match([], [], "not-a-mode")

    def test_report_is_explicitly_not_a_failure_diagnosis(self) -> None:
        matrix = {"scenarios": [{"id": "no-runs", "signals": ["chat.search"]}]}
        result = CHECKER.report(matrix, Path("/dev/null"), Path("/fictional/no-runs"), 1, "baseline")
        self.assertFalse(result["all_expected_signals_matched"])
        self.assertIn("NeMo Insights", result["interpretation"])

    def test_select_scenarios_rejects_unknown_id(self) -> None:
        matrix = {"scenarios": [{"id": "present", "signals": []}]}
        with self.assertRaisesRegex(ValueError, "unknown scenario IDs"):
            CHECKER.select_scenarios(matrix, {"missing"})

    def test_malformed_trace_error_is_a_status_not_reflected_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atif = root / "case-trial-01" / "relay" / "atif"
            atif.mkdir(parents=True)
            atif.joinpath("trace.json").write_text(json.dumps({
                "schema_version": "ATIF-v1.7",
                "steps": [{"tool_calls": [{"function_name": "tool-with-private-error-text"}]}],
            }))
            result = CHECKER.trial_report({"id": "case", "signals": []}, 1, root)
        self.assertEqual(result, {"case_id": "case-trial-01", "trial": 1, "status": "unreadable_atif"})
