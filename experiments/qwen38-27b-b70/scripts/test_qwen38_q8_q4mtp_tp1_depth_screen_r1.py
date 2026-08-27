from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PREREG = ROOT / "experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-depth-screen-r1-prereg.json"
RUNNER = ROOT / "experiments/qwen38-27b-b70/scripts/run-20260827-qwen38-q8-q4mtp-tp1-screen-attempt.sh"
AMENDMENT = ROOT / "experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-depth-screen-r1-control-amendment.json"


class Qwen38Q8Q4MtpDepthScreenTest(unittest.TestCase):
    def test_prereg_is_screen_only_and_target_exact(self) -> None:
        value = json.loads(PREREG.read_text(encoding="utf-8"))
        self.assertEqual(value["screen"]["depths"], [1, 2])
        self.assertTrue(value["screen"]["complete_target_oracle_parity_required"])
        self.assertIn("No one-server screen value", value["decision_rule"]["screen_only"])
        self.assertIn("No result transfers to 32K", value["decision_rule"]["no_transfer"])

    def test_runner_is_fail_closed_and_cold_suite_only(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")
        for required in (
            "--return-token-ids",
            "--require-natural-eos",
            "--no-cache-prompt",
            "--slot-prompt-similarity 0",
            "target_oracle_exact_prompts",
            "drafted > 0 and accepted > 0",
            "repository must be clean",
        ):
            self.assertIn(required, text)
        self.assertNotIn("--prompt-id", text)
        self.assertNotIn("cache_prompt\":true", text)

    def test_post_screen_control_cannot_change_winner(self) -> None:
        value = json.loads(AMENDMENT.read_text(encoding="utf-8"))
        self.assertEqual(value["authorized_addition"]["arm"], "mtp0-matched-control")
        self.assertIn("cannot select or alter", value["decision_boundary"]["purpose"])
        self.assertIn("12/12", value["authorized_addition"]["required_output"])


if __name__ == "__main__":
    unittest.main()
