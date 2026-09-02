#!/usr/bin/env python3
"""Report-only A2 diagnosis of A1's first BF16 M=1 authority mismatch."""

from __future__ import annotations

import argparse
from array import array
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time
from typing import Any


HERE = Path(__file__).resolve().parent
A1_TOOL = HERE / "census-q38-bf16-dense-invariance.py"
A1_TOOL_SHA256 = "e4700fc44a65d71c7b0a7df5ff34924d808ba685c4157b0e2c12fd4b9d4bdf22"
A1_ROOT = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
    "bf16-dense-invariance-phase1-20260902-a1"
)
SHARD_CONTRACT = A1_ROOT / "shard-contract.json"
SHARD_CONTRACT_FILE_SHA256 = (
    "6b82f878734c32099f7dbb0491a0ede061d00fbe7d9c4b4e4e0a49433090a5be"
)
SHARD_CONTRACT_SHA256 = (
    "8ff2556748595bb736ea25caded6bf62cb7c37d8dd0eba0e2819d10f24e179d8"
)
A2_ROOT = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
    "bf16-singleton-diagnostic-20260902-a2"
)
FAMILY = "hc_down_inject"
SENTINEL = "layer00-attn-r0"
SEED = 2026090201
ROWS = 256
COLS = 336
ACTIVE_COLS = 324
PASSES = 4
FOCUS_ROWS = (0, 1, 2, 31, 63, 127, 191, 255)
FOCUS_REPEATS = 20
REPLICAS = (1, 2)
CELL_TIMEOUT_SECONDS = 600
PLAN_TIMEOUT_SECONDS = 1500
AUTHORITY_ENV = "Q38_BF16_SINGLETON_A2_EXECUTE"
A2_ENVIRONMENT = {
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


def load_a1():
    if sha256(A1_TOOL) != A1_TOOL_SHA256:
        raise RuntimeError("A1 tool identity drift")
    spec = importlib.util.spec_from_file_location("q38_bf16_a1_frozen", A1_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import frozen A1 tool")
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
        if key in A2_ENVIRONMENT or key.startswith(prefixes)
    }
    if relevant != A2_ENVIRONMENT:
        raise RuntimeError(f"A2 GEMM environment drift: {sorted(relevant)}")
    return relevant


def bf16_to_float(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits << 16))[0]


def compare_bf16(
    reference: bytes, candidate: bytes, *, rows: int, cols: int
) -> dict[str, Any]:
    expected_bytes = rows * cols * 2
    if len(reference) != expected_bytes or len(candidate) != expected_bytes:
        raise ValueError("BF16 snapshot length does not match shape")
    left = array("H")
    right = array("H")
    left.frombytes(reference)
    right.frombytes(candidate)
    regions = {
        "active_columns_0_324": {
            "differing_elements": 0,
            "rows": set(),
            "cols": set(),
            "sum_abs": 0.0,
            "max_abs": 0.0,
            "by_row": {},
        },
        "synthetic_padding_columns_324_336": {
            "differing_elements": 0,
            "rows": set(),
            "cols": set(),
            "sum_abs": 0.0,
            "max_abs": 0.0,
            "by_row": {},
        },
    }
    first_differences = []
    for index, (a, b) in enumerate(zip(left, right)):
        if a == b:
            continue
        row, col = divmod(index, cols)
        region_name = (
            "active_columns_0_324"
            if col < ACTIVE_COLS
            else "synthetic_padding_columns_324_336"
        )
        region = regions[region_name]
        delta = abs(bf16_to_float(a) - bf16_to_float(b))
        if not math.isfinite(delta):
            delta = float("inf")
        region["differing_elements"] += 1
        region["rows"].add(row)
        region["cols"].add(col)
        region["sum_abs"] += delta
        region["max_abs"] = max(region["max_abs"], delta)
        row_detail = region["by_row"].setdefault(
            row, {"count": 0, "cols": set(), "sum_abs": 0.0, "max_abs": 0.0}
        )
        row_detail["count"] += 1
        row_detail["cols"].add(col)
        row_detail["sum_abs"] += delta
        row_detail["max_abs"] = max(row_detail["max_abs"], delta)
        if len(first_differences) < 16:
            first_differences.append(
                {"row": row, "col": col, "reference_bits": a, "candidate_bits": b}
            )
    result = {}
    for name, region in regions.items():
        count = region["differing_elements"]
        result[name] = {
            "exact": count == 0,
            "differing_elements": count,
            "differing_rows": sorted(region["rows"]),
            "differing_cols": sorted(region["cols"]),
            "differing_row_count": len(region["rows"]),
            "differing_col_count": len(region["cols"]),
            "max_abs_difference": region["max_abs"],
            "mean_abs_difference_over_differences": region["sum_abs"] / count
            if count
            else 0.0,
            "per_row_differences": {
                str(row): {
                    "differing_elements": detail["count"],
                    "differing_cols": sorted(detail["cols"]),
                    "max_abs_difference": detail["max_abs"],
                    "mean_abs_difference": detail["sum_abs"] / detail["count"],
                }
                for row, detail in sorted(region["by_row"].items())
            },
        }
    differing_elements = sum(
        region["differing_elements"] for region in regions.values()
    )
    differing_rows = set().union(*(region["rows"] for region in regions.values()))
    return {
        "exact": differing_elements == 0,
        "differing_elements": differing_elements,
        "differing_rows": sorted(differing_rows),
        "differing_row_count": len(differing_rows),
        "regions": result,
        "first_differences": first_differences,
    }


def snapshot_record(payload: bytes, *, rows: int, cols: int) -> dict[str, Any]:
    width = cols * 2
    active = b"".join(
        payload[row * width : row * width + ACTIVE_COLS * 2] for row in range(rows)
    )
    padding = b"".join(
        payload[row * width + ACTIVE_COLS * 2 : (row + 1) * width]
        for row in range(rows)
    )
    padding_bits = array("H")
    padding_bits.frombytes(padding)
    padding_nonzero = [
        {
            "row": index // max(1, cols - ACTIVE_COLS),
            "col": ACTIVE_COLS + index % max(1, cols - ACTIVE_COLS),
            "bits": bits,
        }
        for index, bits in enumerate(padding_bits)
        if bits & 0x7FFF
    ]
    return {
        "sha256": digest_bytes(payload),
        "active_columns_0_324_sha256": digest_bytes(active),
        "synthetic_padding_columns_324_336_sha256": digest_bytes(padding),
        "synthetic_padding_all_numeric_zero": not padding_nonzero,
        "synthetic_padding_nonzero_count": len(padding_nonzero),
        "synthetic_padding_first_nonzero": padding_nonzero[:16],
        "row_sha256": [
            digest_bytes(payload[row * width : (row + 1) * width])
            for row in range(rows)
        ],
        "row_active_columns_0_324_sha256": [
            digest_bytes(payload[row * width : row * width + ACTIVE_COLS * 2])
            for row in range(rows)
        ],
        "row_synthetic_padding_columns_324_336_sha256": [
            digest_bytes(payload[row * width + ACTIVE_COLS * 2 : (row + 1) * width])
            for row in range(rows)
        ],
    }


def validate_snapshot(payload: bytes, *, rows: int, cols: int) -> None:
    if len(payload) != rows * cols * 2:
        raise RuntimeError("A2 output shape/byte-length drift")
    values = array("H")
    values.frombytes(payload)
    if any((bits & 0x7F80) == 0x7F80 for bits in values):
        raise RuntimeError("A2 output contains non-finite BF16 values")


def classify_protocol(
    invocations: list[bytes], *, rows: int, cols: int
) -> dict[str, Any]:
    if not invocations:
        raise ValueError("protocol requires at least one invocation")
    for invocation in invocations:
        validate_snapshot(invocation, rows=rows, cols=cols)
    reference = invocations[0]
    return {
        "invocations": [
            snapshot_record(value, rows=rows, cols=cols) for value in invocations
        ],
        "comparisons_to_invocation0": [
            compare_bf16(reference, value, rows=rows, cols=cols)
            for value in invocations[1:]
        ],
        "unique_invocation_sha256": sorted(
            {digest_bytes(value) for value in invocations}
        ),
    }


def tensor_bytes(tensor) -> bytes:
    import torch

    return tensor.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()


def native_map_snapshot() -> dict[str, Any]:
    a1 = load_a1()
    maps = Path("/proc/self/maps").read_text(encoding="utf-8")
    paths = sorted(
        {
            str(Path(line.split()[-1]).resolve())
            for line in maps.splitlines()
            if "/" in line.split()[-1]
            and any(
                token in Path(line.split()[-1]).name
                for token in ("libsycl", "libtorch_xpu", "libmkl", "libze_", "libdnnl")
            )
        }
    )
    mappings = [{"path": path, "sha256": a1.sha256(Path(path))} for path in paths]
    roles = {}
    for role, (basename, expected_sha) in a1.EXPECTED_NATIVE_LIBRARIES.items():
        matches = [item for item in mappings if Path(item["path"]).name == basename]
        if len(matches) > 1:
            raise RuntimeError(f"ambiguous pre-GEMM {role} mapping")
        if matches and matches[0]["sha256"] != expected_sha:
            raise RuntimeError(f"pre-GEMM {role} mapping identity drift")
        roles[role] = {
            "status": "validated" if matches else "not_loaded_yet",
            "mapping": matches[0] if matches else None,
        }
    standalone_dnnl = [
        item for item in mappings if Path(item["path"]).name.startswith("libdnnl.so")
    ]
    if standalone_dnnl:
        raise RuntimeError(
            f"unexpected standalone pre-GEMM oneDNN mapping: {standalone_dnnl}"
        )
    return {"mappings": mappings, "expected_roles": roles}


def run_cell(replica: int) -> dict[str, Any]:
    if replica not in REPLICAS:
        raise ValueError("replica is outside A2")
    signal.alarm(CELL_TIMEOUT_SECONDS)
    verify_environment()
    a1 = load_a1()
    admission = a1.validate_admission()
    identity = a1.verify_static_identity()
    a1.refuse_active_accelerator_owner()
    lock = a1.acquire_component_lock()
    if (
        SHARD_CONTRACT.is_symlink()
        or sha256(SHARD_CONTRACT) != SHARD_CONTRACT_FILE_SHA256
    ):
        raise RuntimeError("A1 shard contract is absent or invalid")
    contract = json.loads(SHARD_CONTRACT.read_text(encoding="utf-8"))
    if a1.canonical_sha256(contract) != SHARD_CONTRACT_SHA256:
        raise RuntimeError("A1 shard contract canonical identity drift")
    a1.validate_shard_contract(contract)

    import torch
    import torch.nn.functional as F
    import safetensors

    if torch.__version__ != a1.TORCH_VERSION:
        raise RuntimeError(f"Torch identity drift: {torch.__version__}")
    build_sha = hashlib.sha256(torch.__config__.show().encode()).hexdigest()
    if build_sha != a1.TORCH_BUILD_CONFIG_SHA256:
        raise RuntimeError(f"Torch build identity drift: {build_sha}")
    if safetensors.__version__ != a1.SAFETENSORS_VERSION:
        raise RuntimeError(f"Safetensors identity drift: {safetensors.__version__}")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("A2 requires exactly one selected XPU")

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
    native_pre_gemm = native_map_snapshot()

    # This exact two-pass A1-style deferred-list/cat pair is deliberately the
    # first GEMM work. No immediate-snapshot or warmed diagnostic precedes it.
    cold_a1_pair = []
    for _ in range(2):
        outputs = [F.linear(inputs[row : row + 1], weight) for row in range(ROWS)]
        joined = torch.cat(outputs, dim=0)
        torch.xpu.synchronize()
        if joined.dtype != torch.bfloat16 or tuple(joined.shape) != (ROWS, COLS):
            raise RuntimeError("A2 cold output shape/dtype drift")
        payload = tensor_bytes(joined)
        validate_snapshot(payload, rows=ROWS, cols=COLS)
        cold_a1_pair.append(payload)

    immediate = []
    for _ in range(PASSES):
        row_payloads = []
        for row in range(ROWS):
            output = F.linear(inputs[row : row + 1], weight)
            torch.xpu.synchronize()
            if output.dtype != torch.bfloat16 or tuple(output.shape) != (1, COLS):
                raise RuntimeError("A2 immediate output shape/dtype drift")
            payload = tensor_bytes(output)
            validate_snapshot(payload, rows=1, cols=COLS)
            row_payloads.append(payload)
        immediate.append(b"".join(row_payloads))

    deferred_warm = []
    for _ in range(PASSES):
        outputs = [F.linear(inputs[row : row + 1], weight) for row in range(ROWS)]
        joined = torch.cat(outputs, dim=0)
        torch.xpu.synchronize()
        if joined.dtype != torch.bfloat16 or tuple(joined.shape) != (ROWS, COLS):
            raise RuntimeError("A2 warmed deferred output shape/dtype drift")
        payload = tensor_bytes(joined)
        validate_snapshot(payload, rows=ROWS, cols=COLS)
        deferred_warm.append(payload)

    focus = {}
    for row in FOCUS_ROWS:
        values = []
        for _ in range(FOCUS_REPEATS):
            output = F.linear(inputs[row : row + 1], weight)
            torch.xpu.synchronize()
            if output.dtype != torch.bfloat16 or tuple(output.shape) != (1, COLS):
                raise RuntimeError("A2 focus output shape/dtype drift")
            payload = tensor_bytes(output)
            validate_snapshot(payload, rows=1, cols=COLS)
            values.append(payload)
        focus[str(row)] = classify_protocol(values, rows=1, cols=COLS)

    input_after = a1.tensor_sha256(inputs)
    weight_after = a1.tensor_sha256(weight)
    diagnostic_errors = []
    if input_expected != input_after or weight_expected != weight_after:
        diagnostic_errors.append(
            {
                "type": "MutationError",
                "message": "A2 input or weight mutated",
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
    immediate_report = classify_protocol(immediate, rows=ROWS, cols=COLS)
    cold_report = classify_protocol(cold_a1_pair, rows=ROWS, cols=COLS)
    deferred_report = classify_protocol(deferred_warm, rows=ROWS, cols=COLS)
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-singleton-a2-cell.v1",
        "status": "diagnostic_complete"
        if not diagnostic_errors
        else "diagnostic_error",
        "classification": "report_only_m1_singleton_diagnostic",
        "identity": {
            **identity,
            "a1_tool_sha256": A1_TOOL_SHA256,
            "a1_shard_contract_canonical_sha256": SHARD_CONTRACT_SHA256,
            "family": FAMILY,
            "sentinel": sentinel,
            "seed": SEED,
            "replica": replica,
            "source_tensors": source_tensors,
            "checkpoint_shards": shards,
            "input_sha256": input_expected,
            "weight_sha256": weight_expected,
            "environment": verify_environment(),
            "native_mappings_pre_gemm": native_pre_gemm,
            "native_libraries_post_gemm": native_post_gemm,
            "admission": admission,
        },
        "protocol": {
            "rows": ROWS,
            "cols": COLS,
            "passes": PASSES,
            "focus_rows": list(FOCUS_ROWS),
            "focus_repeats": FOCUS_REPEATS,
        },
        "cold_a1_style_pair": cold_report,
        "immediate_row_snapshot": immediate_report,
        "warmed_a1_style_deferred_cat": deferred_report,
        "fixed_row_repeats": focus,
        "diagnostic_errors": diagnostic_errors,
        "interpretation": {
            "immediate_varies": len(immediate_report["unique_invocation_sha256"]) > 1,
            "cold_a1_pair_varies": len(cold_report["unique_invocation_sha256"]) > 1,
            "warmed_deferred_varies": len(deferred_report["unique_invocation_sha256"])
            > 1,
            "runtime_change_authorized": False,
            "speed_or_quality_credit": False,
        },
    }


def atomic_write(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def infer_conclusion(records: list[dict[str, Any]]) -> str:
    def comparisons(name: str):
        return [
            comparison
            for record in records
            for comparison in record[name]["comparisons_to_invocation0"]
        ]

    cold = comparisons("cold_a1_style_pair")
    immediate = comparisons("immediate_row_snapshot")
    deferred = comparisons("warmed_a1_style_deferred_cat")
    focus = [
        comparison
        for record in records
        for row in record["fixed_row_repeats"].values()
        for comparison in row["comparisons_to_invocation0"]
    ]

    def region_diff(items, region: str) -> bool:
        return any(not item["regions"][region]["exact"] for item in items)

    def cross_process_diff(name: str, region_hash: str) -> bool:
        if len(records) < 2:
            return False
        values = [
            tuple(item[region_hash] for item in record[name]["invocations"])
            for record in records
        ]
        return len(set(values)) > 1

    immediate_or_focus_active = region_diff(
        immediate + focus, "active_columns_0_324"
    ) or cross_process_diff("immediate_row_snapshot", "active_columns_0_324_sha256")
    if len(records) >= 2:
        focus_active_by_process = [
            tuple(
                (
                    row_id,
                    tuple(
                        item["active_columns_0_324_sha256"]
                        for item in row["invocations"]
                    ),
                )
                for row_id, row in sorted(record["fixed_row_repeats"].items())
            )
            for record in records
        ]
        immediate_or_focus_active = (
            immediate_or_focus_active or len(set(focus_active_by_process)) > 1
        )
    warmed_deferred_active = region_diff(
        deferred, "active_columns_0_324"
    ) or cross_process_diff(
        "warmed_a1_style_deferred_cat", "active_columns_0_324_sha256"
    )
    cold_active = region_diff(cold, "active_columns_0_324") or cross_process_diff(
        "cold_a1_style_pair", "active_columns_0_324_sha256"
    )
    tail_any = region_diff(
        cold + immediate + deferred + focus,
        "synthetic_padding_columns_324_336",
    ) or any(
        cross_process_diff(name, "synthetic_padding_columns_324_336_sha256")
        for name in (
            "cold_a1_style_pair",
            "immediate_row_snapshot",
            "warmed_a1_style_deferred_cat",
        )
    )
    tail_any = (
        tail_any
        or any(
            not invocation["synthetic_padding_all_numeric_zero"]
            for record in records
            for name in (
                "cold_a1_style_pair",
                "immediate_row_snapshot",
                "warmed_a1_style_deferred_cat",
            )
            for invocation in record[name]["invocations"]
        )
        or any(
            not invocation["synthetic_padding_all_numeric_zero"]
            for record in records
            for row in record["fixed_row_repeats"].values()
            for invocation in row["invocations"]
        )
    )
    if len(records) >= 2:
        focus_tail_by_process = [
            tuple(
                (
                    row_id,
                    tuple(
                        item["synthetic_padding_columns_324_336_sha256"]
                        for item in row["invocations"]
                    ),
                )
                for row_id, row in sorted(record["fixed_row_repeats"].items())
            )
            for record in records
        ]
        tail_any = tail_any or len(set(focus_tail_by_process)) > 1
    if immediate_or_focus_active:
        return "genuine_warmed_m1_flinear_active_output_repeatability_failure"
    if warmed_deferred_active:
        return "warmed_deferred_queue_or_buffer_lifetime_active_output_failure"
    if cold_active:
        return "cold_start_active_output_instability_not_reproduced_when_warm"
    if tail_any:
        return "synthetic_padding_tail_only_instability_not_production_output_nondeterminism"
    return "a1_mismatch_not_reproduced_in_bounded_a2"


def summarize(root: Path) -> dict[str, Any]:
    records = [
        json.loads((root / f"replica{replica}.json").read_text())
        for replica in REPLICAS
    ]
    identities = [record["identity"] for record in records]
    cross_process = {
        key: len({identity[key] for identity in identities}) == 1
        for key in ("input_sha256", "weight_sha256")
    }
    protocol_hashes = {
        name: [
            hashlib.sha256(
                json.dumps(record[name], sort_keys=True).encode()
            ).hexdigest()
            for record in records
        ]
        for name in (
            "cold_a1_style_pair",
            "immediate_row_snapshot",
            "warmed_a1_style_deferred_cat",
            "fixed_row_repeats",
        )
    }
    identity_exact = all(cross_process.values())
    return {
        "schema": "neural.download.qwen38-flash-next.bf16-singleton-a2-summary.v1",
        "status": "diagnostic_complete" if identity_exact else "diagnostic_error",
        "replicas": list(REPLICAS),
        "identity_exact_across_processes": identity_exact,
        "identity_comparisons": cross_process,
        "protocol_sha256_by_replica": protocol_hashes,
        "protocol_exact_across_processes": {
            name: len(set(values)) == 1 for name, values in protocol_hashes.items()
        },
        "diagnostic_conclusion": (
            infer_conclusion(records)
            if identity_exact
            else "identity_drift_no_interpretation"
        ),
        "report_only": True,
        "runtime_change_authorized": False,
    }


def run_cell_enveloped(replica: int) -> None:
    if not A2_ROOT.is_dir() or A2_ROOT.is_symlink():
        raise RuntimeError("A2 cell requires the parent-created external evidence root")
    output = A2_ROOT / f"replica{replica}.json"
    started = time.time_ns()
    payload: dict[str, Any] | None = None
    failure: BaseException | None = None
    try:
        payload = run_cell(replica)
        if payload.get("status") != "diagnostic_complete":
            failure = RuntimeError(
                "A2 cell recorded a mutation or native-provider error"
            )
    except BaseException as error:
        failure = error
        payload = {
            "schema": "neural.download.qwen38-flash-next.bf16-singleton-a2-cell.v1",
            "status": "diagnostic_error",
            "classification": "report_only_failure_envelope",
            "identity": {
                "a1_tool_sha256": A1_TOOL_SHA256,
                "a1_shard_contract_file_sha256": SHARD_CONTRACT_FILE_SHA256,
                "a1_shard_contract_canonical_sha256": SHARD_CONTRACT_SHA256,
                "family": FAMILY,
                "sentinel": SENTINEL,
                "seed": SEED,
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
                "receipt": load_a1().validate_admission(),
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
            f"A2 replica {replica} failed after preserving its diagnostic envelope"
        ) from failure


def run_plan() -> Path:
    if os.environ.get(AUTHORITY_ENV) != "YES":
        raise RuntimeError(f"set {AUTHORITY_ENV}=YES")
    a1 = load_a1()
    initial = a1.validate_admission()
    a1.verify_static_identity()
    a1.refuse_active_accelerator_owner()
    if A2_ROOT.exists():
        raise FileExistsError(f"refusing existing A2 root: {A2_ROOT}")
    A2_ROOT.mkdir(parents=True)
    deadline = time.monotonic() + PLAN_TIMEOUT_SECONDS
    for replica in REPLICAS:
        before = a1.validate_admission()
        if before["aer_event_count"] != initial["aer_event_count"]:
            raise RuntimeError("new AER event before A2 cell")
        child_error: BaseException | None = None
        postflight_error: BaseException | None = None
        parent_postflight: dict[str, Any] = {"status": "not_run"}
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "run-cell",
                    "--replica",
                    str(replica),
                ],
                check=True,
                env=dict(A2_ENVIRONMENT),
                timeout=min(
                    CELL_TIMEOUT_SECONDS, max(1, int(deadline - time.monotonic()))
                ),
            )
        except BaseException as error:
            child_error = error
        finally:
            try:
                after = a1.validate_admission()
                if after["aer_event_count"] != before["aer_event_count"]:
                    raise RuntimeError("new AER event during A2 cell")
                parent_postflight = {"status": "pass", "receipt": after}
            except BaseException as error:
                postflight_error = error
                parent_postflight = {
                    "status": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                }
            atomic_write(
                A2_ROOT / f"parent-postflight-replica{replica}.json",
                parent_postflight,
            )
            child_output = A2_ROOT / f"replica{replica}.json"
            if child_error is not None and not child_output.exists():
                atomic_write(
                    child_output,
                    {
                        "schema": "neural.download.qwen38-flash-next.bf16-singleton-a2-cell.v1",
                        "status": "diagnostic_error",
                        "classification": "parent_preserved_missing_child_envelope",
                        "identity": {
                            "a1_tool_sha256": A1_TOOL_SHA256,
                            "family": FAMILY,
                            "sentinel": SENTINEL,
                            "seed": SEED,
                            "replica": replica,
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
            raise RuntimeError(
                f"A2 child replica {replica} failed; parent postflight preserved"
            ) from child_error
        if postflight_error is not None:
            raise RuntimeError(
                f"A2 parent postflight replica {replica} failed"
            ) from postflight_error
    summary_path = A2_ROOT / "summary.json"
    result = summarize(A2_ROOT)
    result["initial_health"] = initial
    result["final_health"] = a1.validate_admission()
    atomic_write(summary_path, result)
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("plan")
    sub.add_parser("run-plan")
    cell = sub.add_parser("run-cell")
    cell.add_argument("--replica", type=int, choices=REPLICAS, required=True)
    args = parser.parse_args()
    if args.command in (None, "plan"):
        print(
            json.dumps(
                {
                    "family": FAMILY,
                    "sentinel": SENTINEL,
                    "seed": SEED,
                    "replicas": list(REPLICAS),
                    "device_execution": False,
                },
                sort_keys=True,
            )
        )
        return
    if args.command == "run-plan":
        print(run_plan())
        return
    run_cell_enveloped(args.replica)


if __name__ == "__main__":
    main()
