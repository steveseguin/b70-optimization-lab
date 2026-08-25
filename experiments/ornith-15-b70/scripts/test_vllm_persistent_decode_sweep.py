#!/usr/bin/env python3
"""CPU-only contract tests for the persistent vLLM decode sweep."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("vllm-persistent-decode-sweep.py")


def load_module():
    spec = importlib.util.spec_from_file_location("persistent_decode_sweep", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PersistentDecodeSweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_compare_request_tokens_reports_exact_and_first_mismatch(self) -> None:
        result = self.module.compare_request_tokens(
            [[10, 11, 12], [20, 21, 22], [30, 31]],
            [[10, 11, 12], [20, 99, 22], [30, 31, 32]],
        )
        self.assertEqual(
            result,
            {
                "identical_requests": 1,
                "requests": 3,
                "first_mismatch_token_index": [None, 1, 2],
                "mismatch_token_counts": [0, 1, 1],
            },
        )

    def test_oracle_entry_retains_tokens_only_when_requested(self) -> None:
        arm = {
            "generated_output_tokens": 3,
            "elapsed_s": 1.5,
            "decode_window_s": 1.0,
            "median_per_request_decode_tok_s": 2.0,
            "request_token_ids_sha256": ["digest"],
        }
        compact = self.module.oracle_entry(
            request_index=4,
            arm=arm,
            request_token_ids=[[7, 8, 9]],
            record_token_ids=False,
        )
        detailed = self.module.oracle_entry(
            request_index=4,
            arm=arm,
            request_token_ids=[[7, 8, 9]],
            record_token_ids=True,
        )
        self.assertNotIn("token_ids", compact)
        self.assertEqual(detailed["token_ids"], [7, 8, 9])
        self.assertEqual(compact["request_index"], detailed["request_index"])
        self.assertEqual(compact["request_index"], 4)
        self.assertEqual(compact["token_ids_sha256"], "digest")
        self.assertEqual(detailed["token_ids_sha256"], "digest")

    def test_prompt_ids_are_repeatable_and_request_distinct(self) -> None:
        first = self.module.make_prompt_token_ids(
            request_index=0, token_count=128, vocab_size=151936, seed=20260825
        )
        repeat = self.module.make_prompt_token_ids(
            request_index=0, token_count=128, vocab_size=151936, seed=20260825
        )
        second = self.module.make_prompt_token_ids(
            request_index=1, token_count=128, vocab_size=151936, seed=20260825
        )
        self.assertEqual(first, repeat)
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 128)
        self.assertEqual(len(second), 128)
        self.assertTrue(all(1024 <= token < 151936 for token in first + second))


if __name__ == "__main__":
    unittest.main()
