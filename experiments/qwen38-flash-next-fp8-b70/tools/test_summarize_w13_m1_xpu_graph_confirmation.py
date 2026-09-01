#!/usr/bin/env python3
"""CPU-only tests for the W13 M1 graph confirmation summarizer."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("summarize-w13-m1-xpu-graph-confirmation.py")
SPEC = importlib.util.spec_from_file_location("q38_w13_confirmation", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConfirmationSummaryTests(unittest.TestCase):
    def write_matrix(
        self,
        root: Path,
        *,
        candidate_factor: float = 0.9,
        after_factor: float = 1.001,
        mutate=None,
    ) -> None:
        receipt = root / "checkpoint-receipt.json"
        receipt.write_text("{}\n", encoding="utf-8")
        (root / "checkpoint-receipt.sha256").write_text("a" * 64 + "\n")
        receipt_path = str(receipt.resolve())
        for layer in MODULE.LAYERS:
            for rank in MODULE.EP_RANKS:
                for seed in MODULE.SEEDS:
                    cell = f"l{layer}-r{rank}-s{seed}"
                    before_path = (root / f"{cell}-control-before.jsonl").resolve()
                    base = 200.0 + rank + layer / 10.0
                    for arm, config, authority, timing in (
                        ("control-before", {}, None, base),
                        (
                            "candidate",
                            MODULE.CANDIDATE_CONFIG,
                            str(before_path),
                            base * candidate_factor,
                        ),
                        ("control-after", {}, str(before_path), base * after_factor),
                    ):
                        identity = {
                            "model_path": MODULE.MODEL_PATH,
                            "model_revision": MODULE.MODEL_REVISION,
                            "model_index_sha256": MODULE.MODEL_INDEX_SHA256,
                            "model_config_sha256": MODULE.MODEL_CONFIG_SHA256,
                            "layer": layer,
                            "ep_rank": rank,
                            "seed": seed,
                            "global_expert_range": [rank * 128, rank * 128 + 127],
                            "checkpoint_shards": MODULE.expected_checkpoint_shards(
                                layer
                            ),
                            "runtime_source_receipt": MODULE.RUNTIME_SOURCE_RECEIPT,
                        }
                        value = {
                            "status": "pass",
                            "classification": "qwen38_flash_next_w13_m1_xpu_graph_component",
                            "identity": identity,
                            "config_receipt": {
                                "requested": config,
                                "resolved_w2": MODULE.PROTECTED_W2,
                                "w2_unchanged": True,
                            },
                            "weights": {
                                "checkpoint_checksum_mode": "frozen_receipt",
                                "checkpoint_receipt_path": receipt_path,
                                "checkpoint_receipt_sha256": "a" * 64,
                            },
                            "correctness": {
                                "exact_replays": 100,
                                "config_local_eager_graph_equal": True,
                                "matches_control_authority": True,
                                "unique_eager_hashes": 100,
                                "unique_graph_hashes": 100,
                                "control_authority_path": authority,
                            },
                            "graph": {
                                "event_median_us": timing,
                                "timing_input_index": 0,
                            },
                        }
                        if mutate is not None:
                            mutate(cell, arm, value)
                        (root / f"{cell}-{arm}.jsonl").write_text(
                            json.dumps(value) + "\n", encoding="utf-8"
                        )
                        (root / f"{cell}-{arm}.exit-code").write_text(
                            "0\n", encoding="utf-8"
                        )

    def test_passes_all_24_exact_cells(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root)
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(len(result["rows"]), 24)
            self.assertEqual(result["gates"]["positive_cells"], 24)
            self.assertFalse(result["raw_cross_rank_timings_pooled"])

    def test_rejects_control_drift_over_two_percent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root, after_factor=1.03)
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "failed_closed")
            self.assertFalse(result["gates"]["all_control_drifts_within_two_percent"])

    def test_rejects_one_inexact_cell(self) -> None:
        def mutate(cell, arm, value):
            if cell == "l47-r3-s20260830" and arm == "candidate":
                value["correctness"]["matches_control_authority"] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root, mutate=mutate)
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "failed_closed")
            self.assertFalse(result["gates"]["all_24_cells_exact"])

    def test_rejects_fewer_than_20_positive_cells(self) -> None:
        def mutate(cell, arm, value):
            if arm == "candidate" and cell in {
                "l0-r0-s20260826",
                "l0-r0-s20260827",
                "l0-r0-s20260830",
                "l0-r1-s20260826",
                "l0-r1-s20260827",
            }:
                value["graph"]["event_median_us"] *= 1.12

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root, mutate=mutate)
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "failed_closed")
            self.assertEqual(result["gates"]["positive_cells"], 19)

    def test_rejects_single_cell_regression_over_two_percent(self) -> None:
        def mutate(cell, arm, value):
            if cell == "l47-r3-s20260830" and arm == "candidate":
                value["graph"]["event_median_us"] *= 1.14

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root, mutate=mutate)
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "failed_closed")
            self.assertFalse(result["gates"]["no_cell_regressed_more_than_two_percent"])

    def test_rejects_nonzero_exit_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root)
            (root / "l0-r0-s20260826-candidate.exit-code").write_text(
                "1\n", encoding="utf-8"
            )
            result = MODULE.summarize(root)
            self.assertEqual(result["status"], "failed_closed")
            self.assertFalse(result["gates"]["all_24_cells_exact"])


if __name__ == "__main__":
    unittest.main()
