#!/usr/bin/env python3
"""Probe dense-scratch CPU-staged XPU attention.

The paged XPU FlashAttention path returns unstable LSE values when we split a
sequence across scratch paged caches, which breaks exact softmax-state merging.
This probe tests a different active-overflow shape:

1. use normal paged attention as the output reference
2. copy older KV blocks to CPU RAM
3. stage CPU/GPU KV chunks into dense XPU scratch tensors
4. run dense FlashAttention per chunk with return_softmax_lse=True
5. merge dense chunk outputs/LSE values

If this matches the paged reference output, dense scratch is the safer first
route for system-RAM-backed active context on XPU.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import torch

from vllm.v1.attention.backends.fa_utils import flash_attn_varlen_func
from vllm.v1.attention.ops.merge_attn_states import merge_attn_states


def gbps(num_bytes: int, seconds: float) -> float | None:
    if seconds <= 0:
        return None
    return num_bytes / seconds / 1e9


def allocate_cpu_like(tensor: torch.Tensor, pin_memory: bool) -> torch.Tensor:
    try:
        return torch.empty(
            tuple(tensor.shape),
            dtype=tensor.dtype,
            device="cpu",
            pin_memory=pin_memory,
        )
    except RuntimeError:
        if pin_memory:
            return allocate_cpu_like(tensor, pin_memory=False)
        raise


def dense_attention(
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    scale: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    cu_q = torch.tensor([0, query.shape[0]], dtype=torch.int32, device=query.device)
    cu_k = torch.tensor([0, key.shape[0]], dtype=torch.int32, device=query.device)
    out, lse = flash_attn_varlen_func(
        q=query,
        k=key,
        v=value,
        cu_seqlens_q=cu_q,
        max_seqlen_q=query.shape[0],
        cu_seqlens_k=cu_k,
        max_seqlen_k=key.shape[0],
        softmax_scale=scale,
        causal=False,
        window_size=[-1, -1],
        return_softmax_lse=True,
        fa_version=2,
    )
    return out, lse


def paged_attention(
    query: torch.Tensor,
    key_cache: torch.Tensor,
    value_cache: torch.Tensor,
    block_table: torch.Tensor,
    seq_len: int,
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
        max_seqlen_k=seq_len,
        softmax_scale=scale,
        causal=True,
        window_size=[-1, -1],
        block_table=block_table,
        return_softmax_lse=True,
        fa_version=2,
    )
    return out, lse


def merge_pair(
    left_out: torch.Tensor | None,
    left_lse: torch.Tensor | None,
    right_out: torch.Tensor,
    right_lse: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    if left_out is None or left_lse is None:
        return right_out, right_lse
    merged_out = torch.empty_like(right_out)
    merged_lse = torch.empty_like(right_lse)
    merge_attn_states(
        output=merged_out,
        prefix_output=left_out,
        prefix_lse=left_lse,
        suffix_output=right_out,
        suffix_lse=right_lse,
        output_lse=merged_lse,
    )
    return merged_out, merged_lse


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        return {"ok": False, "error": "torch.xpu is unavailable"}

    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    dtype = getattr(torch, args.dtype)
    scale = args.scale if args.scale is not None else args.head_size**-0.5

    if args.prefix_blocks <= 0:
        raise ValueError("--prefix-blocks must be positive")
    if args.prefix_blocks >= args.blocks:
        raise ValueError("--prefix-blocks must be smaller than --blocks")
    if args.stage_tokens <= 0:
        raise ValueError("--stage-tokens must be positive")

    seq_len = args.blocks * args.block_size
    prefix_len = args.prefix_blocks * args.block_size
    suffix_len = seq_len - prefix_len
    stage_tokens = min(args.stage_tokens, seq_len)

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
    block_table = torch.arange(
        args.blocks, dtype=torch.int32, device=device
    ).view(1, args.blocks)

    # Paged output is the normal vLLM-style reference. Its returned LSE is not
    # trusted on XPU, but its output matches dense full attention closely.
    for _ in range(args.warmup_calls):
        paged_attention(query, key_cache, value_cache, block_table, seq_len, scale)
    paged_out, paged_lse = paged_attention(
        query, key_cache, value_cache, block_table, seq_len, scale
    )

    dense_key = key_cache.reshape(seq_len, args.heads, args.head_size)
    dense_value = value_cache.reshape(seq_len, args.heads, args.head_size)
    for _ in range(args.warmup_calls):
        dense_attention(query, dense_key, dense_value, scale)
    dense_full_out, dense_full_lse = dense_attention(
        query, dense_key, dense_value, scale
    )

    cpu_prefix_key = allocate_cpu_like(
        key_cache[: args.prefix_blocks], args.pin_memory
    )
    cpu_prefix_value = allocate_cpu_like(
        value_cache[: args.prefix_blocks], args.pin_memory
    )
    cpu_prefix_key.copy_(key_cache[: args.prefix_blocks], non_blocking=True)
    cpu_prefix_value.copy_(value_cache[: args.prefix_blocks], non_blocking=True)
    torch.xpu.synchronize()

    scratch_key = torch.empty(
        stage_tokens,
        args.heads,
        args.head_size,
        device=device,
        dtype=dtype,
    )
    scratch_value = torch.empty_like(scratch_key)

    # Warm the dense scratch shape.
    warm_tokens = min(stage_tokens, prefix_len)
    scratch_key[:warm_tokens].copy_(
        cpu_prefix_key.reshape(prefix_len, args.heads, args.head_size)[:warm_tokens],
        non_blocking=True,
    )
    scratch_value[:warm_tokens].copy_(
        cpu_prefix_value.reshape(prefix_len, args.heads, args.head_size)[:warm_tokens],
        non_blocking=True,
    )
    torch.xpu.synchronize()
    for _ in range(args.warmup_calls):
        dense_attention(query, scratch_key[:warm_tokens], scratch_value[:warm_tokens], scale)

    staged_out: torch.Tensor | None = None
    staged_lse: torch.Tensor | None = None
    chunk_reports: list[dict[str, Any]] = []
    total_copy_bytes = 0
    total_copy_seconds = 0.0
    total_attention_seconds = 0.0

    cpu_prefix_key_dense = cpu_prefix_key.reshape(prefix_len, args.heads, args.head_size)
    cpu_prefix_value_dense = cpu_prefix_value.reshape(
        prefix_len, args.heads, args.head_size
    )

    def run_chunk(
        start_token: int,
        end_token: int,
        source: str,
    ) -> None:
        nonlocal staged_out, staged_lse
        nonlocal total_copy_bytes, total_copy_seconds, total_attention_seconds

        count = end_token - start_token
        copy_start = time.perf_counter()
        if source == "cpu":
            scratch_key[:count].copy_(
                cpu_prefix_key_dense[start_token:end_token],
                non_blocking=True,
            )
            scratch_value[:count].copy_(
                cpu_prefix_value_dense[start_token:end_token],
                non_blocking=True,
            )
        elif source == "gpu":
            scratch_key[:count].copy_(
                dense_key[start_token:end_token],
                non_blocking=True,
            )
            scratch_value[:count].copy_(
                dense_value[start_token:end_token],
                non_blocking=True,
            )
        else:
            raise ValueError(source)
        torch.xpu.synchronize()
        copy_seconds = time.perf_counter() - copy_start

        attn_start = time.perf_counter()
        chunk_out, chunk_lse = dense_attention(
            query,
            scratch_key[:count],
            scratch_value[:count],
            scale,
        )
        staged_out, staged_lse = merge_pair(
            staged_out,
            staged_lse,
            chunk_out,
            chunk_lse,
        )
        torch.xpu.synchronize()
        attn_seconds = time.perf_counter() - attn_start

        copy_bytes = (
            scratch_key[:count].numel() + scratch_value[:count].numel()
        ) * scratch_key.element_size()
        total_copy_bytes += copy_bytes
        total_copy_seconds += copy_seconds
        total_attention_seconds += attn_seconds
        chunk_reports.append(
            {
                "source": source,
                "start_token": start_token,
                "tokens": count,
                "copy_seconds": copy_seconds,
                "copy_gbps": gbps(copy_bytes, copy_seconds),
                "attention_seconds": attn_seconds,
            }
        )

    for start in range(0, prefix_len, stage_tokens):
        run_chunk(start, min(prefix_len, start + stage_tokens), "cpu")

    for start in range(prefix_len, seq_len, stage_tokens):
        run_chunk(start, min(seq_len, start + stage_tokens), "gpu")

    assert staged_out is not None
    assert staged_lse is not None

    max_output_vs_paged = float((staged_out - paged_out).abs().max().item())
    max_output_vs_dense_full = float(
        (staged_out - dense_full_out).abs().max().item()
    )
    max_lse_vs_dense_full = float(
        (staged_lse.float() - dense_full_lse.float()).abs().max().item()
    )
    paged_dense_output_error = float((paged_out - dense_full_out).abs().max().item())
    paged_dense_lse_error = float(
        (paged_lse.float() - dense_full_lse.float()).abs().max().item()
    )

    return {
        "ok": bool(
            max_output_vs_paged <= args.output_tolerance
            and max_output_vs_dense_full <= args.output_tolerance
            and max_lse_vs_dense_full <= args.lse_tolerance
        ),
        "device": str(device),
        "dtype": args.dtype,
        "seed": args.seed,
        "queries": args.queries,
        "heads": args.heads,
        "head_size": args.head_size,
        "block_size": args.block_size,
        "blocks": args.blocks,
        "seq_len": seq_len,
        "prefix_blocks": args.prefix_blocks,
        "prefix_len": prefix_len,
        "suffix_len": suffix_len,
        "stage_tokens": stage_tokens,
        "pin_memory_requested": args.pin_memory,
        "cpu_key_is_pinned": bool(cpu_prefix_key.is_pinned()),
        "cpu_value_is_pinned": bool(cpu_prefix_value.is_pinned()),
        "cpu_kv_bytes": int(
            (cpu_prefix_key.numel() + cpu_prefix_value.numel())
            * cpu_prefix_key.element_size()
        ),
        "total_stage_copy_bytes": int(total_copy_bytes),
        "total_stage_copy_seconds": total_copy_seconds,
        "total_stage_copy_gbps": gbps(total_copy_bytes, total_copy_seconds),
        "total_stage_attention_seconds": total_attention_seconds,
        "chunk_reports": chunk_reports,
        "paged_dense_output_error": paged_dense_output_error,
        "paged_dense_lse_error": paged_dense_lse_error,
        "max_output_vs_paged": max_output_vs_paged,
        "max_output_vs_dense_full": max_output_vs_dense_full,
        "max_lse_vs_dense_full": max_lse_vs_dense_full,
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
    parser.add_argument("--blocks", type=int, default=16)
    parser.add_argument("--prefix-blocks", type=int, default=8)
    parser.add_argument("--stage-tokens", type=int, default=2048)
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument("--warmup-calls", type=int, default=2)
    parser.add_argument("--pin-memory", action="store_true")
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
