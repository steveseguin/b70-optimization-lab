#!/usr/bin/env python3
"""Verify every published Q4_K_M context marker against retained evidence."""

from pathlib import Path
import json
import unittest


REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / "packages/qwen38-27b-q4km-tp1-b70/package.json"
EVIDENCE = REPO / "experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.json"


class Qwen38Q4kmPackageProfilesTest(unittest.TestCase):
    def test_profiles_are_exact_evidence_arrays(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        profiles = {item["id"]: item for item in package["performance_profiles"]}
        expected = {
            "decode-f16-kv-vs-context-depth": evidence["decode_tg128_tok_s"]["kv_f16"],
            "prefill-f16-kv-vs-context-depth": evidence["prefill_pp2048_tok_s"]["kv_f16"],
            "decode-q8-kv-vs-context-depth": evidence["decode_tg128_tok_s"]["kv_q8_0"],
            "prefill-q8-kv-vs-context-depth": evidence["prefill_pp2048_tok_s"]["kv_q8_0"],
        }
        self.assertEqual(set(profiles), set(expected))
        for profile_id, values in expected.items():
            points = profiles[profile_id]["points"]
            self.assertEqual([p["context_tokens"] for p in points], evidence["depths"])
            self.assertEqual([p["value"] for p in points], values)
            self.assertEqual([p["samples"] for p in points], [5] * len(values))
            self.assertIn("no point is interpolated or extrapolated", profiles[profile_id]["scope"])


if __name__ == "__main__":
    unittest.main()
