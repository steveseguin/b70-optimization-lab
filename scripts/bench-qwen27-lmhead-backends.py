#!/usr/bin/env python3
"""Microbench Qwen27 INT8 LM-head backend candidates on XPU.

This is diagnostic only. It compares the current oneDNN dense W8A8 path used
by the runtime INT8 LM-head against the existing Xe2 grouped W8A8 kernel forced
into a single-expert dense shape. It does not validate endpoint throughput.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def parse_rows(value: str) -> list[int]:
    rows: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        rows.append(int(part))
    if not rows:
        raise argparse.ArgumentTypeError("expected at least one row count")
    return rows


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = (len(ordered) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def summarize(times: list[float]) -> dict[str, float | int]:
    return {
        "count": len(times),
        "median_ms": statistics.median(times),
        "mean_ms": statistics.mean(times),
        "p10_ms": percentile(times, 0.10),
        "p90_ms": percentile(times, 0.90),
        "min_ms": min(times),
        "max_ms": max(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0.0,
    }


def bench(
    *,
    name: str,
    fn: Callable[[], Any],
    torch: Any,
    warmup: int,
    iterations: int,
) -> dict[str, Any]:
    try:
        for _ in range(warmup):
            fn()
        torch.xpu.synchronize()
        times: list[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            fn()
            torch.xpu.synchronize()
            times.append((time.perf_counter() - t0) * 1000.0)
        return {"name": name, **summarize(times)}
    except Exception as exc:  # noqa: BLE001 - record kernel incompatibility.
        return {"name": name, "error": repr(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=parse_rows, default=parse_rows("1,2,3,4"))
    parser.add_argument("--hidden", type=int, default=5120)
    parser.add_argument("--vocab", type=int, default=248320)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--output-json")
    args = parser.parse_args()

    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if args.device.startswith("xpu"):
        torch.xpu.set_device(0)

    output: dict[str, Any] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Diagnostic LM-head backend microbench for Qwen27 runtime INT8 "
            "LM-head. Not a headline endpoint throughput result."
        ),
        "torch": torch.__version__,
        "op_library": getattr(vllm_xpu_kernels._xpu_C, "__file__", None),
        "env": {
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "SYCL_CACHE_PERSISTENT": os.environ.get("SYCL_CACHE_PERSISTENT"),
        },
        "shape": {
            "hidden": args.hidden,
            "vocab": args.vocab,
            "rows": args.rows,
        },
        "warmup": args.warmup,
        "iterations": args.iterations,
        "results": [],
    }

    for rows in args.rows:
        generator = torch.Generator(device=args.device)
        generator.manual_seed(args.seed + rows)
        hidden_q = torch.randint(
            -127,
            128,
            (rows, args.hidden),
            device=args.device,
            generator=generator,
            dtype=torch.int8,
        ).contiguous()
        hidden_scales = (
            torch.rand(
                (rows, 1),
                device=args.device,
                generator=generator,
                dtype=torch.float32,
            ) * 0.02 + 0.001
        ).contiguous()
        weight = torch.randint(
            -127,
            128,
            (args.hidden, args.vocab),
            device=args.device,
            generator=generator,
            dtype=torch.int8,
        ).contiguous()
        weight_scales_f32 = (
            torch.rand(
                (args.vocab,),
                device=args.device,
                generator=generator,
                dtype=torch.float32,
            ) * 0.02 + 0.001
        ).contiguous()
        weight_scales_bf16 = weight_scales_f32.to(torch.bfloat16).contiguous()
        grouped_weight = weight.view(1, args.hidden, args.vocab)
        rows_per_expert = torch.tensor([rows], device=args.device, dtype=torch.int32)
        grouped_output = torch.empty(
            (rows, args.vocab), device=args.device, dtype=torch.bfloat16)

        def one_dnn_bf16_scale():
            return torch.ops._xpu_C.int8_gemm_w8a8(
                hidden_q,
                hidden_scales,
                weight,
                weight_scales_bf16,
                torch.bfloat16,
                None,
            )

        def one_dnn_f32_scale():
            return torch.ops._xpu_C.int8_gemm_w8a8(
                hidden_q,
                hidden_scales,
                weight,
                weight_scales_f32,
                torch.bfloat16,
                None,
            )

        def grouped_bf16_scale():
            torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
                hidden_q,
                hidden_scales.view(-1),
                grouped_weight,
                weight_scales_bf16.view(1, args.vocab),
                None,
                grouped_output,
                rows_per_expert,
                args.vocab,
                args.hidden,
                1,
            )
            return grouped_output

        def grouped_f32_scale():
            torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_interface(
                hidden_q,
                hidden_scales.view(-1),
                grouped_weight,
                weight_scales_f32.view(1, args.vocab),
                None,
                grouped_output,
                rows_per_expert,
                args.vocab,
                args.hidden,
                1,
            )
            return grouped_output

        row_result = {
            "rows": rows,
            "backends": [
                bench(
                    name="onednn_int8_gemm_w8a8_bf16scale",
                    fn=one_dnn_bf16_scale,
                    torch=torch,
                    warmup=args.warmup,
                    iterations=args.iterations,
                ),
                bench(
                    name="onednn_int8_gemm_w8a8_f32scale",
                    fn=one_dnn_f32_scale,
                    torch=torch,
                    warmup=args.warmup,
                    iterations=args.iterations,
                ),
                bench(
                    name="xe2_grouped_w8a8_singleexpert_bf16scale",
                    fn=grouped_bf16_scale,
                    torch=torch,
                    warmup=args.warmup,
                    iterations=args.iterations,
                ),
                bench(
                    name="xe2_grouped_w8a8_singleexpert_f32scale",
                    fn=grouped_f32_scale,
                    torch=torch,
                    warmup=args.warmup,
                    iterations=args.iterations,
                ),
            ],
        }
        output["results"].append(row_result)
        print(json.dumps(row_result, indent=2))

    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
