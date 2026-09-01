#!/usr/bin/env python3
"""CPU-only tests for the frozen W13 graph census summarizer."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


TOOL = Path(__file__).with_name("summarize-w13-m1-xpu-graph-census.py")
SPEC = importlib.util.spec_from_file_location("q38_w13_census_summary", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {TOOL}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.identity = {
            "model_revision": "bcd9f01ddc9cff2316eb84281bebcd5b058bddce",
            "layer": 0,
            "ep_rank": 0,
            "seed": 20260827,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def arm(
        self,
        config: dict,
        authority: str | None,
        median: float,
        *,
        exact: bool = True,
    ) -> dict:
        return {
            "status": "pass",
            "classification": "qwen38_flash_next_w13_m1_xpu_graph_component",
            "identity": self.identity.copy(),
            "config_receipt": {
                "requested": config,
                "resolved_w2": MODULE.PROTECTED_W2.copy(),
                "w2_unchanged": True,
            },
            "correctness": {
                "exact_replays": 100,
                "config_local_eager_graph_equal": exact,
                "matches_control_authority": exact,
                "unique_eager_hashes": 100,
                "unique_graph_hashes": 100,
                "control_authority_path": authority,
            },
            "graph": {"event_median_us": median, "timing_input_index": 0},
        }

    def write_matrix(
        self,
        *,
        winner: str | None = None,
        drifted: str | None = None,
        inexact: str | None = None,
        failed: str | None = None,
        valid_json_nonzero: str | None = None,
        identity_drift_after: str | None = None,
    ) -> None:
        for name, config in MODULE.CANDIDATES.items():
            before_path = (self.root / f"{name}-control-before.jsonl").resolve()
            before = self.arm({}, None, 100.0)
            candidate_median = 95.0 if name == winner else 99.0
            candidate = self.arm(
                config,
                str(before_path),
                candidate_median,
                exact=name != inexact,
            )
            after_median = 103.0 if name == drifted else 100.0
            after = self.arm({}, str(before_path), after_median)
            if identity_drift_after is not None and name == identity_drift_after:
                before["identity"] = {**self.identity, "runtime": "B"}
                candidate["identity"] = before["identity"].copy()
                after["identity"] = before["identity"].copy()
            before_path.write_text(json.dumps(before) + "\n", encoding="utf-8")
            candidate_path = self.root / f"{name}-candidate.jsonl"
            candidate_path.write_text(
                "" if name == failed else json.dumps(candidate) + "\n",
                encoding="utf-8",
            )
            (self.root / f"{name}-control-after.jsonl").write_text(
                json.dumps(after) + "\n", encoding="utf-8"
            )
            (self.root / f"{name}-control-before.exit-code").write_text(
                "0\n", encoding="utf-8"
            )
            candidate_exit = 1 if name in (failed, valid_json_nonzero) else 0
            (self.root / f"{name}-candidate.exit-code").write_text(
                f"{candidate_exit}\n", encoding="utf-8"
            )
            (self.root / f"{name}-control-after.exit-code").write_text(
                "0\n", encoding="utf-8"
            )

    def test_exact_three_percent_winner_freezes_confirmation(self) -> None:
        self.write_matrix(winner="w13-n128")
        summary, packet = MODULE.summarize(self.root)
        self.assertEqual(summary["qualified_candidates"], ["w13-n128"])
        self.assertEqual(summary["discovery_winner"], "w13-n128")
        self.assertIsNotNone(packet)
        self.assertEqual(packet["matrix"]["cells"], 24)
        self.assertEqual(packet["matrix"]["total_processes"], 72)
        self.assertFalse(packet["execution"]["authorized_now"])

    def test_control_drift_above_two_percent_rejects_candidate(self) -> None:
        self.write_matrix(winner="w13-n32", drifted="w13-n32")
        summary, packet = MODULE.summarize(self.root)
        self.assertGreater(summary["rows"]["w13-n32"]["control_drift_percent"], 2)
        self.assertFalse(summary["rows"]["w13-n32"]["qualified_discovery_positive"])
        self.assertIsNone(packet)

    def test_inexact_candidate_cannot_advance(self) -> None:
        self.write_matrix(winner="w13-n256", inexact="w13-n256")
        summary, packet = MODULE.summarize(self.root)
        self.assertFalse(summary["rows"]["w13-n256"]["exact"])
        self.assertIsNone(summary["rows"]["w13-n256"]["latency_reduction_percent"])
        self.assertIsNone(packet)

    def test_failed_candidate_is_preserved_as_rejection(self) -> None:
        self.write_matrix(winner="w13-k64", failed="w13-k64")
        summary, packet = MODULE.summarize(self.root)
        row = summary["rows"]["w13-k64"]
        self.assertFalse(row["exact"])
        self.assertIsNotNone(row["candidate_error"])
        self.assertIsNone(row["candidate_us"])
        self.assertIsNone(packet)

    def test_nonzero_exit_rejects_even_valid_candidate_json(self) -> None:
        self.write_matrix(winner="w13-k64", valid_json_nonzero="w13-k64")
        summary, packet = MODULE.summarize(self.root)
        row = summary["rows"]["w13-k64"]
        self.assertFalse(row["exact"])
        self.assertEqual(row["exit_codes"]["candidate"], 1)
        self.assertEqual(row["candidate_error"], "candidate process exited 1")
        self.assertIsNone(packet)

    def test_cross_bracket_identity_drift_invalidates_entire_census(self) -> None:
        self.write_matrix(winner="w13-warps4", identity_drift_after="w13-stage5")
        with self.assertRaisesRegex(ValueError, "identity drifted across brackets"):
            MODULE.summarize(self.root)


if __name__ == "__main__":
    unittest.main()
