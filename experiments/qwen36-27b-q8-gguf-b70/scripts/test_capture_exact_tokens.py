#!/usr/bin/env python3
"""Offline unit tests for exact-token alignment and timing accounting."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("capture-exact-tokens.py")
SPEC = importlib.util.spec_from_file_location("capture_exact_tokens", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"could not load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExactTokenMetricTests(unittest.TestCase):
    def test_primary_uses_99_intervals(self) -> None:
        offsets = [index * 0.05 for index in range(100)]
        metric = MODULE.interval_metric(
            offsets, 0, 99, "tok_s_1_100_intervals_after_ttft"
        )
        self.assertEqual(metric["event_count"], 100)
        self.assertEqual(metric["interval_count"], 99)
        self.assertEqual(metric["numerator"], 99)
        self.assertAlmostEqual(metric["duration_s"], 4.95)
        self.assertAlmostEqual(metric["tok_s"], 20.0)

    def test_full_window_uses_511_intervals(self) -> None:
        offsets = [0.2 + index * 0.04 for index in range(512)]
        metric = MODULE.interval_metric(
            offsets, 0, 511, "tok_s_1_512_intervals_after_ttft"
        )
        self.assertEqual(metric["event_count"], 512)
        self.assertEqual(metric["interval_count"], 511)
        self.assertEqual(metric["numerator"], 511)
        self.assertAlmostEqual(metric["tok_s"], 25.0)

    def test_missing_full_endpoint_fails_closed(self) -> None:
        offsets = [index * 0.05 for index in range(512)]
        offsets[511] = None
        metric = MODULE.interval_metric(
            offsets, 0, 511, "tok_s_1_512_intervals_after_ttft"
        )
        self.assertEqual(metric["event_count"], 0)
        self.assertEqual(metric["interval_count"], 0)
        self.assertIsNone(metric["duration_s"])
        self.assertIsNone(metric["tok_s"])

    def test_unique_alignment_recovers_one_suppressed_event(self) -> None:
        complete = [10, 20, 30, 40, 50]
        streamed = [10, 20, 40, 50]
        self.assertEqual(
            MODULE.unique_subsequence_positions(complete, streamed), [0, 1, 3, 4]
        )

    def test_ambiguous_alignment_is_rejected(self) -> None:
        self.assertIsNone(MODULE.unique_subsequence_positions([1, 1, 2], [1, 2]))


class TokenIdValidationTests(unittest.TestCase):
    def test_only_nonempty_integer_lists_are_token_lists(self) -> None:
        self.assertTrue(MODULE.is_nonempty_token_id_list([0, 1, 2]))
        for value in (
            [],
            [True, 1],
            [1, False],
            [1.0, 2],
            ["1", 2],
            "not-a-list",
            None,
        ):
            with self.subTest(value=value):
                self.assertFalse(MODULE.is_nonempty_token_id_list(value))


class PairedContextSuiteTests(unittest.TestCase):
    def test_selected_band_is_materialized_with_calibration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite = root / "suite.json"
            builder = root / "builder.py"
            suite.write_text(
                json.dumps(
                    {
                        "suite_id": "paired-v1",
                        "pairs": [
                            {
                                "band": "middle",
                                "cases": [
                                    {
                                        "id": "a",
                                        "value": "alpha",
                                        "calibrated_prompt_tokens": 17,
                                    },
                                    {
                                        "id": "b",
                                        "value": "beta",
                                        "calibrated_prompt_tokens": 19,
                                    },
                                ],
                            }
                        ],
                    }
                )
            )
            builder.write_text("def make_prompt(case): return 'prompt-' + case['value']\n")
            meta, prompts = MODULE.load_prompts(suite, builder, "middle")
        self.assertEqual(meta["selected_band"], "middle")
        self.assertEqual(
            prompts,
            [
                {
                    "id": "a",
                    "prompt": "prompt-alpha",
                    "calibrated_prompt_tokens": 17,
                },
                {
                    "id": "b",
                    "prompt": "prompt-beta",
                    "calibrated_prompt_tokens": 19,
                },
            ],
        )


class OracleGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [{"prompt_id": "a"}, {"prompt_id": "b"}]
        self.oracle = {
            "intrinsic_gate": {"passed": True},
            "oracle_comparison": {"status": "BASELINE_CAPTURE_READY"},
            "rows": [
                {
                    "prompt_id": prompt_id,
                    "token_ids": [1, 2],
                    "content_sha256": f"content-{prompt_id}",
                    "rendered_prompt_sha256": f"prompt-{prompt_id}",
                }
                for prompt_id in ("a", "b")
            ],
        }

    def test_valid_baseline_oracle_passes(self) -> None:
        self.assertTrue(MODULE.oracle_baseline_valid(self.oracle, self.rows))

    def test_failed_duplicate_or_incomplete_oracle_is_rejected(self) -> None:
        for mutation in ("failed", "duplicate", "incomplete", "boolean-token"):
            with self.subTest(mutation=mutation):
                oracle = copy.deepcopy(self.oracle)
                if mutation == "failed":
                    oracle["intrinsic_gate"]["passed"] = False
                elif mutation == "duplicate":
                    oracle["rows"][1]["prompt_id"] = "a"
                elif mutation == "boolean-token":
                    oracle["rows"][1]["token_ids"][0] = True
                else:
                    oracle["rows"][1].pop("token_ids")
                self.assertFalse(MODULE.oracle_baseline_valid(oracle, self.rows))

    def test_longer_generation_must_preserve_sealed_prefix(self) -> None:
        current = [
            {
                "prompt_id": row["prompt_id"],
                "rendered_prompt_sha256": row["rendered_prompt_sha256"],
                "token_ids": row["token_ids"] + [3, 4, 5],
            }
            for row in self.oracle["rows"]
        ]
        passed, results = MODULE.compare_prefix_oracle(self.oracle, current)
        self.assertTrue(passed)
        self.assertTrue(all(row["token_prefix_exact"] for row in results))
        current[1]["token_ids"][0] = 99
        passed, _ = MODULE.compare_prefix_oracle(self.oracle, current)
        self.assertFalse(passed)

    def test_boolean_oracle_token_cannot_equal_integer_token(self) -> None:
        oracle = copy.deepcopy(self.oracle)
        oracle["rows"][0]["token_ids"][0] = True
        current = [
            {
                "prompt_id": row["prompt_id"],
                "rendered_prompt_sha256": row["rendered_prompt_sha256"],
                "token_ids": [1, 2, 3],
            }
            for row in self.oracle["rows"]
        ]
        self.assertFalse(MODULE.oracle_baseline_valid(oracle, current))
        passed, _ = MODULE.compare_prefix_oracle(oracle, current)
        self.assertFalse(passed)


class PromptProcessingGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = {
            "stream_prompt_n": 4096,
            "stream_prompt_ms": 1234.5,
            "stream_prompt_per_second": 4096 * 1000.0 / 1234.5,
            "service_prompt_tok_s_to_first_token": 301.2,
        }

    def test_complete_positive_finite_fields_pass(self) -> None:
        self.assertTrue(MODULE.full_512_prompt_processing_valid(self.row))

    def test_missing_or_invalid_fields_fail(self) -> None:
        invalid_values = (None, 0, -1, float("nan"), float("inf"), "100")
        for field in self.row:
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    row = copy.deepcopy(self.row)
                    row[field] = value
                    self.assertFalse(MODULE.full_512_prompt_processing_valid(row))
        row = copy.deepcopy(self.row)
        row["stream_prompt_n"] = 4096.0
        self.assertFalse(MODULE.full_512_prompt_processing_valid(row))

    def test_reported_prompt_rate_must_match_local_arithmetic(self) -> None:
        row = copy.deepcopy(self.row)
        row["stream_prompt_per_second"] *= 1.01
        self.assertFalse(MODULE.full_512_prompt_processing_valid(row))

    def test_computed_prompt_rate(self) -> None:
        self.assertAlmostEqual(
            MODULE.computed_prompt_tok_s(4096, 1234.5),
            4096 * 1000.0 / 1234.5,
        )
        for prompt_n, prompt_ms in (
            (True, 1000.0),
            (0, 1000.0),
            (1, True),
            (1, 0.0),
            (1, float("inf")),
        ):
            with self.subTest(prompt_n=prompt_n, prompt_ms=prompt_ms):
                self.assertIsNone(MODULE.computed_prompt_tok_s(prompt_n, prompt_ms))


class Post512CanaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tokens = list(range(128))
        self.content = "known canary output"
        self.rendered = "<|im_start|>user\nknown prompt<|im_end|>"
        self.prepared = {
            "prompt_id": "incident-retrospective",
            "prompt_sha256": "raw-prompt-sha",
            "expected": {
                "rendered_prompt_sha256": MODULE.hashlib.sha256(
                    self.rendered.encode()
                ).hexdigest(),
                "token_ids": self.tokens,
                "content": self.content,
            },
        }
        self.response = {
            "tokens": self.tokens,
            "content": self.content,
            "id_slot": 0,
            "stop_type": "limit",
            "truncated": False,
            "timings": {"cache_n": 0, "predicted_n": 128},
        }

    def test_exact_uncached_slot_zero_canary_passes(self) -> None:
        result = MODULE.analyze_post_512_canary(
            self.prepared, self.rendered, self.response
        )
        self.assertTrue(result["passed"])
        self.assertTrue(all(result["checks"].values()))

    def test_any_required_canary_drift_fails(self) -> None:
        mutations = {
            "rendered": lambda rendered, response: (rendered + " drift", response),
            "tokens": lambda rendered, response: (
                rendered,
                {**response, "tokens": [999, *self.tokens[1:]]},
            ),
            "content": lambda rendered, response: (
                rendered,
                {**response, "content": "drift"},
            ),
            "slot": lambda rendered, response: (
                rendered,
                {**response, "id_slot": 1},
            ),
            "stop": lambda rendered, response: (
                rendered,
                {**response, "stop_type": "eos"},
            ),
            "truncated": lambda rendered, response: (
                rendered,
                {**response, "truncated": True},
            ),
            "cache": lambda rendered, response: (
                rendered,
                {**response, "timings": {"cache_n": 1, "predicted_n": 128}},
            ),
            "predicted": lambda rendered, response: (
                rendered,
                {**response, "timings": {"cache_n": 0, "predicted_n": 127}},
            ),
            "boolean-token": lambda rendered, response: (
                rendered,
                {**response, "tokens": [True, *self.tokens[1:]]},
            ),
            "boolean-slot": lambda rendered, response: (
                rendered,
                {**response, "id_slot": False},
            ),
            "boolean-cache": lambda rendered, response: (
                rendered,
                {**response, "timings": {"cache_n": False, "predicted_n": 128}},
            ),
            "boolean-predicted": lambda rendered, response: (
                rendered,
                {**response, "timings": {"cache_n": 0, "predicted_n": True}},
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                rendered, response = mutate(
                    self.rendered, copy.deepcopy(self.response)
                )
                result = MODULE.analyze_post_512_canary(
                    self.prepared, rendered, response
                )
                self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
