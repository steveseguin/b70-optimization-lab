#!/usr/bin/env python3
"""Attribute Qwen3.8 TP2 output-head latency at the production shape.

This is an operator microbenchmark, not model-throughput evidence. It compares
the checkpoint's BF16 linear with a per-token/per-output-channel W8A8 path for
one TP2 vocabulary shard. A candidate still needs model output and endpoint
gates before it can be promoted.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import statistics
import time
from pathlib import Path

import torch
import torch.nn.functional as F
import vllm_xpu_kernels._xpu_C  # noqa: F401 - registers torch operators


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--m", type=int, default=64)
    parser.add_argument("--k", type=int, default=5120)
    parser.add_argument("--n", type=int, default=124160)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=5)
    return parser.parse_args()


def timed_samples(invoke, warmup: int, iterations: int, repeats: int) -> list[float]:
    for _ in range(warmup):
        invoke()
    torch.xpu.synchronize()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(iterations):
            invoke()
        torch.xpu.synchronize()
        samples.append((time.perf_counter_ns() - start) / iterations / 1000.0)
    return samples


def summarize(samples: list[float]) -> dict[str, object]:
    return {
        "samples_us": samples,
        "median_us": statistics.median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
    }


def main() -> None:
    args = parse_args()
    assert args.m > 0 and args.k > 0 and args.n > 0
    assert args.warmup > 0 and args.iterations > 0 and args.repeats >= 3

    device = torch.device("xpu:0")
    torch.manual_seed(20260826)
    x = torch.randn((args.m, args.k), device=device, dtype=torch.bfloat16)
    weight = (
        torch.randn((args.n, args.k), device=device, dtype=torch.bfloat16) * 0.02
    )

    weight_f = weight.float()
    weight_scale = weight_f.abs().amax(dim=1).clamp_min(1.0e-10) / 127.0
    weight_q_t = (
        torch.round(weight_f / weight_scale[:, None])
        .clamp(-127, 127)
        .to(torch.int8)
        .t()
        .contiguous()
    )
    weight_scale = weight_scale.to(torch.bfloat16).contiguous()
    del weight_f
    torch.xpu.empty_cache()

    def bf16() -> torch.Tensor:
        return F.linear(x, weight)

    def quantize() -> tuple[torch.Tensor, torch.Tensor]:
        return torch.ops._xpu_C.per_token_quant_int8_xpu(x)

    x_q, x_scale = quantize()

    def int8_gemm() -> torch.Tensor:
        return torch.ops._xpu_C.int8_gemm_w8a8(
            x_q,
            x_scale,
            weight_q_t,
            weight_scale,
            torch.bfloat16,
            None,
        )

    def int8_end_to_end() -> torch.Tensor:
        q, scale = quantize()
        return torch.ops._xpu_C.int8_gemm_w8a8(
            q,
            scale,
            weight_q_t,
            weight_scale,
            torch.bfloat16,
            None,
        )

    exact = bf16()
    approximate = int8_gemm()
    error = (exact.float() - approximate.float()).abs()
    exact_argmax = exact.argmax(dim=-1)
    approximate_argmax = approximate.argmax(dim=-1)

    rows = {
        "bf16_linear": summarize(
            timed_samples(bf16, args.warmup, args.iterations, args.repeats)
        ),
        "int8_quantize": summarize(
            timed_samples(quantize, args.warmup, args.iterations, args.repeats)
        ),
        "int8_gemm_prequantized": summarize(
            timed_samples(int8_gemm, args.warmup, args.iterations, args.repeats)
        ),
        "int8_quantize_plus_gemm": summarize(
            timed_samples(
                int8_end_to_end, args.warmup, args.iterations, args.repeats
            )
        ),
    }
    bf16_us = float(rows["bf16_linear"]["median_us"])
    int8_us = float(rows["int8_quantize_plus_gemm"]["median_us"])
    payload = {
        "kind": "attribution_microbenchmark_not_endpoint_throughput",
        "image": os.environ.get("BENCH_IMAGE", "unknown"),
        "kernel_source_commit": os.environ.get("KERNEL_SOURCE_COMMIT", "unknown"),
        "torch": torch.__version__,
        "kernel_package": importlib.metadata.version("vllm-xpu-kernels"),
        "device": torch.xpu.get_device_name(0),
        "shape": {"m": args.m, "k": args.k, "n": args.n},
        "dtype": "bfloat16",
        "warmup": args.warmup,
        "iterations_per_repeat": args.iterations,
        "repeats": args.repeats,
        "rows": rows,
        "int8_speedup_x": bf16_us / int8_us,
        "int8_wall_reduction_percent": (bf16_us - int8_us) / bf16_us * 100.0,
        "synthetic_numerics": {
            "argmax_equal_rows": int((exact_argmax == approximate_argmax).sum()),
            "argmax_total_rows": args.m,
            "mean_abs_error": float(error.mean()),
            "max_abs_error": float(error.max()),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
