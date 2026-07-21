#!/usr/bin/env python3
"""Default-off sustained M=1 kernel loop for external read-only telemetry."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time

import torch
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._moe_C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


def time_batch(call, count: int) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(count):
        call()
    end.record()
    end.synchronize()
    return start.elapsed_time(end) * 1000.0 / count


def make_shared_down(device: torch.device):
    m, n, k = 1, 4096, 512
    activation = torch.randn((m, k), device=device).to(torch.float8_e4m3fn)
    activation_scales = torch.rand((m, k // 128), device=device)
    weights = [
        torch.randn((n, k), device=device).to(torch.float8_e4m3fn).t()
        for _ in range(43)
    ]
    weight_scales = [
        torch.ones(
            (k // 128, n // 128), dtype=torch.float8_e8m0fnu, device=device
        )
        for _ in range(43)
    ]
    empty_bias = torch.Tensor()
    weight_index = 0

    def run():
        nonlocal weight_index
        index = weight_index
        weight_index = (weight_index + 1) % len(weights)
        return torch.ops._xpu_C.fp8_gemm(
            activation,
            weights[index],
            torch.bfloat16,
            activation_scales,
            weight_scales[index],
            empty_bias,
        )

    return run, 2_106_000


def make_mxfp4(device: torch.device):
    hidden_size, intermediate, local_experts = 4096, 2048, 40
    hidden = torch.ones((1, hidden_size), dtype=torch.bfloat16, device=device)
    route_bank = [
        torch.tensor(
            [[i % 40, (i + 1) % 40, (i + 2) % 40, 40, 80, 120]],
            dtype=torch.int32,
            device=device,
        )
        for i in range(0, 40, 3)
    ]
    topk_weights = torch.full((1, 6), 1 / 6, dtype=torch.float32, device=device)
    expert_map = torch.empty((160,), dtype=torch.int32, device=device)
    torch.ops._moe_C.init_expert_map(expert_map, local_experts, 0, 4)
    w13 = torch.zeros(
        (local_experts, 2 * intermediate, hidden_size // 2),
        dtype=torch.uint8,
        device=device,
    ).view(torch.float4_e2m1fn_x2)
    s13 = torch.full(
        (local_experts, 2 * intermediate, hidden_size // 32),
        121,
        dtype=torch.uint8,
        device=device,
    )
    w2 = torch.zeros(
        (local_experts, hidden_size, intermediate // 2),
        dtype=torch.uint8,
        device=device,
    ).view(torch.float4_e2m1fn_x2)
    s2 = torch.full(
        (local_experts, hidden_size, intermediate // 32),
        121,
        dtype=torch.uint8,
        device=device,
    )
    gemm1 = torch.empty((6, 2 * intermediate), dtype=torch.bfloat16, device=device)
    activation = torch.empty((6, intermediate), dtype=torch.bfloat16, device=device)
    gemm2 = torch.empty((6, hidden_size), dtype=torch.bfloat16, device=device)
    output = torch.empty((1, hidden_size), dtype=torch.bfloat16, device=device)
    os.environ["VLLM_XPU_MXFP4_M1_PREFETCH_MODE"] = ""
    route_index = 0

    def run():
        nonlocal route_index
        topk_ids = route_bank[route_index]
        route_index = (route_index + 1) % len(route_bank)
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            hidden, w13, s13, None, gemm1, topk_ids, expert_map,
            2 * intermediate, hidden_size, local_experts, True,
        )
        torch.ops._C.silu_and_mul_clamp(activation, gemm1, 10.0)
        torch.ops._xpu_C.cutlass_grouped_gemm_m1_topk_interface(
            activation, w2, s2, None, gemm2, topk_ids, expert_map,
            hidden_size, intermediate, local_experts, False,
        )
        torch.ops._moe_C.moe_gather_direct_m1(
            output, gemm2, topk_weights, topk_ids, expert_map, local_experts,
        )
        return output

    return run, 3 * 13_369_344


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("mxfp4", "shared_down"))
    parser.add_argument("--seconds", type=float, default=45)
    parser.add_argument("--batch", type=int, default=200)
    args = parser.parse_args()
    device = torch.device("xpu:0")
    make = make_mxfp4 if args.mode == "mxfp4" else make_shared_down
    call, logical_bytes = make(device)
    for _ in range(40):
        call()
    torch.xpu.synchronize()
    samples = []
    start = time.monotonic()
    calls = 0
    while time.monotonic() - start < args.seconds:
        samples.append(time_batch(call, args.batch))
        calls += args.batch
    elapsed = time.monotonic() - start
    print(
        json.dumps(
            {
                "mode": args.mode,
                "device": torch.xpu.get_device_name(device),
                "logical_bytes_per_call": logical_bytes,
                "calls": calls,
                "duration_s": elapsed,
                "median_us": statistics.median(samples),
                "best_us": min(samples),
                "logical_GBps": logical_bytes / statistics.median(samples) / 1000,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
