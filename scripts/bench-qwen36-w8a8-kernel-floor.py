#!/usr/bin/env python3
"""Benchmark W8A8 tiny-shape floors for Qwen3.6 A3B decode on XPU.

This compares the current grouped-GEMM W8A8 path with dense W8A8 and
quantization kernels on route-captured decode shapes. It is a diagnostic for
where the next exact-preserving optimization should go; it is not an endpoint
throughput benchmark.
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
    values: list[int] = []
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
            values.extend(range(start, stop, step))
        else:
            values.append(int(item))
    if not values:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return values


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
            if not isinstance(record.get("counts"), list):
                skipped += 1
                continue
            records.append(record)

    if not records:
        raise ValueError(f"No route records matched filters in {path}")

    layers: dict[str, int] = {}
    for record in records:
        layer = str(record.get("layer") or "")
        layers[layer] = layers.get(layer, 0) + 1
    return records, {
        "route_jsonl": path,
        "records_loaded": loaded,
        "records_matched": len(records),
        "records_skipped": skipped,
        "layers": dict(sorted(layers.items())),
    }


def aggregate_counts(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("empty route window")
    num_experts = int(records[0].get("num_experts") or len(records[0]["counts"]))
    counts = [0] * num_experts
    layers: dict[str, int] = {}
    calls: dict[str, int] = {}
    for record in records:
        record_counts = [int(item) for item in record["counts"]]
        if len(record_counts) != num_experts:
            raise ValueError("mixed expert counts in route window")
        for idx, count in enumerate(record_counts):
            counts[idx] += count
        layer = str(record.get("layer") or "")
        layers[layer] = layers.get(layer, 0) + 1
        call = str(record.get("call") or "")
        calls[call] = calls.get(call, 0) + 1
    return {
        "counts": counts,
        "layers": dict(sorted(layers.items())),
        "calls": dict(sorted(calls.items())),
        "first_layer": records[0].get("layer"),
        "first_call": records[0].get("call"),
    }


def select_cases(
    records: list[dict[str, Any]],
    *,
    starts: list[int],
    window_size: int,
    max_cases: int | None,
) -> list[dict[str, Any]]:
    cases = []
    for start in starts:
        if start < 0 or start >= len(records):
            continue
        window = records[start:start + window_size]
        if len(window) != window_size:
            continue
        case = aggregate_counts(window)
        case["route_start_index"] = start
        case["route_window_size"] = window_size
        cases.append(case)
        if max_cases is not None and len(cases) >= max_cases:
            break
    if not cases:
        raise ValueError("No route cases selected")
    return cases


def active_counts(counts: list[int]) -> list[tuple[int, int]]:
    return [(idx, count) for idx, count in enumerate(counts) if count > 0]


def mean(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return ordered[int(idx)]
    frac = idx - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def summarize(values: list[float]) -> dict[str, Any]:
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
    num_experts = int(text_config["num_experts"])
    dtype = torch.bfloat16 if args.dtype == "bf16" else torch.float16
    records, route_metadata = load_route_records(
        args.route_jsonl,
        layer_regex=args.route_layer_regex,
        stage_regex=args.route_stage_regex,
        min_num_tokens=args.route_min_num_tokens,
        max_num_tokens=args.route_max_num_tokens,
    )
    cases = select_cases(
        records,
        starts=args.route_start_indices,
        window_size=args.route_window_size,
        max_cases=args.max_cases,
    )

    def make_events() -> tuple[torch.xpu.Event, torch.xpu.Event]:
        return (
            torch.xpu.Event(enable_timing=True),
            torch.xpu.Event(enable_timing=True),
        )

    def timed(label: str, fn) -> dict[str, Any]:
        for _ in range(args.warmup):
            fn()
        torch.xpu.synchronize()
        samples = []
        for _ in range(args.iterations):
            start, end = make_events()
            start.record()
            out = fn()
            end.record()
            torch.xpu.synchronize()
            samples.append(float(start.elapsed_time(end) * 1000.0))
        result = {"label": label}
        result.update(summarize(samples))
        if out is not None and hasattr(out, "float"):
            result["output_all_finite"] = bool(
                torch.isfinite(out.float()).all().item())
            result["output_max_abs"] = float(out.float().abs().max().item())
        return result

    def make_int8_inputs(total_rows: int, k_dim: int, n_dim: int, seed: int):
        generator = torch.Generator(device=args.device)
        generator.manual_seed(seed)
        a = torch.randint(
            -127,
            128,
            (total_rows, k_dim),
            device=args.device,
            generator=generator,
            dtype=torch.int8,
        ).contiguous()
        a_scale = (
            torch.rand(
                (total_rows, 1),
                device=args.device,
                generator=generator,
                dtype=torch.float32,
            ) * 0.02 + 0.001
        ).contiguous()
        b = torch.randint(
            -127,
            128,
            (num_experts, k_dim, n_dim),
            device=args.device,
            generator=generator,
            dtype=torch.int8,
        ).contiguous()
        b_scale = (
            torch.rand(
                (num_experts, n_dim),
                device=args.device,
                generator=generator,
                dtype=torch.float32,
            ) * 0.02 + 0.001
        ).contiguous()
        return a, a_scale, b, b_scale

    def grouped_op(a, a_scale, b, b_scale, counts, n_dim, k_dim):
        d = torch.empty((a.shape[0], n_dim), device=args.device, dtype=dtype)
        rows_per_expert = torch.tensor(
            counts,
            device=args.device,
            dtype=torch.int32,
        )

        def call():
            torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
                ptr_A=a,
                ptr_A_scales=a_scale.view(-1),
                ptr_B=b,
                ptr_B_scales=b_scale,
                ptr_bias=None,
                ptr_D=d,
                rows_per_expert=rows_per_expert,
                N=n_dim,
                K=k_dim,
                num_experts=len(counts),
            )
            return d

        return call

    def dense_single_op(a, a_scale, b, b_scale):
        # Same M/K/N as grouped, but one dense expert. This measures dense W8A8
        # tiny-shape floor; it is not model-equivalent for routed experts.
        return lambda: torch.ops._xpu_C.int8_gemm_w8a8(
            a,
            a_scale,
            b[0],
            b_scale[0],
            dtype,
            None,
        )

    def dense_active_loop_op(a, a_scale, b, b_scale, active):
        outputs = []
        offset = 0
        for expert, count in active:
            outputs.append((a[offset:offset + count], a_scale[offset:offset + count],
                            b[expert], b_scale[expert]))
            offset += count

        def call():
            last = None
            for sub_a, sub_scale, sub_b, sub_b_scale in outputs:
                last = torch.ops._xpu_C.int8_gemm_w8a8(
                    sub_a,
                    sub_scale,
                    sub_b,
                    sub_b_scale,
                    dtype,
                    None,
                )
            return last

        return call

    results = []
    for case_idx, case in enumerate(cases):
        counts = [int(item) for item in case["counts"]]
        active = active_counts(counts)
        total_rows = sum(counts)
        compact_counts = [count for _, count in active]

        for stage in (["gemm1", "gemm2"] if args.gemm_stage == "both"
                      else [args.gemm_stage]):
            if stage == "gemm1":
                k_dim = hidden_size
                n_dim = 2 * inter_size
            else:
                k_dim = inter_size
                n_dim = hidden_size
            a, a_scale, b, b_scale = make_int8_inputs(
                total_rows,
                k_dim,
                n_dim,
                args.seed + case_idx * 1009 + (0 if stage == "gemm1" else 19),
            )

            case_prefix = {
                "case_index": case_idx,
                "route_start_index": case["route_start_index"],
                "route_window_size": case["route_window_size"],
                "first_layer": case["first_layer"],
                "first_call": case["first_call"],
                "layers": case["layers"],
                "calls": case["calls"],
                "gemm_stage": stage,
                "k": k_dim,
                "n": n_dim,
                "total_rows": total_rows,
                "active_experts": len(active),
                "full_num_experts": num_experts,
            }

            for bench in (
                    timed(
                        "grouped_exact_256",
                        grouped_op(a, a_scale, b, b_scale, counts, n_dim, k_dim),
                    ),
                    timed(
                        "dense_single_not_model_equivalent",
                        dense_single_op(a, a_scale, b, b_scale),
                    ),
                    timed(
                        "dense_active_loop_model_shape_many_launches",
                        dense_active_loop_op(a, a_scale, b, b_scale, active),
                    ),
            ):
                results.append({**case_prefix, **bench})

            if args.include_compact_grouped:
                compact_b = torch.stack([b[expert] for expert, _ in active]).contiguous()
                compact_b_scale = torch.stack(
                    [b_scale[expert] for expert, _ in active]).contiguous()
                bench = timed(
                    "grouped_compact_active_not_model_equivalent",
                    grouped_op(
                        a,
                        a_scale,
                        compact_b,
                        compact_b_scale,
                        compact_counts,
                        n_dim,
                        k_dim,
                    ),
                )
                results.append({**case_prefix, **bench})

    quant_results = []
    if args.include_quant:
        quant_shapes = [
            ("quant_hidden_rows8", (8, hidden_size)),
            ("quant_hidden_rows24", (24, hidden_size)),
            ("quant_inter_rows8", (8, inter_size)),
            ("quant_inter_rows24", (24, inter_size)),
            ("silu_quant_rows8", (8, 2 * inter_size)),
            ("silu_quant_rows24", (24, 2 * inter_size)),
        ]
        generator = torch.Generator(device=args.device)
        generator.manual_seed(args.seed + 9999)
        for label, shape in quant_shapes:
            x = torch.randn(
                shape,
                device=args.device,
                dtype=dtype,
                generator=generator,
            )
            if label.startswith("silu"):
                fn = lambda x=x: torch.ops._xpu_C.silu_and_mul_quant_int8_xpu(x)[0]
            else:
                fn = lambda x=x: torch.ops._xpu_C.per_token_quant_int8_xpu(x)[0]
            item = timed(label, fn)
            item["shape"] = list(shape)
            quant_results.append(item)

    aggregates: dict[str, dict[str, Any]] = {}
    for item in results:
        key = "|".join([item["label"], item["gemm_stage"],
                        str(item["route_window_size"])])
        bucket = aggregates.setdefault(key, {
            "label": item["label"],
            "gemm_stage": item["gemm_stage"],
            "route_window_size": item["route_window_size"],
            "case_count": 0,
            "means": [],
        })
        bucket["case_count"] += 1
        bucket["means"].append(item["mean_us"])
    aggregate_results = []
    for bucket in aggregates.values():
        means = bucket.pop("means")
        aggregate_results.append({
            **bucket,
            "mean_of_case_means_us": mean(means),
            "median_of_case_means_us": statistics.median(means),
            "min_case_mean_us": min(means),
            "max_case_mean_us": max(means),
        })

    return {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "purpose": "W8A8 tiny-shape floor diagnostic for Qwen3.6 A3B decode.",
        "model_config": args.model_config,
        "device": args.device,
        "dtype": args.dtype,
        "tp_size": args.tp_size,
        "hidden_size": hidden_size,
        "inter_size_per_tp": inter_size,
        "num_experts": num_experts,
        "torch_version": torch.__version__,
        "kernel_module": getattr(vllm_xpu_kernels._xpu_C, "__file__", None),
        "env": {
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "VLLM_XPU_W8A8_GROUPED_GEMM_POLICY": os.environ.get(
                "VLLM_XPU_W8A8_GROUPED_GEMM_POLICY"),
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
        },
        "args": {
            "route_layer_regex": args.route_layer_regex,
            "route_stage_regex": args.route_stage_regex,
            "route_start_indices": args.route_start_indices,
            "route_window_size": args.route_window_size,
            "max_cases": args.max_cases,
            "gemm_stage": args.gemm_stage,
            "warmup": args.warmup,
            "iterations": args.iterations,
            "include_compact_grouped": args.include_compact_grouped,
            "include_quant": args.include_quant,
        },
        "route_metadata": route_metadata,
        "aggregates": sorted(
            aggregate_results,
            key=lambda item: (item["gemm_stage"], item["label"]),
        ),
        "quant_results": quant_results,
        "cases": results,
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
    parser.add_argument("--include-compact-grouped", action="store_true")
    parser.add_argument("--include-quant", action="store_true")
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260611)
    parser.add_argument("--output-json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_benchmark(args)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
