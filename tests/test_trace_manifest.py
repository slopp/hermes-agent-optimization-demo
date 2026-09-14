import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.validate_trace_manifest import validate


class TraceManifestTest(unittest.TestCase):
    def _make_root(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "fixtures").mkdir()
        (root / "traces" / "baseline").mkdir(parents=True)
        (root / "traces" / "provenance").mkdir(parents=True)
        (root / "fixtures" / "world-v1.json").write_text('{"world_version":"v1"}')
        (root / "traces" / "baseline" / "trace-1.atof.jsonl").write_text('{"fictional":true}\n')
        (root / "traces" / "provenance" / "baseline.json").write_text('{"schema_version":"run-provenance-v1"}\n')
        return temp, root

    def test_complete_manifest_with_locked_fixture_and_trace_is_valid(self) -> None:
        temp, root = self._make_root()
        self.addCleanup(temp.cleanup)
        fixture = root / "fixtures" / "world-v1.json"
        trace = root / "traces" / "baseline" / "trace-1.atof.jsonl"
        provenance = root / "traces" / "provenance" / "baseline.json"
        manifest = {
            "schema_version": "1.2",
            "collection_status": "complete",
            "fixture": {"path": "fixtures/world-v1.json", "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()},
            "runs": [{"id": "baseline", "agent_runtime": "Hermes/OpenShell", "agent_revision": "abc123", "harness_profile": "baseline", "model": "test-model", "sampling": {}, "relay_format": "ATOF", "tool_catalog": "extended", "provenance_path": "traces/provenance/baseline.json", "provenance_sha256": hashlib.sha256(provenance.read_bytes()).hexdigest()}],
            "public_data_review": {"approved": True, "reviewer": "fictional-reviewer", "reviewed_at": "2026-09-11T00:00:00Z"},
            "traces": [{"trace_id": "trace-1", "case_id": "case-1", "run_id": "baseline", "path": "traces/baseline/trace-1.atof.jsonl", "sha256": hashlib.sha256(trace.read_bytes()).hexdigest()}],
        }
        self.assertEqual(validate(manifest, root), [])

    def test_complete_manifest_requires_public_review(self) -> None:
        temp, root = self._make_root()
        self.addCleanup(temp.cleanup)
        fixture = root / "fixtures" / "world-v1.json"
        provenance = root / "traces" / "provenance" / "baseline.json"
        manifest = {
            "schema_version": "1.2",
            "collection_status": "complete",
            "fixture": {"path": "fixtures/world-v1.json", "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()},
            "runs": [{"id": "baseline", "agent_runtime": "Hermes/OpenShell", "agent_revision": "abc123", "harness_profile": "baseline", "model": "test-model", "sampling": {}, "relay_format": "ATOF", "tool_catalog": "extended", "provenance_path": "traces/provenance/baseline.json", "provenance_sha256": hashlib.sha256(provenance.read_bytes()).hexdigest()}],
            "public_data_review": {"approved": False},
            "traces": [],
        }
        self.assertIn("complete collection requires public_data_review.approved=true", validate(manifest, root))

    def test_accepts_explicitly_normalized_atif_run_format(self) -> None:
        temp, root = self._make_root()
        self.addCleanup(temp.cleanup)
        fixture = root / "fixtures" / "world-v1.json"
        trace = root / "traces" / "baseline" / "trace-1.atof.jsonl"
        provenance = root / "traces" / "provenance" / "baseline.json"
        manifest = {
            "schema_version": "1.2",
            "collection_status": "pending",
            "fixture": {"path": "fixtures/world-v1.json", "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()},
            "runs": [{"id": "baseline", "agent_runtime": "Hermes/OpenShell", "agent_revision": "0.20.6", "harness_profile": "baseline", "model": "test-model", "sampling": {}, "relay_format": "ATOF-normalized-ATIF-v1.7", "tool_catalog": "extended", "provenance_path": "traces/provenance/baseline.json", "provenance_sha256": hashlib.sha256(provenance.read_bytes()).hexdigest()}],
            "public_data_review": {"approved": False},
            "traces": [{"trace_id": "trace-1", "case_id": "case-1", "run_id": "baseline", "path": "traces/baseline/trace-1.atof.jsonl", "sha256": hashlib.sha256(trace.read_bytes()).hexdigest()}],
        }

        self.assertEqual(validate(manifest, root), [])

    def test_rejects_trace_path_outside_repository(self) -> None:
        temp, root = self._make_root()
        self.addCleanup(temp.cleanup)
        fixture = root / "fixtures" / "world-v1.json"
        provenance = root / "traces" / "provenance" / "baseline.json"
        manifest = {
            "schema_version": "1.2",
            "collection_status": "pending",
            "fixture": {"path": "fixtures/world-v1.json", "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()},
            "runs": [{"id": "baseline", "agent_runtime": "Hermes/OpenShell", "agent_revision": "abc123", "harness_profile": "baseline", "model": "test-model", "sampling": {}, "relay_format": "ATOF", "tool_catalog": "extended", "provenance_path": "traces/provenance/baseline.json", "provenance_sha256": hashlib.sha256(provenance.read_bytes()).hexdigest()}],
            "public_data_review": {"approved": False},
            "traces": [{"trace_id": "bad", "case_id": "case", "run_id": "baseline", "path": "../outside.atof.jsonl", "sha256": "not-a-real-hash"}],
        }
        self.assertIn("trace path must be repository-relative for bad", validate(manifest, root))
