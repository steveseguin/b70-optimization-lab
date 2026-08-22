#!/usr/bin/env python3
"""Tests for exact-row depth-sweep package migration."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("sync-depth-sweep-profiles.py")
SPEC = importlib.util.spec_from_file_location("sync_depth_sweep_profiles", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SyncDepthSweepProfilesTest(unittest.TestCase):
    def test_emits_only_exact_positive_measured_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            evidence = repo / "repro/example/sweep.json"
            evidence.parent.mkdir(parents=True)
            rows = self._rows()
            evidence.write_text(json.dumps(rows), encoding="utf-8")
            package = {
                "library": {
                    "context_curve": {
                        "scope": "Measured engine rows",
                        "evidence": "repro/example/sweep.json",
                    }
                }
            }

            profiles = MODULE.measured_profiles(repo, package)

            self.assertEqual([profile["metric"] for profile in profiles], ["decode", "prefill"])
            for profile in profiles:
                self.assertEqual(
                    [point["context_tokens"] for point in profile["points"]],
                    [2048, 8192],
                )
                self.assertEqual([point["samples"] for point in profile["points"]], [5, 5])
                self.assertNotIn(0, [point["context_tokens"] for point in profile["points"]])
            self.assertEqual(
                [point["value"] for point in profiles[0]["points"]],
                [48.0, 44.0],
            )
            self.assertIn("no missing depth is interpolated", profiles[0]["scope"])

    def test_rejects_unpaired_depths(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            evidence = repo / "repro/example/sweep.json"
            evidence.parent.mkdir(parents=True)
            rows = [
                row
                for row in self._rows()
                if not (row["n_depth"] == 8192 and row["n_prompt"] == 2048)
            ]
            evidence.write_text(json.dumps(rows), encoding="utf-8")
            package = {
                "library": {
                    "context_curve": {
                        "scope": "Measured engine rows",
                        "evidence": "repro/example/sweep.json",
                    }
                }
            }
            with self.assertRaisesRegex(ValueError, "decode and prefill depths differ"):
                MODULE.measured_profiles(repo, package)

    @staticmethod
    def _rows() -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for depth, decode, prefill in (
            (0, 50.0, 2000.0),
            (2048, 48.0, 1800.0),
            (8192, 44.0, 1500.0),
        ):
            rows.extend(
                [
                    {
                        "n_depth": depth,
                        "n_prompt": 2048,
                        "n_gen": 0,
                        "avg_ts": prefill,
                        "samples_ts": [prefill] * 5,
                    },
                    {
                        "n_depth": depth,
                        "n_prompt": 0,
                        "n_gen": 128,
                        "avg_ts": decode,
                        "samples_ts": [decode] * 5,
                    },
                ]
            )
        return rows


if __name__ == "__main__":
    unittest.main()
