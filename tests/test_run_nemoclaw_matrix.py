import unittest

from scripts.run_nemoclaw_matrix import attempt_failed, retryable_failure, terminal_failure


class NemoClawMatrixRunnerTests(unittest.TestCase):
    def test_detects_hermes_terminal_error_returned_with_exit_zero(self) -> None:
        response = 'API call failed after 3 retries: HTTP 429: {"status":429}'

        self.assertEqual(terminal_failure(response), "api call failed after")

    def test_accepts_normal_answer(self) -> None:
        self.assertIsNone(terminal_failure("The security packet is missing."))

    def test_retries_nonzero_runtime_exit(self) -> None:
        self.assertTrue(retryable_failure(125, None))
        self.assertFalse(retryable_failure(124, None))
        self.assertFalse(retryable_failure(0, None))

    def test_timeout_is_failed_but_not_retryable(self) -> None:
        self.assertTrue(attempt_failed(124, None))
        self.assertFalse(retryable_failure(124, None))


if __name__ == "__main__":
    unittest.main()
