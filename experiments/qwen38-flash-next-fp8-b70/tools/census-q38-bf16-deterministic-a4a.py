#!/usr/bin/env python3
"""A4a M=1 census of the deterministic oneDNN attribute on Flash-Next."""

from __future__ import annotations

import argparse
from array import array
from functools import cache
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import signal
import statistics
import subprocess
import sys
import time
from typing import Any


HERE = Path(__file__).resolve().parent
A1_TOOL = HERE / "census-q38-bf16-dense-invariance.py"
A1_TOOL_SHA256 = "e4700fc44a65d71c7b0a7df5ff34924d808ba685c4157b0e2c12fd4b9d4bdf22"
A3_TOOL = HERE / "diagnose-q38-bf16-singleton-a3.py"
A3_TOOL_SHA256 = "8ddd0dae1b1a1153bc9c791c9192df87ed0daeb1dcdc7f73313564e8e16dca57"
A3_RESULT = HERE.parent / "data/20260902-bf16-singleton-a3-result.json"
A3_RESULT_SHA256 = "82c71fafec724369d4fd58d8e6ab1948db4ca75db8b9285de0e51710f22f2bef"
EVIDENCE_BASE = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
A4A_ROOT = EVIDENCE_BASE / "bf16-deterministic-census-20260902-a4a"
ROWS = 256
SWEEPS = 100
WARMUP_SWEEPS = 4
INPUT_SEED = 2026090201
ARMS = ("native", "mkldnn-deterministic")
REPLICAS = (1, 2)
AUTHORITY_ENV = "Q38_BF16_DETERMINISTIC_A4A_EXECUTE"
CELL_TIMEOUT_SECONDS = 1200
PLAN_TIMEOUT_SECONDS = 12 * 60 * 60
BOOTSTRAP_SEED = 2026090204
BOOTSTRAP_REPLICATES = 10_000
CENTRAL_RATIO_MAX = 1.000
BOOTSTRAP_UPPER_95_MAX = 1.010
COUNTERBALANCE_HALF_RATIO_MAX = 1.020
HOT_FAMILY_CALL_THRESHOLD = 12
HOT_FAMILY_POINT_RATIO_MAX = 1.020
A4A_ENVIRONMENT = {
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


def canonical_sha256(value: object) -> str:
    return digest_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    )


def _load_tool(path: Path, expected_sha256: str, name: str):
    if sha256(path) != expected_sha256:
        raise RuntimeError(f"{name} tool identity drift")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen {name} tool")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@cache
def load_a1():
    return _load_tool(A1_TOOL, A1_TOOL_SHA256, "q38_bf16_a1_frozen")


@cache
def load_a3():
    return _load_tool(A3_TOOL, A3_TOOL_SHA256, "q38_bf16_a3_frozen")


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
        if key in A4A_ENVIRONMENT or key.startswith(prefixes)
    }
    if relevant != A4A_ENVIRONMENT:
        raise RuntimeError(f"A4a GEMM environment drift: {sorted(relevant)}")
    return relevant


def validate_catalog() -> None:
    a1 = load_a1()
    a1.validate_catalog()
    if len(a1.FAMILIES) != 14:
        raise RuntimeError("A4a requires exactly 14 frozen BF16 families")
    if sum(spec["calls"] for spec in a1.FAMILIES.values()) != 532:
        raise RuntimeError("A4a multiplicities must sum to 532")
    for family, spec in a1.FAMILIES.items():
        if len(spec["sentinels"]) != 2:
            raise RuntimeError(f"A4a family {family} must have two sentinels")


def active_columns(family: str) -> int:
    a1 = load_a1()
    if family not in a1.FAMILIES:
        raise ValueError("unknown A4a family")
    return 324 if family == "hc_down_inject" else int(a1.FAMILIES[family]["n"])


def canonical_cells() -> list[dict[str, Any]]:
    validate_catalog()
    cells = []
    for family_index, (family, spec) in enumerate(load_a1().FAMILIES.items()):
        for sentinel_index, sentinel in enumerate(spec["sentinels"]):
            index = family_index * 2 + sentinel_index
            cells.append(
                {
                    "cell_index": index,
                    "family_index": family_index,
                    "sentinel_index": sentinel_index,
                    "family": family,
                    "sentinel": sentinel["id"],
                    "calls_per_token": spec["calls"],
                    "counterbalance_pattern": "ABBA" if index % 2 == 0 else "BAAB",
                }
            )
    if len(cells) != 28:
        raise RuntimeError("A4a canonical cell count drift")
    return cells


def arm_schedule(cell_index: int) -> list[dict[str, Any]]:
    if cell_index < 0 or cell_index >= 28:
        raise ValueError("A4a cell index outside plan")
    if cell_index % 2 == 0:
        values = (
            ("native", 1, "A"),
            ("mkldnn-deterministic", 1, "B"),
            ("mkldnn-deterministic", 2, "B"),
            ("native", 2, "A"),
        )
    else:
        values = (
            ("mkldnn-deterministic", 1, "B"),
            ("native", 1, "A"),
            ("native", 2, "A"),
            ("mkldnn-deterministic", 2, "B"),
        )
    return [
        {"arm": arm, "replica": replica, "label": label, "position": position}
        for position, (arm, replica, label) in enumerate(values, start=1)
    ]


def process_plan() -> list[dict[str, Any]]:
    result = []
    for cell in canonical_cells():
        for arm in arm_schedule(cell["cell_index"]):
            result.append({**cell, **arm})
    if len(result) != 112:
        raise RuntimeError("A4a process count drift")
    return result


def cell_directory(cell: dict[str, Any], *, root: Path = A4A_ROOT) -> Path:
    return (
        root
        / "cells"
        / (f"{cell['cell_index']:02d}-{cell['family']}--{cell['sentinel']}")
    )


def arm_filename(arm: str, replica: int) -> str:
    if arm not in ARMS or replica not in REPLICAS:
        raise ValueError("A4a arm filename identity outside plan")
    return f"{arm}-replica{replica}.json"


def row_hashes(payload: bytes, *, n: int, active_n: int) -> dict[str, Any]:
    if len(payload) != ROWS * n * 2 or not 0 < active_n <= n:
        raise ValueError("A4a output byte shape drift")
    width = n * 2
    active_width = active_n * 2
    full = []
    active = []
    tail = []
    tail_numeric_zero = True
    for row in range(ROWS):
        row_payload = payload[row * width : (row + 1) * width]
        active_payload = row_payload[:active_width]
        tail_payload = row_payload[active_width:]
        full.append(digest_bytes(row_payload))
        active.append(digest_bytes(active_payload))
        if active_n < n:
            tail.append(digest_bytes(tail_payload))
            values = array("H")
            values.frombytes(tail_payload)
            tail_numeric_zero = tail_numeric_zero and all(
                bits & 0x7FFF == 0 for bits in values
            )
    return {
        "row_full_sha256": full,
        "row_active_sha256": active,
        "row_tail_sha256": tail,
        "tail_all_numeric_zero": tail_numeric_zero,
    }


def snapshot(payload: bytes, *, n: int, active_n: int) -> dict[str, Any]:
    rows = row_hashes(payload, n=n, active_n=active_n)
    width = n * 2
    active_width = active_n * 2
    active_payload = b"".join(
        payload[row * width : row * width + active_width] for row in range(ROWS)
    )
    tail_payload = b"".join(
        payload[row * width + active_width : (row + 1) * width] for row in range(ROWS)
    )
    return {
        "full_sha256": digest_bytes(payload),
        "active_sha256": digest_bytes(active_payload),
        "tail_sha256": digest_bytes(tail_payload),
        **rows,
    }


def input_row_hashes(input_cpu) -> list[str]:
    import torch

    raw = input_cpu.detach().contiguous().view(torch.uint8).numpy().tobytes()
    width = input_cpu.shape[1] * 2
    hashes = [digest_bytes(raw[row * width : (row + 1) * width]) for row in range(ROWS)]
    if len(set(hashes)) != ROWS:
        raise RuntimeError("A4a fixed input rows are not all distinct")
    return hashes


def execute_arm(torch, functional, inputs, weight, *, family: str, arm: str):
    a1 = load_a1()
    a3 = load_a3()
    n = int(a1.FAMILIES[family]["n"])
    active_n = active_columns(family)
    requested = arm == "mkldnn-deterministic"
    setting_receipt: dict[str, Any]
    with a3.scoped_mkldnn_deterministic(torch, requested) as setting_receipt:
        for _ in range(WARMUP_SWEEPS):
            output, _ = a3.timed_ordinal_sweep(torch, functional, inputs, weight)
            if output.dtype != torch.bfloat16 or tuple(output.shape) != (ROWS, n):
                raise RuntimeError("A4a warmup output shape/dtype drift")
        snapshots = []
        latencies_us = []
        for _ in range(SWEEPS):
            output, elapsed_us = a3.timed_ordinal_sweep(
                torch, functional, inputs, weight
            )
            if output.dtype != torch.bfloat16 or tuple(output.shape) != (ROWS, n):
                raise RuntimeError("A4a measured output shape/dtype drift")
            if not bool(torch.isfinite(output).all().item()):
                raise RuntimeError("A4a measured output contains non-finite BF16")
            payload = a3.load_a2().tensor_bytes(output)
            snapshots.append(snapshot(payload, n=n, active_n=active_n))
            latencies_us.append(elapsed_us)
    if setting_receipt["restored"] != setting_receipt["before"]:
        raise RuntimeError("A4a backend setting restoration drift")
    return {
        "setting": setting_receipt,
        "warmup_sweeps": WARMUP_SWEEPS,
        "measured_sweeps": SWEEPS,
        "snapshots": snapshots,
        "unique_full_sha256": sorted({item["full_sha256"] for item in snapshots}),
        "unique_active_sha256": sorted({item["active_sha256"] for item in snapshots}),
        "unique_tail_sha256": sorted({item["tail_sha256"] for item in snapshots}),
        "all_tail_numeric_zero": all(
            item["tail_all_numeric_zero"] for item in snapshots
        ),
        "latency": a3.latency_report(latencies_us),
    }


def run_cell(args: argparse.Namespace) -> dict[str, Any]:
    if args.arm not in ARMS or args.replica not in REPLICAS:
        raise ValueError("A4a arm identity outside plan")
    signal.alarm(CELL_TIMEOUT_SECONDS)
    verify_environment()
    a1 = load_a1()
    a3 = load_a3()
    cell = canonical_cells()[args.cell_index]
    expected_schedule = {
        (entry["arm"], entry["replica"]): entry
        for entry in arm_schedule(args.cell_index)
    }
    if (
        cell["family"] != args.family
        or cell["sentinel"] != args.sentinel
        or (args.arm, args.replica) not in expected_schedule
    ):
        raise RuntimeError("A4a CLI identity differs from canonical plan")
    schedule = expected_schedule[(args.arm, args.replica)]
    if schedule["position"] != args.position:
        raise RuntimeError("A4a counterbalance position drift")
    admission = a1.validate_admission()
    identity = a1.verify_static_identity()
    a1.refuse_active_accelerator_owner()
    lock = a1.acquire_component_lock()
    a2 = a3.load_a2()
    if (
        a2.SHARD_CONTRACT.is_symlink()
        or sha256(a2.SHARD_CONTRACT) != a2.SHARD_CONTRACT_FILE_SHA256
    ):
        raise RuntimeError("A4a frozen shard contract is absent or invalid")
    contract = json.loads(a2.SHARD_CONTRACT.read_text(encoding="utf-8"))
    if a1.canonical_sha256(contract) != a2.SHARD_CONTRACT_SHA256:
        raise RuntimeError("A4a shard contract canonical identity drift")
    a1.validate_shard_contract(contract)

    import safetensors
    import torch
    import torch.nn.functional as functional

    if torch.__version__ != a1.TORCH_VERSION:
        raise RuntimeError(f"Torch identity drift: {torch.__version__}")
    if torch.version.git_version != a3.TORCH_GIT_VERSION:
        raise RuntimeError(f"Torch Git identity drift: {torch.version.git_version}")
    build_sha = hashlib.sha256(torch.__config__.show().encode()).hexdigest()
    if build_sha != a1.TORCH_BUILD_CONFIG_SHA256:
        raise RuntimeError(f"Torch build identity drift: {build_sha}")
    if safetensors.__version__ != a1.SAFETENSORS_VERSION:
        raise RuntimeError(f"Safetensors identity drift: {safetensors.__version__}")
    if sha256(a3.PROVIDER_LIBRARY) != a3.PROVIDER_LIBRARY_SHA256:
        raise RuntimeError("A4a Torch XPU provider library identity drift")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("A4a requires exactly one selected XPU")

    sentinel = a1.resolve_sentinel(args.family, args.sentinel)
    weight_cpu, shards, source_tensors = a1.load_weight(args.family, sentinel)
    if not set(shards).issubset(contract["shards"]):
        raise RuntimeError("A4a selected checkpoint shard is outside contract")
    generator = torch.Generator(device="cpu").manual_seed(INPUT_SEED)
    input_cpu = (
        torch.randn((ROWS, a1.FAMILIES[args.family]["k"]), generator=generator)
        .mul_(0.01)
        .to(torch.bfloat16)
    )
    input_rows = input_row_hashes(input_cpu)
    input_expected = a1.tensor_sha256(input_cpu)
    weight_expected = a1.tensor_sha256(weight_cpu)
    device = torch.device("xpu:0")
    weight = weight_cpu.to(device)
    inputs = input_cpu.to(device)
    torch.xpu.synchronize()
    native_pre_gemm = a2.native_map_snapshot()

    arm_report = execute_arm(
        torch, functional, inputs, weight, family=args.family, arm=args.arm
    )
    input_after = a1.tensor_sha256(inputs)
    weight_after = a1.tensor_sha256(weight)
    errors = []
    if input_after != input_expected or weight_after != weight_expected:
        errors.append(
            {
                "type": "MutationError",
                "message": "A4a input or weight mutated",
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
        errors.append(native_post_gemm["error"])
    del lock
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-deterministic-a4a-cell.v1",
        "status": "classified" if not errors else "diagnostic_error",
        "classification": "component_only_real_weight_m1_deterministic_census",
        "identity": {
            **identity,
            "model": "Qwen/Qwen3.8-Flash-Next-FP8",
            "model_revision": a1.MODEL_REVISION,
            "a1_tool_sha256": A1_TOOL_SHA256,
            "a3_tool_sha256": A3_TOOL_SHA256,
            "a3_result_sha256": A3_RESULT_SHA256,
            "provider_library_sha256": a3.PROVIDER_LIBRARY_SHA256,
            "family": args.family,
            "sentinel": sentinel,
            "cell_index": args.cell_index,
            "counterbalance_pattern": cell["counterbalance_pattern"],
            "counterbalance_position": args.position,
            "arm": args.arm,
            "replica": args.replica,
            "seed": INPUT_SEED,
            "input_sha256": input_expected,
            "input_row_sha256": input_rows,
            "weight_sha256": weight_expected,
            "source_tensors": source_tensors,
            "checkpoint_shards": shards,
            "shard_contract_sha256": a2.SHARD_CONTRACT_SHA256,
            "environment": verify_environment(),
            "native_mappings_pre_gemm": native_pre_gemm,
            "native_libraries_post_gemm": native_post_gemm,
            "admission": admission,
        },
        "shape": {
            "input": [1, a1.FAMILIES[args.family]["k"]],
            "weight": [
                a1.FAMILIES[args.family]["n"],
                a1.FAMILIES[args.family]["k"],
            ],
            "sweep_rows": ROWS,
            "active_output_columns": [0, active_columns(args.family)],
            "synthetic_tail_columns": [
                active_columns(args.family),
                a1.FAMILIES[args.family]["n"],
            ],
            "calls_per_target_token": a1.FAMILIES[args.family]["calls"],
        },
        "arm_report": arm_report,
        "diagnostic_errors": errors,
        "credit": {
            "report_only": True,
            "endpoint_change_authorized": False,
            "speed_credit": False,
            "quality_credit": False,
        },
    }


def atomic_write(path: Path, value: object) -> None:
    load_a1().atomic_write_json(path, value)


def run_cell_enveloped(args: argparse.Namespace) -> None:
    if not A4A_ROOT.is_dir() or A4A_ROOT.is_symlink():
        raise RuntimeError("A4a child requires parent-created evidence root")
    output = args.output.resolve()
    expected_parent = cell_directory(canonical_cells()[args.cell_index]).resolve()
    if output.parent != expected_parent or output.name != arm_filename(
        args.arm, args.replica
    ):
        raise RuntimeError("A4a child output escaped its canonical path")
    started = time.time_ns()
    payload: dict[str, Any] | None = None
    failure: BaseException | None = None
    try:
        payload = run_cell(args)
        if payload.get("status") != "classified":
            failure = RuntimeError("A4a cell recorded identity/provider error")
    except BaseException as error:
        failure = error
        payload = {
            "schema": "neural.download.qwen38-flash-next.bf16-deterministic-a4a-cell.v1",
            "status": "diagnostic_error",
            "classification": "report_only_failure_envelope",
            "identity": {
                "family": args.family,
                "sentinel": {"id": args.sentinel},
                "cell_index": args.cell_index,
                "counterbalance_position": args.position,
                "arm": args.arm,
                "replica": args.replica,
                "a1_tool_sha256": A1_TOOL_SHA256,
                "a3_tool_sha256": A3_TOOL_SHA256,
            },
            "error": {"type": type(error).__name__, "message": str(error)},
            "runtime_change_authorized": False,
        }
    finally:
        assert payload is not None
        try:
            payload["child_postflight"] = {
                "status": "pass",
                "receipt": load_a1().validate_admission(),
            }
        except BaseException as error:
            payload["child_postflight"] = {
                "status": "error",
                "error": {"type": type(error).__name__, "message": str(error)},
            }
            if failure is None:
                failure = error
                payload["status"] = "diagnostic_error"
        payload["started_time_ns"] = started
        payload["completed_time_ns"] = time.time_ns()
        atomic_write(output, payload)
    if failure is not None:
        raise RuntimeError("A4a cell failed after preserving its envelope") from failure


def _record_output_exact(record: dict[str, Any]) -> bool:
    report = record["arm_report"]
    snapshots = report["snapshots"]
    if len(snapshots) != SWEEPS:
        raise RuntimeError("A4a record sweep count drift")
    row_count = len(snapshots[0]["row_active_sha256"])
    if row_count != ROWS or any(
        len(snapshot["row_active_sha256"]) != ROWS
        or len(snapshot["row_full_sha256"]) != ROWS
        for snapshot in snapshots
    ):
        raise RuntimeError("A4a record row-hash count drift")
    return (
        len(report["unique_active_sha256"]) == 1
        and len(report["unique_tail_sha256"]) == 1
        and report["all_tail_numeric_zero"]
        and all(
            len({snapshot["row_active_sha256"][row] for snapshot in snapshots}) == 1
            for row in range(row_count)
        )
    )


def summarize_cell(
    records: list[dict[str, Any]], cell: dict[str, Any]
) -> dict[str, Any]:
    native = sorted(
        (record for record in records if record["identity"]["arm"] == "native"),
        key=lambda record: record["identity"]["replica"],
    )
    candidate = sorted(
        (
            record
            for record in records
            if record["identity"]["arm"] == "mkldnn-deterministic"
        ),
        key=lambda record: record["identity"]["replica"],
    )
    if len(native) != 2 or len(candidate) != 2:
        raise RuntimeError("A4a cell does not contain two records per arm")
    identity_fields = (
        "model_revision",
        "a1_tool_sha256",
        "a3_tool_sha256",
        "a3_result_sha256",
        "provider_library_sha256",
        "input_sha256",
        "weight_sha256",
        "shard_contract_sha256",
    )
    identity_exact = {
        key: len({record["identity"][key] for record in records}) == 1
        for key in identity_fields
    }
    if not all(identity_exact.values()):
        raise RuntimeError(f"A4a cell identity drift: {identity_exact}")
    for record in records:
        arm = record["identity"]["arm"]
        setting = record["arm_report"]["setting"]
        requested = arm == "mkldnn-deterministic"
        if (
            setting["requested"] is not requested
            or setting["after_set"] is not requested
            or setting["restored"] != setting["before"]
        ):
            raise RuntimeError("A4a backend setting receipt drift")
        if (
            record["shape"]["calls_per_target_token"] != cell["calls_per_token"]
            or record["identity"]["counterbalance_pattern"]
            != cell["counterbalance_pattern"]
            or record.get("child_postflight", {}).get("status") != "pass"
        ):
            raise RuntimeError("A4a shape/counterbalance/postflight drift")
    native_exact = all(_record_output_exact(record) for record in native)
    candidate_exact_within = all(_record_output_exact(record) for record in candidate)
    candidate_active_hashes = {
        snapshot["active_sha256"]
        for record in candidate
        for snapshot in record["arm_report"]["snapshots"]
    }
    candidate_exact_across = (
        candidate_exact_within and len(candidate_active_hashes) == 1
    )
    native_active_hashes = {
        snapshot["active_sha256"]
        for record in native
        for snapshot in record["arm_report"]["snapshots"]
    }
    native_varies = not native_exact or len(native_active_hashes) != 1
    row_count = ROWS
    missing_row_support = []
    for row in range(row_count):
        native_support = {
            snapshot["row_active_sha256"][row]
            for record in native
            for snapshot in record["arm_report"]["snapshots"]
        }
        candidate_values = {
            snapshot["row_active_sha256"][row]
            for record in candidate
            for snapshot in record["arm_report"]["snapshots"]
        }
        if not candidate_values.issubset(native_support):
            missing_row_support.append(row)
    whole_row_native_membership = not missing_row_support
    stable_native_aggregate_match = native_varies or candidate_active_hashes.issubset(
        native_active_hashes
    )
    tail_exact = all(
        record["arm_report"]["all_tail_numeric_zero"]
        and len(record["arm_report"]["unique_tail_sha256"]) == 1
        for record in records
    )
    native_replica_us = [
        record["arm_report"]["latency"]["median"] / ROWS for record in native
    ]
    candidate_replica_us = [
        record["arm_report"]["latency"]["median"] / ROWS for record in candidate
    ]
    native_us = statistics.median(native_replica_us)
    candidate_us = statistics.median(candidate_replica_us)
    ratio = candidate_us / native_us
    return {
        **cell,
        "counterbalance": [
            {
                "arm": record["identity"]["arm"],
                "replica": record["identity"]["replica"],
                "position": record["identity"]["counterbalance_position"],
            }
            for record in sorted(
                records,
                key=lambda record: record["identity"]["counterbalance_position"],
            )
        ],
        "identity_exact_across_processes": identity_exact,
        "native_exact_within_and_across": native_exact
        and len(native_active_hashes) == 1,
        "native_varies": native_varies,
        "candidate_exact_within_processes": candidate_exact_within,
        "candidate_exact_across_processes": candidate_exact_across,
        "candidate_whole_row_hashes_in_native_support": whole_row_native_membership,
        "coordinate_support_implied_by_whole_row_membership": whole_row_native_membership,
        "missing_native_support_rows": missing_row_support,
        "stable_native_aggregate_match": stable_native_aggregate_match,
        "tail_exact": tail_exact,
        "parity_pass": whole_row_native_membership and stable_native_aggregate_match,
        "exactness_pass": candidate_exact_across
        and whole_row_native_membership
        and stable_native_aggregate_match
        and tail_exact,
        "latency": {
            "unit": "microseconds_per_m1_call",
            "native_replica_medians": native_replica_us,
            "candidate_replica_medians": candidate_replica_us,
            "native_median": native_us,
            "candidate_median": candidate_us,
            "candidate_native_ratio": ratio,
        },
    }


def percentile_nearest_rank(values: list[float], probability: float) -> float:
    if not values or not 0 < probability <= 1:
        raise ValueError("invalid nearest-rank percentile")
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def family_cluster_bootstrap(
    family_results: list[dict[str, Any]],
    *,
    seed: int = BOOTSTRAP_SEED,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    if len(family_results) != 14 or replicates <= 0:
        raise ValueError("A4a bootstrap requires 14 families and positive replicates")
    generator = random.Random(seed)
    ratios = []
    for _ in range(replicates):
        sample = [generator.choice(family_results) for _ in family_results]
        native = sum(
            item["calls_per_token"] * item["native_median_us"] for item in sample
        )
        candidate = sum(
            item["calls_per_token"] * item["candidate_median_us"] for item in sample
        )
        ratios.append(candidate / native)
    return {
        "method": "family_cluster_bootstrap_with_both_sentinels_and_replicas_retained",
        "seed": seed,
        "replicates": replicates,
        "one_sided_upper_95_ratio": percentile_nearest_rank(ratios, 0.95),
    }


def summarize(root: Path) -> dict[str, Any]:
    cells = canonical_cells()
    records_by_cell: dict[int, list[dict[str, Any]]] = {
        cell["cell_index"]: [] for cell in cells
    }
    position_counts = {
        arm: {str(position): 0 for position in range(1, 5)} for arm in ARMS
    }
    identity_failures = []
    for planned in process_plan():
        path = cell_directory(planned, root=root) / arm_filename(
            planned["arm"], planned["replica"]
        )
        if not path.is_file():
            raise RuntimeError(f"A4a planned evidence missing: {path}")
        record = json.loads(path.read_text(encoding="utf-8"))
        identity = record.get("identity", {})
        observed = {
            "family": identity.get("family"),
            "sentinel": identity.get("sentinel", {}).get("id"),
            "cell_index": identity.get("cell_index"),
            "arm": identity.get("arm"),
            "replica": identity.get("replica"),
            "position": identity.get("counterbalance_position"),
        }
        expected = {
            "family": planned["family"],
            "sentinel": planned["sentinel"],
            "cell_index": planned["cell_index"],
            "arm": planned["arm"],
            "replica": planned["replica"],
            "position": planned["position"],
        }
        if observed != expected or record.get("status") != "classified":
            identity_failures.append(
                {"path": str(path), "observed": observed, "expected": expected}
            )
        records_by_cell[planned["cell_index"]].append(record)
        position_counts[planned["arm"]][str(planned["position"])] += 1
    if identity_failures:
        raise RuntimeError(f"A4a record identity failures: {identity_failures}")
    counterbalance_balanced = all(
        count == 14
        for arm_counts in position_counts.values()
        for count in arm_counts.values()
    )
    if not counterbalance_balanced:
        raise RuntimeError(f"A4a counterbalance position drift: {position_counts}")

    cell_results = [
        summarize_cell(records_by_cell[cell["cell_index"]], cell) for cell in cells
    ]
    family_results = []
    for family, spec in load_a1().FAMILIES.items():
        family_cells = [item for item in cell_results if item["family"] == family]
        native_points = [item["latency"]["native_median"] for item in family_cells]
        candidate_points = [
            item["latency"]["candidate_median"] for item in family_cells
        ]
        native_median = statistics.median(native_points)
        candidate_median = statistics.median(candidate_points)
        family_results.append(
            {
                "family": family,
                "calls_per_token": spec["calls"],
                "native_sentinel_us": native_points,
                "candidate_sentinel_us": candidate_points,
                "native_median_us": native_median,
                "candidate_median_us": candidate_median,
                "candidate_native_ratio": candidate_median / native_median,
                "native_min_us": min(native_points),
                "native_max_us": max(native_points),
                "candidate_min_us": min(candidate_points),
                "candidate_max_us": max(candidate_points),
            }
        )
    multiplicity_sum = sum(item["calls_per_token"] for item in family_results)
    native_central = sum(
        item["calls_per_token"] * item["native_median_us"] for item in family_results
    )
    candidate_central = sum(
        item["calls_per_token"] * item["candidate_median_us"] for item in family_results
    )
    sensitivity = {
        "native_min_us": sum(
            item["calls_per_token"] * item["native_min_us"] for item in family_results
        ),
        "native_max_us": sum(
            item["calls_per_token"] * item["native_max_us"] for item in family_results
        ),
        "candidate_min_us": sum(
            item["calls_per_token"] * item["candidate_min_us"]
            for item in family_results
        ),
        "candidate_max_us": sum(
            item["calls_per_token"] * item["candidate_max_us"]
            for item in family_results
        ),
    }
    half_ratios = {}
    for parity, name in ((0, "ABBA_even_cells"), (1, "BAAB_odd_cells")):
        selected = [item for item in cell_results if item["cell_index"] % 2 == parity]
        native = sum(
            item["calls_per_token"] * item["latency"]["native_median"]
            for item in selected
        )
        candidate = sum(
            item["calls_per_token"] * item["latency"]["candidate_median"]
            for item in selected
        )
        half_ratios[name] = candidate / native
    bootstrap = family_cluster_bootstrap(family_results)
    hot_point_failures = [
        {
            "cell_index": item["cell_index"],
            "family": item["family"],
            "sentinel": item["sentinel"],
            "ratio": item["latency"]["candidate_native_ratio"],
        }
        for item in cell_results
        if item["calls_per_token"] >= HOT_FAMILY_CALL_THRESHOLD
        and item["latency"]["candidate_native_ratio"] > HOT_FAMILY_POINT_RATIO_MAX
    ]
    central_ratio = candidate_central / native_central
    exactness_failures = [
        {
            "cell_index": item["cell_index"],
            "family": item["family"],
            "sentinel": item["sentinel"],
        }
        for item in cell_results
        if not item["exactness_pass"]
    ]
    cost_gate = {
        "central_ratio": central_ratio,
        "central_ratio_max": CENTRAL_RATIO_MAX,
        "central_pass": central_ratio <= CENTRAL_RATIO_MAX,
        "family_cluster_bootstrap": bootstrap,
        "bootstrap_upper_95_max": BOOTSTRAP_UPPER_95_MAX,
        "bootstrap_pass": bootstrap["one_sided_upper_95_ratio"]
        <= BOOTSTRAP_UPPER_95_MAX,
        "counterbalance_half_ratios": half_ratios,
        "counterbalance_half_ratio_max": COUNTERBALANCE_HALF_RATIO_MAX,
        "counterbalance_halves_pass": all(
            ratio <= COUNTERBALANCE_HALF_RATIO_MAX for ratio in half_ratios.values()
        ),
        "hot_family_call_threshold": HOT_FAMILY_CALL_THRESHOLD,
        "hot_family_point_ratio_max": HOT_FAMILY_POINT_RATIO_MAX,
        "hot_family_point_failures": hot_point_failures,
        "hot_family_points_pass": not hot_point_failures,
    }
    cost_gate["passed"] = all(
        cost_gate[key]
        for key in (
            "central_pass",
            "bootstrap_pass",
            "counterbalance_halves_pass",
            "hot_family_points_pass",
        )
    )
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-deterministic-a4a-summary.v1",
        "status": "complete",
        "classification": "component_only_14_family_m1_deterministic_census",
        "processes": {"planned": 112, "completed": 112},
        "counterbalance_position_counts": position_counts,
        "counterbalance_balanced": counterbalance_balanced,
        "multiplicity_sum": multiplicity_sum,
        "cell_results": cell_results,
        "family_results": family_results,
        "weighted_cost_us_per_target_token": {
            "native_central": native_central,
            "candidate_central": candidate_central,
            "candidate_native_ratio": central_ratio,
            "sentinel_min_max_sensitivity": sensitivity,
        },
        "exactness": {
            "all_cells_pass": not exactness_failures,
            "failures": exactness_failures,
        },
        "cost_gate": cost_gate,
        "component_candidate_advances": not exactness_failures and cost_gate["passed"],
        "endpoint_change_authorized": False,
        "speed_or_quality_credit": False,
    }


def run_plan() -> Path:
    if os.environ.get(AUTHORITY_ENV) != "YES":
        raise RuntimeError(f"set {AUTHORITY_ENV}=YES")
    validate_catalog()
    a1 = load_a1()
    initial = a1.validate_admission()
    a1.verify_static_identity()
    a1.refuse_active_accelerator_owner()
    if sha256(A3_RESULT) != A3_RESULT_SHA256:
        raise RuntimeError("A4a prerequisite A3 result drift")
    if A4A_ROOT.exists():
        raise FileExistsError(f"refusing existing A4a root: {A4A_ROOT}")
    A4A_ROOT.mkdir()
    stage = "create_cells_directory"
    current_process: dict[str, Any] | None = None
    completed_processes: list[dict[str, Any]] = []
    failure_details: list[dict[str, Any]] = []
    try:
        (A4A_ROOT / "cells").mkdir()
        stage = "build_process_plan"
        planned_processes = process_plan()
        deadline = time.monotonic() + PLAN_TIMEOUT_SECONDS
        for planned in planned_processes:
            current_process = planned
            stage = "pre_cell_deadline"
            if time.monotonic() >= deadline:
                raise TimeoutError("A4a exceeded its frozen plan timeout")
            stage = "create_cell_directory"
            directory = cell_directory(planned, root=A4A_ROOT)
            directory.mkdir(parents=True, exist_ok=True)
            output = directory / arm_filename(planned["arm"], planned["replica"])
            stage = "pre_cell_health"
            before = a1.validate_admission()
            if before["aer_event_count"] != initial["aer_event_count"]:
                raise RuntimeError("new AER event before A4a cell")

            stage = "child_execute"
            child_error: BaseException | None = None
            try:
                subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "run-cell",
                        "--cell-index",
                        str(planned["cell_index"]),
                        "--family",
                        planned["family"],
                        "--sentinel",
                        planned["sentinel"],
                        "--arm",
                        planned["arm"],
                        "--replica",
                        str(planned["replica"]),
                        "--position",
                        str(planned["position"]),
                        "--output",
                        str(output),
                    ],
                    check=True,
                    env=dict(A4A_ENVIRONMENT),
                    timeout=min(
                        CELL_TIMEOUT_SECONDS,
                        max(1, int(deadline - time.monotonic())),
                    ),
                )
            except BaseException as error:
                child_error = error
                failure_details.append(
                    {
                        "stage": stage,
                        "planned": planned,
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                )

            stage = "parent_postflight_health"
            postflight_error: BaseException | None = None
            try:
                after = a1.validate_admission()
                if after["aer_event_count"] != before["aer_event_count"]:
                    raise RuntimeError("new AER event during A4a cell")
                parent_postflight = {"status": "pass", "receipt": after}
            except BaseException as error:
                postflight_error = error
                parent_postflight = {
                    "status": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                }
                failure_details.append(
                    {
                        "stage": stage,
                        "planned": planned,
                        "type": type(error).__name__,
                        "message": str(error),
                    }
                )
            stage = "parent_postflight_write"
            atomic_write(
                directory
                / f"parent-postflight-{planned['position']}-{planned['arm']}-replica{planned['replica']}.json",
                parent_postflight,
            )
            if child_error is not None and not output.exists():
                stage = "missing_child_envelope_write"
                atomic_write(
                    output,
                    {
                        "schema": "neural.download.qwen38-flash-next.bf16-deterministic-a4a-cell.v1",
                        "status": "diagnostic_error",
                        "classification": "parent_preserved_missing_child_envelope",
                        "identity": planned,
                        "error": {
                            "type": type(child_error).__name__,
                            "message": str(child_error),
                        },
                        "parent_postflight": parent_postflight,
                    },
                )
            if child_error is not None or postflight_error is not None:
                stage = "cell_failure_classification"
                raise RuntimeError("A4a child or postflight failed")
            completed_processes.append(planned)

        current_process = None
        stage = "final_health"
        final_health = {"status": "pass", "receipt": a1.validate_admission()}
        stage = "summarize"
        result = summarize(A4A_ROOT)
        result["initial_health"] = initial
        result["final_health"] = final_health
        summary_path = A4A_ROOT / "summary.json"
        stage = "summary_write"
        atomic_write(summary_path, result)
        return summary_path
    except BaseException as error:
        primary_error = {
            "stage": stage,
            "type": type(error).__name__,
            "message": str(error),
        }
        try:
            final_health = {"status": "pass", "receipt": a1.validate_admission()}
        except BaseException as health_error:
            final_health = {
                "status": "error",
                "error": {
                    "type": type(health_error).__name__,
                    "message": str(health_error),
                },
            }
        atomic_write(
            A4A_ROOT / "plan-status.json",
            {
                "schema": "neural.download.qwen38-flash-next.bf16-deterministic-a4a-plan.v1",
                "status": "diagnostic_error",
                "failure_location": {
                    "stage": stage,
                    "current_process": current_process,
                },
                "primary_error": primary_error,
                "failure_details": failure_details,
                "completed_process_count": len(completed_processes),
                "completed_processes": completed_processes,
                "initial_health": initial,
                "final_health": final_health,
            },
        )
        raise RuntimeError(
            "A4a failed after preserving plan status and final health"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("plan")
    sub.add_parser("run-plan")
    cell = sub.add_parser("run-cell")
    cell.add_argument("--cell-index", type=int, choices=range(28), required=True)
    cell.add_argument("--family", choices=tuple(load_a1().FAMILIES), required=True)
    cell.add_argument("--sentinel", required=True)
    cell.add_argument("--arm", choices=ARMS, required=True)
    cell.add_argument("--replica", type=int, choices=REPLICAS, required=True)
    cell.add_argument("--position", type=int, choices=range(1, 5), required=True)
    cell.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command in (None, "plan"):
        print(
            json.dumps(
                {
                    "schema": "neural.download.qwen38-flash-next.bf16-deterministic-a4a-plan.v1",
                    "families": len(load_a1().FAMILIES),
                    "cells": canonical_cells(),
                    "processes": process_plan(),
                    "process_count": 112,
                    "calls_per_target_token": 532,
                    "device_execution": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    if args.command == "run-plan":
        print(run_plan())
        return
    run_cell_enveloped(args)


if __name__ == "__main__":
    main()
