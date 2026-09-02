#!/usr/bin/env python3
"""Bounded A3 discriminator for the Flash-Next BF16 M=1 provider."""

from __future__ import annotations

import argparse
from array import array
from contextlib import contextmanager
from functools import cache
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time
from typing import Any, Iterator


HERE = Path(__file__).resolve().parent
A2_TOOL = HERE / "diagnose-q38-bf16-singleton-a2.py"
A2_TOOL_SHA256 = "32e517ff435d4f99ce160c08c4a3172cfcaeb3b4df60848127926d4c2436192f"
PROVIDER_LIBRARY = Path(
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib/libtorch_xpu.so"
)
PROVIDER_LIBRARY_SHA256 = (
    "ee584edab22b995637c5f6ec83fc10dea5931469c86cf2ad91952bb3e1108290"
)
TORCH_GIT_VERSION = "70d99e998b4955e0049d13a98d77ae1b14db1f45"
A3_ROOT = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
    "bf16-singleton-diagnostic-20260902-a3"
)
FAMILY = "hc_down_inject"
SENTINEL = "layer00-attn-r0"
SEED = 2026090201
ROWS = 256
COLS = 336
ACTIVE_COLS = 324
FOCUS_ROWS = (221, 205, 148, 78)
RECURRENT_COORDINATES = {
    221: (80,),
    205: (84,),
    148: (204, 264),
    78: (63,),
}
CONSECUTIVE_REPEATS = 100
ORDINAL_SWEEPS = 100
WARMUP_SWEEPS = 4
ARMS = ("native", "mkldnn-deterministic")
REPLICAS = (1, 2)
CELL_TIMEOUT_SECONDS = 1200
PLAN_TIMEOUT_SECONDS = 2700
AUTHORITY_ENV = "Q38_BF16_SINGLETON_A3_EXECUTE"
A3_ENVIRONMENT = {
    "HOME": "/home/steve",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
    "PATH": "/home/steve/.venvs/vllm-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "PYTHONNOUSERSITE": "1",
    "PYTHONSAFEPATH": "1",
    "Q38_BF16_DENSE_CENSUS_EXECUTE": "YES",
    AUTHORITY_ENV: "YES",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@cache
def load_a2():
    if sha256(A2_TOOL) != A2_TOOL_SHA256:
        raise RuntimeError("A2 tool identity drift")
    spec = importlib.util.spec_from_file_location("q38_bf16_a2_frozen", A2_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import frozen A2 tool")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_environment(environment: dict[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if environment is None else environment)
    prefixes = (
        "CCL_",
        "DNNL_",
        "I_MPI_",
        "KMP_",
        "LD_",
        "MKL_",
        "ONEAPI_",
        "ONEDNN_",
        "OMP_",
        "Q38_",
        "SYCL_",
        "TORCH_",
        "VLLM_",
        "ZE_",
    )
    relevant = {
        key: value
        for key, value in environment.items()
        if key in A3_ENVIRONMENT or key.startswith(prefixes)
    }
    if relevant != A3_ENVIRONMENT:
        raise RuntimeError(f"A3 GEMM environment drift: {sorted(relevant)}")
    return relevant


def bf16_bits(payload: bytes, *, row: int, col: int, cols: int = COLS) -> int:
    offset = (row * cols + col) * 2
    if offset < 0 or offset + 2 > len(payload):
        raise ValueError("BF16 coordinate outside payload")
    values = array("H")
    values.frombytes(payload[offset : offset + 2])
    return int(values[0])


def coordinate_distributions(
    payloads: list[bytes], *, rows: int, coordinates: dict[int, tuple[int, ...]]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row, cols in coordinates.items():
        if row >= rows:
            raise ValueError("coordinate row outside protocol payload")
        for col in cols:
            counts: dict[str, int] = {}
            for payload in payloads:
                bits = bf16_bits(payload, row=row, col=col)
                key = f"0x{bits:04x}"
                counts[key] = counts.get(key, 0) + 1
            result[f"{row},{col}"] = {
                "row": row,
                "col": col,
                "sample_count": len(payloads),
                "unique_bf16_bits": len(counts),
                "bf16_bits_counts": dict(sorted(counts.items())),
            }
    return result


def compact_snapshot(payload: bytes, *, rows: int) -> dict[str, Any]:
    a2 = load_a2()
    a2.validate_snapshot(payload, rows=rows, cols=COLS)
    width = COLS * 2
    active = b"".join(
        payload[row * width : row * width + ACTIVE_COLS * 2] for row in range(rows)
    )
    tail = b"".join(
        payload[row * width + ACTIVE_COLS * 2 : (row + 1) * width]
        for row in range(rows)
    )
    tail_values = array("H")
    tail_values.frombytes(tail)
    return {
        "sha256": digest_bytes(payload),
        "active_columns_0_324_sha256": digest_bytes(active),
        "synthetic_padding_columns_324_336_sha256": digest_bytes(tail),
        "synthetic_padding_all_numeric_zero": all(
            bits & 0x7FFF == 0 for bits in tail_values
        ),
    }


def extract_row(payload: bytes, row: int) -> bytes:
    if row < 0 or row >= ROWS or len(payload) != ROWS * COLS * 2:
        raise ValueError("row extraction shape/index drift")
    width = COLS * 2
    return payload[row * width : (row + 1) * width]


def latency_report(samples_us: list[float]) -> dict[str, Any]:
    if not samples_us or any(
        not math.isfinite(value) or value < 0 for value in samples_us
    ):
        raise RuntimeError("invalid synchronized event latency")
    ordered = sorted(samples_us)
    return {
        "unit": "microseconds",
        "synchronized_xpu_event": True,
        "samples": samples_us,
        "count": len(samples_us),
        "minimum": ordered[0],
        "median": statistics.median(ordered),
        "maximum": ordered[-1],
    }


def protocol_report(
    payloads: list[bytes],
    *,
    rows: int,
    coordinates: dict[int, tuple[int, ...]],
    latencies_us: list[float],
) -> dict[str, Any]:
    if not payloads:
        raise ValueError("protocol has no payloads")
    a2 = load_a2()
    snapshots = [compact_snapshot(payload, rows=rows) for payload in payloads]
    reference = payloads[0]
    comparisons = [
        a2.compare_bf16(reference, payload, rows=rows, cols=COLS)
        for payload in payloads[1:]
    ]
    return {
        "invocations": snapshots,
        "unique_full_output_sha256": sorted(
            {snapshot["sha256"] for snapshot in snapshots}
        ),
        "unique_active_output_sha256": sorted(
            {snapshot["active_columns_0_324_sha256"] for snapshot in snapshots}
        ),
        "unique_synthetic_tail_sha256": sorted(
            {
                snapshot["synthetic_padding_columns_324_336_sha256"]
                for snapshot in snapshots
            }
        ),
        "all_synthetic_padding_numeric_zero": all(
            snapshot["synthetic_padding_all_numeric_zero"] for snapshot in snapshots
        ),
        "comparisons_to_invocation0": comparisons,
        "coordinate_distributions": coordinate_distributions(
            payloads, rows=rows, coordinates=coordinates
        ),
        "latency": latency_report(latencies_us),
    }


@contextmanager
def scoped_mkldnn_deterministic(torch, requested: bool) -> Iterator[dict[str, Any]]:
    before = bool(torch.backends.mkldnn.deterministic)
    receipt: dict[str, Any] = {
        "before": before,
        "requested": requested,
        "after_set": None,
        "restored": None,
    }
    try:
        torch.backends.mkldnn.deterministic = requested
        receipt["after_set"] = bool(torch.backends.mkldnn.deterministic)
        if receipt["after_set"] is not requested:
            raise RuntimeError("mkldnn deterministic setting did not apply")
        yield receipt
    finally:
        torch.backends.mkldnn.deterministic = before
        receipt["restored"] = bool(torch.backends.mkldnn.deterministic)
        if receipt["restored"] is not before and sys.exc_info()[0] is None:
            raise RuntimeError("mkldnn deterministic setting did not restore")


def timed_linear(torch, functional, inputs, weight):
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    output = functional.linear(inputs, weight)
    end.record()
    torch.xpu.synchronize()
    elapsed_us = float(start.elapsed_time(end)) * 1000.0
    return output, elapsed_us


def timed_ordinal_sweep(torch, functional, inputs, weight):
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    outputs = [functional.linear(inputs[row : row + 1], weight) for row in range(ROWS)]
    joined = torch.cat(outputs, dim=0)
    end.record()
    torch.xpu.synchronize()
    elapsed_us = float(start.elapsed_time(end)) * 1000.0
    return joined, elapsed_us


def execute_arm(torch, functional, inputs, weight, *, arm: str) -> dict[str, Any]:
    if arm not in ARMS:
        raise ValueError("unknown A3 arm")
    requested = arm == "mkldnn-deterministic"
    setting_receipt: dict[str, Any]
    with scoped_mkldnn_deterministic(torch, requested) as setting_receipt:
        for _ in range(WARMUP_SWEEPS):
            joined, _ = timed_ordinal_sweep(torch, functional, inputs, weight)
            if joined.dtype != torch.bfloat16 or tuple(joined.shape) != (ROWS, COLS):
                raise RuntimeError("A3 warmup output shape/dtype drift")

        consecutive: dict[str, Any] = {}
        for row in FOCUS_ROWS:
            payloads = []
            latencies_us = []
            for _ in range(CONSECUTIVE_REPEATS):
                output, elapsed_us = timed_linear(
                    torch, functional, inputs[row : row + 1], weight
                )
                if output.dtype != torch.bfloat16 or tuple(output.shape) != (1, COLS):
                    raise RuntimeError("A3 consecutive output shape/dtype drift")
                payload = load_a2().tensor_bytes(output)
                load_a2().validate_snapshot(payload, rows=1, cols=COLS)
                payloads.append(payload)
                latencies_us.append(elapsed_us)
            local_coordinates = {
                0: tuple(RECURRENT_COORDINATES[row]),
            }
            report = protocol_report(
                payloads,
                rows=1,
                coordinates=local_coordinates,
                latencies_us=latencies_us,
            )
            report["source_row"] = row
            report["reported_coordinate_translation"] = {
                f"0,{col}": f"{row},{col}" for col in RECURRENT_COORDINATES[row]
            }
            consecutive[str(row)] = report

        ordinal_payloads = []
        ordinal_latencies_us = []
        for _ in range(ORDINAL_SWEEPS):
            joined, elapsed_us = timed_ordinal_sweep(torch, functional, inputs, weight)
            if joined.dtype != torch.bfloat16 or tuple(joined.shape) != (ROWS, COLS):
                raise RuntimeError("A3 ordinal output shape/dtype drift")
            payload = load_a2().tensor_bytes(joined)
            load_a2().validate_snapshot(payload, rows=ROWS, cols=COLS)
            ordinal_payloads.append(payload)
            ordinal_latencies_us.append(elapsed_us)
        ordinal = protocol_report(
            ordinal_payloads,
            rows=ROWS,
            coordinates=RECURRENT_COORDINATES,
            latencies_us=ordinal_latencies_us,
        )
        ordinal["focus_row_invocations"] = {
            str(row): [
                compact_snapshot(extract_row(payload, row), rows=1)
                for payload in ordinal_payloads
            ]
            for row in FOCUS_ROWS
        }
    if setting_receipt["restored"] != setting_receipt["before"]:
        raise RuntimeError("A3 backend setting restoration drift")
    return {
        "setting": setting_receipt,
        "warmup_complete_sweeps": WARMUP_SWEEPS,
        "consecutive_focus_rows": consecutive,
        "full_order_ordinal_sweeps": ordinal,
    }


def run_cell(arm: str, replica: int) -> dict[str, Any]:
    if arm not in ARMS:
        raise ValueError("arm is outside A3")
    if replica not in REPLICAS:
        raise ValueError("replica is outside A3")
    signal.alarm(CELL_TIMEOUT_SECONDS)
    verify_environment()
    a2 = load_a2()
    a1 = a2.load_a1()
    admission = a1.validate_admission()
    identity = a1.verify_static_identity()
    a1.refuse_active_accelerator_owner()
    lock = a1.acquire_component_lock()
    if (
        a2.SHARD_CONTRACT.is_symlink()
        or sha256(a2.SHARD_CONTRACT) != a2.SHARD_CONTRACT_FILE_SHA256
    ):
        raise RuntimeError("A1 shard contract is absent or invalid")
    contract = json.loads(a2.SHARD_CONTRACT.read_text(encoding="utf-8"))
    if a1.canonical_sha256(contract) != a2.SHARD_CONTRACT_SHA256:
        raise RuntimeError("A1 shard contract canonical identity drift")
    a1.validate_shard_contract(contract)

    import safetensors
    import torch
    import torch.nn.functional as functional

    if torch.__version__ != a1.TORCH_VERSION:
        raise RuntimeError(f"Torch identity drift: {torch.__version__}")
    if torch.version.git_version != TORCH_GIT_VERSION:
        raise RuntimeError(f"Torch Git identity drift: {torch.version.git_version}")
    if sha256(PROVIDER_LIBRARY) != PROVIDER_LIBRARY_SHA256:
        raise RuntimeError("Torch XPU provider library identity drift")
    build_sha = hashlib.sha256(torch.__config__.show().encode()).hexdigest()
    if build_sha != a1.TORCH_BUILD_CONFIG_SHA256:
        raise RuntimeError(f"Torch build identity drift: {build_sha}")
    if safetensors.__version__ != a1.SAFETENSORS_VERSION:
        raise RuntimeError(f"Safetensors identity drift: {safetensors.__version__}")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("A3 requires exactly one selected XPU")

    sentinel = a1.resolve_sentinel(FAMILY, SENTINEL)
    weight_cpu, shards, source_tensors = a1.load_weight(FAMILY, sentinel)
    generator = torch.Generator(device="cpu").manual_seed(SEED)
    input_cpu = (
        torch.randn((ROWS, a1.FAMILIES[FAMILY]["k"]), generator=generator)
        .mul_(0.01)
        .to(torch.bfloat16)
    )
    input_expected = a1.tensor_sha256(input_cpu)
    weight_expected = a1.tensor_sha256(weight_cpu)
    device = torch.device("xpu:0")
    weight = weight_cpu.to(device)
    inputs = input_cpu.to(device)
    torch.xpu.synchronize()
    native_pre_gemm = a2.native_map_snapshot()

    arm_report = execute_arm(torch, functional, inputs, weight, arm=arm)
    input_after = a1.tensor_sha256(inputs)
    weight_after = a1.tensor_sha256(weight)
    diagnostic_errors = []
    if input_expected != input_after or weight_expected != weight_after:
        diagnostic_errors.append(
            {
                "type": "MutationError",
                "message": "A3 input or weight mutated",
                "input_after_sha256": input_after,
                "weight_after_sha256": weight_after,
            }
        )
    try:
        native_post_gemm = {
            "status": "validated",
            "contract": a1.loaded_native_library_contract(),
        }
    except BaseException as error:
        native_post_gemm = {
            "status": "error",
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        diagnostic_errors.append(native_post_gemm["error"])
    del lock
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-singleton-a3-cell.v1",
        "status": "diagnostic_complete"
        if not diagnostic_errors
        else "diagnostic_error",
        "classification": "report_only_targeted_m1_backend_discriminator",
        "identity": {
            **identity,
            "a2_tool_sha256": A2_TOOL_SHA256,
            "a1_tool_sha256": a2.A1_TOOL_SHA256,
            "a1_shard_contract_canonical_sha256": a2.SHARD_CONTRACT_SHA256,
            "family": FAMILY,
            "sentinel": sentinel,
            "seed": SEED,
            "arm": arm,
            "replica": replica,
            "model_revision": a1.MODEL_REVISION,
            "source_tensors": source_tensors,
            "checkpoint_shards": shards,
            "input_sha256": input_expected,
            "weight_sha256": weight_expected,
            "environment": verify_environment(),
            "native_mappings_pre_gemm": native_pre_gemm,
            "native_libraries_post_gemm": native_post_gemm,
            "deterministic_provider_evidence": {
                "library": str(PROVIDER_LIBRARY),
                "library_sha256": PROVIDER_LIBRARY_SHA256,
                "torch_git_version": TORCH_GIT_VERSION,
                "binary_imports_deterministic_mkldnn": True,
                "binary_contains_onednn_deterministic_attribute": True,
                "source_mapping_independently_audited": True,
                "runtime_verbose_receipt": False,
            },
            "admission": admission,
        },
        "protocol": {
            "rows": ROWS,
            "cols": COLS,
            "active_cols": ACTIVE_COLS,
            "focus_rows": list(FOCUS_ROWS),
            "recurrent_coordinates": {
                str(row): list(cols) for row, cols in RECURRENT_COORDINATES.items()
            },
            "consecutive_repeats": CONSECUTIVE_REPEATS,
            "ordinal_sweeps": ORDINAL_SWEEPS,
        },
        "arm_report": arm_report,
        "diagnostic_errors": diagnostic_errors,
        "interpretation": {
            "runtime_change_authorized": False,
            "speed_or_quality_credit": False,
            "endpoint_claim_authorized": False,
        },
    }


def atomic_write(path: Path, value: object) -> None:
    load_a2().atomic_write(path, value)


def run_cell_enveloped(arm: str, replica: int) -> None:
    if not A3_ROOT.is_dir() or A3_ROOT.is_symlink():
        raise RuntimeError("A3 cell requires the parent-created external evidence root")
    output = A3_ROOT / f"{arm}-replica{replica}.json"
    started = time.time_ns()
    payload: dict[str, Any] | None = None
    failure: BaseException | None = None
    try:
        payload = run_cell(arm, replica)
        if payload.get("status") != "diagnostic_complete":
            failure = RuntimeError("A3 cell recorded a mutation or provider error")
    except BaseException as error:
        failure = error
        payload = {
            "schema": "neural.download.qwen38-flash-next.bf16-singleton-a3-cell.v1",
            "status": "diagnostic_error",
            "classification": "report_only_failure_envelope",
            "identity": {
                "a2_tool_sha256": A2_TOOL_SHA256,
                "family": FAMILY,
                "sentinel": SENTINEL,
                "seed": SEED,
                "arm": arm,
                "replica": replica,
            },
            "error": {"type": type(error).__name__, "message": str(error)},
            "runtime_change_authorized": False,
        }
    finally:
        assert payload is not None
        try:
            payload["child_postflight"] = {
                "status": "pass",
                "receipt": load_a2().load_a1().validate_admission(),
            }
        except BaseException as postflight_error:
            payload["child_postflight"] = {
                "status": "error",
                "error": {
                    "type": type(postflight_error).__name__,
                    "message": str(postflight_error),
                },
            }
            if failure is None:
                failure = postflight_error
                payload["status"] = "diagnostic_error"
        payload["started_time_ns"] = started
        payload["completed_time_ns"] = time.time_ns()
        atomic_write(output, payload)
    if failure is not None:
        raise RuntimeError(
            f"A3 arm {arm} replica {replica} failed after preserving its diagnostic envelope"
        ) from failure


def summarize(root: Path) -> dict[str, Any]:
    records = {
        (arm, replica): json.loads(
            (root / f"{arm}-replica{replica}.json").read_text(encoding="utf-8")
        )
        for arm in ARMS
        for replica in REPLICAS
    }
    identities = [record["identity"] for record in records.values()]
    identity_comparisons = {
        key: len({identity[key] for identity in identities}) == 1
        for key in ("input_sha256", "weight_sha256", "model_revision")
    }
    identity_exact = all(identity_comparisons.values())
    arm_summary = {}
    authority_hashes_by_arm: dict[str, dict[str, str]] = {}
    for arm in ARMS:
        replica_summaries = {}
        for replica in REPLICAS:
            report = records[(arm, replica)]["arm_report"]
            ordinal = report["full_order_ordinal_sweeps"]
            replica_summaries[str(replica)] = {
                "setting": report["setting"],
                "ordinal_unique_full_outputs": len(
                    ordinal["unique_full_output_sha256"]
                ),
                "ordinal_unique_active_outputs": len(
                    ordinal["unique_active_output_sha256"]
                ),
                "ordinal_unique_tails": len(ordinal["unique_synthetic_tail_sha256"]),
                "ordinal_tail_all_numeric_zero": ordinal[
                    "all_synthetic_padding_numeric_zero"
                ],
                "ordinal_coordinate_unique_bits": {
                    coordinate: value["unique_bf16_bits"]
                    for coordinate, value in ordinal["coordinate_distributions"].items()
                },
                "ordinal_focus_unique_active_outputs": {
                    row: len(
                        {item["active_columns_0_324_sha256"] for item in invocations}
                    )
                    for row, invocations in ordinal["focus_row_invocations"].items()
                },
                "consecutive_unique_active_outputs": {
                    row: len(value["unique_active_output_sha256"])
                    for row, value in report["consecutive_focus_rows"].items()
                },
                "consecutive_coordinate_unique_bits": {
                    row: {
                        value["reported_coordinate_translation"][coordinate]: detail[
                            "unique_bf16_bits"
                        ]
                        for coordinate, detail in value[
                            "coordinate_distributions"
                        ].items()
                    }
                    for row, value in report["consecutive_focus_rows"].items()
                },
                "ordinal_latency_median_us": ordinal["latency"]["median"],
                "consecutive_latency_median_us_by_row": {
                    row: value["latency"]["median"]
                    for row, value in report["consecutive_focus_rows"].items()
                },
            }
        output_authorities = {}
        for replica in REPLICAS:
            report = records[(arm, replica)]["arm_report"]
            ordinal = report["full_order_ordinal_sweeps"]
            output_authorities[str(replica)] = {
                "ordinal_invocation_hashes": [
                    {
                        "full": item["sha256"],
                        "active": item["active_columns_0_324_sha256"],
                        "tail": item["synthetic_padding_columns_324_336_sha256"],
                        "tail_all_numeric_zero": item[
                            "synthetic_padding_all_numeric_zero"
                        ],
                    }
                    for item in ordinal["invocations"]
                ],
                "ordinal_coordinate_distributions": ordinal["coordinate_distributions"],
                "ordinal_focus_row_invocation_hashes": ordinal["focus_row_invocations"],
                "consecutive_invocation_hashes": {
                    row: [
                        {
                            "full": item["sha256"],
                            "active": item["active_columns_0_324_sha256"],
                            "tail": item["synthetic_padding_columns_324_336_sha256"],
                            "tail_all_numeric_zero": item[
                                "synthetic_padding_all_numeric_zero"
                            ],
                        }
                        for item in value["invocations"]
                    ]
                    for row, value in report["consecutive_focus_rows"].items()
                },
                "consecutive_coordinate_distributions": {
                    row: value["coordinate_distributions"]
                    for row, value in report["consecutive_focus_rows"].items()
                },
            }
        protocol_hashes = {
            replica: digest_bytes(json.dumps(authority, sort_keys=True).encode())
            for replica, authority in output_authorities.items()
        }
        authority_hashes_by_arm[arm] = protocol_hashes
        ordinal_active_sequences = {
            replica: tuple(
                item["active"] for item in authority["ordinal_invocation_hashes"]
            )
            for replica, authority in output_authorities.items()
        }
        consecutive_active_sequences = {
            row: {
                replica: tuple(
                    item["active"]
                    for item in authority["consecutive_invocation_hashes"][row]
                )
                for replica, authority in output_authorities.items()
            }
            for row in map(str, FOCUS_ROWS)
        }
        arm_summary[arm] = {
            "replicas": replica_summaries,
            "output_authority_sha256_by_replica": protocol_hashes,
            "output_authority_exact_across_processes": len(
                set(protocol_hashes.values())
            )
            == 1,
            "ordinal_active_sequence_exact_across_processes": len(
                set(ordinal_active_sequences.values())
            )
            == 1,
            "consecutive_active_sequence_exact_across_processes_by_row": {
                row: len(set(values.values())) == 1
                for row, values in consecutive_active_sequences.items()
            },
        }
    setting_exact = (
        all(
            records[("native", replica)]["arm_report"]["setting"]["after_set"] is False
            for replica in REPLICAS
        )
        and all(
            records[("mkldnn-deterministic", replica)]["arm_report"]["setting"][
                "after_set"
            ]
            is True
            for replica in REPLICAS
        )
        and all(
            record["arm_report"]["setting"]["restored"]
            == record["arm_report"]["setting"]["before"]
            for record in records.values()
        )
    )
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-singleton-a3-summary.v1",
        "status": "diagnostic_complete"
        if identity_exact and setting_exact
        else "diagnostic_error",
        "arms": list(ARMS),
        "identity_exact_across_processes": identity_exact,
        "identity_comparisons": identity_comparisons,
        "backend_setting_exact_and_restored": setting_exact,
        "native_candidate_output_authority_exact_by_replica": {
            str(replica): authority_hashes_by_arm["native"][str(replica)]
            == authority_hashes_by_arm["mkldnn-deterministic"][str(replica)]
            for replica in REPLICAS
        },
        "arm_summary": arm_summary,
        "report_only": True,
        "runtime_change_authorized": False,
    }


def run_plan() -> Path:
    if os.environ.get(AUTHORITY_ENV) != "YES":
        raise RuntimeError(f"set {AUTHORITY_ENV}=YES")
    a1 = load_a2().load_a1()
    initial = a1.validate_admission()
    a1.verify_static_identity()
    a1.refuse_active_accelerator_owner()
    if A3_ROOT.exists():
        raise FileExistsError(f"refusing existing A3 root: {A3_ROOT}")
    A3_ROOT.mkdir(parents=True)
    deadline = time.monotonic() + PLAN_TIMEOUT_SECONDS
    failures: list[dict[str, str]] = []
    for arm in ARMS:
        for replica in REPLICAS:
            before = a1.validate_admission()
            child_error: BaseException | None = None
            postflight_error: BaseException | None = None
            parent_postflight: dict[str, Any] = {"status": "not_run"}
            try:
                subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "run-cell",
                        "--arm",
                        arm,
                        "--replica",
                        str(replica),
                    ],
                    check=True,
                    env=dict(A3_ENVIRONMENT),
                    timeout=min(
                        CELL_TIMEOUT_SECONDS,
                        max(1, int(deadline - time.monotonic())),
                    ),
                )
            except BaseException as error:
                child_error = error
            finally:
                try:
                    after = a1.validate_admission()
                    if after["aer_event_count"] != before["aer_event_count"]:
                        raise RuntimeError("new AER event during A3 arm")
                    parent_postflight = {"status": "pass", "receipt": after}
                except BaseException as error:
                    postflight_error = error
                    parent_postflight = {
                        "status": "error",
                        "error": {"type": type(error).__name__, "message": str(error)},
                    }
                atomic_write(
                    A3_ROOT / f"parent-postflight-{arm}-replica{replica}.json",
                    parent_postflight,
                )
                child_output = A3_ROOT / f"{arm}-replica{replica}.json"
                if child_error is not None and not child_output.exists():
                    atomic_write(
                        child_output,
                        {
                            "schema": "neural.download.qwen38-flash-next.bf16-singleton-a3-cell.v1",
                            "status": "diagnostic_error",
                            "classification": "parent_preserved_missing_child_envelope",
                            "identity": {
                                "arm": arm,
                                "replica": replica,
                                "a2_tool_sha256": A2_TOOL_SHA256,
                            },
                            "error": {
                                "type": type(child_error).__name__,
                                "message": str(child_error),
                            },
                            "parent_postflight": parent_postflight,
                            "runtime_change_authorized": False,
                        },
                    )
            if child_error is not None:
                failures.append(
                    {
                        "arm": arm,
                        "replica": str(replica),
                        "type": type(child_error).__name__,
                        "message": str(child_error),
                    }
                )
            if postflight_error is not None:
                failures.append(
                    {
                        "arm": arm,
                        "replica": str(replica),
                        "type": type(postflight_error).__name__,
                        "message": str(postflight_error),
                    }
                )
                break
        if failures:
            break
    final_health: dict[str, Any]
    try:
        final_health = {"status": "pass", "receipt": a1.validate_admission()}
    except BaseException as error:
        final_health = {
            "status": "error",
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        failures.append(final_health["error"])
    if failures:
        atomic_write(
            A3_ROOT / "plan-status.json",
            {
                "schema": "neural.download.qwen38-flash-next.bf16-singleton-a3-plan.v1",
                "status": "diagnostic_error",
                "failures": failures,
                "initial_health": initial,
                "final_health": final_health,
            },
        )
        raise RuntimeError("A3 plan failed after preserving evidence and postflight")
    result = summarize(A3_ROOT)
    result["initial_health"] = initial
    result["final_health"] = final_health
    summary_path = A3_ROOT / "summary.json"
    atomic_write(summary_path, result)
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("plan")
    sub.add_parser("run-plan")
    cell = sub.add_parser("run-cell")
    cell.add_argument("--arm", choices=ARMS, required=True)
    cell.add_argument("--replica", type=int, choices=REPLICAS, required=True)
    args = parser.parse_args()
    if args.command in (None, "plan"):
        print(
            json.dumps(
                {
                    "family": FAMILY,
                    "sentinel": SENTINEL,
                    "seed": SEED,
                    "arms": list(ARMS),
                    "replicas_per_arm": len(REPLICAS),
                    "focus_rows": list(FOCUS_ROWS),
                    "device_execution": False,
                },
                sort_keys=True,
            )
        )
        return
    if args.command == "run-plan":
        print(run_plan())
        return
    run_cell_enveloped(args.arm, args.replica)


if __name__ == "__main__":
    main()
