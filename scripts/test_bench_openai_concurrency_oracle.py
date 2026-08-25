#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PATH = Path(__file__).with_name("bench-openai-concurrency-oracle.py")
SPEC = importlib.util.spec_from_file_location("concurrency_oracle", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConcurrencyOracleTests(unittest.TestCase):
    def test_parse_counts_rejects_unsorted_or_duplicate(self) -> None:
        with self.assertRaises(Exception):
            MODULE.parse_counts("1,4,2")
        with self.assertRaises(Exception):
            MODULE.parse_counts("1,2,2")

    def test_expand_prompts_is_distinct_and_bounded(self) -> None:
        prompts = MODULE.expand_prompts([{"id": "a", "prompt": "hello"}], 3)
        self.assertEqual(len(prompts), 3)
        self.assertEqual(len({row["id"] for row in prompts}), 3)
        self.assertEqual(len({row["prompt"] for row in prompts}), 3)

    def test_summary_uses_batch_wall_and_per_prompt_oracle(self) -> None:
        oracle = {
            "a": {"sha256": "x"},
            "b": {"sha256": "y"},
        }
        rows = [
            {
                "prompt_id": "a",
                "sha256": "x",
                "completion_tokens": 100,
                "tok_s_wall_full": 10.0,
                "usage": {"prompt_tokens_details": {"cached_tokens": 0}},
            },
            {
                "prompt_id": "b",
                "sha256": "wrong",
                "completion_tokens": 100,
                "tok_s_wall_full": 20.0,
                "usage": {"prompt_tokens_details": {"cached_tokens": 0}},
            },
        ]
        summary = MODULE.summarize_batch(
            concurrency=2,
            repeat=1,
            elapsed_s=4.0,
            rows=rows,
            oracle_by_id=oracle,
        )
        self.assertEqual(summary["aggregate_tok_s_wall"], 50.0)
        self.assertEqual(summary["oracle_exact_count"], 1)
        self.assertFalse(summary["oracle_exact_all"])
        self.assertTrue(summary["cached_tokens_all_zero"])


if __name__ == "__main__":
    unittest.main()
