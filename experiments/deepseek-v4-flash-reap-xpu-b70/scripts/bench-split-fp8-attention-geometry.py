#!/usr/bin/env python3
"""Benchmark DeepSeek V4 split-FP8 sparse decode launch geometry on one XPU."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import torch

from vllm.models.deepseek_v4.xpu.xpu_sparse_decode_fp8 import (
    split_fp8_sparse_attention,
)
from vllm.triton_utils import triton


def make_cache(num_rows: int, block_size: int, device: torch.device) -> torch.Tensor:
    num_blocks = (num_rows + block_size - 1) // block_size
    cache = torch.zeros(
        (num_blocks, block_size, 584), dtype=torch.uint8, device=device
    )
    # Each block stores block_size * 576 token bytes followed by eight UE8M0
    # scales per token.  Exponent 127 is unit scale.
    cache.view(num_blocks, -1)[:, block_size * 576 :].fill_(127)
    return cache


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heads", type=int, default=64)
    parser.add_argument("--tokens", type=int, default=1, choices=(1, 2))
    parser.add_argument(
        "--index-family",
        choices=("identical", "shifted", "disjoint"),
        default="identical",
    )
    parser.add_argument("--compressed-width", type=int, default=256)
    parser.add_argument("--compressed-len", type=int, default=32)
    parser.add_argument("--swa-width", type=int, default=128)
    parser.add_argument("--swa-len", type=int, default=32)
    parser.add_argument("--warmup-ms", type=int, default=100)
    parser.add_argument("--rep-ms", type=int, default=300)
    parser.add_argument(
        "--single-geometry",
        action="store_true",
        help="Only benchmark the promoted block_h=4/qk_warps=16/pv_warps=8 geometry.",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    device = torch.device("xpu")
    torch.manual_seed(7)
    index_extent = max(args.compressed_width, args.swa_width)
    if args.index_family == "shifted":
        index_extent += args.tokens - 1
    elif args.index_family == "disjoint":
        index_extent *= args.tokens
    num_rows = max(index_extent, 256)
    block_size = 256
    compressed_cache = make_cache(num_rows, block_size, device)
    swa_cache = make_cache(num_rows, block_size, device)

    def make_indices(width: int) -> torch.Tensor:
        base = torch.arange(width, dtype=torch.int32, device=device)
        if args.index_family == "identical":
            return base.unsqueeze(0).repeat(args.tokens, 1)
        if args.index_family == "shifted":
            return torch.stack([base + row for row in range(args.tokens)])
        return torch.stack([base + row * width for row in range(args.tokens)])

    compressed_indices = make_indices(args.compressed_width)
    swa_indices = make_indices(args.swa_width)
    compressed_lens = torch.tensor(
        [args.compressed_len] * args.tokens, dtype=torch.int32, device=device
    )
    swa_lens = torch.tensor(
        [args.swa_len] * args.tokens, dtype=torch.int32, device=device
    )
    q = torch.randn(
        (args.tokens, args.heads, 512), dtype=torch.bfloat16, device=device
    )
    sink = torch.linspace(-1.0, 1.0, args.heads, dtype=torch.float32, device=device)
    reference = torch.empty_like(q)
    output = torch.empty_like(q)

    def run(block_h: int, qk_warps: int, pv_warps: int) -> None:
        split_fp8_sparse_attention(
            q,
            compressed_cache,
            compressed_indices,
            compressed_lens,
            swa_cache,
            swa_indices,
            swa_lens,
            sink,
            512**-0.5,
            output,
            block_h=block_h,
            qk_num_warps=qk_warps,
            pv_num_warps=pv_warps,
        )

    run(16, 8, 4)
    torch.xpu.synchronize()
    reference.copy_(output)
    rows: list[dict[str, float | int]] = []
    geometries = (
        [(4, 16, 8)]
        if args.single_geometry
        else itertools.product((4, 8, 16), (4, 8, 16), (4, 8))
    )
    for block_h, qk_warps, pv_warps in geometries:
        run(block_h, qk_warps, pv_warps)
        torch.xpu.synchronize()
        torch.testing.assert_close(output, reference, atol=0, rtol=0)
        median_ms, min_ms, max_ms = triton.testing.do_bench(
            lambda: run(block_h, qk_warps, pv_warps),
            warmup=args.warmup_ms,
            rep=args.rep_ms,
            quantiles=[0.5, 0.2, 0.8],
        )
        rows.append(
            {
                "block_h": block_h,
                "qk_warps": qk_warps,
                "pv_warps": pv_warps,
                "median_us": median_ms * 1000,
                "min_us": min_ms * 1000,
                "max_us": max_ms * 1000,
            }
        )

    rows.sort(key=lambda row: row["median_us"])
    payload = json.dumps(
        {
            "shape": {
                "tokens": args.tokens,
                "index_family": args.index_family,
                "heads": args.heads,
                "compressed_width": args.compressed_width,
                "compressed_len": args.compressed_len,
                "swa_width": args.swa_width,
                "swa_len": args.swa_len,
            },
            "rows": rows,
        },
        indent=2,
    )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
