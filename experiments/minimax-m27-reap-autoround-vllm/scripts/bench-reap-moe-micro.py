#!/usr/bin/env python3
"""Microbenchmark REAP MiniMax-M2.7 E=192 INT4 MoE decode kernels.

This is intentionally synthetic: it validates kernel-level timing for the
actual REAP per-rank routed expert shape without loading the full model.
Use one process per env-knob setting because llm-scaler reads several knobs
into static variables on first use.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

import torch


LLM_SCALER_ROOT = Path(
    os.environ.get(
        "LLM_SCALER_ROOT",
        "/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm",
    )
)
sys.path.insert(0, str(LLM_SCALER_ROOT / "tests"))
sys.path.insert(0, str(LLM_SCALER_ROOT / "python"))

from custom_esimd_kernels_vllm import (  # noqa: E402
    moe_forward_tiny_cutlass_nmajor_int4_u4,
    moe_forward_tiny_cutlass_nmajor_int4_u4_minimax,
    moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws,
    moe_forward_tiny_cutlass_nmajor_int4_u4_ws,
    to_cutlass_nmajor_int4,
)
from test_moe_int4_kernel import quantize_int4  # noqa: E402


ENV_KEYS = (
    "VLLM_XPU_MOE_WS_UP_NTILE",
    "VLLM_XPU_MOE_WS_DOWN_HTILE",
    "VLLM_XPU_MINIMAX_WS_TOPK_WEIGHT_FP16",
    "VLLM_XPU_MINIMAX_WS_REUSE_DECODE_BUFFERS",
    "VLLM_XPU_MINIMAX_WS_REUSE_INTERMEDIATES",
    "VLLM_XPU_MINIMAX_WS_REUSE_TOPK_BUFFERS",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu")
    parser.add_argument("--hidden-size", type=int, default=3072)
    parser.add_argument("--intermediate-size", type=int, default=384)
    parser.add_argument("--num-experts", type=int, default=192)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--tokens", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--runs", type=int, default=80)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--scale", type=float, default=0.02)
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def synchronize() -> None:
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        torch.xpu.synchronize()


def bench(fn: Callable[[], torch.Tensor], warmup: int, runs: int) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    synchronize()

    samples = []
    for _ in range(runs):
        synchronize()
        start = time.perf_counter()
        fn()
        synchronize()
        samples.append((time.perf_counter() - start) * 1000.0)

    samples.sort()
    return {
        "median_ms": statistics.median(samples),
        "mean_ms": statistics.mean(samples),
        "p05_ms": samples[max(0, int(0.05 * len(samples)) - 1)],
        "p95_ms": samples[min(len(samples) - 1, int(0.95 * len(samples)))],
        "min_ms": min(samples),
        "max_ms": max(samples),
    }


def build_weight(rows: int, cols: int, scale: float, device: str) -> tuple[torch.Tensor, torch.Tensor]:
    weight = (torch.randn(rows, cols) * scale).half()
    qweight, scales = quantize_int4(weight)
    return to_cutlass_nmajor_int4(qweight).to(device), scales.to(device)


def build_inputs(args: argparse.Namespace) -> dict[str, torch.Tensor]:
    torch.manual_seed(args.seed)
    h = args.hidden_size
    n = args.intermediate_size
    e = args.num_experts
    device = args.device

    w13_q, w13_s = [], []
    w2_q, w2_s = [], []
    for _ in range(e):
        q, s = build_weight(2 * n, h, args.scale, device)
        w13_q.append(q)
        w13_s.append(s)
        q, s = build_weight(h, n, args.scale, device)
        w2_q.append(q)
        w2_s.append(s)

    return {
        "w13_q": torch.stack(w13_q).contiguous(),
        "w13_s": torch.stack(w13_s).contiguous(),
        "w2_q": torch.stack(w2_q).contiguous(),
        "w2_s": torch.stack(w2_s).contiguous(),
        "e_score_bias": torch.randn(e, dtype=torch.float32, device=device) * 0.01,
    }


def run_for_tokens(
    args: argparse.Namespace,
    weights: dict[str, torch.Tensor],
    n_tokens: int,
) -> dict[str, object]:
    torch.manual_seed(args.seed + n_tokens)
    x = (torch.randn(n_tokens, args.hidden_size) * 0.1).half().to(args.device)
    router_logits = (torch.randn(n_tokens, args.num_experts) * 0.1).float().to(
        args.device
    )
    scores = router_logits.sigmoid() + weights["e_score_bias"].unsqueeze(0)
    topk_weight, topk_idx = torch.topk(scores, args.top_k, dim=-1)
    exact_weight = router_logits.sigmoid().gather(1, topk_idx)
    topk_weight = exact_weight / exact_weight.sum(dim=-1, keepdim=True)
    topk_weight = topk_weight.contiguous()
    topk_idx = topk_idx.to(torch.int32).contiguous()

    def routed_u4() -> torch.Tensor:
        return moe_forward_tiny_cutlass_nmajor_int4_u4(
            x,
            weights["w13_q"],
            weights["w13_s"],
            weights["w2_q"],
            weights["w2_s"],
            topk_weight,
            topk_idx,
        )

    def routed_ws() -> torch.Tensor:
        return moe_forward_tiny_cutlass_nmajor_int4_u4_ws(
            x,
            weights["w13_q"],
            weights["w13_s"],
            weights["w2_q"],
            weights["w2_s"],
            topk_weight,
            topk_idx,
        )

    def routed_ws_fp16_weight() -> torch.Tensor:
        return moe_forward_tiny_cutlass_nmajor_int4_u4_ws(
            x,
            weights["w13_q"],
            weights["w13_s"],
            weights["w2_q"],
            weights["w2_s"],
            topk_weight.to(torch.float16),
            topk_idx,
        )

    def minimax_logits() -> torch.Tensor:
        return moe_forward_tiny_cutlass_nmajor_int4_u4_minimax(
            x,
            weights["w13_q"],
            weights["w13_s"],
            weights["w2_q"],
            weights["w2_s"],
            router_logits,
            weights["e_score_bias"],
            args.top_k,
            True,
        )

    def minimax_logits_ws() -> torch.Tensor:
        return moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws(
            x,
            weights["w13_q"],
            weights["w13_s"],
            weights["w2_q"],
            weights["w2_s"],
            router_logits,
            weights["e_score_bias"],
            args.top_k,
            True,
        )

    ref = routed_u4()
    synchronize()
    comparisons = {}
    for name, fn in (
        ("routed_ws", routed_ws),
        ("routed_ws_fp16_weight", routed_ws_fp16_weight),
        ("minimax_logits", minimax_logits),
        ("minimax_logits_ws", minimax_logits_ws),
    ):
        out = fn()
        synchronize()
        comparisons[name] = float((ref.float() - out.float()).abs().max().item())

    timings = {
        "routed_u4": bench(routed_u4, args.warmup, args.runs),
        "routed_ws": bench(routed_ws, args.warmup, args.runs),
        "routed_ws_fp16_weight": bench(
            routed_ws_fp16_weight, args.warmup, args.runs
        ),
        "minimax_logits": bench(minimax_logits, args.warmup, args.runs),
        "minimax_logits_ws": bench(minimax_logits_ws, args.warmup, args.runs),
    }
    return {
        "tokens": n_tokens,
        "max_abs_diff_vs_routed_u4": comparisons,
        "timings": timings,
    }


def main() -> None:
    args = parse_args()
    weights = build_inputs(args)
    results = {
        "shape": {
            "hidden_size": args.hidden_size,
            "intermediate_size": args.intermediate_size,
            "num_experts": args.num_experts,
            "top_k": args.top_k,
        },
        "env": {key: os.environ.get(key, "") for key in ENV_KEYS},
        "warmup": args.warmup,
        "runs": args.runs,
        "results": [run_for_tokens(args, weights, n) for n in args.tokens],
    }
    text = json.dumps(results, indent=2, sort_keys=True)
    print(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
