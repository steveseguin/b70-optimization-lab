#!/usr/bin/env python3
"""CPU-only fail-closed tests for the fa0 graph-port R3 lifecycle repair."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r3.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_fa0_graph_port_parent_sentinel_r3", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)
BASE = RUNNER.BASE


class Fa0GraphPortR3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.r2 = RUNNER.R2.load_manifest()
        self.overlay = RUNNER.load_overlay()
        self.r3 = RUNNER.synthesize_manifest(self.r2, self.overlay)

    def test_exact_r3_campaign_root_and_ack_are_create_only(self) -> None:
        RUNNER.validate_overlay(self.overlay)
        RUNNER.validate_manifest(self.r3)
        self.assertTrue(self.r3["campaign_id"].endswith("-r3"))
        self.assertTrue(self.r3["lifecycle"]["output_root"].endswith("-r3"))
        self.assertEqual(self.r3["lifecycle"]["exact_ack"], RUNNER.ACK)
        self.assertTrue(self.overlay["lifecycle"]["create_only"])
        self.assertTrue(self.overlay["lifecycle"]["r1_and_r2_roots_immutable"])

    def test_only_runtime_provenance_and_lifecycle_metadata_change(self) -> None:
        self.assertEqual(self.r3["source"], self.r2["source"])
        self.assertEqual(self.r3["model"], self.r2["model"])
        self.assertEqual(self.r3["canary"], self.r2["canary"])
        r3_runtime = copy.deepcopy(self.r3["runtime"])
        provenance = r3_runtime.pop("source_provenance")
        self.assertEqual(r3_runtime, self.r2["runtime"])
        self.assertEqual(provenance, self.r2["source"]["provenance"])
        self.assertEqual(self.r3["runtime"]["effective_shared_libraries"], self.r2["runtime"]["effective_shared_libraries"])

    def test_missing_or_divergent_runtime_provenance_fails_closed(self) -> None:
        missing = copy.deepcopy(self.r3)
        missing["runtime"].pop("source_provenance")
        with self.assertRaises(BASE.GateError):
            RUNNER.validate_manifest(missing)
        divergent = copy.deepcopy(self.r3)
        divergent["runtime"]["source_provenance"]["classification"] = "drift"
        with self.assertRaises(BASE.GateError):
            RUNNER.validate_manifest(divergent)

    def test_sealed_source_build_and_dso_identical_to_r2(self) -> None:
        for key in ("source", "model", "canary", "acceptance"):
            self.assertEqual(self.r3[key], self.r2[key])
        for key in (
            "build_root", "binary", "graph_backend", "cmake_cache", "makefile",
            "sycl_flags", "required_cmake", "effective_shared_libraries_scope",
            "effective_shared_libraries_status", "effective_shared_libraries",
        ):
            self.assertEqual(self.r3["runtime"][key], self.r2["runtime"][key])
        self.assertEqual(len(self.r3["runtime"]["effective_shared_libraries"]), 34)

    def test_parent_arms_remain_64_tokens_and_exact_delta(self) -> None:
        self.assertEqual(self.r3["canary"]["generated_tokens_per_arm"], 64)
        root = Path("/tmp/fa0-r3-environment-unit-test")
        control = BASE.arm_environment(root, "0", "0")
        candidate = BASE.arm_environment(root, "1", "8")
        changed = {name for name in set(control) | set(candidate) if control.get(name) != candidate.get(name)}
        self.assertEqual(changed, {"GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE"})

    def test_static_check_returns_synthesized_r3_not_r2(self) -> None:
        with mock.patch.object(RUNNER.R2, "static_check", return_value=(self.r2, [{"soname": "fixture"}])):
            with mock.patch.object(BASE, "verify_artifact"):
                manifest, libraries = RUNNER.static_check()
        self.assertEqual(manifest["campaign_id"], RUNNER.CAMPAIGN_ID)
        self.assertEqual(manifest["runtime"]["source_provenance"], manifest["source"]["provenance"])
        self.assertEqual(libraries, [{"soname": "fixture"}])

    def test_zero_curve_site_speed_and_replacement_authority(self) -> None:
        authority = self.overlay["authority"]
        self.assertTrue(authority["parent_sentinel_only"])
        for key in (
            "curve_authorized", "site_publication_authorized", "speed_claim_authorized",
            "quality_claim_authorized", "record_or_submission_authorized",
            "protected_graph_off_values_may_be_replaced",
        ):
            self.assertFalse(authority[key])
        self.assertTrue(authority["historical_featured_speeds_are_immutable"])


if __name__ == "__main__":
    unittest.main()
