#!/usr/bin/env python3
"""Regression tests for LocalMaxxing metric-accounting preflight."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "submit_localmaxxing_results.py"
SPEC = importlib.util.spec_from_file_location("localmaxxing_submit", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def queue_item(metric_name: str, accounting: str) -> dict:
    return {
        "label": "metric-accounting-test",
        "payload": {
            "promptTokens": 10,
            "outputTokens": 100,
            "engineFlags": {
                "commandSnippet": "test-server --model test",
                "apiKvCacheDtype": "auto",
                "apiAttentionBackend": "flash_attn",
                "realisticSuiteGatePassed": True,
                "realisticSuiteCachedTokensAllZero": True,
                "realisticSuiteId": "test-v1",
                "realisticPromptTokenCounts": [10],
                "realisticOutputTokenCounts": [100],
                "primaryMetricName": metric_name,
                "primaryMetricAccounting": accounting,
                "primaryMetricAggregation": "median-of-prompt-class-medians",
                "metricWindowGeneratedTokens": 100,
                "metricWindowIntervals": 99,
            },
        },
    }


class LocalMaxxingMetricAccountingTest(unittest.TestCase):
    def test_conventional_interval_metric_passes(self) -> None:
        item = queue_item(
            "median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft",
            "inter-token-intervals",
        )
        self.assertEqual(MODULE.preflight_payload(item), [])

    def test_legacy_inclusive_event_metric_is_blocked(self) -> None:
        item = queue_item(
            "median_tok_s_1_100_after_ttft",
            "legacy-inclusive-events",
        )
        problems = MODULE.preflight_payload(item)
        self.assertTrue(any("primaryMetricName" in problem for problem in problems))
        self.assertTrue(
            any("primaryMetricAccounting" in problem for problem in problems)
        )

    def test_api_projection_preserves_full_offload_and_mtp_identity(self) -> None:
        flags = queue_item(
            "median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft",
            "inter-token-intervals",
        )["payload"]["engineFlags"]
        flags.update(
            {
                "gpuLayers": -1,
                "mtpEnabled": True,
                "specMethod": "draft-mtp",
                "specNumTokens": 3,
                "specDecoding": True,
                "targetModelVerifiedAcceptedTokens": True,
            }
        )

        projected = MODULE.api_engine_flags(flags)

        self.assertEqual(projected["gpuLayers"], -1)
        self.assertTrue(projected["mtpEnabled"])
        self.assertTrue(projected["specDecoding"])
        self.assertEqual(projected["specMethod"], "draft-mtp")
        self.assertEqual(projected["specNumTokens"], 3)
        self.assertIn(
            '"targetModelVerifiedAcceptedTokens": true',
            projected["extraFlags"],
        )


if __name__ == "__main__":
    unittest.main()
