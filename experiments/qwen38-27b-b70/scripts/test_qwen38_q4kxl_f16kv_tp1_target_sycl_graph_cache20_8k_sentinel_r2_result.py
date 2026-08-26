#!/usr/bin/env python3
"""Focused inert tests for the Q4_K_XL cache20 R2 result validator."""

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
VALIDATOR = HERE / "validate-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-result.py"


def load():
    spec = importlib.util.spec_from_file_location("q4kxl_cache20_r2_result", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ResultValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load()

    def test_frozen_counter_conservation(self):
        text = (
            "[SYCL-GRAPH] summary device=0 requested=146 compatibility_rejected=0 "
            "device_unsupported=0 cache_entries=20 cache_limit=20 cache_hit=126 "
            "cache_miss=20 cache_full=0 direct_replay=126 recorded=20 created=20 "
            "updated=0 recreated=0 replayed=146"
        )
        match = self.validator.SUMMARY_RE.search(text)
        self.assertIsNotNone(match)
        row = {key: int(value) for key, value in match.groupdict().items()}
        self.assertEqual(row["requested"], row["cache_hit"] + row["cache_miss"])
        self.assertEqual(row["requested"], row["replayed"])
        self.assertEqual(row["cache_hit"], row["direct_replay"])
        self.assertEqual(row["cache_miss"], row["created"])

    def test_actual_hash_bound_result(self):
        if not self.validator.DEFAULT_ROOT.is_dir():
            self.skipTest("external raw root is not mounted")
        result = self.validator.validate(
            self.validator.DEFAULT_ROOT, self.validator.DEFAULT_RECEIPT
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["raw_files_verified"], 16)
        self.assertLess(result["graph_on_relative_percent"], 0)
        self.assertEqual(result["terminal_authority"]["site_cells"], 0)
        self.assertTrue(result["terminal_authority"]["full_curve_preregistration"])

    def test_authority_widening_fails_closed(self):
        if not self.validator.DEFAULT_ROOT.is_dir():
            self.skipTest("external raw root is not mounted")
        receipt = json.loads(self.validator.DEFAULT_RECEIPT.read_text(encoding="utf-8"))
        widened = copy.deepcopy(receipt)
        widened["terminal_authority"]["site_cells"] = 1
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "widened.json"
            path.write_text(json.dumps(widened), encoding="utf-8")
            with self.assertRaisesRegex(self.validator.ValidationError, "authority"):
                self.validator.validate(self.validator.DEFAULT_ROOT, path)


if __name__ == "__main__":
    unittest.main()
