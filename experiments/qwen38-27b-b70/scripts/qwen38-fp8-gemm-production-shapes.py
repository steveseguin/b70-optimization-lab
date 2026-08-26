#!/usr/bin/env python3
"""Time the Qwen3.8 TP2 FP8 GEMMs without claiming endpoint throughput.

This is an attribution microbenchmark.  It uses the block-scale layouts sent by
vLLM to either ``_xpu_C::fp8_gemm`` (W8A8) or
``_xpu_C::fp8_gemm_w8a16`` at concurrency 64 and synchronizes each sample
batch. Results are only comparable when the image, GPU, shapes, kernel,
warmup, and iteration counts are recorded together.
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
import vllm_xpu_kernels._xpu_C  # noqa: F401 - registers torch operators


SHAPES = {
    "attention_qkv": (5120, 4096),
    "mlp_gate_up": (5120, 8704),
    "mlp_down": (8704, 5120),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kernel", choices=("w8a8", "w8a16"), default="w8a8")
    parser.add_argument("--m", type=int, default=64)
    parser.add_argument("--block", type=int, default=128)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assert args.m > 0 and args.block > 0
    assert args.warmup > 0 and args.iterations > 0 and args.repeats >= 3

    device = torch.device("xpu:0")
    dtype = torch.float8_e4m3fn
    torch.manual_seed(20260826)
    rows = []

    for name, (k, n) in SHAPES.items():
        assert k % args.block == 0 and n % args.block == 0
        # Match vLLM's logical layouts: A [M,K] contiguous, checkpoint weight
        # [N,K] contiguous then transposed to an NT [K,N] view, and block
        # scales contiguous as [K/128,N/128].
        a_dtype = dtype if args.kernel == "w8a8" else torch.float16
        a = torch.empty((args.m, k), dtype=a_dtype, device=device).fill_(0.5)
        weight_nk = torch.empty((n, k), dtype=dtype, device=device).fill_(0.25)
        b = weight_nk.t()
        a_scale = torch.ones(
            (args.m, k // args.block), dtype=torch.float32, device=device
        )
        b_scale = torch.ones(
            (k // args.block, n // args.block),
            dtype=torch.float32,
            device=device,
        )

        if args.kernel == "w8a8":

            def invoke() -> torch.Tensor:
                return torch.ops._xpu_C.fp8_gemm(
                    a, b, torch.float16, a_scale, b_scale, None
                )

        else:

            def invoke() -> torch.Tensor:
                return torch.ops._xpu_C.fp8_gemm_w8a16(
                    a, b, b_scale, None
                )

        reference = invoke()
        for _ in range(args.warmup - 1):
            invoke()
        torch.xpu.synchronize()

        samples_us = []
        output_identical = True
        for _ in range(args.repeats):
            start = time.perf_counter_ns()
            last = None
            for _ in range(args.iterations):
                last = invoke()
            torch.xpu.synchronize()
            elapsed_ns = time.perf_counter_ns() - start
            samples_us.append(elapsed_ns / args.iterations / 1000.0)
            output_identical = output_identical and torch.equal(last, reference)

        rows.append(
            {
                "name": name,
                "kernel": args.kernel,
                "m": args.m,
                "k": k,
                "n": n,
                "samples_us": samples_us,
                "median_us": statistics.median(samples_us),
                "min_us": min(samples_us),
                "max_us": max(samples_us),
                "output_identical_within_run": output_identical,
                "a_contiguous": a.is_contiguous(),
                "b_contiguous": b.is_contiguous(),
                "b_stride": list(b.stride()),
                "a_scale_shape": list(a_scale.shape),
                "b_scale_shape": list(b_scale.shape),
            }
        )
        del a, weight_nk, b, a_scale, b_scale, reference
        torch.xpu.empty_cache()

    payload = {
        "kind": "attribution_microbenchmark_not_endpoint_throughput",
        "kernel": args.kernel,
        "image": os.environ.get("BENCH_IMAGE", "unknown"),
        "torch": torch.__version__,
        "kernel_package": importlib.metadata.version("vllm-xpu-kernels"),
        "device": torch.xpu.get_device_name(0),
        "warmup": args.warmup,
        "iterations_per_repeat": args.iterations,
        "repeats": args.repeats,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
