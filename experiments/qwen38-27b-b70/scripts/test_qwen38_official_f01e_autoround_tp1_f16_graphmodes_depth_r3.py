#!/usr/bin/env python3
"""Inert contract tests for the official-f01e AutoRound graph-mode block."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-r3-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-r3.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_only_two_high_value_f16_arms(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 0)
        self.assertEqual(run["kv_cache_dtype"], "float16")
        self.assertEqual(
            [arm["graph_mode"] for arm in self.manifest["arms"]],
            ["off", "PIECEWISE"],
        )

    def test_exact_depths_and_zero_semantics(self) -> None:
        contract = self.manifest["exact_depth_contract"]
        self.assertEqual(
            contract["depths"], [2048, 4096, 8192, 16384, 24576, 32768]
        )
        self.assertIn("missing", contract["depth_zero"])
        self.assertEqual(contract["metric_intervals"], 99)

    def test_image_and_model_are_revision_pinned(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(
            run["image_id"],
            "sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f",
        )
        self.assertEqual(
            run["model_revision"], "bce40cacab0a4535b92fb3d57615c2bea9adf3d1"
        )
        self.assertEqual(
            run["vllm_commit"], "ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9"
        )

    def test_protected_speed_semantics(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertTrue(interpretation["protected_full_and_piecewise_cells_are_untouched"])

    def test_runner_is_inert_and_fresh(self) -> None:
        for token in (
            "--check",
            "--plan",
            "--execute",
            "exact acknowledgement required",
            "repository must be clean",
            "fresh campaign roots",
            "--enforce-eager",
            'cudagraph_mode":"PIECEWISE',
            "historical_replacement_allowed",
        ):
            self.assertIn(token, self.runner)

    def test_clean_main_failure_is_propagated(self) -> None:
        self.assertIn(
            'launch_head=$(require_clean_pushed_main) || die "clean pushed main check failed"',
            self.runner,
        )

    def test_execute_passes_frozen_context_capacity(self) -> None:
        self.assertIn(
            '--case-id "depth-$depth" --context-capacity 32896 --response-adapter vllm',
            self.runner,
        )


if __name__ == "__main__":
    unittest.main()
