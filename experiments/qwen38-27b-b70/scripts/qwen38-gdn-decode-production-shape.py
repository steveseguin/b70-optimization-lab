#!/usr/bin/env python3
"""Matched-image microbenchmark for the Qwen3.8 TP2 GDN decode op.

This times the monolithic operator used by the promoted vLLM image.  It is an
operator attribution test, not an endpoint result.  The dimensions come from
the official Qwen3.8-27B config and the batch is the promoted c64 lane.
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assert args.batch > 0 and args.warmup > 0
    assert args.iterations > 0 and args.repeats >= 3
    device = torch.device("xpu:0")
    dtype = torch.bfloat16
    torch.manual_seed(20260826)

    # Official Qwen3.8-27B GDN dimensions, sharded over TP2.
    nk, nv, dk, dv, tp, width = 16, 48, 128, 128, 2, 4
    local_k, local_v = nk // tp, nv // tp
    qkvz_width = local_k * (2 * dk + 2 * dv * nv // nk)
    ba_width = local_k * (2 * nv // nk)
    qkv_width = local_k * (2 * dk + dv * nv // nk)
    cache_batch = max(256, args.batch * 2)

    projected_qkvz = torch.randn(
        (args.batch, qkvz_width), dtype=dtype, device=device
    )
    projected_ba = torch.randn((args.batch, ba_width), dtype=dtype, device=device)
    conv_state = torch.randn(
        (cache_batch, width - 1, qkv_width), dtype=dtype, device=device
    )
    ssm_state = torch.randn(
        (cache_batch, local_v, dv, dk), dtype=dtype, device=device
    )
    conv_weights = torch.randn((qkv_width, width), dtype=dtype, device=device)
    conv_bias = torch.randn((qkv_width,), dtype=dtype, device=device)
    a_log = torch.randn((local_v,), dtype=torch.float32, device=device)
    dt_bias = torch.randn((local_v,), dtype=dtype, device=device)
    query_start = torch.arange(args.batch + 1, dtype=torch.int32, device=device)
    state_indices = torch.arange(args.batch, dtype=torch.int32, device=device)
    has_initial_state = torch.ones(args.batch, dtype=torch.bool, device=device)
    core_out = torch.zeros((args.batch, local_v, dv), dtype=dtype, device=device)
    z = torch.empty_like(core_out)

    def invoke() -> None:
        torch.ops._xpu_C.gdn_attention(
            core_out,
            z,
            projected_qkvz,
            projected_ba,
            nk,
            nv,
            dk,
            dv,
            conv_state,
            ssm_state,
            conv_weights,
            conv_bias,
            "silu",
            a_log,
            dt_bias,
            0,
            args.batch,
            0,
            has_initial_state,
            query_start,
            None,
            state_indices,
            None,
            None,
            None,
            None,
            args.batch,
            tp,
            False,
        )

    for _ in range(args.warmup):
        invoke()
    torch.xpu.synchronize()

    samples_us = []
    for _ in range(args.repeats):
        start = time.perf_counter_ns()
        for _ in range(args.iterations):
            invoke()
        torch.xpu.synchronize()
        samples_us.append(
            (time.perf_counter_ns() - start) / args.iterations / 1000.0
        )

    payload = {
        "kind": "attribution_microbenchmark_not_endpoint_throughput",
        "image": os.environ.get("BENCH_IMAGE", "unknown"),
        "torch": torch.__version__,
        "kernel_package": importlib.metadata.version("vllm-xpu-kernels"),
        "device": torch.xpu.get_device_name(0),
        "shape": {
            "batch": args.batch,
            "num_k_heads": nk,
            "num_v_heads": nv,
            "head_k_dim": dk,
            "head_v_dim": dv,
            "tp_size": tp,
            "conv_width": width,
            "qkvz_width_per_rank": qkvz_width,
            "ba_width_per_rank": ba_width,
            "qkv_width_per_rank": qkv_width,
        },
        "warmup": args.warmup,
        "iterations_per_repeat": args.iterations,
        "repeats": args.repeats,
        "samples_us": samples_us,
        "median_us": statistics.median(samples_us),
        "min_us": min(samples_us),
        "max_us": max(samples_us),
        "outputs_finite": bool(torch.isfinite(core_out).all().item()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
