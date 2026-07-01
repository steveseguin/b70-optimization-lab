#!/usr/bin/env python3
"""Benchmark W8A8 grouped-GEMM shapes from hot-replicated route plans.

The input is produced by `qwen36-hotrep-route-plan.py`. This harness times:

- `exact_full`: the current full logical expert table for the whole route
  window on one TP rank.
- `hotrep_one_launch_rankmax`: an idealized one-launch per-rank hot+cold table,
  taking the max rank time as the parallel lower-bound.
- `hotrep_two_launch_rankmax`: hot and cold as separate per-rank grouped-GEMM
  launches, again taking the max rank sum.

This is still a grouped-GEMM shape screen, not a full fused-MoE endpoint result.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


DEFAULT_MODEL_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)


def load_text_config(path: str) -> dict[str, Any]:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    text_config = cfg.get("text_config")
    if not isinstance(text_config, dict):
        raise ValueError(f"Missing text_config in {path}")
    return text_config


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(ordered[lo])
    frac = pos - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "mean_us": mean(values),
        "median_us": statistics.median(values) if values else math.nan,
        "p05_us": percentile(values, 0.05),
        "p95_us": percentile(values, 0.95),
        "min_us": min(values) if values else math.nan,
        "max_us": max(values) if values else math.nan,
        "samples": len(values),
    }


def summarize_numbers(values: list[float | int]) -> dict[str, Any]:
    vals = [float(value) for value in values]
    return {
        "mean": mean(vals),
        "min": min(vals) if vals else math.nan,
        "max": max(vals) if vals else math.nan,
    }


def format_mib(value: int) -> float:
    return value / (1024.0 * 1024.0)


def tensor_bytes(shape: tuple[int, ...], element_size: int) -> int:
    total = 1
    for dim in shape:
        total *= dim
    return total * element_size


def compact_nonzero_counts(mapping: dict[str, int]) -> list[int]:
    return [int(value) for _, value in sorted(
        ((int(key), int(value)) for key, value in mapping.items() if int(value) > 0),
        key=lambda item: item[0],
    )]


def counts_from_window(window: dict[str, Any], num_experts: int) -> list[int]:
    counts = [0] * num_experts
    for rank in window["rank_summaries"]:
        for row in rank.get("hot_rows_detail") or []:
            counts[int(row["expert"])] += 1
        for row in rank.get("cold_rows_detail") or []:
            counts[int(row["expert"])] += 1
    if sum(counts) != int(window["assignments"]):
        raise ValueError("full counts do not reconstruct the route assignments")
    return counts


def rank_count_vectors(window: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for rank in window["rank_summaries"]:
        hot_counts = [int(value) for value in rank["hot_counts_by_compact_expert"]]
        cold_counts = compact_nonzero_counts(rank["cold_counts_by_logical_expert"])
        out.append({
            "rank": int(rank["rank"]),
            "hot_counts": hot_counts,
            "cold_counts": cold_counts,
            "combined_counts": hot_counts + cold_counts,
            "hot_rows": sum(hot_counts),
            "cold_rows": sum(cold_counts),
        })
    return out


def shape_metadata(counts: list[int], *, hidden: int, inter_per_tp: int, stage: str) -> dict[str, Any]:
    rows = sum(counts)
    experts = len(counts)
    active = sum(1 for value in counts if int(value) > 0)
    if stage == "gemm1":
        k_dim = hidden
        n_dim = 2 * inter_per_tp
    elif stage == "gemm2":
        k_dim = inter_per_tp
        n_dim = hidden
    else:
        raise ValueError(f"unknown stage {stage}")
    allocated_bytes = (
        rows * k_dim +                  # ptr_A int8
        rows * 4 +                      # ptr_A_scales fp32
        experts * k_dim * n_dim +       # ptr_B int8
        experts * n_dim * 4 +           # ptr_B_scales fp32
        rows * n_dim * 2 +              # ptr_D bf16
        experts * 4                     # rows_per_expert int32
    )
    return {
        "rows": rows,
        "experts": experts,
        "active_experts": active,
        "k": k_dim,
        "n": n_dim,
        "allocated_mib_estimate": format_mib(allocated_bytes),
    }


def shape_aggregate(stage_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = {}

    def bucket_for(mode: str, stage: str) -> dict[str, Any]:
        return buckets.setdefault((mode, stage), {
            "mode": mode,
            "stage": stage,
            "cases": 0,
            "rows": [],
            "experts": [],
            "active_experts": [],
            "allocated_mib_estimate": [],
        })

    for row in stage_results:
        mode = str(row["mode"])
        stage = str(row["stage"])
        bucket = bucket_for(mode, stage)
        bucket["cases"] += 1

        if mode == "exact_full":
            bucket["rows"].append(int(row["rows"]))
            bucket["experts"].append(int(row["experts"]))
            bucket["active_experts"].append(int(row["active_experts"]))
            bucket["allocated_mib_estimate"].append(float(row["allocated_mib_estimate"]))
            continue

        rank_rows: list[int] = []
        rank_experts: list[int] = []
        rank_active: list[int] = []
        rank_mib: list[float] = []
        for rank_result in row.get("rank_results", []):
            if mode == "hotrep_two_launch_rankmax":
                hot = rank_result["hot"]
                cold = rank_result["cold"]
                rank_rows.append(int(hot["rows"]) + int(cold["rows"]))
                rank_experts.append(int(hot["experts"]) + int(cold["experts"]))
                rank_active.append(int(hot["active_experts"]) + int(cold["active_experts"]))
                rank_mib.append(
                    float(hot["allocated_mib_estimate"]) +
                    float(cold["allocated_mib_estimate"])
                )
            else:
                rank_rows.append(int(rank_result["rows"]))
                rank_experts.append(int(rank_result["experts"]))
                rank_active.append(int(rank_result["active_experts"]))
                rank_mib.append(float(rank_result["allocated_mib_estimate"]))

        bucket["rows"].append(max(rank_rows) if rank_rows else 0)
        bucket["experts"].append(max(rank_experts) if rank_experts else 0)
        bucket["active_experts"].append(max(rank_active) if rank_active else 0)
        bucket["allocated_mib_estimate"].append(max(rank_mib) if rank_mib else 0.0)

    rows = []
    for (_, _), bucket in sorted(buckets.items()):
        rows.append({
            "mode": bucket["mode"],
            "stage": bucket["stage"],
            "cases": bucket["cases"],
            "rows": summarize_numbers(bucket["rows"]),
            "experts": summarize_numbers(bucket["experts"]),
            "active_experts": summarize_numbers(bucket["active_experts"]),
            "allocated_mib_estimate": summarize_numbers(bucket["allocated_mib_estimate"]),
        })
    return rows


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

    meta = shape_metadata(
        counts,
        hidden=hidden,
        inter_per_tp=inter_per_tp,
        stage=stage,
    )
    if meta["rows"] <= 0:
        return meta, [0.0] * iterations
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


def evaluate_plan(args: argparse.Namespace) -> dict[str, Any]:
    text_config = load_text_config(args.model_config)
    hidden = int(text_config["hidden_size"])
    inter_per_tp = int(text_config["moe_intermediate_size"]) // args.tp_size
    num_experts = int(text_config["num_experts"])
    plans = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.route_plan_json]

    gpu_enabled = not args.dry_run
    if gpu_enabled:
        import torch
        import vllm_xpu_kernels._xpu_C  # noqa: F401
        torch.manual_seed(args.seed)

    case_results: list[dict[str, Any]] = []
    stage_results: list[dict[str, Any]] = []
    for plan_index, plan in enumerate(plans):
        for window_index, window in enumerate(plan["windows"]):
            full_counts = counts_from_window(window, num_experts)
            rank_vectors = rank_count_vectors(window)
            for stage in (["gemm1", "gemm2"] if args.gemm_stage == "both" else [args.gemm_stage]):
                if gpu_enabled:
                    full_meta, full_timings = run_gpu_case(
                        counts=full_counts,
                        stage=stage,
                        hidden=hidden,
                        inter_per_tp=inter_per_tp,
                        dtype_name=args.dtype,
                        device=args.device,
                        seed=args.seed + plan_index * 10000 + window_index * 101,
                        warmup=args.warmup,
                        iterations=args.iterations,
                    )
                else:
                    full_meta = shape_metadata(
                        full_counts,
                        hidden=hidden,
                        inter_per_tp=inter_per_tp,
                        stage=stage,
                    )
                    full_timings = []
                full_result = {
                    "plan_index": plan_index,
                    "plan_path": args.route_plan_json[plan_index],
                    "route_start_index": window["route_start_index"],
                    "mode": "exact_full",
                    "stage": stage,
                    **full_meta,
                    **summarize(full_timings),
                }
                stage_results.append(full_result)

                one_launch_rank_results = []
                two_launch_rank_results = []
                for rank_item in rank_vectors:
                    rank = rank_item["rank"]
                    if gpu_enabled:
                        combined_meta, combined_timings = run_gpu_case(
                            counts=rank_item["combined_counts"],
                            stage=stage,
                            hidden=hidden,
                            inter_per_tp=inter_per_tp,
                            dtype_name=args.dtype,
                            device=args.device,
                            seed=args.seed + plan_index * 10000 + window_index * 101 + rank * 17 + 100000,
                            warmup=args.warmup,
                            iterations=args.iterations,
                        )
                        hot_meta, hot_timings = run_gpu_case(
                            counts=rank_item["hot_counts"],
                            stage=stage,
                            hidden=hidden,
                            inter_per_tp=inter_per_tp,
                            dtype_name=args.dtype,
                            device=args.device,
                            seed=args.seed + plan_index * 10000 + window_index * 101 + rank * 17 + 200000,
                            warmup=args.warmup,
                            iterations=args.iterations,
                        )
                        cold_meta, cold_timings = run_gpu_case(
                            counts=rank_item["cold_counts"],
                            stage=stage,
                            hidden=hidden,
                            inter_per_tp=inter_per_tp,
                            dtype_name=args.dtype,
                            device=args.device,
                            seed=args.seed + plan_index * 10000 + window_index * 101 + rank * 17 + 300000,
                            warmup=args.warmup,
                            iterations=args.iterations,
                        )
                    else:
                        combined_meta = shape_metadata(
                            rank_item["combined_counts"],
                            hidden=hidden,
                            inter_per_tp=inter_per_tp,
                            stage=stage,
                        )
                        hot_meta = shape_metadata(
                            rank_item["hot_counts"],
                            hidden=hidden,
                            inter_per_tp=inter_per_tp,
                            stage=stage,
                        )
                        cold_meta = shape_metadata(
                            rank_item["cold_counts"],
                            hidden=hidden,
                            inter_per_tp=inter_per_tp,
                            stage=stage,
                        )
                        combined_timings = []
                        hot_timings = []
                        cold_timings = []
                    one_launch_rank_results.append({
                        "rank": rank,
                        **combined_meta,
                        **summarize(combined_timings),
                    })
                    two_launch_rank_results.append({
                        "rank": rank,
                        "hot": {**hot_meta, **summarize(hot_timings)},
                        "cold": {**cold_meta, **summarize(cold_timings)},
                        "rank_sum_mean_us": (
                            summarize(hot_timings)["mean_us"] +
                            summarize(cold_timings)["mean_us"]
                            if hot_timings or cold_timings else math.nan
                        ),
                    })

                one_rank_means = [item["mean_us"] for item in one_launch_rank_results if not math.isnan(item["mean_us"])]
                two_rank_means = [item["rank_sum_mean_us"] for item in two_launch_rank_results if not math.isnan(item["rank_sum_mean_us"])]
                stage_results.append({
                    "plan_index": plan_index,
                    "plan_path": args.route_plan_json[plan_index],
                    "route_start_index": window["route_start_index"],
                    "mode": "hotrep_one_launch_rankmax",
                    "stage": stage,
                    "rank_results": one_launch_rank_results,
                    "mean_us": max(one_rank_means) if one_rank_means else math.nan,
                    "rank_mean_us_values": one_rank_means,
                })
                stage_results.append({
                    "plan_index": plan_index,
                    "plan_path": args.route_plan_json[plan_index],
                    "route_start_index": window["route_start_index"],
                    "mode": "hotrep_two_launch_rankmax",
                    "stage": stage,
                    "rank_results": two_launch_rank_results,
                    "mean_us": max(two_rank_means) if two_rank_means else math.nan,
                    "rank_mean_us_values": two_rank_means,
                })

    by_case: dict[tuple[int, str, str], dict[str, Any]] = {}
    for row in stage_results:
        key = (int(row["plan_index"]), str(row["route_start_index"]), str(row["mode"]))
        item = by_case.setdefault(key, {
            "plan_index": row["plan_index"],
            "plan_path": row["plan_path"],
            "route_start_index": row["route_start_index"],
            "mode": row["mode"],
            "stage_mean_us": {},
        })
        item["stage_mean_us"][row["stage"]] = row["mean_us"]
    for item in by_case.values():
        if "gemm1" in item["stage_mean_us"] and "gemm2" in item["stage_mean_us"]:
            item["total_mean_us"] = item["stage_mean_us"]["gemm1"] + item["stage_mean_us"]["gemm2"]
        else:
            item["total_mean_us"] = next(iter(item["stage_mean_us"].values()))
        case_results.append(item)

    aggregate: dict[str, dict[str, Any]] = {}
    for item in case_results:
        bucket = aggregate.setdefault(item["mode"], {
            "mode": item["mode"],
            "total_cases": 0,
            "total_mean_us": [],
        })
        bucket["total_cases"] += 1
        if not math.isnan(item["total_mean_us"]):
            bucket["total_mean_us"].append(item["total_mean_us"])
    aggregate_rows = []
    for mode, item in sorted(aggregate.items()):
        aggregate_rows.append({
            "mode": mode,
            "cases": item["total_cases"],
            "timed_cases": len(item["total_mean_us"]),
            "total_mean_us": summarize(item["total_mean_us"]),
        })

    return {
        "metadata": {
            "route_plan_json": args.route_plan_json,
            "model_config": args.model_config,
            "tp_size": args.tp_size,
            "hidden_size": hidden,
            "intermediate_per_tp": inter_per_tp,
            "num_experts": num_experts,
            "device": args.device,
            "dry_run": args.dry_run,
            "warmup": args.warmup,
            "iterations": args.iterations,
            "gemm_stage": args.gemm_stage,
        },
        "stage_results": stage_results,
        "case_results": sorted(case_results, key=lambda item: (item["plan_index"], item["route_start_index"], item["mode"])),
        "aggregate": aggregate_rows,
        "shape_aggregate": shape_aggregate(stage_results),
    }


def write_markdown(path: str, result: dict[str, Any]) -> None:
    lines = []
    lines.append("# Qwen3.6 Hotrep Route-Plan Grouped-GEMM Screen")
    lines.append("")
    meta = result["metadata"]
    lines.append(f"Dry run: `{meta['dry_run']}`")
    lines.append(f"Inputs: `{', '.join(meta['route_plan_json'])}`")
    lines.append("")
    lines.append("## Timing Aggregate")
    lines.append("")
    lines.append("| mode | cases | timed cases | total mean us | p95 us | min us | max us |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for row in result["aggregate"]:
        total = row["total_mean_us"]
        lines.append(
            f"| `{row['mode']}` | {row['cases']} | {row['timed_cases']} | "
            f"{total['mean_us']:.3f} | {total['p95_us']:.3f} | "
            f"{total['min_us']:.3f} | {total['max_us']:.3f} |"
        )
    lines.append("")
    lines.append("## Shape Aggregate")
    lines.append("")
    lines.append(
        "| mode | stage | cases | rows mean/max | experts mean/max | "
        "active experts mean/max | max alloc MiB |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for row in result.get("shape_aggregate", []):
        lines.append(
            f"| `{row['mode']}` | `{row['stage']}` | {row['cases']} | "
            f"{row['rows']['mean']:.1f}/{row['rows']['max']:.0f} | "
            f"{row['experts']['mean']:.1f}/{row['experts']['max']:.0f} | "
            f"{row['active_experts']['mean']:.1f}/{row['active_experts']['max']:.0f} | "
            f"{row['allocated_mib_estimate']['max']:.2f} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    if meta["dry_run"]:
        lines.append(
            "- This artifact validates shape extraction only. Run without "
            "`--dry-run` in a clean XPU benchmark window to get timings."
        )
        lines.append(
            "- The shape aggregate compares the current full expert table with "
            "the hot-replicated per-rank lower-bound shapes before any endpoint "
            "or kernel change."
        )
    else:
        lines.append(
            "- `hotrep_one_launch_rankmax` is the ideal one-dispatch shape "
            "lower-bound for a per-rank hot+cold table."
        )
        lines.append(
            "- `hotrep_two_launch_rankmax` estimates the launch-tax version. "
            "If it loses while one-launch wins, the implementation needs a "
            "real fused/persistent path."
        )
    lines.append("")
    lines.append("## Timing Command")
    lines.append("")
    timing_cmd = [
        "python3 scripts/bench-qwen36-hotrep-route-plan-gemm.py \\",
        f"  --route-plan-json {' '.join(meta['route_plan_json'])} \\",
        "  --output-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing.json \\",
        "  --markdown-out data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing.md",
    ]
    lines.append("```bash")
    lines.extend(timing_cmd)
    lines.append("```")
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-plan-json", nargs="+", required=True)
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--dtype", choices=["bf16", "fp16"], default="bf16")
    parser.add_argument("--gemm-stage", choices=["gemm1", "gemm2", "both"], default="both")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260612)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out")
    args = parser.parse_args()

    result = evaluate_plan(args)
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.markdown_out:
        write_markdown(args.markdown_out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
