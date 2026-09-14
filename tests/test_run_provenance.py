import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("write_run_provenance", ROOT / "scripts" / "write_run_provenance.py")
PROVENANCE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PROVENANCE)


class RunProvenanceTest(unittest.TestCase):
    def test_records_hashes_but_not_sensitive_or_content_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            fixture = directory / "world.json"
            profile = directory / "profile.md"
            config = directory / "config.yaml"
            fixture.write_text('{"world_version":"v1"}\n')
            profile.write_text("fictional profile\n")
            config.write_text("model: fictional\n")
            result = PROVENANCE.build_provenance(
                fixture=fixture,
                profile=profile,
                config=config,
                hermes_revision="abc123",
                arm="baseline",
                provider="nvidia",
                model="nvidia/fake-model",
                base_url="",
                tool_catalog="extended",
                ignore_rules=True,
                wall_timeout_seconds=180,
                collection_mode="local-hermes",
                inference_route="hub-test",
                collected_at="2026-09-11T00:00:00Z",
            )
        serialized = json.dumps(result)
        self.assertEqual(result["schema_version"], "run-provenance-v1")
        self.assertEqual(result["harness"]["hermes_revision"], "abc123")
        self.assertTrue(result["harness"]["ignore_rules"])
        self.assertEqual(result["harness"]["wall_timeout_seconds"], 180)
        self.assertEqual(result["collection"]["mode"], "local-hermes")
        self.assertEqual(result["collection"]["inference_route"], "hub-test")
        self.assertEqual(result["inference"]["base_url"], "provider-managed")
        self.assertNotIn("NVIDIA_API_KEY", serialized)
        self.assertNotIn("fictional profile", serialized)
        self.assertNotIn("model: fictional", serialized)

    def test_requires_real_input_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing"
            with self.assertRaisesRegex(ValueError, "fixture file is missing"):
                PROVENANCE.build_provenance(
                    fixture=missing,
                    profile=missing,
                    config=missing,
                    hermes_revision="abc",
                    arm="baseline",
                    provider="nvidia",
                    model="model",
                    base_url="",
                    tool_catalog="extended",
                    ignore_rules=True,
                    wall_timeout_seconds=180,
                    collection_mode="local-hermes",
                    inference_route="build",
                )
