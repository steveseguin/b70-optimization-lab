#!/usr/bin/env python3
"""Probe XPU FlashAttention full-vs-split paged decode equivalence.

This isolates the vLLM/XPU kernel primitive from the full server. It builds a
small synthetic paged KV cache on one XPU, runs normal decode attention over all
blocks, then runs prefix/suffix attention over block-table slices and merges
the partial results with vLLM's merge_attn_states().

If this passes, the failed Stage A server shortcut is likely metadata/scheduler
specific. If it fails, the split primitive itself needs deeper XPU work before
CPU-paged attention can be exact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch

from vllm.v1.attention.backends.fa_utils import flash_attn_varlen_func
from vllm.v1.attention.ops.merge_attn_states import merge_attn_states


def manual_merge(
    prefix_output: torch.Tensor,
    prefix_lse: torch.Tensor,
    suffix_output: torch.Tensor,
    suffix_lse: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    merged_lse = torch.logaddexp(prefix_lse.float(), suffix_lse.float())
    prefix_weight = torch.exp(prefix_lse.float() - merged_lse).transpose(0, 1)
    suffix_weight = torch.exp(suffix_lse.float() - merged_lse).transpose(0, 1)
    while prefix_weight.ndim < prefix_output.ndim:
        prefix_weight = prefix_weight.unsqueeze(-1)
        suffix_weight = suffix_weight.unsqueeze(-1)
    merged_output = (
        prefix_output.float() * prefix_weight
        + suffix_output.float() * suffix_weight
    ).to(prefix_output.dtype)
    return merged_output, merged_lse


def run_attention(
    *,
    query: torch.Tensor,
    key_cache: torch.Tensor,
    value_cache: torch.Tensor,
    block_table: torch.Tensor,
    seq_len: int,
    max_seq_len: int,
    causal: bool,
    scale: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    cu_q = torch.tensor([0, query.shape[0]], dtype=torch.int32, device=query.device)
    seq_lens = torch.tensor([seq_len], dtype=torch.int32, device=query.device)
    out, lse = flash_attn_varlen_func(
        q=query,
        k=key_cache,
        v=value_cache,
        cu_seqlens_q=cu_q,
        max_seqlen_q=query.shape[0],
        seqused_k=seq_lens,
        max_seqlen_k=max_seq_len,
        softmax_scale=scale,
        causal=causal,
        window_size=[-1, -1],
        block_table=block_table,
        return_softmax_lse=True,
        fa_version=2,
    )
    return out, lse


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    dtype = getattr(torch, args.dtype)
    scale = args.scale if args.scale is not None else args.head_size**-0.5

    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        return {"ok": False, "error": "torch.xpu is unavailable"}

    seq_len = args.blocks * args.block_size
    split_blocks = args.split_blocks or args.blocks // 2
    if split_blocks <= 0 or split_blocks >= args.blocks:
        raise ValueError("split blocks must be between 1 and blocks - 1")
    prefix_len = split_blocks * args.block_size
    suffix_len = seq_len - prefix_len

    query = torch.randn(
        args.queries,
        args.heads,
        args.head_size,
        device=device,
        dtype=dtype,
    )
    key_cache = torch.randn(
        args.blocks,
        args.block_size,
        args.heads,
        args.head_size,
        device=device,
        dtype=dtype,
    )
    value_cache = torch.randn_like(key_cache)
    block_table = torch.arange(args.blocks, dtype=torch.int32, device=device).view(
        1, args.blocks
    )

    full_causal, full_causal_lse = run_attention(
        query=query,
        key_cache=key_cache,
        value_cache=value_cache,
        block_table=block_table,
        seq_len=seq_len,
        max_seq_len=seq_len,
        causal=True,
        scale=scale,
    )
    full_noncausal, full_noncausal_lse = run_attention(
        query=query,
        key_cache=key_cache,
        value_cache=value_cache,
        block_table=block_table,
        seq_len=seq_len,
        max_seq_len=seq_len,
        causal=False,
        scale=scale,
    )

    prefix_out, prefix_lse = run_attention(
        query=query,
        key_cache=key_cache,
        value_cache=value_cache,
        block_table=block_table[:, :split_blocks],
        seq_len=prefix_len,
        max_seq_len=prefix_len,
        causal=False,
        scale=scale,
    )

    reports: dict[str, dict[str, float]] = {}
    for suffix_causal in (True, False):
        suffix_out, suffix_lse = run_attention(
            query=query,
            key_cache=key_cache,
            value_cache=value_cache,
            block_table=block_table[:, split_blocks:],
            seq_len=suffix_len,
            max_seq_len=suffix_len,
            causal=suffix_causal,
            scale=scale,
        )
        merged_out = torch.empty_like(full_causal)
        merged_lse = torch.empty_like(full_causal_lse)
        merge_attn_states(
            output=merged_out,
            prefix_output=prefix_out,
            prefix_lse=prefix_lse,
            suffix_output=suffix_out,
            suffix_lse=suffix_lse,
            output_lse=merged_lse,
        )
        manual_out, manual_lse = manual_merge(
            prefix_out,
            prefix_lse,
            suffix_out,
            suffix_lse,
        )
        torch.xpu.synchronize()
        key = f"split_suffix_causal_{str(suffix_causal).lower()}"
        reports[key] = {
            "vllm_merge_max_output_abs_error_vs_full_causal": float(
                (merged_out - full_causal).abs().max().item()
            ),
            "vllm_merge_max_lse_abs_error_vs_full_causal": float(
                (merged_lse - full_causal_lse).abs().max().item()
            ),
            "vllm_merge_max_output_abs_error_vs_full_noncausal": float(
                (merged_out - full_noncausal).abs().max().item()
            ),
            "vllm_merge_max_lse_abs_error_vs_full_noncausal": float(
                (merged_lse - full_noncausal_lse).abs().max().item()
            ),
            "manual_merge_max_output_abs_error_vs_full_causal": float(
                (manual_out - full_causal).abs().max().item()
            ),
            "manual_merge_max_lse_abs_error_vs_full_causal": float(
                (manual_lse - full_causal_lse.float()).abs().max().item()
            ),
            "manual_merge_max_output_abs_error_vs_full_noncausal": float(
                (manual_out - full_noncausal).abs().max().item()
            ),
            "manual_merge_max_lse_abs_error_vs_full_noncausal": float(
                (manual_lse - full_noncausal_lse.float()).abs().max().item()
            ),
            "vllm_vs_manual_output_abs_error": float(
                (merged_out - manual_out).abs().max().item()
            ),
            "vllm_vs_manual_lse_abs_error": float(
                (merged_lse.float() - manual_lse).abs().max().item()
            ),
        }

    full_causal_noncausal_diff = {
        "max_output_abs_error": float((full_causal - full_noncausal).abs().max().item()),
        "max_lse_abs_error": float(
            (full_causal_lse - full_noncausal_lse).abs().max().item()
        ),
    }

    best = min(
        reports.values(),
        key=lambda item: item["manual_merge_max_output_abs_error_vs_full_causal"],
    )
    ok = (
        best["manual_merge_max_output_abs_error_vs_full_causal"]
        <= args.output_tolerance
        and best["manual_merge_max_lse_abs_error_vs_full_causal"]
        <= args.lse_tolerance
    )

    return {
        "ok": bool(ok),
        "device": str(device),
        "dtype": args.dtype,
        "seed": args.seed,
        "queries": args.queries,
        "heads": args.heads,
        "head_size": args.head_size,
        "block_size": args.block_size,
        "blocks": args.blocks,
        "split_blocks": split_blocks,
        "seq_len": seq_len,
        "prefix_len": prefix_len,
        "suffix_len": suffix_len,
        "scale": scale,
        "full_causal_vs_full_noncausal": full_causal_noncausal_diff,
        "reports": reports,
        "output_tolerance": args.output_tolerance,
        "lse_tolerance": args.lse_tolerance,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--queries", type=int, default=1)
    parser.add_argument("--heads", type=int, default=2)
    parser.add_argument("--head-size", type=int, default=128)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--blocks", type=int, default=8)
    parser.add_argument("--split-blocks", type=int, default=0)
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument("--output-tolerance", type=float, default=2e-3)
    parser.add_argument("--lse-tolerance", type=float, default=2e-2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run_probe(args)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
