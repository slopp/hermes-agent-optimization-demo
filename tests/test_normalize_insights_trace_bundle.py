import unittest

from scripts.normalize_insights_trace_bundle import convert


class NormalizeInsightsTraceBundleTest(unittest.TestCase):
    def test_catalog_keeps_mock_schema_without_scoring_redacted_runtime_args(self) -> None:
        trace = {
            "id": "trace-1",
            "attributes": {
                "logical_case_id": "source-coverage",
                "prompt": "Find evidence",
                "final_answer": "Done",
                "tool_catalog": {
                    "terminal": {
                        "type": "object",
                        "required": ["command"],
                        "properties": {"command": {"type": "str"}},
                    }
                },
            },
            "root_spans": [
                {"kind": "TOOL", "tool_name": "terminal", "id": "one"},
                {
                    "kind": "TOOL",
                    "tool_name": "mcp__enterprise_world__chat_search",
                    "id": "two",
                },
            ],
        }
        result = convert(trace, collection="test", ordinal=1)
        catalog = result["extra"]["tool_catalog"]

        self.assertEqual(catalog["terminal"], {})
        self.assertEqual(
            catalog["mcp__enterprise_world__chat_search"]["required"], ["query"]
        )


if __name__ == "__main__":
    unittest.main()
