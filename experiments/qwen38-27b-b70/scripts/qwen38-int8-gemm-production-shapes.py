#!/usr/bin/env python3
"""Time W8A8 GEMMs at the Qwen3.8 TP2 decode shapes.

This is an attribution microbenchmark, not endpoint or quality evidence. The
checkpoint uses block-scaled FP8 for these layers; this script asks whether a
per-output-channel INT8 weight plus per-token INT8 activation is fast enough to
justify a separately gated model-body experiment.
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
    parser.add_argument("--m", type=int, default=64)
    parser.add_argument(
        "--dtype", choices=("float16", "bfloat16"), default="float16"
    )
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assert args.m > 0 and args.warmup > 0 and args.iterations > 0
    assert args.repeats >= 3
    device = torch.device("xpu:0")
    dtype = getattr(torch, args.dtype)
    torch.manual_seed(20260826)
    rows = []

    for name, (k, n) in SHAPES.items():
        x = torch.randn((args.m, k), device=device, dtype=dtype)
        weight = torch.randn((n, k), device=device, dtype=dtype) * 0.02
        weight_f = weight.float()
        weight_scale = weight_f.abs().amax(dim=1).clamp_min(1.0e-10) / 127.0
        weight_q_t = (
            torch.round(weight_f / weight_scale[:, None])
            .clamp(-127, 127)
            .to(torch.int8)
            .t()
            .contiguous()
        )
        weight_scale = weight_scale.to(dtype).contiguous()
        del weight_f
        x_q, x_scale = torch.ops._xpu_C.per_token_quant_int8_xpu(x)

        def gemm() -> torch.Tensor:
            return torch.ops._xpu_C.int8_gemm_w8a8(
                x_q,
                x_scale,
                weight_q_t,
                weight_scale,
                dtype,
                None,
            )

        def end_to_end() -> torch.Tensor:
            q, scale = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
            return torch.ops._xpu_C.int8_gemm_w8a8(
                q,
                scale,
                weight_q_t,
                weight_scale,
                dtype,
                None,
            )

        reference = gemm()
        for _ in range(args.warmup - 1):
            end_to_end()
        torch.xpu.synchronize()

        samples_us = []
        output_identical = True
        for _ in range(args.repeats):
            start = time.perf_counter_ns()
            last = None
            for _ in range(args.iterations):
                last = end_to_end()
            torch.xpu.synchronize()
            samples_us.append(
                (time.perf_counter_ns() - start) / args.iterations / 1000.0
            )
            output_identical = output_identical and torch.equal(last, reference)

        rows.append(
            {
                "name": name,
                "m": args.m,
                "k": k,
                "n": n,
                "samples_us": samples_us,
                "median_us": statistics.median(samples_us),
                "min_us": min(samples_us),
                "max_us": max(samples_us),
                "output_identical_within_run": output_identical,
            }
        )
        torch.xpu.empty_cache()

    payload = {
        "kind": "attribution_microbenchmark_not_endpoint_throughput",
        "image": os.environ.get("BENCH_IMAGE", "unknown"),
        "kernel_source_commit": os.environ.get("KERNEL_SOURCE_COMMIT", "unknown"),
        "torch": torch.__version__,
        "kernel_package": importlib.metadata.version("vllm-xpu-kernels"),
        "device": torch.xpu.get_device_name(0),
        "quantization": "per-token activation/per-output-channel weight INT8",
        "dtype": args.dtype,
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
