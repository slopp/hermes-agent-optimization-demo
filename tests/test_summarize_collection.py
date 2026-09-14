import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("summarize_collection", ROOT / "scripts" / "summarize_collection.py")
SUMMARY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = SUMMARY
SPEC.loader.exec_module(SUMMARY)


class SummarizeCollectionTest(unittest.TestCase):
    def test_summary_never_copies_prompt_answer_or_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = root / "case-1"
            atif_dir = case / "relay" / "atif"
            atif_dir.mkdir(parents=True)
            atif_dir.joinpath("trace.json").write_text(json.dumps({
                "schema_version": "ATIF-v1.7",
                "session_id": "session-1",
                "steps": [{
                    "tool_calls": [{"function_name": "mcp__pa_style_enterprise__connectors_get_status", "arguments": {"connector": "crm"}}],
                    "message": "Sensitive fictional answer text",
                }],
            }))
            case.joinpath("collection-provenance.json").write_text(json.dumps({
                "collection": {"mode": "local-hermes", "inference_route": "hub-test"},
                "harness": {"tool_catalog": "extended", "ignore_rules": True},
            }))
            result = SUMMARY.summarize(root)
        encoded = json.dumps(result)
        self.assertEqual(result["extractable_case_count"], 1)
        self.assertIn("connectors.get_status", encoded)
        self.assertNotIn("Sensitive fictional answer text", encoded)
        self.assertNotIn('"connector": "crm"', encoded)

    def test_summary_does_not_copy_malformed_atif_error_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            atif_dir = root / "case-1" / "relay" / "atif"
            atif_dir.mkdir(parents=True)
            atif_dir.joinpath("trace.json").write_text(json.dumps({
                "schema_version": "ATIF-v1.7",
                "steps": [{"tool_calls": [{"function_name": "tool-with-private-error-text"}]}],
            }))
            result = SUMMARY.summarize(root)
        encoded = json.dumps(result)
        self.assertEqual(result["cases"][0]["status"], "unreadable_atif")
        self.assertNotIn("tool-with-private-error-text", encoded)
