#!/usr/bin/env python3
"""CPU-only fail-closed tests for the fa0 graph-port R2 parent sentinel."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r2.py"
)
SPEC = importlib.util.spec_from_file_location("qwen36_fa0_graph_port_parent_sentinel_r2", SCRIPT)
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


def candidate_summary(**changes: int) -> str:
    values = {
        "requested": 66, "compatibility_rejected": 0, "device_unsupported": 0,
        "cache_entries": 4, "cache_limit": 8, "cache_hit": 62,
        "cache_miss": 4, "cache_full": 0, "direct_replay": 62,
        "recorded": 4, "created": 4, "updated": 0, "recreated": 0,
        "replayed": 66,
    }
    values.update(changes)
    prefix = "\n".join((
        f"[SYCL-GRAPH] requested device=0 count={values['requested']}",
        f"[SYCL-GRAPH] recording_entered device=0 count={values['recorded']}",
        f"[SYCL-GRAPH] replayed device=0 count={values['replayed']}",
        f"[SYCL-GRAPH] direct_replay device=0 count={values['direct_replay']}",
    ))
    body = " ".join(f"{key}={value}" for key, value in values.items())
    return prefix + "\n[SYCL-GRAPH] summary device=0 " + body


class Fa0GraphPortR2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = RUNNER.load_manifest()

    def test_preregistration_is_valid_and_sealed(self) -> None:
        RUNNER.validate_manifest(self.manifest)
        self.assertEqual(self.manifest["build_identity_status"], "sealed")
        RUNNER.require_sealed_packet_identity(self.manifest)
        mutated = copy.deepcopy(self.manifest)
        mutated["build_identity_status"] = "UNSEALED_AWAITING_R2_PATCH_BUILD_AND_DSO_HASHES"
        with self.assertRaisesRegex(BASE.GateError, "R2 packet is unsealed"):
            RUNNER.require_sealed_packet_identity(mutated)

    def test_all_required_hashes_and_dso_closure_are_sealed(self) -> None:
        source = self.manifest["source"]["incremental_memo_overlay"]
        self.assertEqual(source["patch_sha256"], "1575acc5ee07b37eb98186a09d201a895d36501c223dc114110a43ee08f4e0a3")
        self.assertEqual(source["source_manifest_sha256"], "2486cf6349e2428329ae4b9458461c5cadad4501836bc3dc49e070a2f452e69d")
        runtime = self.manifest["runtime"]
        self.assertEqual(runtime["binary"]["sha256"], "68ab26cf34f821a40afb5a05374360e8343b9b802c927fd0850fcd7bf3c7e1fd")
        self.assertEqual(runtime["graph_backend"]["sha256"], "941a8ff9c3266a9e4b3f56da3f533dc17577a78df80dc90cf38eb0017b783590")
        self.assertGreater(runtime["binary"]["size_bytes"], 0)
        self.assertGreater(runtime["graph_backend"]["size_bytes"], 0)
        self.assertEqual(runtime["effective_shared_libraries_status"], "sealed")
        self.assertEqual(len(runtime["effective_shared_libraries"]), 34)
        backend_rows = [row for row in runtime["effective_shared_libraries"] if row["soname"] == "libggml-sycl.so.0"]
        self.assertEqual(len(backend_rows), 1)
        self.assertEqual(backend_rows[0]["sha256"], runtime["graph_backend"]["sha256"])

    def test_source_gate_pins_common_and_post_r2_ggml(self) -> None:
        self.assertEqual(
            RUNNER.SOURCE_PATH_HASHES["ggml/src/ggml-sycl/common.hpp"],
            "ce4c8541381f9e1043e15b21359c8c828fc17f20c48672afb0c6d646c02b7805",
        )
        self.assertEqual(
            RUNNER.SOURCE_PATH_HASHES["ggml/src/ggml-sycl/ggml-sycl.cpp"],
            "f0c4bda8beb3c0b06c72edc202fcc074d72e031433a4eacd8a91b8acf5f468a0",
        )
        self.assertTrue(self.manifest["source"]["incremental_memo_overlay"]["common_hpp_must_remain_unchanged"])

    def test_exact_same_binary_64_token_arm_delta(self) -> None:
        self.assertEqual(self.manifest["canary"]["generated_tokens_per_arm"], 64)
        self.assertEqual(tuple(self.manifest["canary"]["common_argv"]), RUNNER.COMMON_ARGV)
        self.assertEqual(Path(RUNNER.COMMON_ARGV[0]), RUNNER.BINARY)
        root = Path("/tmp/fa0-r2-environment-unit-test")
        control = BASE.arm_environment(root, "0", "0")
        candidate = BASE.arm_environment(root, "1", "8")
        changed = {name for name in set(control) | set(candidate) if control.get(name) != candidate.get(name)}
        self.assertEqual(changed, {"GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE"})

    def test_control_and_candidate_counter_conservation(self) -> None:
        parsed = BASE.validate_control_graph_log(ZERO_SUMMARY)
        self.assertTrue(all(value == 0 for value in parsed.values()))
        parsed = RUNNER.validate_candidate_graph_log(candidate_summary())
        self.assertEqual(parsed["requested"], parsed["cache_hit"] + parsed["cache_miss"])
        self.assertEqual(parsed["cache_hit"], parsed["direct_replay"])
        self.assertEqual(parsed["cache_miss"], parsed["recorded"])
        self.assertEqual(parsed["recorded"], parsed["created"])
        self.assertEqual(parsed["created"], parsed["cache_entries"])
        self.assertEqual(parsed["replayed"], parsed["requested"])
        for mutation in (
            {"cache_hit": 61}, {"direct_replay": 61}, {"created": 3},
            {"replayed": 65}, {"cache_full": 1}, {"updated": 1},
        ):
            with self.assertRaises(BASE.GateError):
                RUNNER.validate_candidate_graph_log(candidate_summary(**mutation))
        with self.assertRaisesRegex(BASE.GateError, "pointer-stability failure"):
            RUNNER.validate_candidate_graph_log(
                candidate_summary() + "\npersistent SYCL graph Q8 memo exhausted 320 pointer-stable slots"
            )

    def test_zero_curve_site_speed_and_replacement_authority(self) -> None:
        interpretation = self.manifest["interpretation"]
        for key in (
            "curve_authorized", "site_publication_authorized", "speed_claim_authorized",
            "quality_claim_authorized", "record_or_submission_authorized",
            "protected_graph_off_values_may_be_replaced",
        ):
            self.assertFalse(interpretation[key])
        self.assertTrue(interpretation["historical_featured_speeds_are_immutable"])

    def test_mutated_authority_or_campaign_fails_manifest(self) -> None:
        for path, value in (
            (("campaign_id",), "r1-reuse-forbidden"),
            (("interpretation", "curve_authorized"), True),
            (("interpretation", "protected_graph_off_values_may_be_replaced"), True),
        ):
            mutated = copy.deepcopy(self.manifest)
            target = mutated
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.assertRaises(BASE.GateError):
                RUNNER.validate_manifest(mutated)


if __name__ == "__main__":
    unittest.main()
