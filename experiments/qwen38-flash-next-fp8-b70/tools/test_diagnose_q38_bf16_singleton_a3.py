#!/usr/bin/env python3
"""CPU-only contracts for the A3 BF16 singleton discriminator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


TOOL = Path(__file__).with_name("diagnose-q38-bf16-singleton-a3.py")
SPEC = importlib.util.spec_from_file_location("q38_bf16_singleton_a3", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {TOOL}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeMkldnn:
    deterministic = False


class FakeTorch:
    backends = SimpleNamespace(mkldnn=FakeMkldnn())


def fake_snapshot(tag: str) -> dict:
    return {
        "sha256": f"full-{tag}",
        "active_columns_0_324_sha256": f"active-{tag}",
        "synthetic_padding_columns_324_336_sha256": "tail-zero",
        "synthetic_padding_all_numeric_zero": True,
    }


def fake_protocol(tag: str, latency: float) -> dict:
    snapshot = fake_snapshot(tag)
    return {
        "invocations": [snapshot],
        "unique_full_output_sha256": [snapshot["sha256"]],
        "unique_active_output_sha256": [snapshot["active_columns_0_324_sha256"]],
        "unique_synthetic_tail_sha256": [
            snapshot["synthetic_padding_columns_324_336_sha256"]
        ],
        "all_synthetic_padding_numeric_zero": True,
        "coordinate_distributions": {
            "0,80": {
                "row": 0,
                "col": 80,
                "sample_count": 1,
                "unique_bf16_bits": 1,
                "bf16_bits_counts": {"0x3f80": 1},
            }
        },
        "focus_row_invocations": {str(row): [snapshot] for row in MODULE.FOCUS_ROWS},
        "latency": {"median": latency},
    }


def fake_record(arm: str, replica: int, latency: float) -> dict:
    requested = arm == "mkldnn-deterministic"
    consecutive = {}
    for row in MODULE.FOCUS_ROWS:
        value = fake_protocol(f"row-{row}", latency)
        value["reported_coordinate_translation"] = {
            "0,80": f"{row},80",
        }
        consecutive[str(row)] = value
    return {
        "identity": {
            "input_sha256": "input",
            "weight_sha256": "weight",
            "model_revision": "revision",
            "arm": arm,
            "replica": replica,
        },
        "arm_report": {
            "setting": {
                "before": False,
                "requested": requested,
                "after_set": requested,
                "restored": False,
            },
            "consecutive_focus_rows": consecutive,
            "full_order_ordinal_sweeps": fake_protocol("ordinal", latency),
        },
    }


class A3Contracts(unittest.TestCase):
    def test_frozen_a2_identity_and_real_coordinates(self) -> None:
        self.assertEqual(MODULE.sha256(MODULE.A2_TOOL), MODULE.A2_TOOL_SHA256)
        self.assertEqual(MODULE.FAMILY, "hc_down_inject")
        self.assertEqual(MODULE.SENTINEL, "layer00-attn-r0")
        self.assertEqual(MODULE.SEED, 2026090201)
        self.assertEqual(MODULE.FOCUS_ROWS, (221, 205, 148, 78))
        self.assertEqual(MODULE.RECURRENT_COORDINATES[148], (204, 264))
        self.assertEqual(MODULE.REPLICAS, (1, 2))

    def test_environment_is_exact(self) -> None:
        self.assertEqual(
            MODULE.verify_environment(dict(MODULE.A3_ENVIRONMENT)),
            MODULE.A3_ENVIRONMENT,
        )
        with self.assertRaisesRegex(RuntimeError, "environment drift"):
            MODULE.verify_environment(
                {**MODULE.A3_ENVIRONMENT, "ONEDNN_VERBOSE": "profile_exec"}
            )

    def test_coordinate_distributions_preserve_raw_bf16_bits(self) -> None:
        first = bytearray(MODULE.COLS * 2)
        second = bytearray(first)
        first[80 * 2 : 80 * 2 + 2] = bytes.fromhex("803f")
        second[80 * 2 : 80 * 2 + 2] = bytes.fromhex("813f")
        result = MODULE.coordinate_distributions(
            [bytes(first), bytes(second)], rows=1, coordinates={0: (80,)}
        )
        self.assertEqual(result["0,80"]["unique_bf16_bits"], 2)
        self.assertEqual(result["0,80"]["bf16_bits_counts"], {"0x3f80": 1, "0x3f81": 1})

    def test_compact_snapshot_separates_active_and_tail(self) -> None:
        payload = bytes(MODULE.COLS * 2)
        record = MODULE.compact_snapshot(payload, rows=1)
        self.assertTrue(record["synthetic_padding_all_numeric_zero"])
        changed = bytearray(payload)
        changed[MODULE.ACTIVE_COLS * 2 : MODULE.ACTIVE_COLS * 2 + 2] = bytes.fromhex(
            "803f"
        )
        changed_record = MODULE.compact_snapshot(bytes(changed), rows=1)
        self.assertEqual(
            changed_record["active_columns_0_324_sha256"],
            record["active_columns_0_324_sha256"],
        )
        self.assertFalse(changed_record["synthetic_padding_all_numeric_zero"])

    def test_backend_flag_is_scoped_and_restored(self) -> None:
        FakeTorch.backends.mkldnn.deterministic = False
        with MODULE.scoped_mkldnn_deterministic(FakeTorch, True) as receipt:
            self.assertTrue(FakeTorch.backends.mkldnn.deterministic)
            self.assertTrue(receipt["after_set"])
        self.assertFalse(FakeTorch.backends.mkldnn.deterministic)
        self.assertFalse(receipt["restored"])

    def test_backend_flag_restores_after_exception(self) -> None:
        FakeTorch.backends.mkldnn.deterministic = False
        with self.assertRaisesRegex(RuntimeError, "body failure"):
            with MODULE.scoped_mkldnn_deterministic(FakeTorch, True):
                raise RuntimeError("body failure")
        self.assertFalse(FakeTorch.backends.mkldnn.deterministic)

    def test_latency_requires_finite_nonnegative_samples(self) -> None:
        self.assertEqual(MODULE.latency_report([3.0, 1.0, 2.0])["median"], 2.0)
        with self.assertRaisesRegex(RuntimeError, "latency"):
            MODULE.latency_report([float("nan")])
        with self.assertRaisesRegex(RuntimeError, "latency"):
            MODULE.latency_report([-1.0])

    def test_summary_has_two_processes_per_arm_and_excludes_latency_from_output_authority(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for arm in MODULE.ARMS:
                for replica in MODULE.REPLICAS:
                    (root / f"{arm}-replica{replica}.json").write_text(
                        json.dumps(fake_record(arm, replica, float(replica))),
                        encoding="utf-8",
                    )
            summary = MODULE.summarize(root)
        self.assertEqual(summary["status"], "diagnostic_complete")
        for arm in MODULE.ARMS:
            arm_summary = summary["arm_summary"][arm]
            self.assertTrue(arm_summary["output_authority_exact_across_processes"])
            self.assertTrue(
                arm_summary["ordinal_active_sequence_exact_across_processes"]
            )

    def test_setting_precedes_first_gemm_in_each_child(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        execute_start = source.index("def execute_arm")
        scope = source.index("with scoped_mkldnn_deterministic", execute_start)
        first_gemm = source.index("timed_ordinal_sweep", scope)
        self.assertLess(scope, first_gemm)
        self.assertNotIn("functional.linear", source[execute_start:scope])

    def test_four_cells_are_explicit_and_plan_is_inert(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn("for arm in ARMS", source)
        self.assertIn("for replica in REPLICAS", source)
        self.assertIn("--replica", source)
        self.assertEqual(MODULE.CONSECUTIVE_REPEATS, 100)
        self.assertEqual(MODULE.ORDINAL_SWEEPS, 100)
        self.assertEqual(MODULE.CELL_TIMEOUT_SECONDS, 1200)
        self.assertEqual(MODULE.PLAN_TIMEOUT_SECONDS, 2700)
        self.assertIn('"device_execution": False', source)

    def test_no_endpoint_or_host_lifecycle_actions(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        for forbidden in ("vllm serve", "docker", "podman", "reboot", "shutdown"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
