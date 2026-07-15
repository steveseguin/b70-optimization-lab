#!/usr/bin/env python3
"""Measure XPU shared-expert/routed-MoE overlap at the V4 decode shape.

This is a scheduling feasibility gate, not a model-quality benchmark.  It uses
the same M=1, H=4096, I=2048, top-k=6, local-E=40 MXFP4 routed expert and TP4
shared-expert projection shapes as the promoted DeepSeek V4 K160 lane.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch

import vllm  # noqa: F401 - registers the quantization operators
import vllm._custom_ops  # noqa: F401
import vllm_xpu_kernels  # noqa: F401
from vllm_xpu_kernels.fused_moe_interface import XpuFusedMoe


def summarize(samples: list[float]) -> dict[str, float | list[float]]:
    return {
        "median_us": statistics.median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
        "samples_us": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    torch.manual_seed(7)
    device = torch.device("xpu")
    dtype = torch.bfloat16
    hidden_size = 4096
    intermediate_size = 2048
    shared_intermediate_per_rank = intermediate_size // 4
    local_experts = 40
    topk = 6
    group_size = 32
    block_size = 128

    hidden = torch.randn((1, hidden_size), device=device, dtype=dtype) / 16

    # Native routed MXFP4 expert weights.  The packed dimension stores two
    # E2M1 values per byte, matching XpuFusedMoe's production layout.
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
    # Match EP4 rank 0: two selected experts are local and four belong to the
    # other ranks.  The production remapper drops non-local expert rows before
    # the two grouped GEMMs while preserving the global top-k combine map.
    topk_ids = torch.tensor(
        [[0, 40, 80, 120, 1, 41]], device=device, dtype=torch.int64
    )
    topk_weights = torch.full(
        (1, topk), 1.0 / topk, device=device, dtype=torch.float32
    )
    routed_out = torch.empty_like(hidden)
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

    # TP4 shared expert: [4096 -> 2*(2048/4)] W8A16, fused clamped
    # SwiGLU+Q8 production, then [2048/4 -> 4096] W8A8.
    gate_weight_nk = torch.randn(
        (2 * shared_intermediate_per_rank, hidden_size), device=device, dtype=dtype
    ).to(torch.float8_e4m3fn)
    gate_scale = torch.ones(
        (hidden_size // block_size, (2 * shared_intermediate_per_rank) // block_size),
        device=device,
        dtype=torch.float8_e8m0fnu,
    )
    down_weight_nk = torch.randn(
        (hidden_size, shared_intermediate_per_rank), device=device, dtype=dtype
    ).to(torch.float8_e4m3fn)
    down_scale = torch.ones(
        (shared_intermediate_per_rank // block_size, hidden_size // block_size),
        device=device,
        dtype=torch.float8_e8m0fnu,
    )
    empty_bias = torch.Tensor()
    shared_q = torch.empty(
        (1, shared_intermediate_per_rank),
        device=device,
        dtype=torch.float8_e4m3fn,
    )
    shared_q_scale = torch.empty(
        (1, shared_intermediate_per_rank // block_size),
        device=device,
        dtype=torch.float32,
    )

    last_shared: torch.Tensor | None = None

    def run_routed() -> torch.Tensor:
        routed.apply(
            output=routed_out,
            hidden_states=hidden,
            topk_weights=topk_weights,
            topk_ids=topk_ids,
        )
        return routed_out

    def run_shared() -> torch.Tensor:
        nonlocal last_shared
        gate_up = torch.ops._xpu_C.fp8_gemm_w8a16(
            hidden, gate_weight_nk.t(), gate_scale, empty_bias
        )
        torch.ops._C.silu_and_mul_per_block_quant(
            shared_q,
            gate_up,
            shared_q_scale,
            block_size,
            None,
            False,
            False,
            10.0,
            1.0,
            0.0,
        )
        last_shared = torch.ops._xpu_C.fp8_gemm(
            shared_q,
            down_weight_nk.t(),
            dtype,
            shared_q_scale,
            down_scale,
            empty_bias,
        )
        return last_shared

    main_stream = torch.xpu.current_stream()
    aux_stream = torch.xpu.Stream()

    def sequential_once() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        routed_value = run_routed()
        shared_value = run_shared()
        return routed_value, shared_value, routed_value + shared_value

    def overlapped_once() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        # Both consumers read the same immutable hidden state.  Publish the
        # main-stream producer boundary, submit shared work first on the aux
        # stream, and join before combining outputs.
        aux_stream.wait_stream(main_stream)
        with torch.xpu.stream(aux_stream):
            shared_value = run_shared()
        routed_value = run_routed()
        main_stream.wait_stream(aux_stream)
        return routed_value, shared_value, routed_value + shared_value

    def time_us(fn) -> list[float]:
        for _ in range(args.warmups):
            fn()
        torch.xpu.synchronize()
        samples = []
        for _ in range(args.repeats):
            start = torch.xpu.Event(enable_timing=True)
            end = torch.xpu.Event(enable_timing=True)
            start.record(main_stream)
            for _ in range(args.iterations):
                fn()
            end.record(main_stream)
            end.synchronize()
            samples.append(start.elapsed_time(end) * 1000.0 / args.iterations)
        return samples

    # Prove that stream scheduling does not alter either independent result or
    # the final combine before interpreting the timing.
    seq_routed, seq_shared, seq_sum = sequential_once()
    torch.xpu.synchronize()
    seq_routed_ref = seq_routed.clone()
    seq_shared_ref = seq_shared.clone()
    seq_sum_ref = seq_sum.clone()
    ov_routed, ov_shared, ov_sum = overlapped_once()
    torch.xpu.synchronize()
    correctness = {
        "routed_bitwise": torch.equal(seq_routed_ref, ov_routed),
        "shared_bitwise": torch.equal(seq_shared_ref, ov_shared),
        "sum_bitwise": torch.equal(seq_sum_ref, ov_sum),
    }

    sequential = summarize(time_us(sequential_once))
    overlapped = summarize(time_us(overlapped_once))
    saved_us = sequential["median_us"] - overlapped["median_us"]
    result = {
        "classification": "deepseek_v4_shared_routed_overlap_microgate",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "shape": {
            "m": 1,
            "hidden_size": hidden_size,
            "intermediate_size": intermediate_size,
            "shared_intermediate_per_rank": shared_intermediate_per_rank,
            "local_experts": local_experts,
            "ep_size": 4,
            "local_topk_rows": 2,
            "topk": topk,
        },
        "warmups": args.warmups,
        "iterations": args.iterations,
        "repeats": args.repeats,
        "correctness": correctness,
        "sequential": sequential,
        "overlapped": overlapped,
        "saved_us_per_layer": saved_us,
        "projected_saved_ms_per_43_layers": saved_us * 43 / 1000.0,
        "gate": {
            "required_projected_ms": 0.5,
            "passed": all(correctness.values()) and saved_us * 43 >= 500.0,
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if all(correctness.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
