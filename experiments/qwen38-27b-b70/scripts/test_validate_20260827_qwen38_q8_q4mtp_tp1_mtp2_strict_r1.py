from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate-20260827-qwen38-q8-q4mtp-tp1-mtp2-strict-r1.py")
SPEC = importlib.util.spec_from_file_location("q8_mtp2_strict", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Q8Mtp2StrictResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = MODULE.build_result("fixture-time")

    def test_qualified_value_and_gain(self) -> None:
        self.assertEqual(self.result["status"], "strict-package-headline-qualified")
        self.assertAlmostEqual(self.result["metric"]["value"], 37.06202846372931)
        self.assertAlmostEqual(self.result["matched_mtp0_control"]["value_tok_s"], 19.58259717754693)
        self.assertGreater(self.result["matched_mtp0_control"]["mtp2_gain_percent"], 89.0)
        self.assertLess(self.result["metric"]["attempt_relative_range_percent"], 1.2)

    def test_quality_and_scope_are_fail_closed(self) -> None:
        self.assertEqual(
            self.result["qualification"]["complete_mtp2_token_arrays_exact_to_matched_mtp0"],
            "24/24",
        )
        authority = self.result["publication_authority"]
        self.assertTrue(authority["single_user_short_context_headline"])
        self.assertFalse(authority["context_curve"])
        self.assertFalse(authority["concurrency_curve"])
        self.assertFalse(authority["interpolation_or_extrapolation"])


if __name__ == "__main__":
    unittest.main()
