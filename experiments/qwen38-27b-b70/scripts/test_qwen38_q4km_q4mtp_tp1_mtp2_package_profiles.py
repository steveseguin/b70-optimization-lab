#!/usr/bin/env python3
"""Bind the published partial MTP2 context profiles to recovered raw evidence."""

from pathlib import Path
import json
import unittest


REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / "packages/qwen38-27b-q4km-mtp2-tp1-b70/package.json"
EVIDENCE = REPO / "experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-r2-result.json"


class Qwen38Q4Mtp2PackageProfilesTest(unittest.TestCase):
    def test_partial_context_profiles_include_only_target_exact_points(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        profiles = {item["id"]: item for item in package["performance_profiles"]}
        exact = [point for point in evidence["points"] if point["target_oracle_exact"]]
        self.assertEqual(evidence["status"], "failed-partial-2k-quarantined")
        self.assertEqual(evidence["quarantined_depths"], [2048])
        self.assertEqual(
            [point["context_tokens"] for point in profiles["http-decode-vs-active-context"]["points"]],
            [point["active_context_tokens"] for point in exact],
        )
        self.assertEqual(
            [point["value"] for point in profiles["http-decode-vs-active-context"]["points"]],
            [point["decode_tok_s"] for point in exact],
        )
        self.assertEqual(
            [point["value"] for point in profiles["http-ttft-vs-active-context"]["points"]],
            [point["ttft_ms"] for point in exact],
        )
        for profile_id in ("http-decode-vs-active-context", "http-ttft-vs-active-context"):
            scope = profiles[profile_id]["scope"]
            self.assertIn("no point is interpolated or extrapolated", scope)
            self.assertNotIn(2048, [point["context_tokens"] for point in profiles[profile_id]["points"]])


if __name__ == "__main__":
    unittest.main()
