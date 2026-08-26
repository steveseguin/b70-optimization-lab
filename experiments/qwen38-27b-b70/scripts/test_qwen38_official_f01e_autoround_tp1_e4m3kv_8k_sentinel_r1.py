#!/usr/bin/env python3
"""Inert contract tests for the official-f01e AutoRound E4M3-KV sentinel."""

from __future__ import annotations

import json
import pathlib
import unittest


REPO = pathlib.Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-r1-prereg.json"
RUNNER = LANE / "scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-8k-sentinel-r1.sh"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_one_low_dose_cell_only(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(run["tensor_parallel"], 1)
        self.assertEqual(run["mtp_depth"], 0)
        self.assertEqual(run["kv_cache_dtype"], "fp8_e4m3")
        self.assertEqual(run["graph_mode"], "off")
        self.assertEqual(self.manifest["exact_depth_contract"]["depths"], [8192])
        self.assertTrue(self.manifest["execution"]["one_gpu_server_lifetime"])

    def test_image_model_and_source_are_pinned(self) -> None:
        run = self.manifest["run_identity"]
        self.assertEqual(
            run["image_id"],
            "sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f",
        )
        self.assertEqual(run["vllm_commit"], "ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9")
        self.assertEqual(run["model_revision"], "bce40cacab0a4535b92fb3d57615c2bea9adf3d1")

    def test_historical_results_are_immutable(self) -> None:
        interpretation = self.manifest["interpretation"]
        self.assertIsNone(interpretation["speed_floor"])
        self.assertFalse(interpretation["historical_replacement_allowed"])
        self.assertFalse(interpretation["prior_e4m3_value_replacement_allowed"])
        self.assertFalse(interpretation["descendant_expansion_is_automatic"])

    def test_quality_and_classification_are_fail_closed(self) -> None:
        quality = self.manifest["quality_contract"]
        self.assertIn("seven exact cases", quality["full_pass"])
        classes = self.manifest["terminal_classification"]
        self.assertEqual(
            set(classes),
            {"passed-quality-clean-sentinel", "quarantined-output-divergent", "unsupported", "failed"},
        )
        self.assertIn("explicit exact-image log line", classes["unsupported"])

    def test_runner_has_exact_delta_and_identity_markers(self) -> None:
        for token in (
            "--kv-cache-dtype fp8_e4m3",
            "--enforce-eager",
            "kv_cache_dtype=fp8_e4m3",
            "enforce_eager=True",
            "quantization=inc",
            "Graph capturing finished",
            "--depth 8192",
            "--context-capacity 32896",
            "--require-baseline",
        ):
            self.assertIn(token, self.runner)
        self.assertEqual(self.runner.count("dockerc run -d"), 1)
        self.assertNotIn("VLLM_XPU_ENABLE_XPU_GRAPH", self.runner)

    def test_unsupported_needs_exact_image_and_specific_line(self) -> None:
        body = self.runner.split("explicit_e4m3_unsupported()", 1)[1].split(
            "write_arm_result()", 1
        )[0]
        for token in (
            '"$(<"$root/image-id.txt")" == "$image_id"',
            "fp8[_ -]?e4m3",
            "kv[_ -]?cache|kv_cache_dtype",
            "not supported|unsupported|invalid (value|dtype)|does not support",
        ):
            self.assertIn(token, body)

    def test_runner_is_inert_and_cleanup_is_global(self) -> None:
        for token in (
            "--check",
            "--plan",
            "--execute",
            "exact acknowledgement required",
            "repository must be clean",
            "fresh campaign roots",
            "trap cleanup_on_exit EXIT",
            "trap 'exit 130' INT",
            "trap 'exit 143' TERM",
            "canonical GPU campaign lock",
        ):
            self.assertIn(token, self.runner)

    def test_clean_main_failure_is_propagated(self) -> None:
        self.assertIn(
            'launch_head=$(require_clean_pushed_main) || die "clean pushed main check failed"',
            self.runner,
        )


if __name__ == "__main__":
    unittest.main()
