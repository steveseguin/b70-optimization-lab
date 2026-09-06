#!/usr/bin/env python3
"""A5 grouped-W16A16 reliability gate for the four K=10240 down cells.

Stage 1 runs only two fresh grouped-GEMM processes per cell and compares every
M=1 output row with the immutable native support recorded by A4a.  Stage 2 is
described, but deliberately not executed here: its N/G/G/N timing bracket is
eligible only after the stage-1 summary passes.
"""

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
import signal
import statistics
import subprocess
import sys
import time
from typing import Any


HERE = Path(__file__).resolve().parent
A1_TOOL = HERE / "census-q38-bf16-dense-invariance.py"
A1_TOOL_SHA256 = "e4700fc44a65d71c7b0a7df5ff34924d808ba685c4157b0e2c12fd4b9d4bdf22"
A4A_TOOL = HERE / "census-q38-bf16-deterministic-a4a.py"
A4A_TOOL_SHA256 = "c2caf7427a229f2d0a3158aa41aefacfddf0d3ccb368946feb01bc8bb5147184"
EVIDENCE_BASE = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
A4A_ROOT = EVIDENCE_BASE / "bf16-deterministic-census-20260902-a4a"
A4A_SUMMARY = A4A_ROOT / "summary.json"
A4A_SUMMARY_SHA256 = "a98b7c7f34df9795027e1e7b956fde8daef485986f9de31d96813b4c98c6d6d2"
A5_ROOT = EVIDENCE_BASE / "bf16-grouped-down-20260902-a5"
A5_TIMING_ROOT = EVIDENCE_BASE / "bf16-grouped-down-timing-20260902-a5b"
RUNTIME_STAGE = Path(
    "/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels"
)
RUNTIME_MANIFEST_SHA256 = (
    "71e263f19ccc1313bbdc21604b4de5171891454fb7e8e35877af083505522951"
)
LOADER_SUFFIX = (
    "/home/steve/.venvs/vllm-xpu/lib",
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib",
    "/opt/intel/oneapi/compiler/2025.3/lib",
    "/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib",
)
ROWS = 256
SWEEPS = 100
WARMUP_SWEEPS = 4
INPUT_SEED = 2026090201
REPLICAS = (1, 2)
AUTHORITY_ENV = "Q38_BF16_GROUPED_A5_EXECUTE"
CELL_TIMEOUT_SECONDS = 1200
PLAN_TIMEOUT_SECONDS = 4 * 60 * 60

TARGET_CELLS: tuple[dict[str, Any], ...] = (
    {
        "cell_index": 0,
        "a4a_cell_index": 0,
        "family": "hc_down_inject",
        "sentinel": "layer00-attn-r0",
        "k": 10240,
        "logical_n": 336,
        "active_n": 324,
        "grouped_n": 352,
        "calls_per_token": 96,
        "native_sha256": (
            "113f350d4b7d93e7a0d716b30be940b3865a535a09f7eb3d72b883736a8ce1eb",
            "beeeb78c8e5b44c5a0a48d7be65588c8e38f242b68dbc283e89e8c3d74875f69",
        ),
    },
    {
        "cell_index": 1,
        "a4a_cell_index": 1,
        "family": "hc_down_inject",
        "sentinel": "layer47-mlp-r3",
        "k": 10240,
        "logical_n": 336,
        "active_n": 324,
        "grouped_n": 352,
        "calls_per_token": 96,
        "native_sha256": (
            "28edb85f5191d469c3e9bddabbe36b734f668b8385ea765b636c890cc51ab28f",
            "f16bc104ab580a222773f3e04213c4ed2651aee20da698929d583a5820561996",
        ),
    },
    {
        "cell_index": 2,
        "a4a_cell_index": 2,
        "family": "final_hc_down",
        "sentinel": "final-r0",
        "k": 10240,
        "logical_n": 320,
        "active_n": 320,
        "grouped_n": 320,
        "calls_per_token": 1,
        "native_sha256": (
            "76d4b7baddeb0b7492e7529628c65b18c4a37c04d806d07d3dbdb2ea0ade9549",
            "f3fc788099e871b1c6bcf47f31fa2b13a482c99baeb5934724cb0c4b63592138",
        ),
    },
    {
        "cell_index": 3,
        "a4a_cell_index": 3,
        "family": "final_hc_down",
        "sentinel": "final-r3",
        "k": 10240,
        "logical_n": 320,
        "active_n": 320,
        "grouped_n": 320,
        "calls_per_token": 1,
        "native_sha256": (
            "b52ce1a8766ec331e01f41f5ba1a8ba731d05483efb85a3a2afda85a5571916a",
            "43b4ccfe76cd70bf15023a3cf9c4eea2fdbfde27696ee6ef7b2dcea8b8ad5c62",
        ),
    },
)

A5_ENVIRONMENT = {
    "HOME": "/home/steve",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "LD_LIBRARY_PATH": ":".join((str(RUNTIME_STAGE), *LOADER_SUFFIX)),
    "ONEAPI_DEVICE_SELECTOR": "level_zero:0",
    "PATH": (
        "/home/steve/.venvs/vllm-xpu/bin:/usr/local/sbin:/usr/local/bin:"
        "/usr/sbin:/usr/bin:/sbin:/bin"
    ),
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTHONSAFEPATH": "1",
    "Q38_BF16_DENSE_CENSUS_EXECUTE": "YES",
    AUTHORITY_ENV: "YES",
}

A5_CELL_SCHEMA = "neural.download.qwen38-flash-next.bf16-grouped-a5-cell.v1"
A5_CELL_CLASSIFICATION = "component_only_grouped_w16a16_m1_candidate"
A5_PROTOCOL = {
    "warmup_sweeps": WARMUP_SWEEPS,
    "measured_sweeps": SWEEPS,
    "calls_per_sweep": ROWS,
}
A5_CREDIT = {
    "report_only": True,
    "timing_stage_authorized": False,
    "endpoint_change_authorized": False,
    "speed_or_quality_credit": False,
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
    return _load_tool(A1_TOOL, A1_TOOL_SHA256, "q38_bf16_a1_for_a5")


@cache
def load_a4a():
    return _load_tool(A4A_TOOL, A4A_TOOL_SHA256, "q38_bf16_a4a_for_a5")


def canonical_cells() -> list[dict[str, Any]]:
    cells = [dict(cell) for cell in TARGET_CELLS]
    if [cell["cell_index"] for cell in cells] != list(range(4)):
        raise RuntimeError("A5 cell indices are not canonical")
    family_multiplicity = {
        family: {cell["calls_per_token"] for cell in cells if cell["family"] == family}
        for family in {cell["family"] for cell in cells}
    }
    if family_multiplicity != {
        "hc_down_inject": {96},
        "final_hc_down": {1},
    }:
        raise RuntimeError("A5 family multiplicity contract drift")
    return cells


def reliability_plan() -> list[dict[str, Any]]:
    return [
        {**cell, "provider": "grouped", "replica": replica}
        for cell in canonical_cells()
        for replica in REPLICAS
    ]


def stage2_timing_plan() -> list[dict[str, Any]]:
    schedule = (
        ("native", 1, 1),
        ("grouped", 1, 2),
        ("grouped", 2, 3),
        ("native", 2, 4),
    )
    return [
        {**cell, "provider": provider, "replica": replica, "position": position}
        for cell in canonical_cells()
        for provider, replica, position in schedule
    ]


def cell_directory(cell: dict[str, Any], *, root: Path = A5_ROOT) -> Path:
    return (
        root
        / "cells"
        / (f"{cell['cell_index']:02d}-{cell['family']}--{cell['sentinel']}")
    )


def candidate_path(cell: dict[str, Any], replica: int, *, root: Path = A5_ROOT):
    if replica not in REPLICAS:
        raise ValueError("A5 replica outside plan")
    return cell_directory(cell, root=root) / f"grouped-replica{replica}.json"


def native_a4a_path(cell: dict[str, Any], replica: int) -> Path:
    a4a_cell = load_a4a().canonical_cells()[cell["a4a_cell_index"]]
    if a4a_cell["family"] != cell["family"] or a4a_cell["sentinel"] != cell["sentinel"]:
        raise RuntimeError("A5-to-A4a cell mapping drift")
    return load_a4a().cell_directory(a4a_cell) / f"native-replica{replica}.json"


def verify_a4a_source() -> dict[int, list[dict[str, Any]]]:
    if sha256(A4A_SUMMARY) != A4A_SUMMARY_SHA256:
        raise RuntimeError("A4a summary identity drift")
    summary = json.loads(A4A_SUMMARY.read_text(encoding="utf-8"))
    if summary.get("status") != "complete" or summary.get("processes") != {
        "planned": 112,
        "completed": 112,
    }:
        raise RuntimeError("A4a summary is not the complete frozen census")
    records: dict[int, list[dict[str, Any]]] = {}
    for cell in canonical_cells():
        cell_records = []
        for replica in REPLICAS:
            path = native_a4a_path(cell, replica)
            expected = cell["native_sha256"][replica - 1]
            if path.is_symlink() or sha256(path) != expected:
                raise RuntimeError(f"A4a native evidence identity drift: {path}")
            record = json.loads(path.read_text(encoding="utf-8"))
            identity = record.get("identity", {})
            if (
                record.get("status") != "classified"
                or identity.get("family") != cell["family"]
                or identity.get("sentinel", {}).get("id") != cell["sentinel"]
                or identity.get("arm") != "native"
                or identity.get("replica") != replica
            ):
                raise RuntimeError("A4a native evidence semantic identity drift")
            cell_records.append(record)
        records[cell["cell_index"]] = cell_records
    return records


def native_support(records: list[dict[str, Any]]) -> list[set[str]]:
    if len(records) != 2:
        raise ValueError("A5 native support requires two A4a records")
    support = [set() for _ in range(ROWS)]
    for record in records:
        snapshots = record.get("arm_report", {}).get("snapshots", [])
        if len(snapshots) != SWEEPS:
            raise RuntimeError("A4a native sweep count drift")
        for snapshot in snapshots:
            row_hashes = snapshot.get("row_active_sha256", [])
            if len(row_hashes) != ROWS:
                raise RuntimeError("A4a native row count drift")
            for row, value in enumerate(row_hashes):
                support[row].add(value)
    if any(not values for values in support):
        raise RuntimeError("A4a native support contains an empty row")
    return support


def a4a_cell_authority(
    cell: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(records) != 2:
        raise ValueError("A5 A4a authority requires exactly two native records")
    records = sorted(records, key=lambda item: item["identity"]["replica"])
    if [item["identity"]["replica"] for item in records] != [1, 2]:
        raise RuntimeError("A5 A4a authority replica set drift")
    fields = (
        "model",
        "model_revision",
        "input_sha256",
        "input_row_sha256",
        "weight_sha256",
        "sentinel",
        "source_tensors",
        "checkpoint_shards",
    )
    authority = {field: records[0]["identity"][field] for field in fields}
    for record in records:
        identity = record["identity"]
        if (
            record.get("schema")
            != "neural.download.qwen38-flash-next.bf16-deterministic-a4a-cell.v1"
            or record.get("status") != "classified"
            or record.get("classification")
            != "component_only_real_weight_m1_deterministic_census"
            or identity.get("cell_index") != cell["a4a_cell_index"]
            or identity.get("family") != cell["family"]
            or identity.get("sentinel", {}).get("id") != cell["sentinel"]
            or identity.get("arm") != "native"
            or any(identity.get(field) != authority[field] for field in fields)
        ):
            raise RuntimeError("A5 A4a authority semantic identity drift")
    if len(authority["input_row_sha256"]) != ROWS:
        raise RuntimeError("A5 A4a input-row authority count drift")
    return authority


def verify_runtime_stage() -> dict[str, str]:
    manifest = RUNTIME_STAGE / "SHA256SUMS"
    if manifest.is_symlink() or sha256(manifest) != RUNTIME_MANIFEST_SHA256:
        raise RuntimeError("A5 grouped runtime manifest identity drift")
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        name = name.removeprefix("*")
        path = RUNTIME_STAGE / name
        if path.is_symlink() or not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"A5 grouped runtime file identity drift: {name}")
        entries[name] = expected
    required = {"_xpu_C.abi3.so", "libgrouped_gemm_xe_2.so"}
    if not required.issubset(entries):
        raise RuntimeError("A5 grouped runtime is incomplete")
    return entries


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
        if key in A5_ENVIRONMENT or key.startswith(prefixes)
    }
    if relevant != A5_ENVIRONMENT:
        raise RuntimeError(f"A5 grouped environment drift: {sorted(relevant)}")
    return relevant


def load_extension() -> None:
    path = RUNTIME_STAGE / "_xpu_C.abi3.so"
    spec = importlib.util.spec_from_file_location("vllm_xpu_kernels._xpu_C", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load A5 grouped runtime extension")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def tensor_bytes(torch, tensor) -> bytes:
    return tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()


def output_snapshot(torch, output, *, active_n: int, grouped_n: int) -> dict[str, Any]:
    if output.dtype != torch.bfloat16 or tuple(output.shape) != (ROWS, grouped_n):
        raise RuntimeError("A5 grouped output shape or dtype drift")
    n = output.shape[1]
    payload = tensor_bytes(torch, output)
    row_width = n * 2
    active_width = active_n * 2
    row_full = []
    row_active = []
    row_tail = []
    tail_zero = True
    active_all = bytearray()
    tail_all = bytearray()
    for row in range(ROWS):
        start = row * row_width
        full = payload[start : start + row_width]
        active = payload[start : start + active_width]
        tail = payload[start + active_width : start + row_width]
        active_all.extend(active)
        tail_all.extend(tail)
        row_full.append(digest_bytes(full))
        row_active.append(digest_bytes(active))
        row_tail.append(digest_bytes(tail))
        values = array("H")
        values.frombytes(tail)
        tail_zero = tail_zero and all(bits & 0x7FFF == 0 for bits in values)
    return {
        "full_sha256": digest_bytes(payload),
        "active_sha256": digest_bytes(bytes(active_all)),
        "tail_sha256": digest_bytes(bytes(tail_all)),
        "row_full_sha256": row_full,
        "row_active_sha256": row_active,
        "row_tail_sha256": row_tail,
        "tail_all_numeric_zero": tail_zero,
    }


def compress_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if len(snapshots) != SWEEPS:
        raise ValueError("A5 candidate sweep count drift")
    return {
        "sweep_full_sha256": [item["full_sha256"] for item in snapshots],
        "sweep_active_sha256": [item["active_sha256"] for item in snapshots],
        "sweep_tail_sha256": [item["tail_sha256"] for item in snapshots],
        "unique_full_sha256": sorted({item["full_sha256"] for item in snapshots}),
        "unique_active_sha256": sorted({item["active_sha256"] for item in snapshots}),
        "unique_tail_sha256": sorted({item["tail_sha256"] for item in snapshots}),
        "row_full_sha256_values": [
            sorted({item["row_full_sha256"][row] for item in snapshots})
            for row in range(ROWS)
        ],
        "row_active_sha256_values": [
            sorted({item["row_active_sha256"][row] for item in snapshots})
            for row in range(ROWS)
        ],
        "row_tail_sha256_values": [
            sorted({item["row_tail_sha256"][row] for item in snapshots})
            for row in range(ROWS)
        ],
        "all_tail_numeric_zero": all(
            item["tail_all_numeric_zero"] for item in snapshots
        ),
    }


def _latency_report(values: list[float]) -> dict[str, Any]:
    if len(values) != SWEEPS or any(
        not math.isfinite(value) or value <= 0 for value in values
    ):
        raise RuntimeError("A5 grouped latency sample drift")
    return {
        "unit": "microseconds_per_256_row_ordinal_sweep",
        "count": len(values),
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "samples": values,
        "screening_only": True,
    }


def expected_shape(cell: dict[str, Any]) -> dict[str, Any]:
    return {
        "m": 1,
        "k": cell["k"],
        "logical_n": cell["logical_n"],
        "active_n": cell["active_n"],
        "grouped_n": cell["grouped_n"],
        "synthetic_tail": [cell["active_n"], cell["grouped_n"]],
        "rows": ROWS,
        "calls_per_target_token": cell["calls_per_token"],
    }


def run_cell(args: argparse.Namespace) -> dict[str, Any]:
    if args.replica not in REPLICAS:
        raise ValueError("A5 replica outside plan")
    signal.alarm(CELL_TIMEOUT_SECONDS)
    verify_environment()
    runtime_manifest = verify_runtime_stage()
    a1 = load_a1()
    a1.validate_catalog()
    cell = canonical_cells()[args.cell_index]
    if cell["family"] != args.family or cell["sentinel"] != args.sentinel:
        raise RuntimeError("A5 CLI cell identity drift")
    admission = a1.validate_admission()
    static_identity = a1.verify_static_identity()
    a1.refuse_active_accelerator_owner()
    lock = a1.acquire_component_lock()

    import safetensors
    import torch

    if torch.__version__ != a1.TORCH_VERSION:
        raise RuntimeError("A5 Torch version drift")
    if safetensors.__version__ != a1.SAFETENSORS_VERSION:
        raise RuntimeError("A5 safetensors version drift")
    load_extension()
    if not hasattr(torch.ops._xpu_C, "cutlass_grouped_gemm_interface"):
        raise RuntimeError("A5 runtime lacks grouped-GEMM interface")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("A5 requires exactly one selected XPU")

    sentinel = a1.resolve_sentinel(cell["family"], cell["sentinel"])
    logical_weight_cpu, shards, source_tensors = a1.load_weight(
        cell["family"], sentinel
    )
    if tuple(logical_weight_cpu.shape) != (cell["logical_n"], cell["k"]):
        raise RuntimeError("A5 logical checkpoint weight shape drift")
    if cell["family"] == "hc_down_inject":
        if bool(torch.count_nonzero(logical_weight_cpu[324:]).item()):
            raise RuntimeError("A5 inherited HC padding is nonzero")
        grouped_weight_cpu = torch.cat(
            (
                logical_weight_cpu[:324],
                torch.zeros((28, cell["k"]), dtype=torch.bfloat16),
            ),
            dim=0,
        ).contiguous()
    else:
        grouped_weight_cpu = logical_weight_cpu.contiguous()
    if tuple(grouped_weight_cpu.shape) != (cell["grouped_n"], cell["k"]):
        raise RuntimeError("A5 grouped physical weight shape drift")

    generator = torch.Generator(device="cpu").manual_seed(INPUT_SEED)
    input_cpu = (
        torch.randn((ROWS, cell["k"]), generator=generator)
        .mul_(0.01)
        .to(torch.bfloat16)
    )
    input_row_sha = [a1.tensor_sha256(input_cpu[row : row + 1]) for row in range(ROWS)]
    if len(set(input_row_sha)) != ROWS:
        raise RuntimeError("A5 fixed input rows are not all distinct")
    logical_weight_sha = a1.tensor_sha256(logical_weight_cpu)
    grouped_weight_sha = a1.tensor_sha256(grouped_weight_cpu)
    input_sha = a1.tensor_sha256(input_cpu)

    device = torch.device("xpu:0")
    inputs = input_cpu.to(device)
    packed = grouped_weight_cpu.t().contiguous().unsqueeze(0).to(device)
    rows_per_expert = torch.ones((1,), dtype=torch.int32, device=device)
    torch.xpu.synchronize()

    def sweep():
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        outputs = []
        for row in range(ROWS):
            output = torch.empty(
                (1, cell["grouped_n"]), dtype=torch.bfloat16, device=device
            )
            torch.ops._xpu_C.cutlass_grouped_gemm_interface(
                inputs[row : row + 1],
                packed,
                None,
                None,
                output,
                rows_per_expert,
                cell["grouped_n"],
                cell["k"],
                1,
                False,
                False,
            )
            outputs.append(output)
        joined = torch.cat(outputs, dim=0)
        end.record()
        end.synchronize()
        return joined, float(start.elapsed_time(end)) * 1000.0

    for _ in range(WARMUP_SWEEPS):
        output, _ = sweep()
        if tuple(output.shape) != (ROWS, cell["grouped_n"]):
            raise RuntimeError("A5 warmup output shape drift")
    snapshots = []
    latency = []
    for _ in range(SWEEPS):
        output, elapsed = sweep()
        if not bool(torch.isfinite(output).all().item()):
            raise RuntimeError("A5 grouped output contains non-finite values")
        snapshots.append(
            output_snapshot(
                torch,
                output,
                active_n=cell["active_n"],
                grouped_n=cell["grouped_n"],
            )
        )
        latency.append(elapsed)
    compressed = compress_snapshots(snapshots)
    input_after = a1.tensor_sha256(inputs)
    packed_after = a1.tensor_sha256(packed)
    expected_packed = a1.tensor_sha256(grouped_weight_cpu.t().contiguous().unsqueeze(0))
    errors = []
    if input_after != input_sha or packed_after != expected_packed:
        errors.append({"type": "MutationError", "message": "input/weight mutated"})
    del lock
    return {
        "schema": A5_CELL_SCHEMA,
        "status": "classified" if not errors else "diagnostic_error",
        "classification": A5_CELL_CLASSIFICATION,
        "identity": {
            **static_identity,
            "model": "Qwen/Qwen3.8-Flash-Next-FP8",
            "model_revision": a1.MODEL_REVISION,
            "a1_tool_sha256": A1_TOOL_SHA256,
            "a4a_tool_sha256": A4A_TOOL_SHA256,
            "a4a_summary_sha256": A4A_SUMMARY_SHA256,
            "family": cell["family"],
            "sentinel": sentinel,
            "cell_index": cell["cell_index"],
            "replica": args.replica,
            "provider": "xe2-grouped-w16a16",
            "input_seed": INPUT_SEED,
            "input_sha256": input_sha,
            "input_row_sha256": input_row_sha,
            "logical_weight_sha256": logical_weight_sha,
            "grouped_weight_sha256": grouped_weight_sha,
            "source_tensors": source_tensors,
            "checkpoint_shards": shards,
            "runtime_stage": str(RUNTIME_STAGE),
            "runtime_manifest_sha256": RUNTIME_MANIFEST_SHA256,
            "runtime_manifest": runtime_manifest,
            "environment": verify_environment(),
            "admission": admission,
        },
        "shape": expected_shape(cell),
        "protocol": A5_PROTOCOL,
        "candidate": compressed,
        "latency": _latency_report(latency),
        "diagnostic_errors": errors,
        "credit": A5_CREDIT,
    }


def atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite A5 evidence: {path}")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.link(temporary, path)
    try:
        temporary.unlink()
    except OSError:
        # The immutable destination is already complete. A best-effort cleanup
        # failure must not turn published evidence into an apparent failed write.
        pass


def run_cell_enveloped(args: argparse.Namespace) -> None:
    cell = canonical_cells()[args.cell_index]
    expected = candidate_path(cell, args.replica)
    if args.output.resolve() != expected.resolve():
        raise RuntimeError("A5 child output escaped canonical path")
    started = time.time_ns()
    failure: BaseException | None = None
    try:
        payload = run_cell(args)
        if payload["status"] != "classified":
            failure = RuntimeError("A5 candidate recorded a diagnostic error")
    except BaseException as error:
        failure = error
        payload = {
            "schema": "neural.download.qwen38-flash-next.bf16-grouped-a5-cell.v1",
            "status": "diagnostic_error",
            "classification": "report_only_failure_envelope",
            "identity": {
                "cell_index": cell["cell_index"],
                "family": cell["family"],
                "sentinel": {"id": cell["sentinel"]},
                "replica": args.replica,
                "provider": "xe2-grouped-w16a16",
            },
            "error": {"type": type(error).__name__, "message": str(error)},
        }
    payload["started_time_ns"] = started
    payload["completed_time_ns"] = time.time_ns()
    atomic_write(expected, payload)
    if failure is not None:
        raise RuntimeError("A5 cell failed after preserving its envelope") from failure


def candidate_contract(
    cell: dict[str, Any],
    record: dict[str, Any],
    *,
    replica: int,
    authority: dict[str, Any],
    runtime_manifest: dict[str, str],
) -> dict[str, bool]:
    identity = record.get("identity", {})
    candidate = record.get("candidate", {})
    expected_identity = {
        "model": authority["model"],
        "model_revision": authority["model_revision"],
        "a1_tool_sha256": A1_TOOL_SHA256,
        "a4a_tool_sha256": A4A_TOOL_SHA256,
        "a4a_summary_sha256": A4A_SUMMARY_SHA256,
        "family": cell["family"],
        "sentinel": authority["sentinel"],
        "cell_index": cell["cell_index"],
        "replica": replica,
        "provider": "xe2-grouped-w16a16",
        "input_seed": INPUT_SEED,
        "input_sha256": authority["input_sha256"],
        "input_row_sha256": authority["input_row_sha256"],
        "logical_weight_sha256": authority["weight_sha256"],
        "source_tensors": authority["source_tensors"],
        "checkpoint_shards": authority["checkpoint_shards"],
        "runtime_stage": str(RUNTIME_STAGE),
        "runtime_manifest_sha256": RUNTIME_MANIFEST_SHA256,
        "runtime_manifest": runtime_manifest,
        "environment": A5_ENVIRONMENT,
    }
    return {
        "schema": record.get("schema") == A5_CELL_SCHEMA,
        "status": record.get("status") == "classified",
        "classification": record.get("classification") == A5_CELL_CLASSIFICATION,
        "identity": all(
            identity.get(key) == value for key, value in expected_identity.items()
        ),
        "shape": record.get("shape") == expected_shape(cell),
        "protocol": record.get("protocol") == A5_PROTOCOL,
        "credit": record.get("credit") == A5_CREDIT,
        "diagnostic_errors": record.get("diagnostic_errors") == [],
        "candidate_structure": (
            len(candidate.get("sweep_full_sha256", [])) == SWEEPS
            and len(candidate.get("sweep_active_sha256", [])) == SWEEPS
            and len(candidate.get("sweep_tail_sha256", [])) == SWEEPS
            and len(candidate.get("row_full_sha256_values", [])) == ROWS
            and len(candidate.get("row_active_sha256_values", [])) == ROWS
            and len(candidate.get("row_tail_sha256_values", [])) == ROWS
        ),
        "candidate_digest_sets_self_consistent": (
            sorted(set(candidate.get("sweep_full_sha256", [])))
            == candidate.get("unique_full_sha256")
            and sorted(set(candidate.get("sweep_active_sha256", [])))
            == candidate.get("unique_active_sha256")
            and sorted(set(candidate.get("sweep_tail_sha256", [])))
            == candidate.get("unique_tail_sha256")
        ),
    }


def classify_cell(
    cell: dict[str, Any],
    candidates: list[dict[str, Any]],
    support: list[set[str]],
    authority: dict[str, Any],
    runtime_manifest: dict[str, str],
) -> dict[str, Any]:
    if len(candidates) != 2 or len(support) != ROWS:
        raise ValueError("A5 cell classification input count drift")
    replicas = [item.get("identity", {}).get("replica") for item in candidates]
    replica_set_exact = all(replica in REPLICAS for replica in replicas) and sorted(
        replicas
    ) == [1, 2]
    candidates = sorted(
        candidates,
        key=lambda item: (
            item.get("identity", {}).get("replica")
            if item.get("identity", {}).get("replica") in REPLICAS
            else -1
        ),
    )
    contracts = [
        candidate_contract(
            cell,
            item,
            replica=replica,
            authority=authority,
            runtime_manifest=runtime_manifest,
        )
        for item, replica in zip(candidates, REPLICAS)
    ]
    contracts_pass = replica_set_exact and all(
        all(contract.values()) for contract in contracts
    )
    grouped_weight_exact = len(
        {item.get("identity", {}).get("grouped_weight_sha256") for item in candidates}
    ) == 1 and all(
        isinstance(item.get("identity", {}).get("grouped_weight_sha256"), str)
        and len(item["identity"]["grouped_weight_sha256"]) == 64
        for item in candidates
    )
    contracts_pass = contracts_pass and grouped_weight_exact
    if not contracts_pass:
        return {
            "cell_index": cell["cell_index"],
            "family": cell["family"],
            "sentinel": cell["sentinel"],
            "shape": expected_shape(cell),
            "replica_set_exact": replica_set_exact,
            "candidate_contracts": contracts,
            "grouped_weight_exact_across_processes": grouped_weight_exact,
            "candidate_contracts_pass": False,
            "parity_pass": False,
        }
    within = []
    row_values = []
    for row in range(ROWS):
        values = {
            value
            for item in candidates
            for value in item["candidate"]["row_active_sha256_values"][row]
        }
        row_values.append(values)
    for item in candidates:
        candidate = item["candidate"]
        within.append(
            len(candidate["unique_full_sha256"]) == 1
            and len(candidate["unique_active_sha256"]) == 1
            and len(candidate["unique_tail_sha256"]) == 1
            and candidate["all_tail_numeric_zero"]
            and all(
                len(candidate["row_full_sha256_values"][row]) == 1
                for row in range(ROWS)
            )
            and all(
                len(candidate["row_active_sha256_values"][row]) == 1
                for row in range(ROWS)
            )
        )
    missing = [
        row for row, values in enumerate(row_values) if not values <= support[row]
    ]
    cross_process = all(len(values) == 1 for values in row_values)
    physical_d_cross_process = (
        candidates[0]["candidate"]["unique_full_sha256"]
        == candidates[1]["candidate"]["unique_full_sha256"]
    )
    tail_exact = all(item["candidate"]["all_tail_numeric_zero"] for item in candidates)
    exact = (
        contracts_pass
        and all(within)
        and cross_process
        and physical_d_cross_process
        and not missing
        and tail_exact
        and all(item.get("status") == "classified" for item in candidates)
    )
    return {
        "cell_index": cell["cell_index"],
        "family": cell["family"],
        "sentinel": cell["sentinel"],
        "shape": expected_shape(cell),
        "replica_set_exact": replica_set_exact,
        "candidate_contracts": contracts,
        "candidate_contracts_pass": contracts_pass,
        "grouped_weight_exact_across_processes": grouped_weight_exact,
        "candidate_exact_within_processes": within,
        "candidate_physical_d_exact_across_processes": physical_d_cross_process,
        "candidate_active_rows_exact_across_processes": cross_process,
        "candidate_same_row_hashes_in_a4a_native_support": not missing,
        "missing_native_support_rows": missing,
        "tails_exact_numeric_zero": tail_exact,
        "latency_screening_us_per_call": [
            item["latency"]["median"] / ROWS for item in candidates
        ],
        "parity_pass": exact,
    }


def summarize(root: Path = A5_ROOT) -> dict[str, Any]:
    a4a_records = verify_a4a_source()
    runtime_manifest = verify_runtime_stage()
    cell_results = []
    for cell in canonical_cells():
        candidates = []
        for replica in REPLICAS:
            path = candidate_path(cell, replica, root=root)
            if not path.is_file() or path.is_symlink():
                raise RuntimeError(f"A5 candidate evidence missing: {path}")
            candidates.append(json.loads(path.read_text(encoding="utf-8")))
        cell_results.append(
            classify_cell(
                cell,
                candidates,
                native_support(a4a_records[cell["cell_index"]]),
                a4a_cell_authority(cell, a4a_records[cell["cell_index"]]),
                runtime_manifest,
            )
        )
    parity = all(item["parity_pass"] for item in cell_results)
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-grouped-a5-summary.v1",
        "status": "parity_passed" if parity else "bounded_negative",
        "classification": "four_k10240_down_cell_grouped_w16a16_reliability",
        "processes": {"planned": 8, "completed": 8},
        "a4a_summary_sha256": A4A_SUMMARY_SHA256,
        "runtime_manifest_sha256": RUNTIME_MANIFEST_SHA256,
        "cell_results": cell_results,
        "all_four_cells_pass": parity,
        "stage2_timing_eligible": parity,
        "stage2_timing_root": str(A5_TIMING_ROOT),
        "stage2_timing_schedule": stage2_timing_plan() if parity else [],
        "endpoint_change_authorized": False,
        "speed_or_quality_credit": False,
    }


def validate_stage2_prerequisite(summary: dict[str, Any]) -> None:
    if (
        summary.get("schema")
        != "neural.download.qwen38-flash-next.bf16-grouped-a5-summary.v1"
        or summary.get("status") != "parity_passed"
        or summary.get("all_four_cells_pass") is not True
        or summary.get("stage2_timing_eligible") is not True
        or summary.get("processes") != {"planned": 8, "completed": 8}
    ):
        raise RuntimeError("A5 stage-1 parity does not authorize timing")
    if A5_TIMING_ROOT.exists():
        raise FileExistsError("refusing existing A5 stage-2 timing root")


def validate_final_health(a1, initial: dict[str, Any]) -> dict[str, Any]:
    receipt = a1.validate_admission()
    if receipt["aer_event_count"] != initial["aer_event_count"]:
        raise RuntimeError("new AER event across A5 plan")
    return {"status": "pass", "receipt": receipt}


def run_plan() -> Path:
    if os.environ.get(AUTHORITY_ENV) != "YES":
        raise RuntimeError(f"set {AUTHORITY_ENV}=YES")
    a1 = load_a1()
    initial = a1.validate_admission()
    a1.verify_static_identity()
    a1.refuse_active_accelerator_owner()
    verify_a4a_source()
    verify_runtime_stage()
    if A5_ROOT.exists():
        raise FileExistsError(f"refusing existing A5 root: {A5_ROOT}")
    A5_ROOT.mkdir()
    started = time.time_ns()
    deadline = time.monotonic() + PLAN_TIMEOUT_SECONDS
    stage = "create_cells_directory"
    current_process: dict[str, Any] | None = None
    completed_processes: list[dict[str, Any]] = []
    summary_path = A5_ROOT / "summary.json"
    try:
        (A5_ROOT / "cells").mkdir()
        for planned in reliability_plan():
            current_process = planned
            stage = "pre_cell_deadline"
            if time.monotonic() >= deadline:
                raise TimeoutError("A5 exceeded plan timeout")
            stage = "create_cell_directory"
            directory = cell_directory(planned)
            directory.mkdir(parents=True, exist_ok=True)
            output = candidate_path(planned, planned["replica"])
            stage = "pre_cell_health"
            before = a1.validate_admission()
            if before["aer_event_count"] != initial["aer_event_count"]:
                raise RuntimeError("new AER event before A5 candidate cell")
            stage = "child_execute"
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
                    "--replica",
                    str(planned["replica"]),
                    "--output",
                    str(output),
                ],
                check=True,
                env=dict(A5_ENVIRONMENT),
                timeout=min(
                    CELL_TIMEOUT_SECONDS, max(1, int(deadline - time.monotonic()))
                ),
            )
            stage = "parent_postflight_health"
            after = a1.validate_admission()
            if after["aer_event_count"] != before["aer_event_count"]:
                raise RuntimeError("new AER event during A5 candidate cell")
            stage = "parent_postflight_write"
            atomic_write(
                directory
                / f"parent-postflight-grouped-replica{planned['replica']}.json",
                {"status": "pass", "receipt": after},
            )
            completed_processes.append(planned)
        current_process = None
        stage = "final_health"
        final_health = validate_final_health(a1, initial)
        stage = "final_postflight_write"
        atomic_write(A5_ROOT / "final-postflight.json", final_health)
        stage = "summarize"
        result = summarize(A5_ROOT)
        result["initial_health"] = initial
        result["final_health"] = final_health
        stage = "summary_write"
        atomic_write(summary_path, result)
        return summary_path
    except BaseException as error:
        try:
            failure_final_health = validate_final_health(a1, initial)
        except BaseException as health_error:
            failure_final_health = {
                "status": "error",
                "error": {
                    "type": type(health_error).__name__,
                    "message": str(health_error),
                },
            }
        atomic_write(
            A5_ROOT / "failure.json",
            {
                "schema": "neural.download.qwen38-flash-next.bf16-grouped-a5-failure.v1",
                "status": "failed_closed",
                "failure_location": {
                    "stage": stage,
                    "current_process": current_process,
                },
                "primary_error": {
                    "type": type(error).__name__,
                    "message": str(error),
                },
                "completed_process_count": len(completed_processes),
                "completed_processes": completed_processes,
                "initial_health": initial,
                "final_health": failure_final_health,
                "passing_summary_absent": not summary_path.exists(),
                "started_time_ns": started,
                "completed_time_ns": time.time_ns(),
                "endpoint_change_authorized": False,
            },
        )
        raise RuntimeError(
            "A5 failed after preserving failure and final health"
        ) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("describe-plan")
    subparsers.add_parser("run-plan")
    summary_parser = subparsers.add_parser("summarize")
    summary_parser.add_argument("--root", type=Path, default=A5_ROOT)
    cell_parser = subparsers.add_parser("run-cell")
    cell_parser.add_argument("--cell-index", type=int, choices=range(4), required=True)
    cell_parser.add_argument("--family", required=True)
    cell_parser.add_argument("--sentinel", required=True)
    cell_parser.add_argument("--replica", type=int, choices=REPLICAS, required=True)
    cell_parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "describe-plan":
        print(
            json.dumps(
                {
                    "stage1_root": str(A5_ROOT),
                    "stage1": reliability_plan(),
                    "stage2_root": str(A5_TIMING_ROOT),
                    "stage2_conditional": stage2_timing_plan(),
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif args.command == "run-cell":
        run_cell_enveloped(args)
    elif args.command == "summarize":
        print(json.dumps(summarize(args.root), indent=2, sort_keys=True))
    elif args.command == "run-plan":
        print(run_plan())
    else:
        raise RuntimeError("unreachable A5 command")


if __name__ == "__main__":
    main()
