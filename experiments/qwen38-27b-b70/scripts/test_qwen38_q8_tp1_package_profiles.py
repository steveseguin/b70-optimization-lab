#!/usr/bin/env python3
"""Assert that the public Q8 TP1 curves exactly mirror committed measurements."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "packages/qwen38-27b-q8-tp1-b70/package.json"
EVIDENCE = ROOT / "experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/result.json"
FAMILY = ROOT / "families/qwen-27b.json"


class Q8PackageProfiles(unittest.TestCase):
    def test_every_public_marker_is_an_exact_evidence_row(self) -> None:
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        measured = {}
        for row in evidence["rows"]:
            if row["n_prompt"] == 2048 and row["n_gen"] == 0:
                measured[("prefill", row["n_depth"])] = row["avg_ts"]
            elif row["n_prompt"] == 0 and row["n_gen"] == 128:
                measured[("decode", row["n_depth"])] = row["avg_ts"]
            else:
                self.fail(f"unexpected evidence row: {row}")

        self.assertEqual(len(package["performance_profiles"]), 2)
        public = {}
        for profile in package["performance_profiles"]:
            self.assertIn("no point is interpolated or extrapolated", profile["scope"])
            for point in profile["points"]:
                self.assertEqual(point["samples"], 5)
                public[(profile["metric"], point["context_tokens"])] = point["value"]
        self.assertEqual(public, measured)
        self.assertEqual(
            package["library"]["featured_metric"]["value"], measured[("decode", 0)]
        )

    def test_family_curve_is_the_same_exact_matrix(self) -> None:
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        family = json.loads(FAMILY.read_text(encoding="utf-8"))
        series = next(
            row
            for row in family["series_measurements"]
            if row["id"] == "q38-q8weights-tp1-kv-f16-context"
        )
        expected = {}
        for row in evidence["rows"]:
            point = expected.setdefault(row["n_depth"], {"x": row["n_depth"], "samples": 5})
            if row["n_prompt"] == 2048:
                point["prefill_tok_s"] = row["avg_ts"]
            else:
                point["decode_tok_s"] = row["avg_ts"]
        self.assertEqual(series["points"], [expected[depth] for depth in sorted(expected)])
        self.assertEqual(series["identity"]["model_sha256"], "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8")


if __name__ == "__main__":
    unittest.main()
