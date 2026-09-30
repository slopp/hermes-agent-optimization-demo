import unittest

from scripts.normalize_insights_trace_bundle import _source_prompt


class NormalizeInsightsTraceBundleTest(unittest.TestCase):
    def test_reads_atof_prompt_without_runtime_context_fallback(self) -> None:
        self.assertEqual(_source_prompt({"prompt": "Original request"}), "Original request")

    def test_prefers_canonical_task_text_when_present(self) -> None:
        self.assertEqual(
            _source_prompt({"task_text": "Canonical request", "prompt": "Other"}),
            "Canonical request",
        )


if __name__ == "__main__":
    unittest.main()
