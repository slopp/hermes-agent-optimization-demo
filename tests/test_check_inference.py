import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("check_inference_hub", ROOT / "scripts" / "check_inference_hub.py")
CHECKER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECKER)


class CheckInferenceTest(unittest.TestCase):
    def test_timeout_defaults_and_is_bounded(self) -> None:
        self.assertEqual(CHECKER.request_timeout(None), 45)
        self.assertEqual(CHECKER.request_timeout("1"), 1)
        self.assertEqual(CHECKER.request_timeout("60"), 60)

    def test_timeout_rejects_invalid_values(self) -> None:
        for value in ("0", "61", "none"):
            with self.assertRaises(ValueError):
                CHECKER.request_timeout(value)
