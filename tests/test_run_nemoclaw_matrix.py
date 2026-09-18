import unittest

from scripts.run_nemoclaw_matrix import terminal_failure


class NemoClawMatrixRunnerTests(unittest.TestCase):
    def test_detects_hermes_terminal_error_returned_with_exit_zero(self) -> None:
        response = 'API call failed after 3 retries: HTTP 429: {"status":429}'

        self.assertEqual(terminal_failure(response), "api call failed after")

    def test_accepts_normal_answer(self) -> None:
        self.assertIsNone(terminal_failure("The security packet is missing."))


if __name__ == "__main__":
    unittest.main()
