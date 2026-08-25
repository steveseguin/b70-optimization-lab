#!/usr/bin/env python3
"""CPU-only contract tests for the sealed fa0 graph-port sentinel."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r1.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_fa0_graph_port_parent_sentinel", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)
BASE = RUNNER.BASE

ZERO_SUMMARY = (
    "[SYCL-GRAPH] summary device=0 requested=0 compatibility_rejected=0 "
    "device_unsupported=0 cache_entries=0 cache_limit=0 cache_hit=0 "
    "cache_miss=0 cache_full=0 direct_replay=0 recorded=0 created=0 "
    "updated=0 recreated=0 replayed=0"
)
CANDIDATE_PREFIX = "\n".join((
    "[SYCL-GRAPH] requested device=0 count=66",
    "[SYCL-GRAPH] recording_entered device=0 count=4",
    "[SYCL-GRAPH] replayed device=0 count=66",
    "[SYCL-GRAPH] direct_replay device=0 count=62",
))


def candidate_summary(*, cache_full: int = 0, replayed: int = 66) -> str:
    return CANDIDATE_PREFIX + "\n" + (
        "[SYCL-GRAPH] summary device=0 requested=66 compatibility_rejected=0 "
        "device_unsupported=0 cache_entries=4 cache_limit=8 cache_hit=62 "
        f"cache_miss=4 cache_full={cache_full} direct_replay=62 recorded=4 "
        f"created=4 updated=0 recreated=0 replayed={replayed}"
    )


class Fa0GraphPortParentSentinelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = RUNNER.load_manifest()

    def test_sealed_manifest_identity_contract(self) -> None:
        RUNNER.validate_manifest(self.manifest)
        self.assertEqual(self.manifest["build_identity_status"], "sealed")
        RUNNER.require_sealed_build_identity(self.manifest)
        value = copy.deepcopy(self.manifest)
        value["build_identity_status"] = "UNSEALED_AWAITING_LLAMA_CLI_AND_DSO_HASHES"
        with self.assertRaisesRegex(BASE.GateError, "build identity is unsealed"):
            RUNNER.require_sealed_build_identity(value)

    def test_seal_rejects_placeholder_or_empty_dso_closure(self) -> None:
        value = copy.deepcopy(self.manifest)
        value["runtime"]["binary"]["sha256"] = "FILL_AFTER_BUILD"
        with self.assertRaises(BASE.GateError):
            RUNNER.require_sealed_build_identity(value)
        value = copy.deepcopy(self.manifest)
        value["runtime"]["effective_shared_libraries"] = []
        with self.assertRaisesRegex(BASE.GateError, "DSO closure is absent"):
            RUNNER.require_sealed_build_identity(value)

    def test_seal_ties_loaded_sycl_dso_to_hashed_backend(self) -> None:
        value = copy.deepcopy(self.manifest)
        value["build_identity_status"] = "sealed"
        value["runtime"]["binary"] = {
            "path": str(RUNNER.BINARY), "size_bytes": 1, "sha256": "0" * 64,
        }
        value["runtime"]["graph_backend"] = {
            "path": str(RUNNER.GRAPH_BACKEND), "size_bytes": 1, "sha256": "1" * 64,
        }
        value["runtime"]["effective_shared_libraries"] = [{
            "soname": "libggml-sycl.so.0",
            "realpath": "/tmp/not-the-sealed-backend.so",
            "sha256": "1" * 64,
        }]
        with mock.patch.object(RUNNER, "GRAPH_BACKEND", Path(__file__)):
            with self.assertRaisesRegex(BASE.GateError, "not the hashed graph backend"):
                RUNNER.require_sealed_build_identity(value)

    def test_same_new_binary_and_exact_arm_delta(self) -> None:
        self.assertEqual(tuple(self.manifest["canary"]["common_argv"]), RUNNER.COMMON_ARGV)
        self.assertEqual(Path(RUNNER.COMMON_ARGV[0]), RUNNER.BINARY)
        root = Path("/tmp/fa0-graph-port-environment-unit-test")
        base = RUNNER.base_environment(root)
        self.assertEqual(
            {name: base[name] for name in RUNNER.EXACT_RUNTIME_KNOBS},
            RUNNER.EXACT_RUNTIME_KNOBS,
        )
        self.assertNotIn("GGML_SYCL_ENABLE_GRAPH", base)
        self.assertNotIn("GGML_SYCL_GRAPH_CACHE_SIZE", base)
        control = BASE.arm_environment(root, "0", "0")
        candidate = BASE.arm_environment(root, "1", "8")
        changed = {name for name in set(control) | set(candidate) if control.get(name) != candidate.get(name)}
        self.assertEqual(changed, {"GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE"})
        self.assertFalse(set(BASE.UNSAFE_GRAPH_VARIABLES) & set(candidate))

    def test_control_requires_one_all_zero_summary(self) -> None:
        parsed = BASE.validate_control_graph_log(ZERO_SUMMARY)
        self.assertTrue(all(value == 0 for value in parsed.values()))
        with self.assertRaises(BASE.GateError):
            BASE.validate_control_graph_log(ZERO_SUMMARY.replace("requested=0", "requested=1"))

    def test_candidate_requires_exact_port_evidence(self) -> None:
        parsed = RUNNER.validate_candidate_graph_log(candidate_summary())
        self.assertEqual(parsed["cache_full"], 0)
        self.assertEqual(parsed["replayed"], parsed["requested"])
        with self.assertRaisesRegex(BASE.GateError, "cache filled"):
            RUNNER.validate_candidate_graph_log(candidate_summary(cache_full=1))
        with self.assertRaisesRegex(BASE.GateError, "replay every"):
            RUNNER.validate_candidate_graph_log(candidate_summary(replayed=65))
        with self.assertRaisesRegex(BASE.GateError, "request/cache accounting"):
            RUNNER.validate_candidate_graph_log(
                candidate_summary().replace("cache_hit=62", "cache_hit=61")
            )
        with self.assertRaisesRegex(BASE.GateError, "miss/create/cache-entry"):
            RUNNER.validate_candidate_graph_log(
                candidate_summary().replace("created=4", "created=3")
            )
        with self.assertRaisesRegex(BASE.GateError, "updated or recreated"):
            RUNNER.validate_candidate_graph_log(
                candidate_summary().replace("updated=0", "updated=1")
            )

    def test_zero_authority_and_frozen_port_packet(self) -> None:
        interpretation = self.manifest["interpretation"]
        for name in (
            "seven_cell_expansion_authorized", "site_publication_authorized",
            "record_or_submission_authorized", "quality_claim_authorized",
        ):
            self.assertFalse(interpretation[name])
        self.assertIsNone(interpretation["speed_measurement_or_floor"])
        self.assertTrue(interpretation["historical_featured_speeds_are_immutable"])
        self.assertIn(RUNNER.PATCH_REL, BASE.PACKET_PATHS)
        self.assertIn(RUNNER.SOURCE_MANIFEST_REL, BASE.PACKET_PATHS)
        self.assertEqual(len(BASE.PACKET_PATHS), len(set(BASE.PACKET_PATHS)))


if __name__ == "__main__":
    unittest.main()
