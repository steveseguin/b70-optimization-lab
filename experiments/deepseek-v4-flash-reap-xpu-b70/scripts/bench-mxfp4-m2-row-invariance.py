#!/usr/bin/env python3
"""Compare production-shape MXFP4 MoE M=2 with two independent M=1 calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._moe_C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401
from vllm_xpu_kernels.fused_moe_interface import XpuFusedMoe


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1776)
    args = parser.parse_args()

    device = torch.device("xpu:0")
    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)

    hidden_size = 4096
    intermediate_size = 2048
    local_experts = 40
    ep_size = 4
    ep_rank = 0
    topk = 6

    w13_u8 = torch.randint(
        0,
        256,
        (local_experts, 2 * intermediate_size, hidden_size // 2),
        dtype=torch.uint8,
        device=device,
    )
    w2_u8 = torch.randint(
        0,
        256,
        (local_experts, hidden_size, intermediate_size // 2),
        dtype=torch.uint8,
        device=device,
    )
    w13_scales = torch.randint(
        96,
        112,
        (local_experts, 2 * intermediate_size, hidden_size // 32),
        dtype=torch.uint8,
        device=device,
    )
    w2_scales = torch.randint(
        96,
        112,
        (local_experts, hidden_size, intermediate_size // 32),
        dtype=torch.uint8,
        device=device,
    )

    moe = XpuFusedMoe(
        w13=w13_u8.view(torch.float4_e2m1fn_x2),
        w13_scales=w13_scales,
        w13_bias=None,
        w2=w2_u8.view(torch.float4_e2m1fn_x2),
        w2_scales=w2_scales,
        w2_bias=None,
        n_experts_per_token=topk,
        activation="silu",
        num_experts=local_experts,
        ep_rank=ep_rank,
        ep_size=ep_size,
        gemm1_clamp_limit=10.0,
    )

    route_patterns = {
        "same_local": [[0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5]],
        "disjoint_local": [[0, 1, 2, 3, 4, 5], [6, 7, 8, 9, 10, 11]],
        "mixed_ep": [[0, 40, 80, 120, 1, 41], [2, 42, 82, 122, 3, 43]],
    }
    rows = []
    for pattern_name, pattern in route_patterns.items():
        topk_ids = torch.tensor(pattern, dtype=torch.int32, device=device)
        topk_weights = torch.tensor(
            [[0.31, 0.23, 0.17, 0.13, 0.09, 0.07]] * 2,
            dtype=torch.float32,
            device=device,
        )
        for epoch in range(args.epochs):
            generator = torch.Generator(device=device).manual_seed(
                args.seed + epoch * 17 + len(rows)
            )
            hidden = (
                torch.randn(
                    (2, hidden_size),
                    dtype=torch.bfloat16,
                    device=device,
                    generator=generator,
                )
                / 16
            )
            out_m2 = torch.empty_like(hidden)
            moe.apply(out_m2, hidden, topk_weights, topk_ids)

            isolated = []
            repeated = []
            for row_index in range(2):
                out_m1 = torch.empty_like(hidden[row_index : row_index + 1])
                moe.apply(
                    out_m1,
                    hidden[row_index : row_index + 1],
                    topk_weights[row_index : row_index + 1],
                    topk_ids[row_index : row_index + 1],
                )
                out_repeat = torch.empty_like(out_m1)
                moe.apply(
                    out_repeat,
                    hidden[row_index : row_index + 1],
                    topk_weights[row_index : row_index + 1],
                    topk_ids[row_index : row_index + 1],
                )
                isolated.append(out_m1)
                repeated.append(out_repeat)
            out_m1s = torch.cat(isolated, dim=0)
            out_repeats = torch.cat(repeated, dim=0)
            torch.xpu.synchronize()

            m2_equal = torch.equal(out_m2, out_m1s)
            m1_repeat_equal = torch.equal(out_m1s, out_repeats)
            diff = (out_m2.float() - out_m1s.float()).abs()
            rows.append(
                {
                    "pattern": pattern_name,
                    "epoch": epoch,
                    "m2_equals_two_m1": m2_equal,
                    "m1_repeat_exact": m1_repeat_equal,
                    "mismatch_count": int((out_m2 != out_m1s).sum().item()),
                    "max_abs_diff": float(diff.max().item()),
                }
            )

    result = {
        "classification": "deepseek_v4_mxfp4_m2_row_invariance",
        "shape": {
            "hidden_size": hidden_size,
            "intermediate_size": intermediate_size,
            "local_experts": local_experts,
            "global_experts": local_experts * ep_size,
            "topk": topk,
            "ep_rank": ep_rank,
            "ep_size": ep_size,
        },
        "epochs_per_pattern": args.epochs,
        "cases": len(rows),
        "m2_exact_cases": sum(row["m2_equals_two_m1"] for row in rows),
        "m1_repeat_exact_cases": sum(row["m1_repeat_exact"] for row in rows),
        "passed": all(
            row["m2_equals_two_m1"] and row["m1_repeat_exact"] for row in rows
        ),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
