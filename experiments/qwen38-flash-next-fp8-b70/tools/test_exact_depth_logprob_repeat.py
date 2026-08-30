#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("run-exact-depth-logprob-repeat.py")
SPEC = importlib.util.spec_from_file_location("q38_logprob_repeat", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class LogprobRepeatTest(unittest.TestCase):
    def test_normalize_step(self) -> None:
        row = MODULE.normalize_logprob_step(
            {
                "tokens": ["token_id:7"],
                "token_logprobs": [-0.25],
                "top_logprobs": [{"token_id:7": -0.25, "token_id:9": -1.5}],
            },
            7,
        )
        self.assertTrue(row["selected_is_top1"])
        self.assertEqual(row["top1_token_id"], 7)
        self.assertEqual(row["top1_top2_logprob_margin"], 1.25)

    def test_selected_not_top1_is_reported(self) -> None:
        row = MODULE.normalize_logprob_step(
            {
                "tokens": ["token_id:7"],
                "token_logprobs": [-2.0],
                "top_logprobs": [{"token_id:9": -0.5, "token_id:7": -2.0}],
            },
            7,
        )
        self.assertFalse(row["selected_is_top1"])

    def test_malformed_token_placeholder_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.parse_token_placeholder("decoded text")

    def test_first_diff(self) -> None:
        self.assertEqual(MODULE.first_diff([1, 2, 3], [1, 4, 3]), 1)
        self.assertEqual(MODULE.first_diff([1, 2], [1, 2, 3]), 2)
        self.assertIsNone(MODULE.first_diff([1, 2], [1, 2]))


if __name__ == "__main__":
    unittest.main()
