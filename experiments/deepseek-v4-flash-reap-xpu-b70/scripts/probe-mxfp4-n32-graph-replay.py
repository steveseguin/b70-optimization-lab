#!/usr/bin/env python3
"""Gate MXFP4 N32 policy parity under changed-input XPU graph replay."""

from __future__ import annotations

import argparse
import json
import os
import statistics
from pathlib import Path

import torch

import vllm  # noqa: F401
import vllm._custom_ops  # noqa: F401
import vllm_xpu_kernels  # noqa: F401
from vllm_xpu_kernels.fused_moe_interface import XpuFusedMoe


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--candidate-policy", choices=("32", "128"), default="32")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    torch.manual_seed(23)
    device = torch.device("xpu")
    dtype = torch.bfloat16
    hidden_size = 4096
    intermediate_size = 2048
    local_experts = 40
    topk = 6
    group_size = 32

    hidden = torch.randn((1, hidden_size), device=device, dtype=dtype) / 16
    w13 = torch.randint(
        0,
        256,
        (local_experts, 2 * intermediate_size, hidden_size // 2),
        device=device,
        dtype=torch.uint8,
    ).view(torch.float4_e2m1fn_x2)
    w2 = torch.randint(
        0,
        256,
        (local_experts, hidden_size, intermediate_size // 2),
        device=device,
        dtype=torch.uint8,
    ).view(torch.float4_e2m1fn_x2)
    w13_scale = torch.randint(
        1,
        0x6F,
        (local_experts, 2 * intermediate_size, hidden_size // group_size),
        device=device,
        dtype=torch.uint8,
    )
    w2_scale = torch.randint(
        1,
        0x6F,
        (local_experts, hidden_size, intermediate_size // group_size),
        device=device,
        dtype=torch.uint8,
    )
    topk_ids = torch.tensor(
        [[0, 40, 80, 120, 1, 41]], device=device, dtype=torch.int64
    )
    topk_weights = torch.full(
        (1, topk), 1.0 / topk, device=device, dtype=torch.float32
    )
    output = torch.empty_like(hidden)
    routed = XpuFusedMoe(
        w13=w13,
        w13_scales=w13_scale,
        w13_bias=None,
        w2=w2,
        w2_scales=w2_scale,
        w2_bias=None,
        n_experts_per_token=topk,
        activation="swigluoai",
        num_experts=local_experts,
        ep_rank=0,
        ep_size=4,
        gemm1_clamp_limit=10.0,
    )

    def call() -> torch.Tensor:
        routed.apply(
            output=output,
            hidden_states=hidden,
            topk_weights=topk_weights,
            topk_ids=topk_ids,
        )
        return output

    os.environ["VLLM_XPU_MXFP4_SMALL_M_N"] = args.candidate_policy
    for _ in range(3):
        call()
    torch.xpu.synchronize()
    graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(graph):
        call()
    graph.replay()
    torch.xpu.synchronize()

    rows = []
    all_exact = True
    try:
        for epoch in range(args.epochs):
            hidden.copy_(
                torch.randn((1, hidden_size), device=device, dtype=dtype) / 16
            )
            os.environ["VLLM_XPU_MXFP4_SMALL_M_N"] = "64"
            call()
            torch.xpu.synchronize()
            expected = output.clone()

            os.environ["VLLM_XPU_MXFP4_SMALL_M_N"] = args.candidate_policy
            graph.replay()
            torch.xpu.synchronize()
            exact = torch.equal(expected, output)
            max_abs = (expected.float() - output.float()).abs().max().item()
            all_exact = all_exact and exact
            rows.append({"epoch": epoch, "exact": exact, "max_abs": max_abs})
    finally:
        graph.reset()
        torch.xpu.synchronize()

    def time_policy_once(policy: str) -> float:
        os.environ["VLLM_XPU_MXFP4_SMALL_M_N"] = policy
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(50):
            call()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / 50

    for _ in range(50):
        os.environ["VLLM_XPU_MXFP4_SMALL_M_N"] = "64"
        call()
        os.environ["VLLM_XPU_MXFP4_SMALL_M_N"] = args.candidate_policy
        call()
    torch.xpu.synchronize()
    n64_samples = []
    candidate_samples = []
    for _ in range(9):
        n64_samples.append(time_policy_once("64"))
        candidate_samples.append(time_policy_once(args.candidate_policy))
    n64_median = statistics.median(n64_samples)
    candidate_median = statistics.median(candidate_samples)

    result = {
        "classification": "deepseek_v4_mxfp4_small_n_graph_replay_gate",
        "candidate_policy": args.candidate_policy,
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "epochs": args.epochs,
        "all_exact_vs_n64": all_exact,
        "timing": {
            "n64_median_us": n64_median,
            "candidate_median_us": candidate_median,
            "saved_us": n64_median - candidate_median,
            "speedup": n64_median / candidate_median,
            "n64_samples_us": n64_samples,
            "candidate_samples_us": candidate_samples,
        },
        "rows": rows,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if all_exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
