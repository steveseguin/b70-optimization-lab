from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run-neural-download-stock-headline-attempt.sh"
PREREG = ROOT / "data/2026-08-27-neural-download-stock-headline-closure-prereg.json"


class StockHeadlineRunnerTest(unittest.TestCase):
    def test_preregistration_closes_the_strict_contract(self) -> None:
        value = json.loads(PREREG.read_text())
        self.assertEqual(value["required_attempts"], 2)
        contract = value["fixed_contract"]
        self.assertEqual(contract["prompt_count"], 12)
        self.assertEqual(contract["prompt_classes"], 6)
        self.assertEqual(contract["max_output_tokens"], 512)
        self.assertEqual(contract["metric_intervals"], 99)
        self.assertFalse(contract["prompt_cache"])
        joined = " ".join(value["qualification"])
        self.assertIn("All 12 complete streamed token-ID arrays", joined)

    def test_runner_is_fail_closed_and_cache_free(self) -> None:
        text = RUNNER.read_text()
        for required in (
            "verify-neural-download-model.py",
            "--api-mode native-raw",
            "--max-tokens 512",
            "--return-token-ids",
            "--require-natural-eos",
            "--no-cache-prompt",
            "--cache-ram 0",
            "--ctx-checkpoints 0",
            "cached_tokens_all_zero",
            "canaries[\"pass_all\"]",
            "repository must be clean",
            "main must be pushed before execution",
        ):
            self.assertIn(required, text)

    def test_only_registered_profiles_are_accepted(self) -> None:
        prereg = json.loads(PREREG.read_text())
        text = RUNNER.read_text()
        for profile in prereg["profiles"]:
            self.assertIn(f"{profile})", text)
        self.assertIn("unregistered PROFILE_ID", text)


if __name__ == "__main__":
    unittest.main()
