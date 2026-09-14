import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("validate_intake_bindings", ROOT / "scripts" / "validate_intake_bindings.py")
BINDINGS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BINDINGS)


class IntakeBindingsTest(unittest.TestCase):
    def _make_bundle(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, dict]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "traces" / "baseline").mkdir(parents=True)
        trace = root / "traces" / "baseline" / "one.atof.jsonl"
        trace.write_text('{"fictional":true}\n')
        manifest = {
            "traces": [
                {
                    "trace_id": "baseline-one",
                    "path": "traces/baseline/one.atof.jsonl",
                    "sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
                }
            ]
        }
        manifest_path = root / "traces" / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        return temp, root, manifest_path, manifest

    def test_accepts_binding_to_locked_checked_in_trace(self) -> None:
        temp, root, manifest_path, manifest = self._make_bundle()
        self.addCleanup(temp.cleanup)
        bindings = {
            "schema_version": "intake-bindings-v1",
            "trace_manifest_path": "traces/manifest.json",
            "trace_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "workspace": "fictional-workspace",
            "agent_name": "Hermes-PA-style-mock",
            "bindings": [
                {
                    "trace_id": "baseline-one",
                    "trace_sha256": manifest["traces"][0]["sha256"],
                    "intake_trace_ref": "intake://trace-123",
                }
            ],
        }
        self.assertEqual(BINDINGS.validate(bindings, manifest, manifest_path, root), [])

    def test_rejects_unknown_or_stale_trace_binding(self) -> None:
        temp, root, manifest_path, manifest = self._make_bundle()
        self.addCleanup(temp.cleanup)
        bindings = {
            "schema_version": "intake-bindings-v1",
            "trace_manifest_path": "traces/manifest.json",
            "trace_manifest_sha256": "stale",
            "workspace": "fictional-workspace",
            "agent_name": "Hermes-PA-style-mock",
            "bindings": [
                {"trace_id": "not-in-manifest", "trace_sha256": "wrong", "intake_trace_ref": "intake://trace-123"}
            ],
        }
        errors = BINDINGS.validate(bindings, manifest, manifest_path, root)
        self.assertIn("trace_manifest_sha256 does not match the supplied manifest", errors)
        self.assertIn("binding references unknown trace_id: 'not-in-manifest'", errors)
