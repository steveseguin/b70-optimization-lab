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
    def test_native_cache_field_accepts_current_and_old_llama_names(self) -> None:
        self.assertEqual(
            MODULE._BASE.native_cached_tokens({"timings": {"cache_n": 0}}), 0
        )
        self.assertEqual(
            MODULE._BASE.native_cached_tokens({"prompt_tokens_cached": 3}), 3
        )
        self.assertIsNone(MODULE._BASE.native_cached_tokens({"tokens_cached": 170}))
        self.assertIsNone(MODULE._BASE.native_cached_tokens({}))

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

    def test_request_id_prefix_uses_shared_safe_encoding(self) -> None:
        self.assertEqual(
            MODULE._BASE.safe_request_id("candidate lane / R2"),
            "candidate-lane-R2",
        )

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

    def test_summary_prefers_complete_token_ids_over_text_chunks(self) -> None:
        oracle = {
            "a": {
                "sha256": "oracle-text",
                "completion_tokens": 3,
                "token_ids": [10, 11, 12],
            }
        }
        rows = [{
            "prompt_id": "a",
            "sha256": "different-streamed-text",
            "completion_tokens": 3,
            "token_ids": [10, 11, 12],
            "tok_s_wall_full": 10.0,
            "usage": {"prompt_tokens_details": {"cached_tokens": 0}},
        }]
        summary = MODULE.summarize_batch(
            concurrency=1,
            repeat=1,
            elapsed_s=1.0,
            rows=rows,
            oracle_by_id=oracle,
        )
        self.assertTrue(summary["oracle_exact_all"])
        self.assertTrue(summary["complete_token_id_identity_all"])
        self.assertEqual(
            summary["oracle_identity_methods"], ["complete_token_ids"]
        )

    def test_incomplete_token_ids_do_not_bypass_text_identity(self) -> None:
        matched, method = MODULE.output_identity_match(
            {
                "sha256": "batch",
                "completion_tokens": 3,
                "token_ids": [10, 11],
            },
            {
                "sha256": "oracle",
                "completion_tokens": 3,
                "token_ids": [10, 11, 12],
            },
        )
        self.assertFalse(matched)
        self.assertEqual(method, "text_sha256")

    def test_complete_token_ids_match_compact_digest(self) -> None:
        token_ids = [10, 11, 12]
        matched, method = MODULE.output_identity_match(
            {"completion_tokens": 3, "token_ids": token_ids},
            {
                "completion_tokens": 3,
                "token_ids_sha256": MODULE.token_ids_sha256(token_ids),
            },
        )
        self.assertTrue(matched)
        self.assertEqual(method, "complete_token_ids_sha256")

    def test_base_prompt_id_removes_only_concurrency_variant_suffix(self) -> None:
        self.assertEqual(MODULE.base_prompt_id("cache-c031"), "cache")
        self.assertEqual(MODULE.base_prompt_id("cache"), "cache")


if __name__ == "__main__":
    unittest.main()
