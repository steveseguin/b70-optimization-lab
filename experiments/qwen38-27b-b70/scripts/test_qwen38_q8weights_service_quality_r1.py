#!/usr/bin/env python3
"""CPU-only contract checks for the frozen Q8 service-quality campaign."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8weights-f16-tp1-service-quality-r1-prereg.json"
RUNNER = ROOT / "experiments/qwen38-27b-b70/scripts/run-qwen38-q8weights-f16-tp1-service-quality-r1.sh"
RESULT = ROOT / "experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-service-quality-20260825-r1"


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

    def test_committed_result_satisfies_every_frozen_gate(self) -> None:
        quality = json.loads((RESULT / "quality.json").read_text(encoding="utf-8"))
        qualification = json.loads(
            (RESULT / "qualification.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            qualification["classification"], "service-quality-qualified"
        )
        self.assertTrue(all(qualification["checks"].values()))
        self.assertEqual(qualification["response_count"], 16)
        self.assertEqual(qualification["cached_tokens"], [0] * 16)
        self.assertTrue(quality["pass_all"])
        self.assertEqual(len(quality["exact_cases"]), 7)
        self.assertTrue(all(row["pass"] for row in quality["exact_cases"]))
        self.assertEqual(quality["repeat_case"]["repeats"], 8)
        self.assertEqual(len(quality["repeat_case"]["unique_hashes"]), 1)
        self.assertTrue(quality["long_context_case"]["pass"])
        self.assertEqual(quality["long_context_case"]["actual_prompt_tokens"], 7617)


if __name__ == "__main__":
    unittest.main()
