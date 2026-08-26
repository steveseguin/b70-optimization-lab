#!/usr/bin/env python3
"""Focused tests for the frozen Qwen3.8 Q8_0-weights/Q8_0-KV estimate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = REPO_ROOT / "tools/qwen38_q8weights_q8kv_estimator_v1.py"
OUTPUT_PATH = REPO_ROOT / "data/qwen38-q8weights-q8kv-tp1-context-estimate-v1.json"
SPEC = importlib.util.spec_from_file_location("qwen38_q8weights_q8kv_estimator_v1", ENGINE_PATH)
assert SPEC and SPEC.loader
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


class EstimateSnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.generated = ENGINE.build_snapshot()
        self.saved = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    def test_saved_snapshot_is_exact_regeneration(self) -> None:
        self.assertEqual(self.saved, self.generated)

    def test_scope_and_grades_are_fail_closed(self) -> None:
        self.assertEqual(self.generated["state"], "estimated")
        self.assertEqual(self.generated["classification"], "estimated-not-measured")
        self.assertEqual(self.generated["grades"]["evidence"]["grade"], "D")
        self.assertEqual(self.generated["grades"]["optimization_maturity"]["state"], "unassessed")
        selectors = self.generated["selectors"]
        self.assertEqual(
            (selectors["tp"], selectors["mtp"], selectors["graph_mode"], selectors["kv"]),
            (1, 0, "off", "q8_0"),
        )
        self.assertEqual(
            [point["active_context_tokens"] for point in self.generated["points"]],
            ENGINE.DEPTHS,
        )

    def test_intervals_are_wider_than_same_runtime_donor_envelope(self) -> None:
        for point in self.generated["points"]:
            result = point["decode_tok_s"]
            anchor = point["target_f16_anchor"]["decode_tok_s"]
            ratios = result["donor_ratios"]
            donor_low = anchor * min(ratios["ud_q5_k_s"], ratios["ud_q4_k_xl"])
            donor_high = anchor * max(ratios["ud_q5_k_s"], ratios["ud_q4_k_xl"])
            self.assertLess(result["lower"], donor_low)
            self.assertGreater(result["upper"], donor_high)
            self.assertLessEqual(result["lower"], result["estimate"])
            self.assertLessEqual(result["estimate"], result["upper"])

    def test_frozen_endpoint_values(self) -> None:
        self.assertEqual(self.generated["points"][0]["decode_tok_s"]["estimate"], 19.579373)
        self.assertEqual(self.generated["points"][-1]["decode_tok_s"]["estimate"], 11.04457)

    def test_no_measurement_or_promotion_authority(self) -> None:
        authority = self.generated["authority"]
        self.assertEqual(authority["estimated_cells"], 7)
        self.assertEqual(authority["measured_cells"], 0)
        self.assertEqual(authority["quality_cells"], 0)
        self.assertFalse(authority["promotion"])
        self.assertFalse(authority["headline"])
        self.assertFalse(authority["protected_value_replacement"])
        self.assertFalse(authority["localmaxxing_submission"])

    def test_engine_and_source_hashes_are_frozen(self) -> None:
        self.assertEqual(self.generated["engine"]["sha256"], hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest())
        for source in self.generated["sources"]:
            actual = hashlib.sha256((REPO_ROOT / source["path"]).read_bytes()).hexdigest()
            self.assertEqual(source["sha256"], actual)


if __name__ == "__main__":
    unittest.main()
