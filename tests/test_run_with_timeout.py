import sys
import time
import unittest

from scripts.run_with_timeout import TIMEOUT_EXIT, run


class RunWithTimeoutTest(unittest.TestCase):
    def test_returns_child_exit_code(self) -> None:
        self.assertEqual(run([sys.executable, "-c", "raise SystemExit(7)"], seconds=2), 7)

    def test_terminates_a_hung_child_with_standard_timeout_exit(self) -> None:
        started = time.monotonic()
        result = run([sys.executable, "-c", "import time; time.sleep(20)"], seconds=1, grace_seconds=1)
        self.assertEqual(result, TIMEOUT_EXIT)
        self.assertLess(time.monotonic() - started, 4)
