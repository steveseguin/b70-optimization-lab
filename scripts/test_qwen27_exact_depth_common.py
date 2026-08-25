#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path
import unittest


SCRIPT = Path(__file__).with_name("qwen27_exact_depth_common.py")
SPEC = importlib.util.spec_from_file_location("qwen27_exact_depth_common", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)


class ExactDepthCommonTests(unittest.TestCase):
    def test_declared_depths_are_exact_and_bools_are_rejected(self) -> None:
        self.assertEqual(
            common.DECLARED_DEPTHS,
            (0, 2048, 4096, 8192, 16384, 24576, 32768),
        )
        for depth in common.DECLARED_DEPTHS:
            self.assertEqual(common.validate_depth(depth), depth)
        for invalid in (True, False, 2048.0, "2048", -1, 32000):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                common.validate_depth(invalid)

    def test_flat_token_validation_is_strict(self) -> None:
        self.assertEqual(common.validate_flat_token_ids([0, 7, 42]), (0, 7, 42))
        self.assertEqual(
            common.validate_flat_token_ids((1, 2), expected_count=2), (1, 2)
        )
        for invalid in ([1, True], [1, 2.0], [1, "2"], [1, [2]], [-1], "1,2"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                common.validate_flat_token_ids(invalid)
        with self.assertRaisesRegex(ValueError, "exactly 3"):
            common.validate_flat_token_ids([1, 2], expected_count=3)

    def test_canonical_hashes_ignore_object_order_but_not_array_order(self) -> None:
        left = {"z": 1, "a": [3, 2, 1], "unicode": "café"}
        right = {"unicode": "café", "a": [3, 2, 1], "z": 1}
        encoded = b'{"a":[3,2,1],"unicode":"caf\xc3\xa9","z":1}'
        expected = hashlib.sha256(encoded).hexdigest()
        self.assertEqual(common.canonical_json_bytes(left), encoded)
        self.assertEqual(common.canonical_json_sha256(left), expected)
        self.assertEqual(common.canonical_fixture_sha256(left), expected)
        self.assertEqual(common.canonical_payload_sha256(right), expected)
        self.assertNotEqual(
            common.canonical_json_sha256(left),
            common.canonical_json_sha256({**left, "a": [1, 2, 3]}),
        )
        for invalid in ({1: "bad"}, {"x": math.nan}, {"x": {1, 2}}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                common.canonical_json_sha256(invalid)

    def test_capacity_covers_depth_plus_128(self) -> None:
        for depth in common.DECLARED_DEPTHS:
            required = depth + common.COMPLETION_TOKEN_BUDGET
            self.assertEqual(common.validate_capacity(depth, required), required)
            with self.assertRaises(ValueError):
                common.validate_capacity(depth, required - 1)
        with self.assertRaises(ValueError):
            common.validate_capacity(2048, True)

    def test_interval_window_is_exactly_100_events_and_99_intervals(self) -> None:
        result = common.interval_window([index * 0.5 for index in range(100)])
        self.assertEqual(result["timestamped_events"], 100)
        self.assertEqual(result["inter_token_intervals"], 99)
        self.assertEqual(result["interval_numerator_tokens"], 99)
        self.assertEqual(result["duration_s"], 49.5)
        self.assertEqual(result["interval_tok_s"], 2.0)
        self.assertTrue(
            math.isclose(result["legacy_inclusive_event_tok_s"], 100 / 49.5)
        )
        for invalid in (
            [index * 0.5 for index in range(99)],
            [index * 0.5 for index in range(101)],
            [0.0] * 100,
            [*range(99), math.inf],
            [*range(99), True],
        ):
            with self.subTest(length=len(invalid)), self.assertRaises(ValueError):
                common.interval_window(invalid)

    def test_stats_use_packet_conventions(self) -> None:
        stats = common.summary_stats([1, 2, 3, 4, 5])
        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["p10"], 1.4)
        self.assertEqual(stats["median"], 3.0)
        self.assertEqual(stats["mean"], 3.0)
        self.assertEqual(stats["min"], 1.0)
        self.assertEqual(stats["max"], 5.0)
        self.assertTrue(math.isclose(stats["stdev"], math.sqrt(2.5)))
        self.assertEqual(common.summary_stats([])["count"], 0)
        with self.assertRaises(ValueError):
            common.summary_stats([1, math.nan])

    def test_exact_oracle_reports_first_token_or_length_divergence(self) -> None:
        exact = common.compare_exact_oracle([10, 20, 30], [10, 20, 30])
        self.assertTrue(exact["passed"])
        self.assertIsNone(exact["first_divergence_index"])
        self.assertEqual(exact["matching_prefix_count"], 3)
        self.assertEqual(
            exact["expected_token_ids_sha256"], exact["actual_token_ids_sha256"]
        )

        mismatch = common.compare_exact_oracle([10, 20, 30], [10, 21, 30])
        self.assertFalse(mismatch["passed"])
        self.assertEqual(mismatch["first_divergence_index"], 1)
        self.assertEqual(mismatch["matching_prefix_count"], 1)

        short = common.compare_exact_oracle([10, 20, 30], [10, 20])
        self.assertFalse(short["passed"])
        self.assertEqual(short["first_divergence_index"], 2)

    def test_metric_delta_is_strict_for_scalars_and_snapshots(self) -> None:
        self.assertEqual(common.metric_delta(2.5, 8), 5.5)
        self.assertEqual(
            common.metric_delta({"accepted": 5}, {"accepted": 17}, "accepted"),
            12.0,
        )
        with self.assertRaises(ValueError):
            common.metric_delta({}, {"accepted": 17}, "accepted")
        with self.assertRaises(ValueError):
            common.metric_delta(True, 2)

    def test_coverage_states_remain_distinct(self) -> None:
        expected = {
            "missing",
            "measured",
            "estimated",
            "closed",
            "quarantined",
            "unsupported",
        }
        self.assertEqual(common.ALLOWED_COVERAGE_STATES, expected)
        for state in expected:
            self.assertEqual(common.validate_coverage_state(state), state)
        for invalid in ("lab-measured", "closed-negative", "unknown", None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                common.validate_coverage_state(invalid)


if __name__ == "__main__":
    unittest.main()
