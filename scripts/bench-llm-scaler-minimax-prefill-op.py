#!/usr/bin/env python3
"""Smoke and timing harness for llm-scaler MiniMax INT4 prefill kernels.

This intentionally starts with a zero-weight correctness check. The prefill
kernel consumes AutoRound/GPTQ-style int32 packed weights where the zero-pointed
INT4 zero value is bit pattern 0x88888888, not an all-zero int32.
"""

from __future__ import annotations

import argparse
import importlib
import json
import time
from pathlib import Path

import torch


ZERO_POINTED_INT4_ZERO_I32 = -0x77777778  # signed int32 bit pattern 0x88888888


def run(args: argparse.Namespace) -> dict:
    importlib.import_module("custom_esimd_kernels_vllm.moe_int4_prefill_ops")
    if not torch.xpu.is_available():
        raise RuntimeError("torch.xpu is not available")

    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    hidden_size = args.hidden_size
    intermediate_size = args.intermediate_size
    num_experts = args.num_experts
    top_k = args.top_k
    group_size = args.group_size

    gate_up_weight = torch.full(
        (num_experts, hidden_size // 8, 2 * intermediate_size),
        ZERO_POINTED_INT4_ZERO_I32,
        dtype=torch.int32,
        device=device,
    )
    gate_up_scale = torch.ones(
        (num_experts, hidden_size // group_size, 2 * intermediate_size),
        dtype=torch.float16,
        device=device,
    ) * args.scale
    down_weight = torch.full(
        (num_experts, intermediate_size // 8, hidden_size),
        ZERO_POINTED_INT4_ZERO_I32,
        dtype=torch.int32,
        device=device,
    )
    down_scale = torch.ones(
        (num_experts, intermediate_size // group_size, hidden_size),
        dtype=torch.float16,
        device=device,
    ) * args.scale

    results = []
    for n_tokens in args.tokens:
        x = torch.randn(
            (n_tokens, hidden_size), dtype=torch.float16, device=device)
        router_logits = torch.randn(
            (n_tokens, num_experts), dtype=torch.float16, device=device)

        y = torch.ops.moe_int4_prefill_ops.moe_prefill_full_int4(
            x,
            router_logits,
            gate_up_weight,
            gate_up_scale,
            down_weight,
            down_scale,
            top_k,
            num_experts,
        )
        torch.xpu.synchronize()
        max_abs = float(y.float().abs().max().cpu())

        start = time.perf_counter()
        for _ in range(args.repeats):
            y = torch.ops.moe_int4_prefill_ops.moe_prefill_full_int4(
                x,
                router_logits,
                gate_up_weight,
                gate_up_scale,
                down_weight,
                down_scale,
                top_k,
                num_experts,
            )
        torch.xpu.synchronize()
        seconds = (time.perf_counter() - start) / args.repeats
        results.append({
            "tokens": n_tokens,
            "ms": seconds * 1000.0,
            "tokens_per_second_layer_equivalent": n_tokens / seconds,
            "max_abs_zero_expected": max_abs,
            "sum": float(y.float().sum().cpu()),
        })

    return {
        "device": args.device,
        "seed": args.seed,
        "hidden_size": hidden_size,
        "intermediate_size": intermediate_size,
        "num_experts": num_experts,
        "top_k": top_k,
        "group_size": group_size,
        "scale": args.scale,
        "zero_pointed_int4_zero_i32": ZERO_POINTED_INT4_ZERO_I32,
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--hidden-size", type=int, default=3072)
    parser.add_argument("--intermediate-size", type=int, default=1536)
    parser.add_argument("--num-experts", type=int, default=256)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--group-size", type=int, default=128)
    parser.add_argument("--scale", type=float, default=0.01)
    parser.add_argument(
        "--tokens",
        type=int,
        nargs="+",
        default=[1, 4, 16, 64, 128, 256, 512],
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(args)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
