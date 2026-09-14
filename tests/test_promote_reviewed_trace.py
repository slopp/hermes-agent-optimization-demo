import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.validate_trace_manifest import validate


PROJECT_ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("promote_reviewed_trace", PROJECT_ROOT / "scripts" / "promote_reviewed_trace.py")
PROMOTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PROMOTER)


class PromoteReviewedTraceTest(unittest.TestCase):
    def _source_run(self, root: Path) -> Path:
        source = root / "source-run"
        (source / "relay" / "atof").mkdir(parents=True)
        (source / "relay" / "atof" / "one.jsonl").write_text('{"fictional": true}\n')
        (source / "collection-provenance.json").write_text(
            json.dumps(
                {
                    "schema_version": "run-provenance-v1",
                    "harness": {
                        "arm": "baseline",
                        "profile_sha256": "profile-hash",
                        "hermes_revision": "abc123",
                        "tool_catalog": "extended",
                    },
                    "inference": {"model": "nvidia/fake"},
                    "collection": {"mode": "local-hermes", "inference_route": "hub-test"},
                }
            )
        )
        return source

    def test_promotion_requires_explicit_review_and_creates_valid_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "fixtures").mkdir()
            (root / "fixtures" / "world-v1.json").write_text('{"world_version":"v1"}\n')
            source = self._source_run(root)
            previous_root = PROMOTER.ROOT
            previous_argv = sys.argv
            self.addCleanup(setattr, PROMOTER, "ROOT", previous_root)
            self.addCleanup(setattr, sys, "argv", previous_argv)
            PROMOTER.ROOT = root
            sys.argv = [
                "promote_reviewed_trace.py",
                "--source-run", str(source),
                "--trace-id", "baseline-case-1",
                "--case-id", "case-1",
                "--run-id", "baseline-build-abc123",
                "--reviewer", "fictional-reviewer",
                "--approve-fictional-content",
            ]
            self.assertEqual(PROMOTER.main(), 0)
            manifest = json.loads((root / "traces" / "manifest.json").read_text())
            self.assertEqual(validate(manifest, root), [])
            self.assertEqual(manifest["runs"][0]["agent_runtime"], "local-hermes")

    def test_promotion_refuses_without_review_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "fixtures").mkdir()
            (root / "fixtures" / "world-v1.json").write_text('{}\n')
            source = self._source_run(root)
            previous_root = PROMOTER.ROOT
            previous_argv = sys.argv
            self.addCleanup(setattr, PROMOTER, "ROOT", previous_root)
            self.addCleanup(setattr, sys, "argv", previous_argv)
            PROMOTER.ROOT = root
            sys.argv = [
                "promote_reviewed_trace.py", "--source-run", str(source), "--trace-id", "trace", "--case-id", "case", "--run-id", "run", "--reviewer", "reviewer"
            ]
            with self.assertRaisesRegex(SystemExit, "approve-fictional-content"):
                PROMOTER.main()
