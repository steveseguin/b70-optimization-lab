#!/usr/bin/env python3
"""Diagnose Qwen27 target-body W4A16 row scaling on XPU.

This synthetic microbenchmark measures the current INC/AutoRound target-body
projection shapes with ``torch.ops._xpu_C.int4_gemm_w4a16``. The default
profile matches the promoted TP2/FP16 endpoint recipe. It projects per-rank
per-call timings over all 64 target layers, but it is not an endpoint benchmark
and is not eligible for LocalMaxxing submission.

Weights use the exact layout produced by ``INCXPULinearMethod`` after loading:
contiguous int32 backing storage shaped [N, K/8], exposed to the operator as a
transposed [K/8, N] view with stride (1, K/8). Scales are contiguous floating
point [K/128, N], the symmetric zero point is scalar int8 value 8, and
bias/g_idx are absent. The scale and activation dtype follows the selected
profile.
"""

from __future__ import annotations

import argparse
import functools
import gc
import hashlib
import importlib
import json
import os
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


GROUP_SIZE = 128
PACK_FACTOR = 8
BASELINE_ROWS = 4
DEFAULT_ROWS = (4, 9, 16, 17, 31, 33)
DEFAULT_CALLS_PER_SAMPLE = 16
DEFAULT_KERNEL_PREFIX = "/home/steve/src/vllm-xpu-kernels"
DEFAULT_INC_SOURCE = (
    "/home/steve/src/vllm/vllm/model_executor/layers/quantization/inc.py"
)

ENV_KEYS = (
    "ONEAPI_DEVICE_SELECTOR",
    "ZE_AFFINITY_MASK",
    "SYCL_DEVICE_FILTER",
    "SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS",
    "UR_L0_USE_IMMEDIATE_COMMANDLISTS",
    "SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE",
    "UR_L0_USE_COPY_ENGINE",
    "DNNL_VERBOSE",
    "ONEDNN_VERBOSE",
    "VLLM_XPU_INT4_GEMM_SCRATCHPAD_RING_SIZE",
    "VLLM_XPU_INT4_W4A16_ACCUMULATION_MODE",
    "COMPILATION_CONFIG",
    "GPU_MEMORY_UTILIZATION",
    "XPU_GRAPH",
    "VLLM_XPU_ENABLE_XPU_GRAPH",
    "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
    "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE",
    "VLLM_XPU_GDN_NATIVE_FALLBACK",
    "LD_LIBRARY_PATH",
)


@dataclass(frozen=True)
class Projection:
    name: str
    input_features: int
    output_features: int
    calls_per_target_step: int
    layer_family: str


TP1_PROJECTIONS = (
    Projection("gdn_qkvz", 5120, 16384, 48, "gdn"),
    Projection("gdn_out", 6144, 5120, 48, "gdn"),
    Projection("mlp_gateup", 5120, 34816, 64, "all_layers"),
    Projection("mlp_down", 17408, 5120, 64, "all_layers"),
    Projection("full_attention_qkvgate", 5120, 14336, 16, "full_attention"),
    Projection("full_attention_out", 6144, 5120, 16, "full_attention"),
)

TP2_PROJECTIONS = (
    Projection("gdn_qkvz", 5120, 8192, 48, "gdn"),
    Projection("gdn_out", 3072, 5120, 48, "gdn"),
    Projection("mlp_gateup", 5120, 17408, 64, "all_layers"),
    Projection("mlp_down", 8704, 5120, 64, "all_layers"),
    Projection("full_attention_qkvgate", 5120, 7168, 16, "full_attention"),
    Projection("full_attention_out", 3072, 5120, 16, "full_attention"),
)

PROFILES = {
    "tp2-fp16": (TP2_PROJECTIONS, "float16", 2),
    "tp1-bf16": (TP1_PROJECTIONS, "bfloat16", 1),
}


def parse_rows(value: str) -> list[int]:
    rows: list[int] = []
    seen: set[int] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        try:
            row_count = int(item)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid row count {item!r}") from exc
        if row_count <= 0:
            raise argparse.ArgumentTypeError("row counts must be positive")
        if row_count not in seen:
            rows.append(row_count)
            seen.add(row_count)
    if not rows:
        raise argparse.ArgumentTypeError("expected at least one row count")
    return rows


def benchmark_rows(requested_rows: list[int]) -> list[int]:
    """Keep rows=4 available even when a CLI override omits the baseline."""
    return [BASELINE_ROWS, *[row for row in requested_rows if row != BASELINE_ROWS]]


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def summarize_ms(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "p10": percentile(values, 0.10),
        "p90": percentile(values, 0.90),
        "min": min(values),
        "max": max(values),
        "population_stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
    }


def projection_plan(projection: Projection) -> dict[str, Any]:
    k = projection.input_features
    n = projection.output_features
    packed_weight_bytes = n * (k // PACK_FACTOR) * 4
    scale_bytes = (k // GROUP_SIZE) * n * 2
    return {
        **asdict(projection),
        "operator_mnk": {"m": "rows", "n": n, "k": k},
        "packed_weight_backing_shape": [n, k // PACK_FACTOR],
        "operator_weight_shape": [k // PACK_FACTOR, n],
        "scale_shape": [k // GROUP_SIZE, n],
        "packed_weight_bytes": packed_weight_bytes,
        "scale_bytes": scale_bytes,
        "synthetic_parameter_bytes": packed_weight_bytes + scale_bytes + 1,
    }


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path_value: str | os.PathLike[str] | None) -> dict[str, Any]:
    if path_value is None:
        return {"path": None, "exists": False, "sha256": None}
    path = Path(path_value).expanduser().resolve()
    return {
        "path": str(path),
        "exists": path.is_file(),
        "sha256": sha256_file(path),
    }


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)


def base_runtime_identity(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "argv": sys.argv,
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "kernel_prefix": str(Path(args.kernel_prefix).expanduser().resolve()),
        "inc_layout_reference": file_identity(args.inc_source),
        "environment": {key: os.environ.get(key) for key in ENV_KEYS},
    }


def collect_xpu_runtime_identity(
    torch_mod: Any,
    extension: Any,
    operator: Any,
    args: argparse.Namespace,
    device_index: int,
) -> dict[str, Any]:
    identity = base_runtime_identity(args)
    try:
        properties = torch_mod.xpu.get_device_properties(device_index)
    except Exception as exc:  # noqa: BLE001 - preserve diagnostic identity.
        properties = f"unavailable:{type(exc).__name__}:{exc}"
    try:
        capability = torch_mod.xpu.get_device_capability(device_index)
    except Exception as exc:  # noqa: BLE001 - API varies by torch build.
        capability = f"unavailable:{type(exc).__name__}:{exc}"
    try:
        operator_schema = str(operator.default._schema)
    except Exception as exc:  # noqa: BLE001 - keep benchmark usable on older builds.
        operator_schema = f"unavailable:{type(exc).__name__}:{exc}"

    identity.update(
        {
            "torch_version": str(torch_mod.__version__),
            "torch_git_version": getattr(torch_mod.version, "git_version", None),
            "torch_xpu_version": getattr(torch_mod.version, "xpu", None),
            "torch_config": torch_mod.__config__.show(),
            "xpu_available": bool(torch_mod.xpu.is_available()),
            "xpu_device_count": int(torch_mod.xpu.device_count()),
            "selected_device_index": device_index,
            "selected_device_name": str(torch_mod.xpu.get_device_name(device_index)),
            "selected_device_properties": json_safe(properties),
            "selected_device_capability": json_safe(capability),
            "kernel_extension": file_identity(getattr(extension, "__file__", None)),
            "operator": "torch.ops._xpu_C.int4_gemm_w4a16",
            "operator_schema": operator_schema,
        }
    )
    return identity


def make_document_base(
    args: argparse.Namespace,
    requested_rows: list[int],
    rows: list[int],
) -> dict[str, Any]:
    projections, dtype_name, tensor_parallel_size = PROFILES[args.profile]
    plans = [projection_plan(projection) for projection in projections]
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": {
            "label": "diagnostic_microbenchmark_not_endpoint_not_localmaxxing",
            "diagnostic": True,
            "endpoint_benchmark": False,
            "localmaxxing_eligible": False,
        },
        "purpose": (
            "Measure row-scaling of current Qwen3.6-27B target-body INC W4A16 "
            f"{args.profile} projections; projected totals are a kernel cost "
            "model only."
        ),
        "benchmark_scope": {
            "model_family": "Qwen3.6-27B INT4 AutoRound",
            "profile": args.profile,
            "tensor_parallel_size": tensor_parallel_size,
            "activation_and_scale_dtype": dtype_name,
            "target_body_layers": 64,
            "gdn_layers": 48,
            "full_attention_layers": 16,
            "projection_calls_per_target_step": sum(
                projection.calls_per_target_step for projection in projections
            ),
            "requested_rows": requested_rows,
            "benchmarked_rows": rows,
            "baseline_rows": BASELINE_ROWS,
            "projections": plans,
        },
        "inc_layout": {
            "quantization": f"symmetric_int4_weight_{dtype_name}_activation",
            "group_size": GROUP_SIZE,
            "pack_factor": PACK_FACTOR,
            "checkpoint_weight_layout": "int32 [K/8, N]",
            "synthetic_backing_layout": "contiguous int32 [N, K/8]",
            "operator_weight_layout": (
                "transposed int32 [K/8, N] view with stride (1, K/8)"
            ),
            "scales_layout": f"contiguous {dtype_name} [K/128, N]",
            "symmetric_zero_point": {
                "shape": [1],
                "dtype": "int8",
                "value": 8,
            },
            "bias": None,
            "g_idx": None,
        },
        "measurement_protocol": {
            "warmup_calls_per_case": args.warmup,
            "measured_samples_per_case": args.iterations,
            "calls_per_measured_sample": args.calls_per_sample,
            "measured_calls_per_case": args.iterations * args.calls_per_sample,
            "timer": (
                "primary XPU event elapsed time plus secondary perf_counter_ns "
                "wall time, each divided by calls_per_measured_sample"
            ),
            "synchronization": (
                "one event synchronization after each multi-call sample; no "
                "per-call synchronization"
            ),
            "torch_compile": False,
            "xpu_graph": False,
            "allocation_policy": (
                "one projection weight/scale set and one activation shape live at a "
                "time; release and empty XPU cache between projections"
            ),
            "projection_primary_basis": (
                "sum(calls_per_target_step * per_call_median_ms)"
            ),
            "aggregate_quantile_caveat": (
                "weighted p10/p90 values sum marginal per-projection quantiles; "
                "they are cost-model bounds, not end-to-end target-step quantiles"
            ),
        },
        "arguments": {
            "device": args.device,
            "warmup": args.warmup,
            "iterations": args.iterations,
            "calls_per_sample": args.calls_per_sample,
            "seed": args.seed,
            "profile": args.profile,
            "dry_run": bool(args.dry_run),
            "output_json": args.output_json,
            "output_tensors": args.output_tensors,
        },
    }


def measure_synchronized_calls(
    torch_mod: Any,
    operation: Callable[[], Any],
    warmup: int,
    iterations: int,
    calls_per_sample: int,
) -> tuple[dict[str, dict[str, float | int]], Any]:
    last_output = None
    for _ in range(warmup):
        last_output = operation()
    torch_mod.xpu.synchronize()

    event_samples_ms: list[float] = []
    wall_samples_ms: list[float] = []
    gc_was_enabled = gc.isenabled()
    if gc_was_enabled:
        gc.disable()
    try:
        for _ in range(iterations):
            start_event = torch_mod.xpu.Event(enable_timing=True)
            end_event = torch_mod.xpu.Event(enable_timing=True)
            started_ns = time.perf_counter_ns()
            start_event.record()
            for _ in range(calls_per_sample):
                last_output = operation()
            end_event.record()
            end_event.synchronize()
            wall_samples_ms.append(
                (time.perf_counter_ns() - started_ns) / 1_000_000.0 / calls_per_sample
            )
            event_samples_ms.append(
                float(start_event.elapsed_time(end_event)) / calls_per_sample
            )
    finally:
        if gc_was_enabled:
            gc.enable()
    return {
        "xpu_event": summarize_ms(event_samples_ms),
        "wall": summarize_ms(wall_samples_ms),
    }, last_output


def validate_inc_tensors(
    qweight_backing: Any,
    qweight: Any,
    scales: Any,
    qzeros: Any,
    projection: Projection,
    torch_mod: Any,
    floating_dtype: Any,
) -> None:
    k = projection.input_features
    n = projection.output_features
    expected_backing_shape = (n, k // PACK_FACTOR)
    expected_weight_shape = (k // PACK_FACTOR, n)
    expected_weight_stride = (1, k // PACK_FACTOR)
    expected_scale_shape = (k // GROUP_SIZE, n)
    checks = (
        (tuple(qweight_backing.shape) == expected_backing_shape, "backing shape"),
        (qweight_backing.is_contiguous(), "backing contiguity"),
        (qweight_backing.dtype == torch_mod.int32, "backing dtype"),
        (tuple(qweight.shape) == expected_weight_shape, "operator weight shape"),
        (tuple(qweight.stride()) == expected_weight_stride, "operator weight stride"),
        (qweight.dtype == torch_mod.int32, "operator weight dtype"),
        (tuple(scales.shape) == expected_scale_shape, "scale shape"),
        (scales.is_contiguous(), "scale contiguity"),
        (scales.dtype == floating_dtype, "scale dtype"),
        (tuple(qzeros.shape) == (1,), "zero-point shape"),
        (qzeros.dtype == torch_mod.int8, "zero-point dtype"),
        (int(qzeros.item()) == 8, "zero-point value"),
    )
    failed = [name for passed, name in checks if not passed]
    if failed:
        raise RuntimeError(
            f"INC layout validation failed for {projection.name}: {', '.join(failed)}"
        )


def benchmark_projection(
    torch_mod: Any,
    operator: Any,
    projection: Projection,
    rows: list[int],
    device: str,
    warmup: int,
    iterations: int,
    calls_per_sample: int,
    seed: int,
    floating_dtype: Any,
    captured_outputs: dict[str, Any] | None,
) -> dict[str, Any]:
    k = projection.input_features
    n = projection.output_features
    generator = torch_mod.Generator(device=device)
    generator.manual_seed(seed)

    # This backing + transpose exactly reproduces INCXPULinearMethod's two
    # transpose repack without ever materializing a dense floating-point weight.
    qweight_backing = torch_mod.randint(
        0,
        2**31 - 1,
        (n, k // PACK_FACTOR),
        dtype=torch_mod.int32,
        device=device,
        generator=generator,
    ).contiguous()
    qweight = qweight_backing.t()
    scales = (
        torch_mod.rand(
            (k // GROUP_SIZE, n),
            dtype=floating_dtype,
            device=device,
            generator=generator,
        )
        * 0.02
        + 0.001
    ).contiguous()
    qzeros = torch_mod.tensor([8], dtype=torch_mod.int8, device=device)
    torch_mod.xpu.synchronize()
    validate_inc_tensors(
        qweight_backing,
        qweight,
        scales,
        qzeros,
        projection,
        torch_mod,
        floating_dtype,
    )

    row_results: list[dict[str, Any]] = []
    for row_count in rows:
        hidden = torch_mod.randn(
            (row_count, k),
            dtype=floating_dtype,
            device=device,
            generator=generator,
        ).contiguous()

        gemm = functools.partial(
            operator,
            hidden,
            qweight,
            None,
            scales,
            qzeros,
            GROUP_SIZE,
            None,
        )

        per_call_ms, last_output = measure_synchronized_calls(
            torch_mod, gemm, warmup, iterations, calls_per_sample
        )
        expected_output_shape = (row_count, n)
        if tuple(last_output.shape) != expected_output_shape:
            raise RuntimeError(
                f"unexpected {projection.name} output shape: "
                f"{tuple(last_output.shape)} != {expected_output_shape}"
            )
        output_all_finite = bool(torch_mod.isfinite(last_output).all().item())
        if captured_outputs is not None:
            captured_outputs[f"{projection.name}/rows{row_count}"] = (
                last_output.detach().cpu()
            )
        row_results.append(
            {
                "rows": row_count,
                "activation_shape": [row_count, k],
                "output_shape": [row_count, n],
                "output_dtype": str(last_output.dtype),
                "output_all_finite": output_all_finite,
                "per_call_ms": per_call_ms,
            }
        )
        del gemm, hidden, last_output

    result = {
        **projection_plan(projection),
        "seed": seed,
        "observed_layout": {
            "packed_weight_backing_stride": list(qweight_backing.stride()),
            "operator_weight_stride": list(qweight.stride()),
            "scale_stride": list(scales.stride()),
            "packed_weight_dtype": str(qweight.dtype),
            "scale_dtype": str(scales.dtype),
            "zero_point_dtype": str(qzeros.dtype),
        },
        "rows": row_results,
    }
    del qweight, qweight_backing, scales, qzeros
    gc.collect()
    torch_mod.xpu.empty_cache()
    torch_mod.xpu.synchronize()
    return result


def projected_target_step_costs(
    projection_results: list[dict[str, Any]],
    rows: list[int],
) -> list[dict[str, Any]]:
    stats = ("median", "mean", "p10", "p90")
    totals_by_row: dict[int, dict[str, float]] = {}
    components_by_row: dict[int, list[dict[str, Any]]] = {}

    for row_count in rows:
        totals = {stat: 0.0 for stat in stats}
        components: list[dict[str, Any]] = []
        for projection in projection_results:
            row_result = next(
                item for item in projection["rows"] if item["rows"] == row_count
            )
            per_call = row_result["per_call_ms"]["xpu_event"]
            weighted = {
                stat: float(per_call[stat]) * projection["calls_per_target_step"]
                for stat in stats
            }
            for stat in stats:
                totals[stat] += weighted[stat]
            components.append(
                {
                    "projection": projection["name"],
                    "calls_per_target_step": projection["calls_per_target_step"],
                    "per_call_ms": {stat: per_call[stat] for stat in stats},
                    "weighted_ms_per_target_step": weighted,
                }
            )
        totals_by_row[row_count] = totals
        components_by_row[row_count] = components

    baseline = totals_by_row[BASELINE_ROWS]
    summaries: list[dict[str, Any]] = []
    for row_count in rows:
        totals = totals_by_row[row_count]
        delta_ms = {stat: totals[stat] - baseline[stat] for stat in stats}
        delta_percent = {
            stat: (delta_ms[stat] / baseline[stat] * 100.0)
            if baseline[stat] != 0.0
            else None
            for stat in stats
        }
        summaries.append(
            {
                "rows": row_count,
                "projected_w4_ms_per_target_step": totals["median"],
                "delta_vs_rows4_ms": delta_ms["median"],
                "delta_vs_rows4_percent": delta_percent["median"],
                "weighted_projection_by_per_call_stat_ms": totals,
                "delta_vs_rows4_by_per_call_stat_ms": delta_ms,
                "delta_vs_rows4_by_per_call_stat_percent": delta_percent,
                "components": components_by_row[row_count],
                "primary_timer": "xpu_event",
            }
        )
    return summaries


def run_benchmark(args: argparse.Namespace, rows: list[int]) -> dict[str, Any]:
    kernel_prefix = str(Path(args.kernel_prefix).expanduser().resolve())
    if kernel_prefix not in sys.path:
        sys.path.insert(0, kernel_prefix)

    import torch

    extension = importlib.import_module("vllm_xpu_kernels._xpu_C")
    if not torch.xpu.is_available():
        raise RuntimeError("torch.xpu is unavailable")
    if not hasattr(torch.ops._xpu_C, "int4_gemm_w4a16"):
        raise RuntimeError("torch.ops._xpu_C.int4_gemm_w4a16 is unavailable")
    requested_device = torch.device(args.device)
    if requested_device.type != "xpu":
        raise ValueError("--device must select an XPU device")
    device_index = requested_device.index
    if device_index is None:
        device_index = 0
    if device_index < 0 or device_index >= torch.xpu.device_count():
        raise ValueError(
            f"XPU device index {device_index} is outside available device count "
            f"{torch.xpu.device_count()}"
        )
    torch.xpu.set_device(device_index)
    device = f"xpu:{device_index}"
    operator = torch.ops._xpu_C.int4_gemm_w4a16
    projections, dtype_name, _ = PROFILES[args.profile]
    floating_dtype = getattr(torch, dtype_name)
    captured_outputs: dict[str, Any] | None = (
        {} if args.output_tensors is not None else None
    )

    projection_results: list[dict[str, Any]] = []
    for index, projection in enumerate(projections):
        print(
            f"[{index + 1}/{len(projections)}] {projection.name}: "
            f"rows={','.join(str(row) for row in rows)}",
            file=sys.stderr,
            flush=True,
        )
        projection_results.append(
            benchmark_projection(
                torch,
                operator,
                projection,
                rows,
                device,
                args.warmup,
                args.iterations,
                args.calls_per_sample,
                args.seed + index * 1009,
                floating_dtype,
                captured_outputs,
            )
        )

    output_tensor_identity = None
    if captured_outputs is not None:
        output_tensor_path = Path(args.output_tensors).expanduser()
        output_tensor_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(captured_outputs, output_tensor_path)
        output_tensor_identity = file_identity(output_tensor_path)

    return {
        "runtime_identity": collect_xpu_runtime_identity(
            torch, extension, operator, args, device_index
        ),
        "results": projection_results,
        "projected_target_step_costs": projected_target_step_costs(
            projection_results, rows
        ),
        "captured_output_tensors": output_tensor_identity,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rows",
        type=parse_rows,
        default=list(DEFAULT_ROWS),
        help=(
            "comma-separated row counts (default: 4,9,16,17,31,33); rows=4 "
            "is automatically included as the delta baseline"
        ),
    )
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default="tp2-fp16",
        help="endpoint shape/dtype profile (default: tp2-fp16)",
    )
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument(
        "--calls-per-sample",
        type=int,
        default=DEFAULT_CALLS_PER_SAMPLE,
        help=(
            "operator calls recorded between one XPU event pair (default: 16); "
            "amortizes synchronization overhead"
        ),
    )
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--kernel-prefix", default=DEFAULT_KERNEL_PREFIX)
    parser.add_argument("--inc-source", default=DEFAULT_INC_SOURCE)
    parser.add_argument(
        "--output-json",
        help="optional path receiving the same JSON document printed to stdout",
    )
    parser.add_argument(
        "--output-tensors",
        help=(
            "optional torch.save path for final output tensors from every case; "
            "use identical seeds to compare accumulation modes"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="emit the benchmark plan as JSON without importing torch or using XPU",
    )
    args = parser.parse_args()
    if args.warmup < 0:
        parser.error("--warmup must be non-negative")
    if args.iterations <= 0:
        parser.error("--iterations must be positive")
    if args.calls_per_sample <= 0:
        parser.error("--calls-per-sample must be positive")
    return args


def main() -> int:
    args = parse_args()
    requested_rows = list(args.rows)
    rows = benchmark_rows(requested_rows)
    document = make_document_base(args, requested_rows, rows)
    if args.dry_run:
        document.update(
            {
                "status": "plan_only",
                "runtime_identity": base_runtime_identity(args),
                "results": [],
                "projected_target_step_costs": [],
            }
        )
    else:
        document.update({"status": "completed", **run_benchmark(args, rows)})

    serialized = json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output_json:
        output_path = Path(args.output_json).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized, encoding="utf-8")
    sys.stdout.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
