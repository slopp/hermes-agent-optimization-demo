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
                "source_batch": "traces/eval-author-batch.json",
            },
            "cases": [
                {
                    "id": "case-1",
                    "case_kind": "trace_derived",
                    "provenance": {
                        "trace_ref": "traces/baseline/case-1.atif.json",
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

    def test_approved_suite_with_platform_provenance_is_valid(self) -> None:
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
        self.assertEqual(validate(suite), [])

    def test_optional_intake_binding_allowlist_rejects_unreviewed_trace(self) -> None:
        suite = {
            "suite_version": "1.1",
            "generation": {"method": "nemo-eval-author-library-runner", "insight_ref": "insights://one", "review_status": "approved", "reviewer": "reviewer", "frozen_at": "2026-09-11T00:00:00Z"},
            "cases": [{"id": "case", "case_kind": "trace_derived", "provenance": {"trace_refs": ["intake://unreviewed"], "eval_author_case_ref": "case-ref"}}],
        }
        self.assertIn(
            "case case references Intake traces not bound to the reviewed bundle: intake://unreviewed",
            validate(suite, {"intake://reviewed"}),
        )

    def test_pending_template_cannot_be_scored_as_trace_derived_suite(self) -> None:
        suite = {
            "suite_version": "1.1",
            "generation": {"method": "nemo-eval-author-library-runner", "insight_ref": "insights://id", "review_status": "pending"},
            "cases": [{"id": "case-1", "case_kind": "trace_derived", "provenance": {"trace_refs": ["intake://trace-1"], "eval_author_case_ref": "task-1"}}],
        }
        self.assertIn("trace-derived suite must be explicitly approved before use", validate(suite))

    def test_held_out_case_must_reference_a_trace_derived_parent(self) -> None:
        suite = {
            "suite_version": "1.1",
            "generation": {"method": "nemo-eval-author-library-runner", "insight_ref": "insights://id", "review_status": "approved", "reviewer": "reviewer", "frozen_at": "2026-09-11T00:00:00Z"},
            "cases": [{"id": "held-out", "case_kind": "held_out", "provenance": {"held_out_from_case_ids": ["missing"], "eval_author_case_ref": "task"}}],
        }
        self.assertIn("held-out case held-out needs existing held_out_from_case_ids", validate(suite))
