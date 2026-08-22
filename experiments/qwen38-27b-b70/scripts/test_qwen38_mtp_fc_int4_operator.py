#!/usr/bin/env python3
"""CPU-only contract tests for the Qwen3.8 ``mtp.fc`` INT4 qualifier."""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("qwen38_mtp_fc_int4_operator.py")
DRIVER_PATH = Path(__file__).with_name(
    "run-20260821-qwen38-mtp-fc-int4-operator-abba.sh"
)
NOTE_PATH = (
    Path(__file__).parent.parent
    / "notes"
    / ("2026-08-21-qwen38-mtp-fc-int4-operator-prereg.md")
)
_LAZY_MODULES = ("torch", "safetensors", "vllm_xpu_kernels")
_MODULES_BEFORE_IMPORT = set(sys.modules)
SPEC = importlib.util.spec_from_file_location(
    "qwen38_mtp_fc_int4_operator", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
QUALIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALIFIER)
_NEW_LAZY_MODULES = {
    name
    for name in sys.modules
    if name not in _MODULES_BEFORE_IMPORT
    and any(name == prefix or name.startswith(f"{prefix}.") for prefix in _LAZY_MODULES)
}


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _metric(*, passed: bool = True) -> dict[str, object]:
    return {
        "passed": passed,
        "atol": QUALIFIER.KERNEL_ATOL,
        "rtol": QUALIFIER.KERNEL_RTOL,
        "maximum_absolute_difference": 0.001,
        "mean_absolute_difference": 0.0001,
        "p99_absolute_difference": 0.0009,
        "maximum_relative_difference": 0.01,
        "cosine_similarity": 0.9999,
    }


def _warning_line(marker: str, source_line: int) -> str:
    return (
        f"[W821 03:45:12.123456789 int4_gemm_w4a16.h:{source_line}] "
        f"Warning: {marker} (function operator())"
    )


def _case(
    rank: int,
    role: str,
    rows: int,
    latency: float,
    *,
    sample_count: int = QUALIFIER.MIN_SAMPLES,
) -> dict[str, object]:
    output_sha = _digest(f"rank{rank}-{role}-m{rows}-output")
    samples = [latency] * sample_count
    return {
        "rows": rows,
        "input_sha256": _digest(f"shared-m{rows}-input"),
        "mutated_input_sha256": _digest(f"shared-m{rows}-mutated-input"),
        "selected_oracle": (
            "live_fp16" if role == "control" else "packed_dequant_fp32"
        ),
        "original_fp16_oracle_sha256": _digest(f"rank{rank}-m{rows}-original-oracle"),
        "dequant_oracle_sha256": _digest(f"rank{rank}-m{rows}-dequant-oracle"),
        "output_sha256": output_sha,
        "stability_replays": QUALIFIER.MIN_STABILITY_REPLAYS,
        "bit_stable": True,
        "serial_m1_output_sha256": output_sha if rows == 6 else None,
        "m6_equals_six_serial_m1": True if rows == 6 else None,
        "oracle_check": _metric(),
        "original_fp16_drift": _metric(passed=role == "control"),
        "mutated_output_sha256": _digest(f"rank{rank}-{role}-m{rows}-mutated-output"),
        "mutation_changed_output": True,
        "mutation_oracle_check": _metric(),
        "event_samples_us_per_call": samples,
        "event_summary_us_per_call": QUALIFIER._sample_summary(samples),
    }


def _make_run_packet(
    rank: int,
    slot: int,
    *,
    m1_control: float = 20.0,
    m1_candidate: float = 19.0,
    m6_control: float = 50.0,
    m6_candidate: float = 32.0,
) -> dict[str, object]:
    roles = ("control", "candidate", "candidate", "control")
    suffixes = ("a1", "b1", "b2", "a2")
    role = roles[slot - 1]
    expected = QUALIFIER.SHARD_DIGESTS[rank]
    marker_count = 1 if role == "candidate" else 0
    started = 1_000_000 + rank * 100_000 + slot * 1_000
    m1_latency = m1_control if role == "control" else m1_candidate
    m6_latency = m6_control if role == "control" else m6_candidate
    if role == "control":
        abi = {
            "operator": "torch.nn.functional.linear",
            "input_dependency": None,
            "completion_barrier_env": "1",
        }
    else:
        abi = {
            "operator": "torch.ops._xpu_C.int4_gemm_w4a16",
            "arguments": [
                "input",
                "qweight",
                "bias=None",
                "scales",
                "qzero=8",
                "group_size=128",
                "g_idx=None",
                "input_dependency=True",
            ],
            "input_dependency": True,
            "completion_barrier_env": "1",
        }
    sentinel = sum(
        value << (4 * index) for index, value in enumerate((0, 1, 7, 8, 9, 14, 15, 0))
    )
    return {
        "schema": QUALIFIER.SCHEMA_RUN,
        "passed": True,
        "classification": "isolated-eager-operator-arm-passed",
        "role": role,
        "tp_rank": rank,
        "arm_id": f"rank{rank}-{suffixes[slot - 1]}",
        "campaign_slot": slot,
        "process": {
            "pid": 100 + rank * 10 + slot,
            "start_ticks": 10_000 + rank * 10 + slot,
            "boot_id": "test-boot",
            "hostname": "test-host",
            "started_time_ns": started,
            "finished_time_ns": started + 100,
        },
        "preflight": {
            "path": "/tmp/mtp-fc-preflight.json",
            "sha256": _digest("preflight"),
            "lab_repo_head": "a" * 40,
            "qualifier_sha256": _digest("qualifier"),
            "driver_sha256": _digest("driver"),
            "health_sha256": _digest("health"),
        },
        "runtime_identity": {
            "python": f"{QUALIFIER.EXPECTED_PYTHON_VERSION_PREFIX}test-build",
            "torch_version": QUALIFIER.EXPECTED_TORCH_VERSION,
            "hostname": "test-host",
            "physical_gpu": 2,
            "logical_device": "xpu:0",
            "ze_affinity_mask": "2",
            "device_name": QUALIFIER.EXPECTED_DEVICE_NAME,
            "device_uuid": QUALIFIER.EXPECTED_GPU2_UUID,
            "pci_bdf_context": QUALIFIER.EXPECTED_GPU2_BDF_CONTEXT,
            "extension_module_path": str(QUALIFIER.EXTENSION_FILE),
            "pythonpath_first": str(QUALIFIER.EXTENSION_FILE.parent.parent),
            "ld_library_path_first": str(QUALIFIER.EXTENSION_FILE.parent),
            "python_dont_write_bytecode": True,
            "torch_compile_used": False,
            "xpu_graph_used": False,
            "vllm_service_used": False,
        },
        "model_identity": {
            "tensor_name": QUALIFIER.TENSOR_NAME,
            "full_shape": list(QUALIFIER.FULL_SHAPE),
            "serialized_dtype": "bfloat16",
            "full_tensor_sha256": QUALIFIER.FULL_TENSOR_SHA256,
            "tp_rank": rank,
            "row_range": [
                rank * QUALIFIER.SHARD_SHAPE[0],
                (rank + 1) * QUALIFIER.SHARD_SHAPE[0],
            ],
            "shard_shape": list(QUALIFIER.SHARD_SHAPE),
            "shard_bf16_sha256": expected["bf16"],
            "live_fp16_sha256": expected["fp16"],
            "cast_order": "output-row shard before BF16-to-FP16 cast",
        },
        "packing": {
            "group_size": QUALIFIER.GROUP_SIZE,
            "qweight_shape": list(QUALIFIER.QWEIGHT_SHAPE),
            "qweight_stride": list(QUALIFIER.QWEIGHT_STRIDE),
            "scales_shape": list(QUALIFIER.SCALE_SHAPE),
            "scales_dtype": "float16",
            "qzero": 8,
            "zero_group_count": 0,
            "hashes": {
                "packed_storage": expected["packed_storage"],
                "qweight_logical": expected["qweight_logical"],
                "scales": expected["scales"],
                "qzero": QUALIFIER.QZERO_SHA256,
            },
            "self_test": {
                "nibble_order": "least-significant-first",
                "sentinel_packed_uint32": sentinel,
                "zero_group_scale": 1.0,
                "zero_group_nibble": 8,
                "zero_group_dequant_exact_zero": True,
            },
        },
        "abi": abi,
        "mapping_evidence": {
            "required_path": str(QUALIFIER.EXTENSION_FILE),
            "required_sha256": QUALIFIER.EXTENSION_SHA256,
            "same_basename_paths": [str(QUALIFIER.EXTENSION_FILE)],
            "mapping_gate_passed": True,
        },
        "marker_evidence": {
            "stderr_path": f"/tmp/rank{rank}-{suffixes[slot - 1]}.stderr.log",
            "stderr_sha256": _digest(f"stderr-{rank}-{slot}"),
            "stderr_line_count": marker_count * 2,
            "input_dependency_marker": QUALIFIER.INPUT_MARKER,
            "input_dependency_marker_count": marker_count,
            "completion_marker": QUALIFIER.COMPLETION_MARKER,
            "completion_marker_count": marker_count,
            "determinism_pad_marker_prefix": QUALIFIER.DETPAD_MARKER,
            "determinism_pad_marker_count": 0,
            "passed": True,
        },
        "cache_evidence": {
            "before_packet_path": "/tmp/cache-snapshot.json",
            "before_packet_sha256": _digest("cache-packet"),
            "before_inventory_sha256": _digest("cache-inventory"),
            "after_inventory_sha256": _digest("cache-inventory"),
            "roots": ["/tmp/cache-root"],
            "unchanged": True,
        },
        "timing_contract": {
            "clock": "torch.xpu.Event elapsed time",
            "warmup_launches": QUALIFIER.WARMUP_LAUNCHES,
            "samples_per_shape": QUALIFIER.MIN_SAMPLES,
            "launches_per_sample": QUALIFIER.MIN_LAUNCHES_PER_SAMPLE,
            "stability_replays_per_shape": QUALIFIER.MIN_STABILITY_REPLAYS,
        },
        "cases": [
            _case(rank, role, 1, m1_latency),
            _case(rank, role, 6, m6_latency),
        ],
        "authorization": (
            "arm evidence only; no endpoint, deployment, or submission authorization"
        ),
    }


def _make_campaign(**latencies: float) -> list[dict[str, object]]:
    return [
        _make_run_packet(rank, slot, **latencies)
        for rank in (0, 1)
        for slot in (1, 2, 3, 4)
    ]


def _make_invalid_packet() -> dict[str, object]:
    return {
        "schema": QUALIFIER.SCHEMA_INVALID,
        "passed": False,
        "classification": "invalid-arm-no-scientific-result",
        "role": "control",
        "tp_rank": 0,
        "arm_id": "rank0-a1",
        "campaign_slot": 1,
        "process": {
            "pid": 101,
            "start_ticks": 1001,
            "boot_id": "test-boot",
            "hostname": "test-host",
            "started_time_ns": 10,
            "finished_time_ns": 20,
        },
        "preflight_path": "/tmp/preflight.json",
        "preflight_sha256_expected": _digest("preflight"),
        "stderr": None,
        "cache_evidence": None,
        "progress": {},
        "failure": {"exception_type": "ContractError", "message": "test failure"},
        "authorization": "stop; preserve root; no same-root retry or later arm",
    }


class ImportAndJsonTests(unittest.TestCase):
    def test_import_is_torch_xpu_and_safetensors_free(self) -> None:
        self.assertEqual(_NEW_LAZY_MODULES, set())

    def test_strict_json_rejects_duplicate_and_nonfinite_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            path.write_text('{"a": 1, "a": 2}\n', encoding="utf-8")
            with self.assertRaisesRegex(QUALIFIER.ContractError, "duplicate JSON key"):
                QUALIFIER.load_json(path)
            for token in ("NaN", "Infinity", "-Infinity"):
                path.write_text(f'{{"value": {token}}}\n', encoding="utf-8")
                with self.assertRaisesRegex(
                    QUALIFIER.ContractError, "non-standard JSON constant"
                ):
                    QUALIFIER.load_json(path)
            path.write_text('{"a": 1, "nested": [true, null]}\n', encoding="utf-8")
            self.assertEqual(
                QUALIFIER.load_json(path), {"a": 1, "nested": [True, None]}
            )

    def test_numeric_and_sha_validators_fail_closed(self) -> None:
        for value in (float("nan"), float("inf"), True, "1.0"):
            with self.subTest(value=value):
                with self.assertRaises(QUALIFIER.ContractError):
                    QUALIFIER._require_finite(value, "value")
        for value in (True, 1.0, "1"):
            with self.subTest(value=value):
                with self.assertRaises(QUALIFIER.ContractError):
                    QUALIFIER._require_int(value, "value")
        for value in ("A" * 64, "a" * 63, 1):
            with self.subTest(value=value):
                with self.assertRaises(QUALIFIER.ContractError):
                    QUALIFIER._require_sha(value, "value")


class FrozenLaunchBoundaryTests(unittest.TestCase):
    def test_frozen_note_and_driver_hash_chain_matches(self) -> None:
        note = NOTE_PATH.read_text(encoding="utf-8")
        operator_sha = QUALIFIER._sha256_file(MODULE_PATH)
        driver_sha = QUALIFIER._sha256_file(DRIVER_PATH)
        test_sha = QUALIFIER._sha256_file(Path(__file__))
        for digest in (operator_sha, driver_sha, test_sha):
            self.assertIn(digest, note)
        driver = DRIVER_PATH.read_text(encoding="utf-8")
        self.assertIn(f"operator_sha={operator_sha}", driver)

    def test_q1_authorization_binds_the_frozen_health_terminal(self) -> None:
        # Q1 authorized 2026-08-22: the launch is enabled, and the enabling
        # constants must be a well-formed, source-pinned health-terminal
        # binding (not None, not a caller input).
        self.assertIs(QUALIFIER.CAMPAIGN_LAUNCH_AUTHORIZED, True)
        self.assertEqual(
            QUALIFIER.AUTHORIZED_HEALTH_TERMINAL_PATH,
            "/home/steve/qwen38-gpu3-incumbent-control-health-20260821-r2/terminal.json",
        )
        self.assertRegex(
            str(QUALIFIER.AUTHORIZED_HEALTH_TERMINAL_SHA256), r"^[0-9a-f]{64}$"
        )
        # The authorization helper must still fail closed if the binding is
        # ever blanked, so the interlock cannot silently become a no-op.
        for blanked in (None, "not-a-sha"):
            with mock.patch.object(
                QUALIFIER, "AUTHORIZED_HEALTH_TERMINAL_SHA256", blanked
            ):
                with self.assertRaisesRegex(
                    QUALIFIER.ContractError, "frozen health terminal"
                ):
                    QUALIFIER._require_campaign_launch_authorized("preflight")
        with mock.patch.object(QUALIFIER, "CAMPAIGN_LAUNCH_AUTHORIZED", False):
            with self.assertRaisesRegex(QUALIFIER.ContractError, "blocked"):
                QUALIFIER._require_campaign_launch_authorized("run")

    def test_driver_run_requires_same_boot_and_pinned_health(self) -> None:
        # With Q1 authorized, run is no longer statically blocked; it is gated
        # on same-boot binding. A wrong-boot invocation must fail (rc 3) before
        # creating the output root, and the health terminal is source-pinned
        # (run takes only OUTPUT_ROOT now, never a caller health path).
        source = DRIVER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("LAUNCH BLOCKED", source)
        self.assertIn("require_same_boot", source)
        self.assertIn("health_boot_id=", source)
        self.assertIn("usage: %s check | run OUTPUT_ROOT | compare OUTPUT_ROOT", source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "must-not-exist"
            result = subprocess.run(
                ["bash", str(DRIVER_PATH), "run", str(root)],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ},
            )
            self.assertEqual(result.returncode, 3)
            self.assertFalse(root.exists())

    def test_driver_binds_watchdog_discovery_and_campaign_terminal(self) -> None:
        source = DRIVER_PATH.read_text(encoding="utf-8")
        # bounded per-arm watchdog with escalation and absence verification
        self.assertIn("arm_deadline_seconds=900", source)
        self.assertIn("kill_active_group", source)
        self.assertIn("timeout-before-term", source)
        # live GPU2 identity rederivation, UUID binding (discovery form), and
        # explicit BDF value-check
        self.assertIn("xpu-smi discovery -j", source)
        self.assertIn("expected_gpu2_uuid=00000000-0000-0043-0000-0000e2238086", source)
        self.assertIn("expected_gpu2_bdf=0000:43:00.0", source)
        # enclosing campaign terminal on complete/failed/interrupted
        self.assertIn("qwen38-mtp-fc-int4-campaign-terminal-v1", source)
        for outcome in ("complete", "failed", "interrupted"):
            self.assertIn(outcome, source)

    def test_driver_carries_phase_specific_schema_and_root_gates(self) -> None:
        source = DRIVER_PATH.read_text(encoding="utf-8")
        for schema in (
            QUALIFIER.SCHEMA_CACHE,
            QUALIFIER.SCHEMA_PREFLIGHT,
            QUALIFIER.SCHEMA_RUN,
            QUALIFIER.SCHEMA_INVALID,
            QUALIFIER.SCHEMA_COMPARE,
        ):
            self.assertIn(schema, source)
        self.assertIn("output root must be outside the lab repository", source)
        self.assertGreaterEqual(source.count("require_output_root_outside_repo"), 3)
        self.assertIn("unexpected rc", source)

    def test_stage_graph_and_deleted_mapping_gates(self) -> None:
        stage = QUALIFIER._stage_graph_identity()
        self.assertEqual(
            stage["manifest_sha256"], QUALIFIER.STAGE_GRAPH_MANIFEST_SHA256
        )
        self.assertEqual(stage["file_count"], 20)
        with tempfile.TemporaryDirectory() as directory:
            extension = Path(directory) / QUALIFIER.EXTENSION_FILE.name
            extension.write_bytes(b"extension")
            digest = QUALIFIER._sha256_file(extension)
            live_line = f"1000-2000 r-xp 00000000 00:00 0 {extension}\n"
            with mock.patch.object(Path, "read_text", return_value=live_line):
                evidence = QUALIFIER._mapped_extension_identity(extension, digest)
            self.assertTrue(evidence["mapping_gate_passed"])
            deleted_line = live_line.rstrip() + " (deleted)\n"
            with (
                mock.patch.object(Path, "read_text", return_value=deleted_line),
                self.assertRaisesRegex(QUALIFIER.ContractError, "mapping is deleted"),
            ):
                QUALIFIER._mapped_extension_identity(extension, digest)


class SafetensorsHeaderTests(unittest.TestCase):
    def _write_header(
        self, path: Path, header: object, *, raw: str | None = None
    ) -> None:
        encoded = (
            raw.encode("utf-8")
            if raw is not None
            else json.dumps(header, separators=(",", ":")).encode("utf-8")
        )
        path.write_bytes(struct.pack("<Q", len(encoded)) + encoded)

    def _entry(self) -> dict[str, object]:
        byte_count = QUALIFIER.FULL_SHAPE[0] * QUALIFIER.FULL_SHAPE[1] * 2
        return {
            "dtype": QUALIFIER.TENSOR_DTYPE,
            "shape": list(QUALIFIER.FULL_SHAPE),
            "data_offsets": [0, byte_count],
        }

    def test_exact_mtp_fc_header_passes_without_payload_or_torch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.safetensors"
            self._write_header(path, {QUALIFIER.TENSOR_NAME: self._entry()})
            result = QUALIFIER._safetensors_header(path)
            self.assertEqual(result["tensor_name"], QUALIFIER.TENSOR_NAME)
            self.assertEqual(result["serialized_dtype"], "BF16")
            self.assertEqual(result["full_shape"], [5120, 10240])

    def test_header_rejects_identity_extent_duplicates_and_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.safetensors"
            variants = []
            wrong_dtype = self._entry()
            wrong_dtype["dtype"] = "F16"
            variants.append({QUALIFIER.TENSOR_NAME: wrong_dtype})
            wrong_shape = self._entry()
            wrong_shape["shape"] = [1, 2]
            variants.append({QUALIFIER.TENSOR_NAME: wrong_shape})
            wrong_extent = self._entry()
            wrong_extent["data_offsets"] = [0, 16]
            variants.append({QUALIFIER.TENSOR_NAME: wrong_extent})
            variants.append({"other": self._entry()})
            for variant in variants:
                with self.subTest(variant=variant):
                    self._write_header(path, variant)
                    with self.assertRaises(QUALIFIER.ContractError):
                        QUALIFIER._safetensors_header(path)

            entry = json.dumps(self._entry(), separators=(",", ":"))
            duplicate = (
                "{"
                + json.dumps(QUALIFIER.TENSOR_NAME)
                + ":"
                + entry
                + ","
                + json.dumps(QUALIFIER.TENSOR_NAME)
                + ":"
                + entry
                + "}"
            )
            self._write_header(path, None, raw=duplicate)
            with self.assertRaisesRegex(QUALIFIER.ContractError, "duplicate JSON key"):
                QUALIFIER._safetensors_header(path)

            path.write_bytes(struct.pack("<Q", 100) + b"{}")
            with self.assertRaisesRegex(QUALIFIER.ContractError, "short safetensors"):
                QUALIFIER._safetensors_header(path)


class ContractConstantsAndPackingTests(unittest.TestCase):
    def test_production_shapes_strides_and_hashes_are_exact(self) -> None:
        self.assertEqual(QUALIFIER.FULL_SHAPE, (5120, 10240))
        self.assertEqual(QUALIFIER.SHARD_SHAPE, (2560, 10240))
        self.assertEqual(QUALIFIER.GROUP_SIZE, 128)
        self.assertEqual(QUALIFIER.PACK_FACTOR, 8)
        self.assertEqual(QUALIFIER.QWEIGHT_SHAPE, (1280, 2560))
        self.assertEqual(QUALIFIER.QWEIGHT_STRIDE, (1, 1280))
        self.assertEqual(QUALIFIER.SCALE_SHAPE, (80, 2560))
        self.assertEqual(
            QUALIFIER.FULL_TENSOR_SHA256,
            "4eee377b67ec2122cf214dbe6946d16261873441f1851d64409d9c7566bb20cc",
        )
        self.assertEqual(
            QUALIFIER.QZERO_SHA256,
            "beead77994cf573341ec17b58bbf7eb34d2711c993c1d976b128b3188dc1829a",
        )
        self.assertEqual(
            QUALIFIER.SHARD_DIGESTS,
            {
                0: {
                    "bf16": (
                        "1757625239f6436af83d61a2353b4f406ae1eef22ac1828b03d6cbbe2913d5ed"
                    ),
                    "fp16": (
                        "6cea656bf5e4d0683dff2a1e65b9c822d62fdb63d8510439afb9cf26d00ccc4b"
                    ),
                    "packed_storage": (
                        "da795b5a921bd14f0d3ae814dab268199ccb88aa16bf1aa69ec27b51a7dfda79"
                    ),
                    "qweight_logical": (
                        "adef7804c30b41794ba89e6fbcec88d14020db5760b4020e8d313a71160fab7a"
                    ),
                    "scales": (
                        "c71498b300127c358d59166fb3380ad58871c700c7c077f81ebd6ff32359cb3b"
                    ),
                },
                1: {
                    "bf16": (
                        "31ee2a7fc864ce05e3263257df7a7a11a0326b90c49c0868807324bce48241ed"
                    ),
                    "fp16": (
                        "7237258ded520195d2e22c4d7a2a6d4c8e0a54158d1bb992d4c9d0701c48395b"
                    ),
                    "packed_storage": (
                        "8eda2db1e4aef2d5e0d711730973b23199a0f27daff7160f43c0c140cda9b03b"
                    ),
                    "qweight_logical": (
                        "79b7f43a70342916d21229a474844fc4ba4eaeafad08247e45c70f6d1ae013f8"
                    ),
                    "scales": (
                        "42594dc0dac733bc2e6044f7cc4b09090087eb82e08e811c5fcea11df9c48986"
                    ),
                },
            },
        )
        self.assertEqual(
            QUALIFIER._preflight_contract_literal()["cast_order"],
            "full BF16 tensor -> output-row shard -> FP16 -> FP32 pack math",
        )

    @unittest.skipUnless(importlib.util.find_spec("torch"), "CPU torch unavailable")
    def test_exact_nibble_and_zero_group_cpu_vector(self) -> None:
        import torch

        pattern = torch.tensor([-7, -6, -1, 0, 1, 5, 6, 7], dtype=torch.float16).repeat(
            16
        )
        weight = torch.stack(
            (
                torch.cat((torch.zeros(128, dtype=torch.float16), pattern)),
                torch.cat((pattern * 2, torch.full((128,), 3, dtype=torch.float16))),
            )
        ).contiguous()
        with (
            mock.patch.object(QUALIFIER, "QWEIGHT_SHAPE", (32, 2)),
            mock.patch.object(QUALIFIER, "QWEIGHT_STRIDE", (1, 32)),
            mock.patch.object(QUALIFIER, "SCALE_SHAPE", (2, 2)),
        ):
            backing, logical, scales, zero_groups = QUALIFIER._pack_weight(
                torch, weight
            )
        self.assertEqual(tuple(backing.shape), (2, 32))
        self.assertEqual(tuple(backing.stride()), (32, 1))
        self.assertEqual(tuple(logical.shape), (32, 2))
        self.assertEqual(tuple(logical.stride()), (1, 32))
        self.assertEqual(tuple(scales.shape), (2, 2))
        self.assertEqual(tuple(scales.stride()), (2, 1))
        self.assertEqual(zero_groups, 1)
        self.assertEqual(int(backing[0, 0].item()) & 0xFFFFFFFF, 0x88888888)
        self.assertEqual(int(backing[0, 16].item()) & 0xFFFFFFFF, 0xFED98721)
        self.assertEqual(int(backing[1, 0].item()) & 0xFFFFFFFF, 0xFED98721)
        self.assertEqual(int(backing[1, 16].item()) & 0xFFFFFFFF, 0xFFFFFFFF)
        self.assertTrue(
            torch.equal(
                scales,
                torch.tensor([[1.0, 2.0], [1.0, 3.0 / 7.0]], dtype=torch.float16),
            )
        )
        expected_hashes = {
            "weight": "aa719a40d1c4a004ac740e26c94cc85bf4c0ad608a45d5b9dd4c6d7cb037fb20",
            "backing": "bfff8d02cf254692b632bb6620ccc717be2b647ebfc3de39252b6eb69dd1033f",
            "logical": "7ffe7057d3545f042f38b691dccd9f4de273c205742863abf915531930ee2e50",
            "scales": "4a8575d5ac74d358db87241dcc54dd48c3d412707a37aadaf8d66874bf14f597",
        }
        self.assertEqual(
            QUALIFIER._tensor_sha256(torch, weight), expected_hashes["weight"]
        )
        self.assertEqual(
            QUALIFIER._tensor_sha256(torch, backing), expected_hashes["backing"]
        )
        self.assertEqual(
            QUALIFIER._tensor_sha256(torch, logical), expected_hashes["logical"]
        )
        self.assertEqual(
            QUALIFIER._tensor_sha256(torch, scales), expected_hashes["scales"]
        )
        decoded = QUALIFIER._decode_weight(torch, backing, scales)
        self.assertTrue(torch.equal(decoded[0, :128], torch.zeros(128)))
        self.assertEqual(
            QUALIFIER._tensor_sha256(torch, torch.tensor([8], dtype=torch.int8)),
            QUALIFIER.QZERO_SHA256,
        )
        self.assertEqual(
            QUALIFIER._packing_self_test(torch),
            {
                "nibble_order": "least-significant-first",
                "sentinel_packed_uint32": 0x0FE98710,
                "zero_group_scale": 1.0,
                "zero_group_nibble": 8,
                "zero_group_dequant_exact_zero": True,
            },
        )


class CacheSnapshotTests(unittest.TestCase):
    def test_cache_inventory_detects_content_and_metadata_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = (Path(directory) / "cache").resolve()
            nested = root / "nested"
            nested.mkdir(parents=True)
            artifact = nested / "artifact.bin"
            artifact.write_bytes(b"first")
            inventory = QUALIFIER._inventory([root])
            packet = {
                "schema": QUALIFIER.SCHEMA_CACHE,
                "created_time_ns": 1,
                **inventory,
            }
            QUALIFIER._validate_cache_packet(packet, Path("cache.json"))
            self.assertEqual(
                QUALIFIER._current_inventory_from_packet(packet), inventory
            )

            artifact.write_bytes(b"second")
            self.assertNotEqual(
                QUALIFIER._current_inventory_from_packet(packet), inventory
            )

            corrupt = copy.deepcopy(packet)
            corrupt["roots"][0]["files"][0]["sha256"] = _digest("tampered")
            with self.assertRaisesRegex(
                QUALIFIER.ContractError, "inventory digest mismatch"
            ):
                QUALIFIER._validate_cache_packet(corrupt, Path("cache.json"))

            unsafe = copy.deepcopy(packet)
            unsafe["roots"][0]["files"][0]["relative_path"] = "../escape"
            unsafe["inventory_sha256"] = QUALIFIER._sha256_bytes(
                QUALIFIER._canonical_json_bytes(unsafe["roots"])
            )
            with self.assertRaisesRegex(
                QUALIFIER.ContractError, "unsafe relative path"
            ):
                QUALIFIER._validate_cache_packet(unsafe, Path("cache.json"))

    def test_snapshot_output_must_stay_outside_cache_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            args = argparse.Namespace(
                output=str(root / "snapshot.json"), root=[str(root)]
            )
            with self.assertRaisesRegex(QUALIFIER.ContractError, "outside cache roots"):
                QUALIFIER.cache_snapshot_command(args)


class HealthIdentityTests(unittest.TestCase):
    def _packet(self) -> dict[str, object]:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return {
            "schema": "qwen38-gpu3-incumbent-control-health-terminal-v1",
            "passed": True,
            "classification": "gpu3-incumbent-control-health-pass",
            "child_process": {"boot_id": boot_id},
            "supervisor_process": {"boot_id": boot_id},
            "worker_success": {
                "device": {
                    "physical_gpu": 3,
                    "logical_device": "xpu:0",
                    "name": QUALIFIER.EXPECTED_DEVICE_NAME,
                    "uuid": QUALIFIER.HEALTH_GPU_UUID,
                }
            },
        }

    def _validate_with_mocked_supervisor(
        self, terminal: Path, packet: dict[str, object]
    ) -> dict[str, object]:
        module = SimpleNamespace()

        class Loader:
            @staticmethod
            def exec_module(target: object) -> None:
                setattr(target, "validate_terminal", lambda _root: packet)

        spec = SimpleNamespace(loader=Loader())
        with (
            mock.patch.object(
                QUALIFIER,
                "_file_identity",
                return_value={
                    "path": str(QUALIFIER.HEALTH_SUPERVISOR),
                    "sha256": QUALIFIER.HEALTH_SUPERVISOR_SHA256,
                },
            ),
            mock.patch.object(
                QUALIFIER.importlib.util,
                "spec_from_file_location",
                return_value=spec,
            ),
            mock.patch.object(
                QUALIFIER.importlib.util, "module_from_spec", return_value=module
            ),
            mock.patch.dict(os.environ, {"PYTHONDONTWRITEBYTECODE": "1"}),
        ):
            return QUALIFIER._health_identity(
                terminal, QUALIFIER._sha256_file(terminal), 2
            )

    def test_nested_terminal_pass_rederives_device_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal = Path(directory) / "terminal.json"
            terminal.write_text("{}\n", encoding="utf-8")
            terminal.chmod(0o444)
            result = self._validate_with_mocked_supervisor(terminal, self._packet())
            self.assertTrue(result["supervisor_validation_passed"])
            self.assertEqual(result["worker_device"]["physical_gpu"], 3)
            self.assertEqual(result["operator_physical_gpu"], 2)
            self.assertEqual(
                result["boot_id"],
                Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            )

    def test_nested_terminal_failures_are_not_hidden_by_top_level_pass(self) -> None:
        mutations = (
            ("schema", "wrong"),
            ("passed", False),
            ("classification", "wrong"),
            ("worker_success", None),
            ("physical_gpu", 2),
            ("logical_device", "xpu:1"),
            ("name", "wrong"),
            ("uuid", "wrong"),
            ("boot_id", "wrong-boot"),
        )
        with tempfile.TemporaryDirectory() as directory:
            terminal = Path(directory) / "terminal.json"
            terminal.write_text("{}\n", encoding="utf-8")
            terminal.chmod(0o444)
            for field, value in mutations:
                with self.subTest(field=field):
                    packet = self._packet()
                    if field in {"physical_gpu", "logical_device", "name", "uuid"}:
                        packet["worker_success"]["device"][field] = value
                    elif field == "boot_id":
                        packet["child_process"]["boot_id"] = value
                    else:
                        packet[field] = value
                    with self.assertRaises(QUALIFIER.ContractError):
                        self._validate_with_mocked_supervisor(terminal, packet)

    def test_health_binding_rejects_wrong_operator_gpu_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            terminal = Path(directory) / "terminal.json"
            terminal.write_text("{}\n", encoding="utf-8")
            terminal.chmod(0o444)
            with mock.patch.dict(os.environ, {"PYTHONDONTWRITEBYTECODE": "1"}):
                with self.assertRaisesRegex(
                    QUALIFIER.ContractError, "only defined for physical GPU 2"
                ):
                    QUALIFIER._health_identity(
                        terminal, QUALIFIER._sha256_file(terminal), 3
                    )


class MarkerAndCaseSchemaTests(unittest.TestCase):
    def test_literal_preserved_composite4dd_marker_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stderr.log"
            path.write_text(
                "[rank0]:[W820 14:41:43.609952164 int4_gemm_w4a16.h:200] "
                "Warning: VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY reached "
                "(function operator())\n"
                "[rank0]:[W820 14:41:43.610476629 int4_gemm_w4a16.h:213] "
                "Warning: VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER reached "
                "(function operator())\n",
                encoding="utf-8",
            )
            candidate = QUALIFIER._marker_evidence(path, "candidate")
            self.assertEqual(candidate["input_dependency_marker_count"], 1)
            self.assertEqual(candidate["completion_marker_count"], 1)

    def test_marker_cardinality_for_control_and_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stderr.log"
            path.write_text("unrelated\n", encoding="utf-8")
            control = QUALIFIER._marker_evidence(path, "control")
            self.assertEqual(control["input_dependency_marker_count"], 0)
            self.assertEqual(control["completion_marker_count"], 0)

            path.write_text(
                _warning_line(
                    QUALIFIER.INPUT_MARKER, QUALIFIER.INPUT_MARKER_SOURCE_LINE
                )
                + "\n"
                + _warning_line(
                    QUALIFIER.COMPLETION_MARKER,
                    QUALIFIER.COMPLETION_MARKER_SOURCE_LINE,
                )
                + "\n",
                encoding="utf-8",
            )
            candidate = QUALIFIER._marker_evidence(path, "candidate")
            self.assertEqual(candidate["input_dependency_marker_count"], 1)
            self.assertEqual(candidate["completion_marker_count"], 1)

            bad_logs = (
                _warning_line(
                    QUALIFIER.INPUT_MARKER, QUALIFIER.INPUT_MARKER_SOURCE_LINE
                )
                + "\n"
                + _warning_line(
                    QUALIFIER.INPUT_MARKER, QUALIFIER.INPUT_MARKER_SOURCE_LINE
                )
                + "\n"
                + _warning_line(
                    QUALIFIER.COMPLETION_MARKER,
                    QUALIFIER.COMPLETION_MARKER_SOURCE_LINE,
                )
                + "\n",
                _warning_line(
                    QUALIFIER.INPUT_MARKER, QUALIFIER.INPUT_MARKER_SOURCE_LINE
                )
                + "\n",
                _warning_line(
                    QUALIFIER.INPUT_MARKER, QUALIFIER.INPUT_MARKER_SOURCE_LINE
                )
                + "\n"
                + _warning_line(
                    QUALIFIER.COMPLETION_MARKER,
                    QUALIFIER.COMPLETION_MARKER_SOURCE_LINE,
                )
                + f"\n{QUALIFIER.DETPAD_MARKER}=1\n",
                _warning_line(
                    QUALIFIER.INPUT_MARKER, QUALIFIER.INPUT_MARKER_SOURCE_LINE
                )
                + " trailing-junk\n"
                + _warning_line(
                    QUALIFIER.COMPLETION_MARKER,
                    QUALIFIER.COMPLETION_MARKER_SOURCE_LINE,
                )
                + "\n",
                f"quoted {QUALIFIER.INPUT_MARKER} then {QUALIFIER.INPUT_MARKER}\n"
                + _warning_line(
                    QUALIFIER.COMPLETION_MARKER,
                    QUALIFIER.COMPLETION_MARKER_SOURCE_LINE,
                )
                + "\n",
            )
            for text in bad_logs:
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaisesRegex(
                        QUALIFIER.ContractError, "operator marker mismatch"
                    ):
                        QUALIFIER._marker_evidence(path, "candidate")

    def test_m6_and_serial_m1_schema_is_exact(self) -> None:
        packet = _make_run_packet(0, 1)
        timing = packet["timing_contract"]
        m1, m6 = packet["cases"]
        QUALIFIER._validate_case(m1, "control", timing, "m1")
        QUALIFIER._validate_case(m6, "control", timing, "m6")

        wrong_m6 = copy.deepcopy(m6)
        wrong_m6["serial_m1_output_sha256"] = _digest("different")
        with self.assertRaisesRegex(QUALIFIER.ContractError, "M6/serial-M1"):
            QUALIFIER._validate_case(wrong_m6, "control", timing, "m6")

        wrong_m1 = copy.deepcopy(m1)
        wrong_m1["serial_m1_output_sha256"] = wrong_m1["output_sha256"]
        with self.assertRaisesRegex(QUALIFIER.ContractError, "carries an M6"):
            QUALIFIER._validate_case(wrong_m1, "control", timing, "m1")

    def test_run_packet_rederives_case_order_samples_and_summary(self) -> None:
        path = Path("/tmp/rank0-a1.json")
        packet = _make_run_packet(0, 1)
        QUALIFIER._validate_run_packet(packet, path, revalidate_external=False)

        reversed_cases = copy.deepcopy(packet)
        reversed_cases["cases"].reverse()
        with self.assertRaisesRegex(QUALIFIER.ContractError, "case order mismatch"):
            QUALIFIER._validate_run_packet(
                reversed_cases, path, revalidate_external=False
            )

        tampered = copy.deepcopy(packet)
        tampered["cases"][0]["event_samples_us_per_call"][0] += 1.0
        with self.assertRaisesRegex(QUALIFIER.ContractError, "does not rederive"):
            QUALIFIER._validate_run_packet(tampered, path, revalidate_external=False)


class CampaignAndCompareTests(unittest.TestCase):
    def test_valid_eight_process_abba_campaign_passes_hurdles(self) -> None:
        campaign = _make_campaign()
        for index, packet in enumerate(campaign):
            QUALIFIER._validate_run_packet(
                packet, Path(f"/tmp/packet-{index}.json"), revalidate_external=False
            )
        with mock.patch.object(QUALIFIER, "BOOTSTRAP_ITERATIONS", 128):
            result = QUALIFIER._compare_packets(campaign)
        self.assertTrue(result["passed"])
        self.assertEqual(result["process_count"], 8)
        self.assertEqual(
            result["classification"],
            "qualified-only-for-default-off-integration-design",
        )
        for rank in result["rank_results"]:
            m6 = next(case for case in rank["shape_results"] if case["rows"] == 6)
            self.assertEqual(m6["central_saving_us_per_call"], 18.0)
            self.assertTrue(m6["passed"])

    def test_fresh_process_serial_order_and_fixture_gates(self) -> None:
        variants: list[tuple[str, list[dict[str, object]]]] = []
        duplicate = _make_campaign()
        duplicate[1]["process"]["pid"] = duplicate[0]["process"]["pid"]
        duplicate[1]["process"]["start_ticks"] = duplicate[0]["process"]["start_ticks"]
        variants.append(("fresh processes", duplicate))

        order = _make_campaign()
        order[0]["process"]["started_time_ns"] = 2_000_000
        order[0]["process"]["finished_time_ns"] = 2_000_100
        variants.append(("campaign order", order))

        overlap = _make_campaign()
        overlap[0]["process"]["finished_time_ns"] = (
            overlap[1]["process"]["started_time_ns"] + 1
        )
        variants.append(("overlap", overlap))

        fixture = _make_campaign()
        fixture[-1]["cases"][0]["input_sha256"] = _digest("drift")
        variants.append(("input fixtures", fixture))

        runtime = _make_campaign()
        runtime[-1]["runtime_identity"]["torch_version"] = "different-runtime"
        variants.append(("campaign identity/timing", runtime))

        for message, campaign in variants:
            with self.subTest(message=message):
                with self.assertRaisesRegex(QUALIFIER.ContractError, message):
                    QUALIFIER._compare_packets(campaign)

    def test_bootstrap_and_strict_hurdle_edges(self) -> None:
        cases = [
            {"event_samples_us_per_call": [50.0] * 4},
            {"event_samples_us_per_call": [32.908] * 4},
            {"event_samples_us_per_call": [32.908] * 4},
            {"event_samples_us_per_call": [50.0] * 4},
        ]
        with mock.patch.object(QUALIFIER, "BOOTSTRAP_ITERATIONS", 32):
            bootstrap = QUALIFIER._bootstrap_abba_savings(cases, seed=1)
        self.assertEqual(bootstrap["iterations"], 32)
        self.assertAlmostEqual(
            bootstrap["combined_95_ci_saving_us_per_call"][0], 17.092
        )
        bad_counts = copy.deepcopy(cases)
        bad_counts[0]["event_samples_us_per_call"].append(50.0)
        with self.assertRaisesRegex(QUALIFIER.ContractError, "different sample counts"):
            QUALIFIER._bootstrap_abba_savings(bad_counts, seed=1)

        exact_hurdle = _make_campaign(m6_candidate=50.0 - 17.092)
        with mock.patch.object(QUALIFIER, "BOOTSTRAP_ITERATIONS", 32):
            result = QUALIFIER._compare_packets(exact_hurdle)
        self.assertFalse(result["passed"])

        uneven_replicates = _make_campaign()
        for rank in (0, 1):
            for slot, latency in ((2, 49.9), (3, 15.8)):
                case = uneven_replicates[rank * 4 + slot - 1]["cases"][1]
                case["event_samples_us_per_call"] = [latency] * QUALIFIER.MIN_SAMPLES
                case["event_summary_us_per_call"] = QUALIFIER._sample_summary(
                    case["event_samples_us_per_call"]
                )
        with mock.patch.object(QUALIFIER, "BOOTSTRAP_ITERATIONS", 32):
            uneven_result = QUALIFIER._compare_packets(uneven_replicates)
        self.assertFalse(uneven_result["passed"])
        self.assertTrue(
            all(
                not next(case for case in rank["shape_results"] if case["rows"] == 6)[
                    "paired_point_estimates_clear_m6_hurdle"
                ]
                for rank in uneven_result["rank_results"]
            )
        )
        self.assertTrue(
            all(
                not next(case for case in rank["shape_results"] if case["rows"] == 6)[
                    "passed"
                ]
                for rank in result["rank_results"]
            )
        )

        m1_regression = _make_campaign(m1_candidate=21.0)
        with mock.patch.object(QUALIFIER, "BOOTSTRAP_ITERATIONS", 32):
            result = QUALIFIER._compare_packets(m1_regression)
        self.assertFalse(result["passed"])

    def test_compare_packet_tamper_does_not_rederive(self) -> None:
        campaign = _make_campaign()
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index, packet in enumerate(campaign):
                path = Path(directory) / f"packet-{index}.json"
                path.write_text(json.dumps(packet), encoding="utf-8")
                path.chmod(0o444)
                paths.append(path.resolve())
            with mock.patch.object(QUALIFIER, "BOOTSTRAP_ITERATIONS", 32):
                comparison = QUALIFIER._compare_packets(campaign)
                comparison["packet_paths"] = [str(path) for path in paths]
                comparison["packet_sha256"] = [
                    QUALIFIER._sha256_file(path) for path in paths
                ]
                validator = mock.patch.object(
                    QUALIFIER,
                    "_validate_run_packet",
                    side_effect=lambda packet, _path, *, revalidate_external: packet,
                )
                with validator:
                    QUALIFIER._validate_compare(
                        comparison, Path(directory) / "compare.json"
                    )
                    paths[0].chmod(0o644)
                    with self.assertRaisesRegex(
                        QUALIFIER.ContractError, "source packet is writable"
                    ):
                        QUALIFIER._validate_compare(
                            comparison, Path(directory) / "compare.json"
                        )
                    paths[0].chmod(0o444)
                    tampered = copy.deepcopy(comparison)
                    tampered["process_count"] = 7
                    with self.assertRaisesRegex(
                        QUALIFIER.ContractError, "does not rederive"
                    ):
                        QUALIFIER._validate_compare(
                            tampered, Path(directory) / "compare.json"
                        )


class InvalidPacketAndCliTests(unittest.TestCase):
    def test_invalid_packet_is_accepted_only_with_terminal_classification(self) -> None:
        path = Path("/tmp/rank0-a1.json")
        packet = _make_invalid_packet()
        QUALIFIER._validate_invalid_packet(packet, path)
        mutations = (
            ("passed", True),
            ("classification", "passed"),
            ("role", "candidate"),
            ("arm_id", "rank0-b1"),
            ("authorization", "retry"),
        )
        for key, value in mutations:
            with self.subTest(key=key):
                corrupt = copy.deepcopy(packet)
                corrupt[key] = value
                with self.assertRaises(QUALIFIER.ContractError):
                    QUALIFIER._validate_invalid_packet(corrupt, path)

        corrupt = copy.deepcopy(packet)
        corrupt["failure"]["message"] = ""
        with self.assertRaisesRegex(QUALIFIER.ContractError, "empty failure evidence"):
            QUALIFIER._validate_invalid_packet(corrupt, path)
        corrupt = copy.deepcopy(packet)
        corrupt["progress"]["unknown"] = True
        with self.assertRaisesRegex(QUALIFIER.ContractError, "partial progress"):
            QUALIFIER._validate_invalid_packet(corrupt, path)

    def test_cli_defaults_and_fixed_cardinality(self) -> None:
        parser = QUALIFIER.build_parser()
        run = parser.parse_args(
            [
                "run",
                "--role",
                "control",
                "--tp-rank",
                "0",
                "--physical-gpu",
                "2",
                "--arm-id",
                "rank0-a1",
                "--campaign-slot",
                "1",
                "--preflight",
                "/tmp/preflight.json",
                "--preflight-sha256",
                _digest("preflight"),
                "--stderr-log",
                "/tmp/stderr.log",
                "--output",
                "/tmp/output.json",
            ]
        )
        self.assertEqual(run.samples, QUALIFIER.MIN_SAMPLES)
        self.assertEqual(run.launches_per_sample, QUALIFIER.MIN_LAUNCHES_PER_SAMPLE)
        self.assertEqual(run.stability_replays, QUALIFIER.MIN_STABILITY_REPLAYS)

        preflight = parser.parse_args(
            [
                "preflight",
                "--output",
                "/tmp/preflight.json",
                "--physical-gpu",
                "2",
                "--script-sha256",
                _digest("script"),
                "--driver",
                "/tmp/driver.sh",
                "--driver-sha256",
                _digest("driver"),
                "--repo-head",
                "a" * 40,
                "--health-packet",
                "/tmp/terminal.json",
                "--health-sha256",
                _digest("health"),
                "--cache-snapshot",
                "/tmp/cache.json",
                "--cache-sha256",
                _digest("cache"),
            ]
        )
        self.assertEqual(preflight.model_file, str(QUALIFIER.MODEL_FILE))
        self.assertEqual(preflight.model_sha256, QUALIFIER.MODEL_SHA256)
        self.assertEqual(preflight.extension, str(QUALIFIER.EXTENSION_FILE))
        self.assertEqual(preflight.extension_sha256, QUALIFIER.EXTENSION_SHA256)

        compare = parser.parse_args(
            ["compare", "--output", "/tmp/compare.json"]
            + [f"/tmp/{index}.json" for index in range(8)]
        )
        self.assertEqual(len(compare.packets), 8)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(
                    [
                        "run",
                        "--role",
                        "control",
                        "--tp-rank",
                        "0",
                        "--physical-gpu",
                        "3",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
