#!/usr/bin/env python3
"""Route-exact W8A8 grouped-GEMM benchmark for Qwen3.6 A3B on XPU.

This is a narrow kernel harness. It replays captured MoE route distributions
against the local `cutlass_grouped_gemm_w8a8_int8_interface` op, without the
rest of the vLLM server or full fused-MoE Python path. Use it for kernel-policy
A/Bs before spending time on endpoint restarts.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
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
        if ":" in item:
            parts = item.split(":")
            if len(parts) not in (2, 3):
                raise argparse.ArgumentTypeError(
                    f"Bad range {item!r}; expected start:stop[:step]")
            start = int(parts[0])
            stop = int(parts[1])
            step = int(parts[2]) if len(parts) == 3 else 1
            if step == 0:
                raise argparse.ArgumentTypeError("range step cannot be zero")
            out.extend(range(start, stop, step))
        else:
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


def load_route_records(
    path: str,
    *,
    layer_regex: str | None,
    stage_regex: str | None,
    min_num_tokens: int | None,
    max_num_tokens: int | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    layer_pattern = re.compile(layer_regex) if layer_regex else None
    stage_pattern = re.compile(stage_regex) if stage_regex else None
    records: list[dict[str, Any]] = []
    loaded = 0
    skipped = 0

    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            loaded += 1
            record = json.loads(line)
            layer = str(record.get("layer") or "")
            stage = str(record.get("stage") or "")
            num_tokens = int(record.get("num_tokens") or 0)
            if layer_pattern and not layer_pattern.search(layer):
                skipped += 1
                continue
            if stage_pattern and not stage_pattern.search(stage):
                skipped += 1
                continue
            if min_num_tokens is not None and num_tokens < min_num_tokens:
                skipped += 1
                continue
            if max_num_tokens is not None and num_tokens > max_num_tokens:
                skipped += 1
                continue
            counts = record.get("counts")
            if not isinstance(counts, list):
                skipped += 1
                continue
            records.append(record)

    if not records:
        raise ValueError(f"No route records matched filters in {path}")

    layers: dict[str, int] = {}
    calls: dict[str, int] = {}
    active_experts: list[int] = []
    total_assignments = 0
    for record in records:
        layer = str(record.get("layer") or "")
        layers[layer] = layers.get(layer, 0) + 1
        call = str(record.get("call") or "")
        calls[call] = calls.get(call, 0) + 1
        counts = [int(item) for item in record["counts"]]
        active_experts.append(sum(1 for count in counts if count > 0))
        total_assignments += sum(counts)

    metadata = {
        "route_jsonl": path,
        "records_loaded": loaded,
        "records_matched": len(records),
        "records_skipped": skipped,
        "layers": dict(sorted(layers.items())),
        "unique_calls": len(calls),
        "active_experts_min": min(active_experts),
        "active_experts_max": max(active_experts),
        "active_experts_mean": sum(active_experts) / len(active_experts),
        "total_assignments": total_assignments,
    }
    return records, metadata


def aggregate_window(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("Cannot aggregate an empty route window")
    num_experts = int(records[0].get("num_experts") or len(records[0]["counts"]))
    counts = [0] * num_experts
    layers: dict[str, int] = {}
    calls: dict[str, int] = {}
    for record in records:
        record_counts = [int(item) for item in record["counts"]]
        if len(record_counts) != num_experts:
            raise ValueError("Route window mixes different expert counts")
        for idx, value in enumerate(record_counts):
            counts[idx] += value
        layer = str(record.get("layer") or "")
        layers[layer] = layers.get(layer, 0) + 1
        call = str(record.get("call") or "")
        calls[call] = calls.get(call, 0) + 1
    return {
        "counts": counts,
        "layers": dict(sorted(layers.items())),
        "calls": dict(sorted(calls.items())),
        "records": len(records),
        "first_call": records[0].get("call"),
        "first_layer": records[0].get("layer"),
    }


def compact_counts(counts: list[int]) -> tuple[list[int], dict[str, Any]]:
    active = [(idx, count) for idx, count in enumerate(counts) if count > 0]
    compact = [count for _, count in active]
    metadata = {
        "logical_to_compact": [
            {"logical_expert": logical, "compact_expert": pos, "rows": count}
            for pos, (logical, count) in enumerate(active)
        ],
        "dropped_inactive_experts": len(counts) - len(active),
    }
    return compact, metadata


def select_windows(
    records: list[dict[str, Any]],
    *,
    start_indices: list[int],
    window_size: int,
    max_cases: int | None,
) -> list[dict[str, Any]]:
    windows = []
    for start in start_indices:
        if start < 0:
            raise ValueError(f"Negative start index {start}")
        if start >= len(records):
            continue
        window_records = records[start:start + window_size]
        if len(window_records) < window_size:
            continue
        aggregate = aggregate_window(window_records)
        aggregate["route_start_index"] = start
        aggregate["route_window_size"] = window_size
        windows.append(aggregate)
        if max_cases is not None and len(windows) >= max_cases:
            break
    if not windows:
        raise ValueError("No route windows selected")
    return windows


def tensor_bytes(shape: tuple[int, ...], element_size: int) -> int:
    total = 1
    for dim in shape:
        total *= dim
    return total * element_size


def format_mib(value: int) -> float:
    return value / (1024.0 * 1024.0)


def mean(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    lower = math.floor(idx)
    upper = math.ceil(idx)
    if lower == upper:
        return ordered[int(idx)]
    frac = idx - lower
    return ordered[lower] * (1.0 - frac) + ordered[upper] * frac


def summarize_timings(values: list[float]) -> dict[str, Any]:
    return {
        "mean_us": mean(values),
        "median_us": statistics.median(values) if values else math.nan,
        "p05_us": percentile(values, 0.05),
        "p95_us": percentile(values, 0.95),
        "min_us": min(values) if values else math.nan,
        "max_us": max(values) if values else math.nan,
        "stdev_us": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "samples": len(values),
    }


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    torch.manual_seed(args.seed)
    text_config = load_text_config(args.model_config)
    hidden_size = int(text_config["hidden_size"])
    inter_size = int(text_config["moe_intermediate_size"]) // args.tp_size
    full_num_experts = int(text_config["num_experts"])
    dtype = torch.bfloat16 if args.dtype == "bf16" else torch.float16

    records, route_metadata = load_route_records(
        args.route_jsonl,
        layer_regex=args.route_layer_regex,
        stage_regex=args.route_stage_regex,
        min_num_tokens=args.route_min_num_tokens,
        max_num_tokens=args.route_max_num_tokens,
    )
    windows = select_windows(
        records,
        start_indices=args.route_start_indices,
        window_size=args.route_window_size,
        max_cases=args.max_cases,
    )

    def make_events() -> tuple[torch.xpu.Event, torch.xpu.Event]:
        return (
            torch.xpu.Event(enable_timing=True),
            torch.xpu.Event(enable_timing=True),
        )

    def run_one(
        *,
        counts: list[int],
        gemm_stage: str,
        case_seed: int,
    ) -> tuple[dict[str, Any], list[float]]:
        total_rows = sum(counts)
        active_experts = sum(1 for count in counts if count > 0)
        num_experts = len(counts)
        if total_rows <= 0:
            raise ValueError("Route case has zero rows")

        if gemm_stage == "gemm1":
            k_dim = hidden_size
            n_dim = 2 * inter_size
        elif gemm_stage == "gemm2":
            k_dim = inter_size
            n_dim = hidden_size
        else:
            raise ValueError(f"Unknown gemm stage {gemm_stage}")

        generator = torch.Generator(device=args.device)
        generator.manual_seed(case_seed)
        ptr_a = torch.randint(
            -127,
            128,
            (total_rows, k_dim),
            generator=generator,
            device=args.device,
            dtype=torch.int8,
        ).contiguous()
        ptr_a_scales = (
            torch.rand(
                (total_rows,),
                generator=generator,
                device=args.device,
                dtype=torch.float32,
            ) * 0.02 + 0.001
        ).contiguous()
        ptr_b = torch.randint(
            -127,
            128,
            (num_experts, k_dim, n_dim),
            generator=generator,
            device=args.device,
            dtype=torch.int8,
        ).contiguous()
        ptr_b_scales = (
            torch.rand(
                (num_experts, n_dim),
                generator=generator,
                device=args.device,
                dtype=torch.float32,
            ) * 0.02 + 0.001
        ).contiguous()
        ptr_d = torch.empty(
            (total_rows, n_dim),
            device=args.device,
            dtype=dtype,
        )
        rows_per_expert = torch.tensor(
            counts,
            device=args.device,
            dtype=torch.int32,
        )

        def op() -> None:
            torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
                ptr_A=ptr_a,
                ptr_A_scales=ptr_a_scales,
                ptr_B=ptr_b,
                ptr_B_scales=ptr_b_scales,
                ptr_bias=None,
                ptr_D=ptr_d,
                rows_per_expert=rows_per_expert,
                N=n_dim,
                K=k_dim,
                num_experts=num_experts,
            )

        for _ in range(args.warmup):
            op()
        torch.xpu.synchronize()

        timings = []
        for _ in range(args.iterations):
            start, end = make_events()
            start.record()
            op()
            end.record()
            torch.xpu.synchronize()
            timings.append(float(start.elapsed_time(end) * 1000.0))

        finite = bool(torch.isfinite(ptr_d.float()).all().item())
        max_abs = float(ptr_d.float().abs().max().item())
        allocated_bytes = (
            tensor_bytes(tuple(ptr_a.shape), ptr_a.element_size()) +
            tensor_bytes(tuple(ptr_a_scales.shape), ptr_a_scales.element_size()) +
            tensor_bytes(tuple(ptr_b.shape), ptr_b.element_size()) +
            tensor_bytes(tuple(ptr_b_scales.shape), ptr_b_scales.element_size()) +
            tensor_bytes(tuple(ptr_d.shape), ptr_d.element_size()) +
            tensor_bytes(tuple(rows_per_expert.shape), rows_per_expert.element_size())
        )
        metadata = {
            "gemm_stage": gemm_stage,
            "num_experts": num_experts,
            "active_experts": active_experts,
            "total_rows": total_rows,
            "k": k_dim,
            "n": n_dim,
            "dtype": args.dtype,
            "allocated_mib_estimate": format_mib(allocated_bytes),
            "output_all_finite": finite,
            "output_max_abs": max_abs,
        }
        return metadata, timings

    case_results: list[dict[str, Any]] = []
    compact_metadata: list[dict[str, Any]] = []
    gemm_stages = ["gemm1", "gemm2"] if args.gemm_stage == "both" else [args.gemm_stage]
    modes = ["exact"]
    if args.compact_active_experts:
        modes.append("compact_active")

    for case_idx, window in enumerate(windows):
        base_counts = [int(item) for item in window["counts"]]
        if len(base_counts) != full_num_experts:
            raise ValueError(
                f"Expected {full_num_experts} experts, got {len(base_counts)}")
        for mode in modes:
            if mode == "exact":
                counts = base_counts
                compaction = None
            else:
                counts, compaction = compact_counts(base_counts)
                compact_metadata.append({
                    "case_index": case_idx,
                    "route_start_index": window["route_start_index"],
                    "route_window_size": window["route_window_size"],
                    **(compaction or {}),
                })
            for gemm_stage in gemm_stages:
                metadata, timings = run_one(
                    counts=counts,
                    gemm_stage=gemm_stage,
                    case_seed=args.seed + case_idx * 17 +
                    (0 if gemm_stage == "gemm1" else 100000) +
                    (0 if mode == "exact" else 200000),
                )
                case_results.append({
                    "case_index": case_idx,
                    "mode": mode,
                    "route_start_index": window["route_start_index"],
                    "route_window_size": window["route_window_size"],
                    "first_call": window["first_call"],
                    "first_layer": window["first_layer"],
                    "layers": window["layers"],
                    "calls": window["calls"],
                    **metadata,
                    **summarize_timings(timings),
                })

    aggregates: dict[str, dict[str, Any]] = {}
    for result in case_results:
        key = "|".join([
            str(result["mode"]),
            str(result["gemm_stage"]),
            str(result["route_window_size"]),
            str(result["num_experts"]),
        ])
        bucket = aggregates.setdefault(key, {
            "mode": result["mode"],
            "gemm_stage": result["gemm_stage"],
            "route_window_size": result["route_window_size"],
            "num_experts": result["num_experts"],
            "case_count": 0,
            "means_us": [],
            "active_experts": [],
            "total_rows": [],
        })
        bucket["case_count"] += 1
        bucket["means_us"].append(result["mean_us"])
        bucket["active_experts"].append(result["active_experts"])
        bucket["total_rows"].append(result["total_rows"])
    aggregate_results = []
    for bucket in aggregates.values():
        means = bucket.pop("means_us")
        active_values = bucket.pop("active_experts")
        row_values = bucket.pop("total_rows")
        aggregate_results.append({
            **bucket,
            "mean_of_case_means_us": mean(means),
            "median_of_case_means_us": statistics.median(means),
            "min_case_mean_us": min(means),
            "max_case_mean_us": max(means),
            "active_experts_min": min(active_values),
            "active_experts_max": max(active_values),
            "active_experts_mean": mean(active_values),
            "total_rows_min": min(row_values),
            "total_rows_max": max(row_values),
            "total_rows_mean": mean(row_values),
        })

    return {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "purpose": (
            "Route-exact W8A8 grouped-GEMM harness for Qwen3.6 A3B "
            "kernel-policy A/Bs."
        ),
        "model_config": args.model_config,
        "tp_size": args.tp_size,
        "hidden_size": hidden_size,
        "inter_size_per_tp": inter_size,
        "full_num_experts": full_num_experts,
        "device": args.device,
        "env": {
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
        },
        "torch_version": torch.__version__,
        "kernel_module": getattr(vllm_xpu_kernels._xpu_C, "__file__", None),
        "route_metadata": route_metadata,
        "args": {
            "route_layer_regex": args.route_layer_regex,
            "route_stage_regex": args.route_stage_regex,
            "route_min_num_tokens": args.route_min_num_tokens,
            "route_max_num_tokens": args.route_max_num_tokens,
            "route_start_indices": args.route_start_indices,
            "route_window_size": args.route_window_size,
            "max_cases": args.max_cases,
            "gemm_stage": args.gemm_stage,
            "compact_active_experts": args.compact_active_experts,
            "warmup": args.warmup,
            "iterations": args.iterations,
            "seed": args.seed,
        },
        "compact_metadata": compact_metadata,
        "aggregates": sorted(
            aggregate_results,
            key=lambda item: (
                item["mode"],
                item["gemm_stage"],
                item["route_window_size"],
                item["num_experts"],
            ),
        ),
        "cases": case_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--route-jsonl", required=True)
    parser.add_argument("--route-layer-regex")
    parser.add_argument("--route-stage-regex", default="^quark_int8_apply$")
    parser.add_argument("--route-min-num-tokens", type=int, default=1)
    parser.add_argument("--route-max-num-tokens", type=int, default=1)
    parser.add_argument(
        "--route-start-indices",
        type=parse_int_list,
        default=parse_int_list("0:96:12"),
    )
    parser.add_argument("--route-window-size", type=int, default=1)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument(
        "--gemm-stage",
        choices=("gemm1", "gemm2", "both"),
        default="both",
    )
    parser.add_argument("--compact-active-experts", action="store_true")
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260611)
    parser.add_argument("--output-json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse route windows and print metadata without importing torch.",
    )
    return parser.parse_args()


def dry_run(args: argparse.Namespace) -> dict[str, Any]:
    text_config = load_text_config(args.model_config)
    records, route_metadata = load_route_records(
        args.route_jsonl,
        layer_regex=args.route_layer_regex,
        stage_regex=args.route_stage_regex,
        min_num_tokens=args.route_min_num_tokens,
        max_num_tokens=args.route_max_num_tokens,
    )
    windows = select_windows(
        records,
        start_indices=args.route_start_indices,
        window_size=args.route_window_size,
        max_cases=args.max_cases,
    )
    summaries = []
    for idx, window in enumerate(windows):
        counts = [int(item) for item in window["counts"]]
        compact, _ = compact_counts(counts)
        summaries.append({
            "case_index": idx,
            "route_start_index": window["route_start_index"],
            "route_window_size": window["route_window_size"],
            "first_call": window["first_call"],
            "first_layer": window["first_layer"],
            "active_experts": sum(1 for count in counts if count > 0),
            "total_rows": sum(counts),
            "compact_active_experts": len(compact),
            "layers": window["layers"],
            "calls": window["calls"],
        })
    return {
        "model_config": args.model_config,
        "hidden_size": int(text_config["hidden_size"]),
        "inter_size_per_tp": int(text_config["moe_intermediate_size"]) //
        args.tp_size,
        "full_num_experts": int(text_config["num_experts"]),
        "route_metadata": route_metadata,
        "selected_windows": summaries,
    }


def main() -> int:
    args = parse_args()
    result = dry_run(args) if args.dry_run else run_benchmark(args)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
