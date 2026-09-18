import unittest

from scripts.materialize_eval_author_tasks import _test_script


class EvalAuthorVerifierTest(unittest.TestCase):
    def test_verifier_emits_current_per_check_evidence(self) -> None:
        script = _test_script()
        self.assertIn("python - <<'PY' > /logs/verifier/results", script)
        self.assertIn('check_id = "answer-" + key.replace("_", "-")', script)
        self.assertIn("\\t{'PASS' if passed else 'FAIL'}", script)
        self.assertIn("/logs/verifier/reward.txt", script)
