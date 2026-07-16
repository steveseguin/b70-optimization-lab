#!/usr/bin/env python3
"""Gate moving DeepSeek V4 Q RMSNorm/RoPE into split-FP8 QK on XPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from vllm.models.deepseek_v4.common.ops.cache_utils import (
    quantize_and_insert_k_cache,
)
from vllm.models.deepseek_v4.xpu.xpu_qnorm_rope_kv_fp8_insert import (
    xpu_kv_rope_fp8_insert_fused,
    xpu_qnorm_rope_kv_fp8_insert_fused,
)
from vllm.models.deepseek_v4.xpu.xpu_sparse_decode_fp8 import (
    split_fp8_sparse_attention,
)
from vllm.triton_utils import triton


def make_cache(
    num_rows: int, block_size: int, device: torch.device, seed: int
) -> torch.Tensor:
    num_blocks = (num_rows + block_size - 1) // block_size
    cache = torch.zeros(
        (num_blocks, block_size, 584), dtype=torch.uint8, device=device
    )
    cache.view(num_blocks, -1)[:, block_size * 576 :].fill_(127)
    generator = torch.Generator(device=device).manual_seed(seed)
    source = torch.randn(
        (num_rows, 512),
        dtype=torch.bfloat16,
        device=device,
        generator=generator,
    )
    slots = torch.arange(num_rows, dtype=torch.int64, device=device)
    quantize_and_insert_k_cache(
        source,
        cache.view(num_blocks, -1),
        slots,
        block_size=block_size,
    )
    return cache


def make_cos_sin_cache(max_position: int, device: torch.device) -> torch.Tensor:
    positions = torch.arange(max_position, dtype=torch.float32, device=device)
    frequencies = 1.0 / (
        10000
        ** (torch.arange(0, 64, 2, dtype=torch.float32, device=device) / 64)
    )
    phases = positions[:, None] * frequencies[None, :]
    return torch.cat((phases.cos(), phases.sin()), dim=1).to(torch.bfloat16)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokens", type=int, default=2, choices=(1, 2))
    parser.add_argument("--heads", type=int, default=64)
    parser.add_argument("--compressed-width", type=int, default=256)
    parser.add_argument("--compressed-len", type=int, default=128)
    parser.add_argument("--swa-width", type=int, default=128)
    parser.add_argument("--swa-len", type=int, default=128)
    parser.add_argument("--changing-cases", type=int, default=8)
    parser.add_argument("--warmup-ms", type=int, default=200)
    parser.add_argument("--rep-ms", type=int, default=1000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    device = torch.device("xpu")
    block_size = 256
    num_rows = max(args.compressed_width, args.swa_width, 256)
    compressed_cache = make_cache(num_rows, block_size, device, seed=101)
    initial_swa_cache = make_cache(num_rows, block_size, device, seed=202)
    baseline_cache = initial_swa_cache.clone()
    candidate_cache = initial_swa_cache.clone()
    compressed_indices = torch.arange(
        args.compressed_width, dtype=torch.int32, device=device
    ).repeat(args.tokens, 1)
    swa_indices = torch.arange(
        args.swa_width, dtype=torch.int32, device=device
    ).repeat(args.tokens, 1)
    compressed_lens = torch.full(
        (args.tokens,), args.compressed_len, dtype=torch.int32, device=device
    )
    swa_lens = torch.full(
        (args.tokens,), args.swa_len, dtype=torch.int32, device=device
    )
    slot_mapping = torch.arange(
        args.swa_len - args.tokens,
        args.swa_len,
        dtype=torch.int64,
        device=device,
    )
    positions = torch.arange(41, 41 + args.tokens, dtype=torch.int64, device=device)
    cos_sin_cache = make_cos_sin_cache(512, device)
    sink = torch.linspace(-1.0, 1.0, args.heads, dtype=torch.float32, device=device)
    eps = 1e-6

    raw_q = torch.empty(
        (args.tokens, args.heads, 512), dtype=torch.bfloat16, device=device
    )
    kv = torch.empty((args.tokens, 512), dtype=torch.bfloat16, device=device)
    baseline_q = torch.empty_like(raw_q)
    candidate_q = torch.empty_like(raw_q)
    baseline_out = torch.empty_like(raw_q)
    candidate_out = torch.empty_like(raw_q)
    score_shape = (
        args.tokens,
        args.heads,
        args.compressed_width + args.swa_width,
    )
    baseline_scores = torch.empty(score_shape, dtype=torch.float32, device=device)
    candidate_scores = torch.empty_like(baseline_scores)
    baseline_lse = torch.empty(
        (args.tokens, args.heads), dtype=torch.float32, device=device
    )
    candidate_lse = torch.empty_like(baseline_lse)

    def reset_inputs(seed: int) -> None:
        generator = torch.Generator(device=device).manual_seed(seed)
        raw_q.copy_(
            torch.randn(
                raw_q.shape,
                dtype=raw_q.dtype,
                device=device,
                generator=generator,
            )
        )
        kv.copy_(
            torch.randn(
                kv.shape,
                dtype=kv.dtype,
                device=device,
                generator=generator,
            )
        )

    def run_baseline() -> None:
        baseline_q.copy_(raw_q)
        xpu_qnorm_rope_kv_fp8_insert_fused(
            baseline_q,
            kv,
            baseline_cache,
            slot_mapping,
            positions,
            cos_sin_cache,
            eps,
            block_size,
        )
        split_fp8_sparse_attention(
            baseline_q,
            compressed_cache,
            compressed_indices,
            compressed_lens,
            baseline_cache,
            swa_indices,
            swa_lens,
            sink,
            512**-0.5,
            baseline_out,
            block_h=4,
            qk_num_warps=16,
            pv_num_warps=8,
            scores_out=baseline_scores,
            lse_out=baseline_lse,
        )

    def run_candidate() -> None:
        candidate_q.copy_(raw_q)
        xpu_kv_rope_fp8_insert_fused(
            kv,
            candidate_cache,
            slot_mapping,
            positions,
            cos_sin_cache,
            block_size,
        )
        split_fp8_sparse_attention(
            candidate_q,
            compressed_cache,
            compressed_indices,
            compressed_lens,
            candidate_cache,
            swa_indices,
            swa_lens,
            sink,
            512**-0.5,
            candidate_out,
            block_h=4,
            qk_num_warps=16,
            pv_num_warps=8,
            raw_q_positions=positions,
            q_cos_sin_cache=cos_sin_cache,
            qnorm_eps=eps,
            scores_out=candidate_scores,
            lse_out=candidate_lse,
        )

    for case in range(args.changing_cases):
        reset_inputs(1000 + case)
        baseline_cache.copy_(initial_swa_cache)
        candidate_cache.copy_(initial_swa_cache)
        run_baseline()
        run_candidate()
        torch.xpu.synchronize()
        torch.testing.assert_close(candidate_cache, baseline_cache, atol=0, rtol=0)
        torch.testing.assert_close(candidate_scores, baseline_scores, atol=0, rtol=0)
        torch.testing.assert_close(candidate_lse, baseline_lse, atol=0, rtol=0)
        torch.testing.assert_close(candidate_out, baseline_out, atol=0, rtol=0)

    reset_inputs(2000)
    baseline_timings = triton.testing.do_bench(
        run_baseline,
        warmup=args.warmup_ms,
        rep=args.rep_ms,
        quantiles=[0.5, 0.2, 0.8],
    )
    candidate_timings = triton.testing.do_bench(
        run_candidate,
        warmup=args.warmup_ms,
        rep=args.rep_ms,
        quantiles=[0.5, 0.2, 0.8],
    )
    baseline_median_ms = float(baseline_timings[0])
    candidate_median_ms = float(candidate_timings[0])
    payload = {
        "shape": {
            "tokens": args.tokens,
            "heads": args.heads,
            "compressed_width": args.compressed_width,
            "compressed_len": args.compressed_len,
            "swa_width": args.swa_width,
            "swa_len": args.swa_len,
        },
        "changing_cases_bitwise_exact": args.changing_cases,
        "baseline_ms": {
            "median": baseline_median_ms,
            "p20": float(baseline_timings[1]),
            "p80": float(baseline_timings[2]),
        },
        "candidate_ms": {
            "median": candidate_median_ms,
            "p20": float(candidate_timings[1]),
            "p80": float(candidate_timings[2]),
        },
        "delta_ms_per_layer": baseline_median_ms - candidate_median_ms,
        "projected_delta_ms_43_layers": 43
        * (baseline_median_ms - candidate_median_ms),
    }
    text = json.dumps(payload, indent=2)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
