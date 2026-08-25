#!/usr/bin/env python3
"""CPU-only fail-closed tests for the cache-scaled fa0 R4 sentinel."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r4.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_fa0_graph_port_parent_r4", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)
BASE = RUNNER.BASE


class Fa0GraphPortR4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.overlay = RUNNER.load_overlay()
        self.r2 = RUNNER.ORIGINAL_LOAD_JSON(RUNNER.R2_MANIFEST)
        self.r4 = RUNNER.synthesize_manifest(self.r2, self.overlay)

    def test_sealed_overlay_and_distinct_create_only_lifecycle(self) -> None:
        RUNNER.validate_overlay(self.overlay)
        RUNNER.validate_manifest(self.r4)
        self.assertTrue(self.r4["campaign_id"].endswith("-r4"))
        self.assertTrue(self.r4["lifecycle"]["output_root"].endswith("-r4"))
        self.assertEqual(self.r4["lifecycle"]["exact_ack"], RUNNER.ACK)
        self.assertTrue(self.overlay["lifecycle"]["create_only"])

    def test_final_source_and_incremental_patch_are_pinned(self) -> None:
        self.assertEqual(self.r4["source"]["post_r4_sha256"], RUNNER.SOURCE_PATH_HASHES)
        self.assertEqual(
            self.r4["source"]["capacity_scaled_overlay"]["incremental_patch_sha256"],
            RUNNER.CAPACITY_PATCH_SHA256,
        )

    def test_build_and_fresh_dso_deltas_are_sealed(self) -> None:
        runtime = self.r4["runtime"]
        self.assertEqual(runtime["binary"]["sha256"], RUNNER.BINARY_SHA256)
        self.assertEqual(runtime["graph_backend"]["sha256"], RUNNER.BACKEND_SHA256)
        rows = {row["soname"]: row for row in runtime["effective_shared_libraries"]}
        self.assertEqual(len(rows), 34)
        self.assertEqual(rows["libggml-sycl.so.0"]["sha256"], RUNNER.BACKEND_SHA256)
        self.assertEqual(rows["libllama-server-impl.so"]["sha256"], RUNNER.SERVER_IMPL_SHA256)

    def test_exact_64_token_same_binary_arms_are_preserved(self) -> None:
        self.assertEqual(self.r4["canary"], self.r2["canary"])
        self.assertEqual(self.r4["canary"]["generated_tokens_per_arm"], 64)
        root = Path("/tmp/fa0-r4-environment-unit-test")
        control = BASE.arm_environment(root, "0", "0")
        candidate = BASE.arm_environment(root, "1", "8")
        changed = {key for key in set(control) | set(candidate) if control.get(key) != candidate.get(key)}
        self.assertEqual(changed, {"GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE"})

    def test_manifest_drift_fails_closed(self) -> None:
        for mutation in ("source", "backend", "authority"):
            value = copy.deepcopy(self.r4)
            if mutation == "source":
                value["source"]["post_r4_sha256"]["ggml/src/ggml-sycl/ggml-sycl.cpp"] = "0" * 64
            elif mutation == "backend":
                value["runtime"]["graph_backend"]["sha256"] = "0" * 64
            else:
                value["r4_overlay"]["authority"]["curve_authorized"] = True
            with self.assertRaises(BASE.GateError):
                RUNNER.validate_manifest(value)

    def test_zero_curve_site_speed_and_replacement_authority(self) -> None:
        authority = self.overlay["authority"]
        self.assertTrue(authority["parent_sentinel_only"])
        for key in (
            "curve_authorized", "site_publication_authorized", "speed_claim_authorized",
            "quality_claim_authorized", "record_or_submission_authorized",
            "protected_graph_off_values_may_be_replaced",
        ):
            self.assertFalse(authority[key])


if __name__ == "__main__":
    unittest.main()
