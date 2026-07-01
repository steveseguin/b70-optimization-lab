#!/usr/bin/env python3
"""M-scaling screen for Qwen3.6 Quark W8A8 grouped GEMM on XPU.

This script answers a specific kernel question:

    Does the current grouped-GEMM op get materially better effective TOPS when
    we aggregate more rows per launch while preserving a real route shape?

It consumes hot-replication route-plan JSONs produced by
`qwen36-hotrep-route-plan.py`, reconstructs full logical expert counts for each
captured window, scales those counts to requested row counts, and times
`cutlass_grouped_gemm_w8a8_int8_interface` for Qwen3.6 MoE GEMM1/GEMM2 shapes.

It is not an endpoint result and does not change model quality. It is a kernel
screen used to decide whether persistent batching/work aggregation is a credible
path toward lower single-request decode latency.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any


DEFAULT_MODEL_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def parse_int_list(value: str) -> list[int]:
    out: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        out.append(int(item))
    if not out:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return out


def load_text_config(path: str) -> dict[str, Any]:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    text_config = cfg.get("text_config")
    if not isinstance(text_config, dict):
        raise ValueError(f"Missing text_config in {path}")
    return text_config


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else math.nan


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "mean": mean(values),
        "median": statistics.median(values) if values else math.nan,
        "p05": percentile(values, 0.05),
        "p95": percentile(values, 0.95),
        "min": min(values) if values else math.nan,
        "max": max(values) if values else math.nan,
        "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
    }


def counts_from_window(window: dict[str, Any], num_experts: int) -> list[int]:
    counts = [0] * num_experts
    for rank in window["rank_summaries"]:
        for row in rank.get("hot_rows_detail") or []:
            counts[int(row["expert"])] += 1
        for row in rank.get("cold_rows_detail") or []:
            counts[int(row["expert"])] += 1
    expected = int(window["assignments"])
    if sum(counts) != expected:
        raise ValueError(
            f"reconstructed {sum(counts)} assignments, expected {expected}")
    return counts


def load_route_windows(paths: list[str], num_experts: int) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for plan_path in paths:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        for index, window in enumerate(plan["windows"]):
            counts = counts_from_window(window, num_experts)
            windows.append({
                "plan_path": plan_path,
                "plan_index": len(windows),
                "window_index": index,
                "layer": plan.get("layer"),
                "route_start_index": window.get("route_start_index"),
                "source_assignments": sum(counts),
                "source_active_experts": sum(1 for value in counts if value > 0),
                "counts": counts,
            })
    if not windows:
        raise ValueError("no route windows loaded")
    return windows


def scale_counts(counts: list[int], target_rows: int) -> list[int]:
    total = sum(counts)
    if total <= 0:
        raise ValueError("cannot scale empty counts")
    if target_rows <= 0:
        raise ValueError("target_rows must be positive")
    scaled = [value * target_rows / total for value in counts]
    floors = [int(math.floor(value)) for value in scaled]
    remaining = target_rows - sum(floors)
    if remaining > 0:
        order = sorted(
            range(len(counts)),
            key=lambda idx: (scaled[idx] - floors[idx], counts[idx], -idx),
            reverse=True,
        )
        for idx in order[:remaining]:
            floors[idx] += 1
    elif remaining < 0:
        order = sorted(
            [idx for idx, value in enumerate(floors) if value > 0],
            key=lambda idx: (scaled[idx] - floors[idx], counts[idx], -idx),
        )
        for idx in order[:abs(remaining)]:
            floors[idx] -= 1
    if sum(floors) != target_rows:
        raise AssertionError("scaled counts do not match target rows")
    return floors


def shape_metadata(
    counts: list[int],
    *,
    hidden: int,
    inter_per_tp: int,
    stage: str,
    output_bytes: int,
) -> dict[str, Any]:
    rows = sum(counts)
    experts = len(counts)
    active = sum(1 for value in counts if value > 0)
    if stage == "gemm1":
        k_dim = hidden
        n_dim = 2 * inter_per_tp
    elif stage == "gemm2":
        k_dim = inter_per_tp
        n_dim = hidden
    else:
        raise ValueError(f"unknown stage {stage}")
    ops = 2.0 * rows * k_dim * n_dim
    a_bytes = rows * k_dim + rows * 4
    active_weight_bytes = active * k_dim * n_dim + active * n_dim * 4
    full_weight_bytes = experts * k_dim * n_dim + experts * n_dim * 4
    output = rows * n_dim * output_bytes
    rows_per_expert = experts * 4
    active_bytes = a_bytes + active_weight_bytes + output + rows_per_expert
    full_bytes = a_bytes + full_weight_bytes + output + rows_per_expert
    return {
        "rows": rows,
        "experts": experts,
        "active_experts": active,
        "k": k_dim,
        "n": n_dim,
        "ops": ops,
        "active_lower_bound_bytes": active_bytes,
        "full_table_upper_bound_bytes": full_bytes,
        "arithmetic_intensity_active_ops_per_byte": (
            ops / active_bytes if active_bytes else math.nan
        ),
        "arithmetic_intensity_full_table_ops_per_byte": (
            ops / full_bytes if full_bytes else math.nan
        ),
    }


def run_gpu_case(
    *,
    counts: list[int],
    stage: str,
    hidden: int,
    inter_per_tp: int,
    dtype_name: str,
    device: str,
    seed: int,
    warmup: int,
    iterations: int,
) -> tuple[dict[str, Any], list[float]]:
    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    output_bytes = 2
    meta = shape_metadata(
        counts,
        hidden=hidden,
        inter_per_tp=inter_per_tp,
        stage=stage,
        output_bytes=output_bytes,
    )
    dtype = torch.bfloat16 if dtype_name == "bf16" else torch.float16
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)

    ptr_a = torch.randint(
        -127,
        128,
        (meta["rows"], meta["k"]),
        generator=generator,
        device=device,
        dtype=torch.int8,
    ).contiguous()
    ptr_a_scales = (
        torch.rand((meta["rows"],), generator=generator, device=device, dtype=torch.float32)
        * 0.02 + 0.001
    ).contiguous()
    ptr_b = torch.randint(
        -127,
        128,
        (meta["experts"], meta["k"], meta["n"]),
        generator=generator,
        device=device,
        dtype=torch.int8,
    ).contiguous()
    ptr_b_scales = (
        torch.rand(
            (meta["experts"], meta["n"]),
            generator=generator,
            device=device,
            dtype=torch.float32,
        ) * 0.02 + 0.001
    ).contiguous()
    ptr_d = torch.empty((meta["rows"], meta["n"]), device=device, dtype=dtype)
    rows_per_expert = torch.tensor(counts, device=device, dtype=torch.int32)

    def op() -> None:
        torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
            ptr_A=ptr_a,
            ptr_A_scales=ptr_a_scales,
            ptr_B=ptr_b,
            ptr_B_scales=ptr_b_scales,
            ptr_bias=None,
            ptr_D=ptr_d,
            rows_per_expert=rows_per_expert,
            N=meta["n"],
            K=meta["k"],
            num_experts=meta["experts"],
        )

    for _ in range(warmup):
        op()
    torch.xpu.synchronize()

    timings = []
    for _ in range(iterations):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        op()
        end.record()
        torch.xpu.synchronize()
        timings.append(float(start.elapsed_time(end) * 1000.0))

    meta["output_all_finite"] = bool(torch.isfinite(ptr_d.float()).all().item())
    meta["output_max_abs"] = float(ptr_d.float().abs().max().item())
    del ptr_a, ptr_a_scales, ptr_b, ptr_b_scales, ptr_d, rows_per_expert
    torch.xpu.empty_cache()
    return meta, timings


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    text_config = load_text_config(args.model_config)
    hidden = int(text_config["hidden_size"])
    inter_per_tp = int(text_config["moe_intermediate_size"]) // args.tp_size
    num_experts = int(text_config["num_experts"])
    stages = ["gemm1", "gemm2"] if args.gemm_stage == "both" else [args.gemm_stage]
    windows = load_route_windows(args.route_plan_json, num_experts)
    if args.max_windows:
        windows = windows[:args.max_windows]

    gpu_enabled = not args.dry_run
    if gpu_enabled:
        import torch
        import vllm_xpu_kernels._xpu_C  # noqa: F401
        torch.manual_seed(args.seed)
        kernel_module = getattr(vllm_xpu_kernels._xpu_C, "__file__", None)
        torch_version = torch.__version__
    else:
        kernel_module = None
        torch_version = None

    rows: list[dict[str, Any]] = []
    for window_index, window in enumerate(windows):
        for target_rows in args.target_rows:
            counts = scale_counts(window["counts"], target_rows)
            for stage in stages:
                if gpu_enabled:
                    meta, timings = run_gpu_case(
                        counts=counts,
                        stage=stage,
                        hidden=hidden,
                        inter_per_tp=inter_per_tp,
                        dtype_name=args.dtype,
                        device=args.device,
                        seed=args.seed + window_index * 10000 +
                        target_rows * 13 + (0 if stage == "gemm1" else 100000),
                        warmup=args.warmup,
                        iterations=args.iterations,
                    )
                else:
                    meta = shape_metadata(
                        counts,
                        hidden=hidden,
                        inter_per_tp=inter_per_tp,
                        stage=stage,
                        output_bytes=2,
                    )
                    meta["output_all_finite"] = None
                    meta["output_max_abs"] = None
                    timings = []
                summary = summarize(timings)
                mean_us = summary["mean"]
                seconds = mean_us * 1e-6 if mean_us and not math.isnan(mean_us) else math.nan
                rows.append({
                    "window_index": window_index,
                    "plan_path": window["plan_path"],
                    "source_layer": window["layer"],
                    "source_route_start_index": window["route_start_index"],
                    "source_assignments": window["source_assignments"],
                    "source_active_experts": window["source_active_experts"],
                    "target_rows": target_rows,
                    "stage": stage,
                    **meta,
                    "timing_us": summary,
                    "effective_tops": (
                        meta["ops"] / seconds / 1e12
                        if seconds and not math.isnan(seconds) and seconds > 0
                        else math.nan
                    ),
                    "active_lower_bound_bandwidth_tb_s": (
                        meta["active_lower_bound_bytes"] / seconds / 1e12
                        if seconds and not math.isnan(seconds) and seconds > 0
                        else math.nan
                    ),
                    "full_table_upper_bound_bandwidth_tb_s": (
                        meta["full_table_upper_bound_bytes"] / seconds / 1e12
                        if seconds and not math.isnan(seconds) and seconds > 0
                        else math.nan
                    ),
                })

    aggregate: list[dict[str, Any]] = []
    for stage in stages:
        for target_rows in args.target_rows:
            items = [
                row for row in rows
                if row["stage"] == stage and row["target_rows"] == target_rows
            ]
            aggregate.append({
                "stage": stage,
                "target_rows": target_rows,
                "cases": len(items),
                "mean_us": summarize([float(row["timing_us"]["mean"]) for row in items if row["timing_us"]["count"]]),
                "effective_tops": summarize([float(row["effective_tops"]) for row in items if not math.isnan(float(row["effective_tops"]))]),
                "active_lower_bound_bandwidth_tb_s": summarize([
                    float(row["active_lower_bound_bandwidth_tb_s"])
                    for row in items
                    if not math.isnan(float(row["active_lower_bound_bandwidth_tb_s"]))
                ]),
                "full_table_upper_bound_bandwidth_tb_s": summarize([
                    float(row["full_table_upper_bound_bandwidth_tb_s"])
                    for row in items
                    if not math.isnan(float(row["full_table_upper_bound_bandwidth_tb_s"]))
                ]),
                "active_experts": summarize([float(row["active_experts"]) for row in items]),
            })

    return {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "metadata": {
            "model_config": args.model_config,
            "route_plan_json": args.route_plan_json,
            "tp_size": args.tp_size,
            "hidden_size": hidden,
            "intermediate_per_tp": inter_per_tp,
            "num_experts": num_experts,
            "target_rows": args.target_rows,
            "max_windows": args.max_windows,
            "device": args.device,
            "dtype": args.dtype,
            "dry_run": args.dry_run,
            "warmup": args.warmup,
            "iterations": args.iterations,
            "seed": args.seed,
            "torch_version": torch_version,
            "kernel_module": kernel_module,
        },
        "aggregate": aggregate,
        "cases": rows,
    }


def write_markdown(path: str, result: dict[str, Any]) -> None:
    meta = result["metadata"]
    lines = []
    lines.append("# Qwen3.6 W8A8 Grouped-GEMM M-Scaling Screen")
    lines.append("")
    lines.append(f"Dry run: `{meta['dry_run']}`")
    lines.append(f"Inputs: `{', '.join(meta['route_plan_json'])}`")
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append("| stage | target rows | cases | us mean | TOPS mean | active BW TB/s | full-table BW TB/s | active experts mean |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in result["aggregate"]:
        lines.append(
            f"| `{row['stage']}` | {row['target_rows']} | {row['cases']} | "
            f"{row['mean_us']['mean']:.3f} | "
            f"{row['effective_tops']['mean']:.3f} | "
            f"{row['active_lower_bound_bandwidth_tb_s']['mean']:.3f} | "
            f"{row['full_table_upper_bound_bandwidth_tb_s']['mean']:.3f} | "
            f"{row['active_experts']['mean']:.1f} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    if meta["dry_run"]:
        lines.append("- This artifact validates shape construction only. Run without `--dry-run` in a clean XPU window for timings.")
    else:
        lines.append("- If effective TOPS rises strongly with target rows, the current decode path is small-M/launch underutilized and persistent row aggregation is a strong candidate.")
        lines.append("- If effective TOPS stays flat, the bottleneck is likely the kernel path/layout itself or a lower-level hardware/runtime limit.")
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def strict_json_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: strict_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strict_json_value(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-plan-json", nargs="+", required=True)
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--target-rows", type=parse_int_list, default=parse_int_list("32,64,128,256,512,1024"))
    parser.add_argument("--max-windows", type=int, default=10)
    parser.add_argument("--gemm-stage", choices=("gemm1", "gemm2", "both"), default="both")
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260612)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    result = evaluate(args)
    Path(args.output_json).write_text(
        json.dumps(strict_json_value(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_out:
        write_markdown(args.markdown_out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
