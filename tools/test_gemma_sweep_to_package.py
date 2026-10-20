"""Guard against substituting requested lengths for measured graph coordinates."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gemma_sweep", ROOT / "tools/gemma4-26b-sweep-to-package.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GemmaSweepPointsTest(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((ROOT / "data/profiles/2026-10-10/gemma-sweep/single-16k-draft3.json").read_text())

    def test_actual_axis_matches_all_receipts_and_retains_requests(self):
        points = MODULE.ctx_points(self.source, "prefill_tps")
        self.assertEqual([p["context_tokens"] for p in points], [292, 509, 2042, 8185, 15793])
        self.assertEqual([p["requested_context_tokens"] for p in points], [300, 512, 2048, 8192, 15800])
        self.assertNotIn(512, [p["context_tokens"] for p in points])
        for point in points:
            row = self.source["single"][str(point["requested_context_tokens"])]
            self.assertEqual({r["prompt_n"] for r in row["runs"]}, {point["context_tokens"]})

    def test_mixed_actual_lengths_fail_instead_of_using_summary_count(self):
        self.source["single"]["512"]["runs"][0]["prompt_n"] = 510
        with self.assertRaisesRegex(ValueError, "repeats do not share"):
            MODULE.ctx_points(self.source, "prefill_tps")

    def test_duplicate_measured_coordinates_fail(self):
        self.source["single"]["513"] = copy.deepcopy(self.source["single"]["512"])
        with self.assertRaisesRegex(ValueError, "duplicate actual"):
            MODULE.ctx_points(self.source, "prefill_tps")

    def test_package_context_curves_match_current_extractor(self):
        package = json.loads((ROOT / "packages/gemma4-26b-a4b-q8-b70/package.json").read_text())
        for profile in package["performance_profiles"]:
            if not profile["id"].startswith("sweep-") or profile.get("x_metric") != "context_tokens":
                continue
            field, scale = {"prefill": ("prefill_tps", 1), "decode": ("decode_tps", 1), "ttft": ("ttft_s", 1000)}[profile["metric"]]
            receipt = json.loads((ROOT / profile["evidence"]).read_text())
            self.assertEqual(profile["points"], MODULE.ctx_points(receipt, field, scale))


if __name__ == "__main__":
    unittest.main()
