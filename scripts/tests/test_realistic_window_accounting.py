#!/usr/bin/env python3
"""Regression tests for realistic-suite event/interval accounting."""

from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
