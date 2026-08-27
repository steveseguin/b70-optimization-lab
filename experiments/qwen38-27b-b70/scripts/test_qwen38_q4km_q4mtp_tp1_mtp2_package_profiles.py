#!/usr/bin/env python3
"""Bind the published MTP2 profiles to their aggregate and raw evidence."""

from pathlib import Path
import hashlib
import json
import statistics
import unittest


REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / "packages/qwen38-27b-q4km-mtp2-tp1-b70/package.json"
EVIDENCE = REPO / "experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1-result.json"
HISTORICAL_EVIDENCE = REPO / "experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-r2-result.json"
CONCURRENCY_EVIDENCE = REPO / "experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-http-concurrency-r2-result.json"


class Qwen38Q4Mtp2PackageProfilesTest(unittest.TestCase):
    def test_mixed_content_profiles_match_qualified_aggregate(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        profiles = {item["id"]: item for item in package["performance_profiles"]}
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["quality"]["mtp2_target_exact_cases"], 36)
        self.assertEqual(
            [point["context_tokens"] for point in profiles["http-decode-vs-active-context"]["points"]],
            [point["active_context_tokens"] for point in evidence["points"]],
        )
        self.assertEqual(
            [point["value"] for point in profiles["http-decode-vs-active-context"]["points"]],
            [point["decode_tok_s"] for point in evidence["points"]],
        )
        self.assertEqual(
            [point["value"] for point in profiles["http-ttft-vs-active-context"]["points"]],
            [point["ttft_ms"] for point in evidence["points"]],
        )
        for profile_id in ("http-decode-vs-active-context", "http-ttft-vs-active-context"):
            scope = profiles[profile_id]["scope"]
            self.assertIn("no point is interpolated or extrapolated", scope.lower())
            self.assertIn(2048, [point["context_tokens"] for point in profiles[profile_id]["points"]])
            self.assertTrue(all(point["samples"] == 6 for point in profiles[profile_id]["points"]))

    def test_historical_repeated_token_divergence_remains_preserved(self) -> None:
        historical = json.loads(HISTORICAL_EVIDENCE.read_text(encoding="utf-8"))
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        self.assertEqual(historical["status"], "failed-partial-2k-quarantined")
        self.assertEqual(historical["quarantined_depths"], [2048])
        self.assertTrue(
            any("older repeated-token diagnostic" in item for item in package["known_limitations"])
        )

    def test_concurrency_profile_matches_two_fresh_qualified_attempts(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        evidence = json.loads(CONCURRENCY_EVIDENCE.read_text(encoding="utf-8"))
        profiles = {item["id"]: item for item in package["performance_profiles"]}
        profile = profiles["http-output-audited-aggregate-vs-concurrent-users"]
        self.assertEqual(
            [point["concurrent_sequences"] for point in profile["points"]],
            [point["concurrent_users"] for point in evidence["points"]],
        )
        self.assertEqual(
            [point["value"] for point in profile["points"]],
            [point["aggregate_tok_s"] for point in evidence["points"]],
        )
        self.assertEqual(evidence["qualification"]["attempts_passed"], 2)
        self.assertEqual(
            evidence["qualification"]["concurrent_semantic_canary"]["passed"], 256
        )
        self.assertEqual(evidence["qualification"]["concurrent_semantic_canary"]["failed"], 0)
        self.assertIn("8K total", profile["scope"])
        self.assertIn("No point is interpolated or extrapolated", profile["scope"])

    def test_concurrency_result_rederives_from_raw_receipts(self) -> None:
        evidence = json.loads(CONCURRENCY_EVIDENCE.read_text(encoding="utf-8"))
        attempts = []
        for attempt in (4, 5):
            root = REPO / (
                "experiments/qwen38-27b-b70/data/"
                f"qwen38-q4km-q4mtp-tp1-mtp2-http-concurrency-20260827-r2-attempt{attempt}"
            )
            qualification = json.loads((root / "qualification.json").read_text())
            canary = json.loads((root / "concurrent-quality-canary.json").read_text())
            self.assertTrue(qualification["completion_tokens_128_all"])
            self.assertTrue(qualification["cached_tokens_all_zero"])
            self.assertEqual(qualification["cross_base_oracle_collision_count"], 0)
            self.assertTrue(canary["pass_all"])
            self.assertEqual(canary["total_requests"], 128)
            attempts.append({row["concurrency"]: row for row in qualification["batches"]})

            for name in ("result.json", "qualification.json", "concurrent-quality-canary.json"):
                key = f"attempt{attempt}/{name}"
                self.assertEqual(
                    hashlib.sha256((root / name).read_bytes()).hexdigest(),
                    evidence["raw_artifacts"]["sha256"][key],
                )

        for point in evidence["points"]:
            users = point["concurrent_users"]
            values = [attempt[users]["aggregate_tok_s_wall"] for attempt in attempts]
            expected_median = statistics.median(values)
            expected_range = (max(values) - min(values)) / expected_median * 100
            self.assertEqual(point["attempt_values"], values)
            self.assertAlmostEqual(point["aggregate_tok_s"], expected_median)
            self.assertAlmostEqual(point["per_user_tok_s"], expected_median / users)
            self.assertAlmostEqual(point["relative_range_percent"], expected_range)


if __name__ == "__main__":
    unittest.main()
