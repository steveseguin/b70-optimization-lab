#!/usr/bin/env python3
"""Regression tests for realistic-suite event/interval accounting."""

from __future__ import annotations

import importlib.util
import json
import math
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "qualify_realistic_window_metrics.py"
SPEC = importlib.util.spec_from_file_location("realistic_window_qualifier", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

BENCH_SCRIPT = Path(__file__).parents[1] / "bench-openai-realistic-suite.py"
BENCH_SPEC = importlib.util.spec_from_file_location(
    "realistic_suite_bench", BENCH_SCRIPT
)
if BENCH_SPEC is None or BENCH_SPEC.loader is None:
    raise RuntimeError(f"cannot load {BENCH_SCRIPT}")
BENCH_MODULE = importlib.util.module_from_spec(BENCH_SPEC)
BENCH_SPEC.loader.exec_module(BENCH_MODULE)


class EventWindowRateTest(unittest.TestCase):
    def test_one_hundred_events_span_ninety_nine_intervals(self) -> None:
        offsets = [index * 0.01 for index in range(100)]
        legacy, conventional = MODULE.event_window_rates(offsets, 100)
        self.assertTrue(math.isclose(legacy, 100 / 0.99))
        self.assertTrue(math.isclose(conventional, 100.0))
        self.assertTrue(math.isclose(conventional / legacy, 0.99))
        bench_legacy, bench_conventional = BENCH_MODULE.event_window_rates(
            offsets, 100
        )
        self.assertTrue(math.isclose(bench_legacy, legacy))
        self.assertTrue(math.isclose(bench_conventional, conventional))

    def test_insufficient_or_degenerate_window_is_unscored(self) -> None:
        self.assertEqual(MODULE.event_window_rates([0.0] * 99, 100), (None, None))
        self.assertEqual(MODULE.event_window_rates([1.0] * 100, 100), (None, None))
        self.assertEqual(MODULE.event_window_rates([0.0], 1), (None, None))

    def test_class_balancing_prevents_row_count_weighting(self) -> None:
        rows = [
            {
                "prompt_class": "code",
                "tok_s_1_100_intervals_after_ttft": value,
            }
            for value in (10.0, 10.0, 10.0, 10.0)
        ] + [
            {
                "prompt_class": "prose",
                "tok_s_1_100_intervals_after_ttft": 30.0,
            }
        ]
        result = MODULE.class_balanced_stats(rows)
        self.assertEqual(result["median"], 20.0)
        self.assertEqual(result["count"], 2)
        self.assertEqual(
            result["aggregation"], "median-of-prompt-class-medians"
        )


class PromotionGateTest(unittest.TestCase):
    def failures(self, **overrides):
        values = {
            "screening_passed": True,
            "selected_prompt_ids": [],
            "completed_prompt_count": 12,
            "suite_prompt_count": 12,
            "max_tokens": 512,
            "metric_tokens": 100,
            "completion_counts": [512] * 12,
            "ignore_eos": False,
            "prompt_classes": [
                "operations", "code", "prose", "code", "operations",
                "analysis", "analysis", "operations", "documentation",
                "structured-writing", "analysis", "prose",
            ],
        }
        values.update(overrides)
        return BENCH_MODULE.promotion_gate_failures(**values)

    def test_complete_full_512_suite_is_eligible(self) -> None:
        self.assertEqual(self.failures(), [])

    def test_128_token_run_can_never_be_final(self) -> None:
        failures = self.failures(
            max_tokens=128,
            completion_counts=[128] * 12,
        )
        self.assertIn("max_tokens_must_equal_512", failures)

    def test_short_metric_window_can_never_be_final(self) -> None:
        failures = self.failures(metric_tokens=50)
        self.assertIn("metric_window_must_equal_100_events", failures)

    def test_short_suite_can_never_be_final(self) -> None:
        failures = self.failures(
            completed_prompt_count=6,
            suite_prompt_count=6,
            completion_counts=[512] * 6,
            prompt_classes=[
                "operations", "code", "prose", "analysis",
                "documentation", "structured-writing",
            ],
        )
        self.assertIn("fixed_suite_has_fewer_than_12_prompts", failures)

    def test_filtered_prompt_can_never_be_final(self) -> None:
        failures = self.failures(
            selected_prompt_ids=["benchmark-analysis"],
            completed_prompt_count=1,
        )
        self.assertIn("prompt_subset_selected", failures)
        self.assertIn("fixed_suite_incomplete", failures)

    def test_natural_eos_after_metric_window_is_eligible(self) -> None:
        failures = self.failures(completion_counts=[512] * 11 + [270])
        self.assertEqual(failures, [])

    def test_completion_before_metric_window_fails(self) -> None:
        failures = self.failures(completion_counts=[512] * 11 + [99])
        self.assertEqual(
            failures,
            ["every_completion_must_cover_100_event_metric"],
        )

    def test_ignore_eos_cannot_be_enabled_for_promotion(self) -> None:
        self.assertEqual(
            self.failures(ignore_eos=True),
            ["ignore_eos_must_be_disabled"],
        )

    def test_one_easy_prompt_class_repeated_cannot_be_promoted(self) -> None:
        self.assertEqual(
            self.failures(prompt_classes=["prose"] * 12),
            ["fixed_suite_lacks_varied_prompt_classes"],
        )


class RecentEvidenceRegressionTest(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[2]

    def failures(self, relative_path: str) -> list[str]:
        data = json.loads((self.ROOT / relative_path).read_text(encoding="utf-8"))
        return MODULE.promotion_evidence_failures(MODULE.qualify(data))

    def qualified(self, relative_path: str) -> dict:
        data = json.loads((self.ROOT / relative_path).read_text(encoding="utf-8"))
        return MODULE.qualify(data)

    def test_fp8_128_cap_evidence_stays_rejected(self) -> None:
        failures = self.failures(
            "experiments/qwen38-27b-b70/data/"
            "qwen38-fp8-w8a16-mtp8-realistic-cold-20260827/r1/"
            "realistic-suite.json"
        )
        self.assertIn("requested_output_tokens_not_512", failures)

    def test_qwen_q4_full_suite_stays_eligible(self) -> None:
        self.assertEqual(
            self.failures(
                "experiments/qwen38-27b-b70/data/"
                "2026-08-21-q4km-tp1-gpu0-final-j.json"
            ),
            [],
        )

    def test_qwen_q4_class_balanced_median_is_reproducible(self) -> None:
        data = self.qualified(
            "experiments/qwen38-27b-b70/data/"
            "2026-08-21-q4km-tp1-gpu0-final-j.json"
        )
        value = data["summary"][
            "class_balanced_tok_s_1_100_intervals_after_ttft"
        ]["median"]
        self.assertTrue(math.isclose(value, 27.825725650072858))

    def test_gemma_full_suite_stays_eligible(self) -> None:
        self.assertEqual(
            self.failures(
                "data/gemma4-q8-gpu3-finalpostnorm-on-full512-"
                "20260630T024027Z-finalpost-full512/realistic-suite.json"
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
