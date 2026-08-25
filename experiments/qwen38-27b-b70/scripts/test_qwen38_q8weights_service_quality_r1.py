#!/usr/bin/env python3
"""CPU-only contract checks for the frozen Q8 service-quality campaign."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8weights-f16-tp1-service-quality-r1-prereg.json"
RUNNER = ROOT / "experiments/qwen38-27b-b70/scripts/run-qwen38-q8weights-f16-tp1-service-quality-r1.sh"


class ServiceQualityContract(unittest.TestCase):
    def test_manifest_has_frozen_quality_boundary(self) -> None:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["service"]["weights"], "Q8_0")
        self.assertEqual(data["service"]["kv"], "F16 K and V")
        self.assertEqual(data["service"]["context_tokens"], 8192)
        self.assertEqual(data["service"]["parallel_slots"], 1)
        self.assertEqual(data["quality_gate"]["exact_cases_required"], "7/7")
        self.assertEqual(data["quality_gate"]["repeat_hash_required"], "8/8 one normalized hash")
        self.assertEqual(data["quality_gate"]["cached_tokens_required"], 0)
        self.assertIsNone(data["quality_gate"]["speed_floor"])

    def test_runner_is_create_only_and_fail_closed(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")
        for marker in (
            "requires_clean_pushed_main",
            "[[ ! -e \"${output}\" ]]",
            "MemoryMax=13G",
            "--cache-ram 0",
            "--ctx-checkpoints 0",
            "cached_tokens_explicit_zero",
            "service-quality-qualified",
        ):
            self.assertIn(marker, MANIFEST.read_text(encoding="utf-8") + text)


if __name__ == "__main__":
    unittest.main()
