#!/usr/bin/env python3
"""Assert that the public Q8 TP1 curves exactly mirror committed measurements."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "packages/qwen38-27b-q8-tp1-b70/package.json"
EVIDENCE = ROOT / "experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/result.json"


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


if __name__ == "__main__":
    unittest.main()
