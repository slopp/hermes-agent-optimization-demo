import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SUITE_SPEC = importlib.util.spec_from_file_location("validate_trace_derived_suite", ROOT / "scripts" / "validate_trace_derived_suite.py")
SUITE_MODULE = importlib.util.module_from_spec(SUITE_SPEC)
assert SUITE_SPEC.loader is not None
sys.modules[SUITE_SPEC.name] = SUITE_MODULE
SUITE_SPEC.loader.exec_module(SUITE_MODULE)
SPEC = importlib.util.spec_from_file_location("validate_candidate_experiment", ROOT / "scripts" / "validate_candidate_experiment.py")
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = CHECKER
SPEC.loader.exec_module(CHECKER)


class CandidateExperimentTest(unittest.TestCase):
    def test_validates_frozen_suite_and_exact_case_sets(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            directory = Path(temporary)
            suite_path = directory / "suite.json"
            suite = {
                "suite_version": "1.1",
                "generation": {"method": "nemo-eval-author-library-runner", "insight_ref": "insights://one", "review_status": "approved", "reviewer": "reviewer", "frozen_at": "2026-09-11T00:00:00Z"},
                "cases": [
                    {"id": "derived", "case_kind": "trace_derived", "provenance": {"trace_refs": ["intake://one"], "eval_author_case_ref": "one"}},
                    {"id": "held", "case_kind": "held_out", "provenance": {"held_out_from_case_ids": ["derived"], "eval_author_case_ref": "two"}},
                ],
            }
            suite_path.write_text(json.dumps(suite))
            profile = directory / "candidate.md"
            profile.write_text("narrow candidate")
            card = directory / "card.md"
            card.write_text("Status: `eval-frozen`\n")
            relative = lambda path: str(path.relative_to(ROOT))
            manifest = {
                "schema_version": "candidate-experiment-v1", "status": "approved_for_test", "insight_ref": "insights://one", "reviewer": "reviewer", "approved_at": "2026-09-11T00:00:00Z",
                "trace_derived_suite_path": relative(suite_path), "trace_derived_suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
                "candidate_profile_path": relative(profile), "candidate_profile_sha256": hashlib.sha256(profile.read_bytes()).hexdigest(),
                "pattern_card_path": relative(card), "case_ids": {"trace_derived": ["derived"], "held_out": ["held"]},
            }
            self.assertEqual(CHECKER.validate(manifest, suite, suite_path), [])

    def test_rejects_case_set_that_omits_held_out_variant(self) -> None:
        # The full success path above establishes the other required fields; an
        # incomplete manifest must not look ready merely because it has an Insight.
        suite = {"suite_version": "1.1", "generation": {"method": "nemo-eval-author-library-runner", "insight_ref": "insights://one", "review_status": "approved", "reviewer": "r", "frozen_at": "now"}, "cases": [{"id": "d", "case_kind": "trace_derived", "provenance": {"trace_refs": ["intake://d"], "eval_author_case_ref": "d"}}, {"id": "h", "case_kind": "held_out", "provenance": {"held_out_from_case_ids": ["d"], "eval_author_case_ref": "h"}}]}
        errors = CHECKER.validate({"schema_version": "candidate-experiment-v1", "status": "approved_for_test", "reviewer": "r", "approved_at": "now", "insight_ref": "insights://one", "case_ids": {"trace_derived": ["d"], "held_out": []}}, suite, ROOT / "evals" / "trace-derived-suite.template.json")
        self.assertIn("case_ids.held_out must exactly match the frozen suite's held_out cases", errors)
