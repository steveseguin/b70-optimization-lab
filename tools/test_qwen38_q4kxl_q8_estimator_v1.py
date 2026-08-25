#!/usr/bin/env python3
"""Focused tests for the frozen Qwen3.8 UD-Q4_K_XL q8 estimate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = REPO_ROOT / "tools/qwen38_q4kxl_q8_estimator_v1.py"
OUTPUT_PATH = REPO_ROOT / "data/qwen38-q4kxl-q8-tp1-context-estimate-v1.json"
SPEC = importlib.util.spec_from_file_location("qwen38_q4kxl_q8_estimator_v1", ENGINE_PATH)
assert SPEC and SPEC.loader
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


class EstimateSnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.generated = ENGINE.build_snapshot()
        self.saved = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    def test_saved_snapshot_is_exact_regeneration(self) -> None:
        self.assertEqual(self.saved, self.generated)

    def test_scope_and_classification_are_fail_closed(self) -> None:
        self.assertEqual(self.generated["state"], "estimated")
        self.assertEqual(self.generated["classification"], "estimated-not-measured")
        self.assertEqual(self.generated["grade"], "D")
        self.assertEqual(self.generated["selectors"]["tp"], 1)
        self.assertEqual(self.generated["selectors"]["mtp"], 0)
        self.assertEqual(self.generated["selectors"]["graph"], "off")
        self.assertEqual(self.generated["selectors"]["kv"], "q8_0")
        self.assertEqual(
            [point["active_context_tokens"] for point in self.generated["points"]],
            ENGINE.DEPTHS,
        )

    def test_estimates_are_inside_donor_envelopes(self) -> None:
        for point in self.generated["points"]:
            result = point["decode_tok_s"]
            self.assertLessEqual(result["lower"], result["estimate"])
            self.assertLessEqual(result["estimate"], result["upper"])
            self.assertGreater(result["lower"], 0)
            self.assertEqual(point["prefill_tok_s"]["state"], "missing")

    def test_frozen_endpoint_values(self) -> None:
        self.assertEqual(self.generated["points"][0]["decode_tok_s"]["estimate"], 21.534223)
        self.assertEqual(self.generated["points"][-1]["decode_tok_s"]["estimate"], 9.756097)

    def test_engine_and_source_hashes_are_frozen(self) -> None:
        engine_hash = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
        self.assertEqual(self.generated["engine"]["sha256"], engine_hash)
        for source in self.generated["sources"]:
            actual = hashlib.sha256((REPO_ROOT / source["path"]).read_bytes()).hexdigest()
            self.assertEqual(source["sha256"], actual)


if __name__ == "__main__":
    unittest.main()
