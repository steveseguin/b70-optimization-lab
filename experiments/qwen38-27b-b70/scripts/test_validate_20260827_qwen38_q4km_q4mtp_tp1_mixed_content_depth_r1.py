from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name(
    "validate-20260827-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1.py"
)
SPEC = importlib.util.spec_from_file_location("mixed_content_result", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MixedContentResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = MODULE.build_result("fixture-time")

    def test_all_quality_and_publication_gates(self) -> None:
        self.assertEqual(self.result["status"], "passed")
        self.assertEqual(self.result["quality"]["mtp2_target_exact_cases"], 36)
        self.assertEqual(self.result["quality"]["request_gate_passes"], 54)
        self.assertFalse(
            self.result["publication_authority"]["single_user_headline_replacement"]
        )
        self.assertFalse(
            self.result["publication_authority"]["natural_task_or_retrieval_claim"]
        )

    def test_every_point_has_two_servers_and_three_classes(self) -> None:
        self.assertEqual(
            [row["active_context_tokens"] for row in self.result["points"]],
            list(MODULE.DEPTHS),
        )
        for row in self.result["points"]:
            self.assertEqual(row["fresh_servers"], 2)
            self.assertEqual(row["content_classes"], 3)
            self.assertEqual(row["target_exact_cases"], 6)
            self.assertLess(row["decode_relative_range_percent"], 1.0)

    def test_32k_value_is_measured_aggregate(self) -> None:
        row = self.result["points"][-1]
        self.assertAlmostEqual(row["decode_tok_s"], 36.50506489804035)
        self.assertAlmostEqual(row["ttft_ms"], 39538.43021352077)
        self.assertGreater(row["decode_speedup_vs_control_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()
