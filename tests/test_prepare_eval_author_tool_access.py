import unittest

from scripts.prepare_eval_author_tool_access import build_decisions


class EvalAuthorToolAccessTest(unittest.TestCase):
    def test_offline_candidate_selects_no_source_tool_access(self) -> None:
        result = build_decisions(
            {"tools": [{"tool_id": "tool-1", "name": "mail.search"}]}
        )
        self.assertEqual(
            result["schema"],
            "nemo.eval_author.trace_environment_tool_access_decisions.v1",
        )
        self.assertEqual(result["decisions"][0]["access"], "none")
        self.assertIsNone(result["decisions"][0]["adapter"])
        self.assertIn("offline world", result["decisions"][0]["note"])
