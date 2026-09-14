import unittest

from scripts.validate_trace_derived_suite import validate


class TraceDerivedSuiteTest(unittest.TestCase):
    def test_local_trace_environment_suite_is_valid_without_platform(self) -> None:
        suite = {
            "suite_version": "2.0",
            "generation": {
                "method": "nemo-eval-author-trace-environment",
                "insight_refs": ["insights://standalone/finding"],
                "review_status": "agent_contextual_privacy_review_complete",
                "source_batch": "traces/world-v2/eval-author-batch.json",
            },
            "cases": [
                {
                    "id": "case-1",
                    "case_kind": "trace_derived",
                    "provenance": {
                        "trace_ref": "traces/world-v2/baseline/case-1.atif.json",
                        "eval_author_case_ref": ".eval-author/case-1",
                    },
                },
                {
                    "id": "case-1-held-out",
                    "case_kind": "held_out",
                    "provenance": {"held_out_from_case_ids": ["case-1"]},
                },
            ],
        }

        self.assertEqual(validate(suite), [])

    def test_legacy_platform_suite_is_rejected(self) -> None:
        suite = {
            "suite_version": "1.1",
            "generation": {
                "method": "nemo-eval-author-library-runner",
                "insight_ref": "insights://insight-123",
                "review_status": "approved",
                "reviewer": "reviewer@example.test",
                "frozen_at": "2026-09-11T12:00:00Z",
            },
            "cases": [
                {"id": "case-1", "case_kind": "trace_derived", "provenance": {"trace_refs": ["intake://trace-1"], "eval_author_case_ref": "task-1"}},
                {"id": "case-1-held-out", "case_kind": "held_out", "provenance": {"held_out_from_case_ids": ["case-1"], "eval_author_case_ref": "task-2"}},
            ],
        }
        self.assertIn("suite_version must be 2.0", validate(suite))

    def test_held_out_case_must_reference_a_trace_derived_parent(self) -> None:
        suite = {
            "suite_version": "2.0",
            "generation": {"method": "nemo-eval-author-trace-environment", "insight_refs": ["insights://id"], "review_status": "agent_contextual_privacy_review_complete", "source_batch": "traces/world-v2/eval-author-batch.json"},
            "cases": [{"id": "held-out", "case_kind": "held_out", "provenance": {"held_out_from_case_ids": ["missing"]}}],
        }
        self.assertIn("held-out case held-out needs existing held_out_from_case_ids", validate(suite))
