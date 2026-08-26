#!/usr/bin/env python3
"""Focused inert tests for the cache20 R2 offline recovery validator."""

import importlib.util
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
VALIDATOR = HERE / "validate-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-offline-recovery.py"


def load():
    spec = importlib.util.spec_from_file_location("q5_cache20_offline_recovery", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class OfflineRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load()

    def test_frozen_counter_parser(self):
        text = (
            "[SYCL-GRAPH] summary device=0 requested=146 compatibility_rejected=0 "
            "device_unsupported=0 cache_entries=20 cache_limit=20 cache_hit=126 "
            "cache_miss=20 cache_full=0 direct_replay=126 recorded=20 created=20 "
            "updated=0 recreated=0 replayed=146"
        )
        match = self.validator.SUMMARY_RE.search(text)
        self.assertIsNotNone(match)
        row = {key: int(value) for key, value in match.groupdict().items()}
        self.assertEqual(row["cache_limit"], 20)
        self.assertEqual(row["cache_hit"], row["direct_replay"])
        self.assertEqual(row["requested"], row["cache_hit"] + row["cache_miss"])
        self.assertEqual(row["requested"], row["replayed"])

    def test_actual_hash_bound_recovery(self):
        if not self.validator.DEFAULT_ROOT.is_dir():
            self.skipTest("external raw root is not mounted")
        result = self.validator.validate(
            self.validator.DEFAULT_ROOT, self.validator.DEFAULT_RECEIPT
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["raw_files_verified"], 13)
        self.assertEqual(result["authority"]["site_cells"], 0)
        self.assertTrue(result["authority"]["full_curve_preregistration"])


if __name__ == "__main__":
    unittest.main()
