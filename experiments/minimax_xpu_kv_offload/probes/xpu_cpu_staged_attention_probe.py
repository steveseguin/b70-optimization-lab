#!/usr/bin/env python3
"""Probe CPU-staged XPU paged attention for active-KV overflow R&D.

This is a standalone feasibility probe for the "system RAM as older KV"
direction. It creates a synthetic paged KV cache on XPU, copies the older
prefix pages to CPU RAM, stages those pages back through a small XPU scratch
cache in chunks, runs FlashAttention for each chunk, and merges the partial
attention states.

It does not patch vLLM scheduling. Passing this probe only means the attention
data path is plausible; the production server still needs logical-vs-physical
KV accounting before a single active request can exceed live GPU KV capacity.
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


def gbps(num_bytes: int, seconds: float) -> float | None:
    if seconds <= 0:
        return None
    return num_bytes / seconds / 1e9


def warm_attention_shape(
    *,
    query: torch.Tensor,
    key_cache: torch.Tensor,
    value_cache: torch.Tensor,
    block_table: torch.Tensor,
    seq_len: int,
    max_seq_len: int,
    causal: bool,
    scale: float,
    repeats: int,
) -> None:
    for _ in range(repeats):
        run_attention(
            query=query,
            key_cache=key_cache,
            value_cache=value_cache,
            block_table=block_table,
            seq_len=seq_len,
            max_seq_len=max_seq_len,
            causal=causal,
            scale=scale,
        )
    torch.xpu.synchronize()


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
    if args.stage_blocks <= 0:
        raise ValueError("--stage-blocks must be positive")

    seq_len = args.blocks * args.block_size
    prefix_len = args.prefix_blocks * args.block_size
    suffix_blocks = args.blocks - args.prefix_blocks
    suffix_len = suffix_blocks * args.block_size
    stage_blocks = min(args.stage_blocks, args.prefix_blocks)

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
    full_block_table = torch.arange(
        args.blocks, dtype=torch.int32, device=device
    ).view(1, args.blocks)
    suffix_block_table = full_block_table[:, args.prefix_blocks :]

    # Warm the full path separately so kernel setup is not mixed into staged
    # correctness. XPU FA2 paged decode has shown first-call anomalies for split
    # suffix shapes, so the staged path also has explicit shape warmups below.
    warm_attention_shape(
        query=query,
        key_cache=key_cache,
        value_cache=value_cache,
        block_table=full_block_table,
        seq_len=seq_len,
        max_seq_len=seq_len,
        causal=True,
        scale=scale,
        repeats=args.warmup_calls,
    )
    full_out, full_lse = run_attention(
        query=query,
        key_cache=key_cache,
        value_cache=value_cache,
        block_table=full_block_table,
        seq_len=seq_len,
        max_seq_len=seq_len,
        causal=True,
        scale=scale,
    )

    cpu_key = allocate_cpu_like(key_cache[: args.prefix_blocks], args.pin_memory)
    cpu_value = allocate_cpu_like(value_cache[: args.prefix_blocks], args.pin_memory)
    cpu_key.copy_(key_cache[: args.prefix_blocks], non_blocking=True)
    cpu_value.copy_(value_cache[: args.prefix_blocks], non_blocking=True)
    torch.xpu.synchronize()

    scratch_key = torch.empty(
        stage_blocks,
        args.block_size,
        args.heads,
        args.head_size,
        device=device,
        dtype=dtype,
    )
    scratch_value = torch.empty_like(scratch_key)
    scratch_block_table = torch.arange(
        stage_blocks, dtype=torch.int32, device=device
    ).view(1, stage_blocks)

    # Warm both a scratch-prefix shape and the live suffix shape. This is
    # intentionally counted outside staged transfer/attention timing.
    warm_prefix_blocks = min(stage_blocks, args.prefix_blocks)
    scratch_key[:warm_prefix_blocks].copy_(
        cpu_key[:warm_prefix_blocks], non_blocking=True
    )
    scratch_value[:warm_prefix_blocks].copy_(
        cpu_value[:warm_prefix_blocks], non_blocking=True
    )
    torch.xpu.synchronize()
    warm_attention_shape(
        query=query,
        key_cache=scratch_key,
        value_cache=scratch_value,
        block_table=scratch_block_table[:, :warm_prefix_blocks],
        seq_len=warm_prefix_blocks * args.block_size,
        max_seq_len=warm_prefix_blocks * args.block_size,
        causal=False,
        scale=scale,
        repeats=args.warmup_calls,
    )
    warm_attention_shape(
        query=query,
        key_cache=key_cache,
        value_cache=value_cache,
        block_table=suffix_block_table,
        seq_len=suffix_len,
        max_seq_len=suffix_len,
        causal=args.suffix_causal,
        scale=scale,
        repeats=args.warmup_calls,
    )

    staged_out: torch.Tensor | None = None
    staged_lse: torch.Tensor | None = None
    chunk_reports: list[dict[str, Any]] = []
    total_copy_bytes = 0
    total_copy_seconds = 0.0
    total_attention_seconds = 0.0

    for start_block in range(0, args.prefix_blocks, stage_blocks):
        chunk_blocks = min(stage_blocks, args.prefix_blocks - start_block)
        chunk_len = chunk_blocks * args.block_size
        chunk_block_table = scratch_block_table[:, :chunk_blocks]

        torch.xpu.synchronize()
        copy_start = time.perf_counter()
        scratch_key[:chunk_blocks].copy_(
            cpu_key[start_block : start_block + chunk_blocks], non_blocking=True
        )
        scratch_value[:chunk_blocks].copy_(
            cpu_value[start_block : start_block + chunk_blocks], non_blocking=True
        )
        torch.xpu.synchronize()
        copy_seconds = time.perf_counter() - copy_start

        attn_start = time.perf_counter()
        chunk_out, chunk_lse = run_attention(
            query=query,
            key_cache=scratch_key,
            value_cache=scratch_value,
            block_table=chunk_block_table,
            seq_len=chunk_len,
            max_seq_len=chunk_len,
            causal=False,
            scale=scale,
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
            cpu_key[start_block : start_block + chunk_blocks].numel()
            + cpu_value[start_block : start_block + chunk_blocks].numel()
        ) * cpu_key.element_size()
        total_copy_bytes += copy_bytes
        total_copy_seconds += copy_seconds
        total_attention_seconds += attn_seconds
        chunk_reports.append(
            {
                "start_block": start_block,
                "blocks": chunk_blocks,
                "tokens": chunk_len,
                "copy_seconds": copy_seconds,
                "copy_gbps": gbps(copy_bytes, copy_seconds),
                "attention_seconds": attn_seconds,
            }
        )

    suffix_start = time.perf_counter()
    suffix_out, suffix_lse = run_attention(
        query=query,
        key_cache=key_cache,
        value_cache=value_cache,
        block_table=suffix_block_table,
        seq_len=suffix_len,
        max_seq_len=suffix_len,
        causal=args.suffix_causal,
        scale=scale,
    )
    staged_out, staged_lse = merge_pair(
        staged_out,
        staged_lse,
        suffix_out,
        suffix_lse,
    )
    torch.xpu.synchronize()
    suffix_seconds = time.perf_counter() - suffix_start

    assert staged_out is not None
    assert staged_lse is not None
    output_abs_error = (staged_out - full_out).abs()
    lse_abs_error = (staged_lse.float() - full_lse.float()).abs()
    max_output_abs_error = float(output_abs_error.max().item())
    max_lse_abs_error = float(lse_abs_error.max().item())

    return {
        "ok": bool(
            max_output_abs_error <= args.output_tolerance
            and (args.ignore_lse or max_lse_abs_error <= args.lse_tolerance)
        ),
        "ignore_lse": args.ignore_lse,
        "device": str(device),
        "dtype": args.dtype,
        "seed": args.seed,
        "queries": args.queries,
        "heads": args.heads,
        "head_size": args.head_size,
        "block_size": args.block_size,
        "blocks": args.blocks,
        "prefix_blocks": args.prefix_blocks,
        "suffix_blocks": suffix_blocks,
        "stage_blocks": stage_blocks,
        "suffix_causal": args.suffix_causal,
        "seq_len": seq_len,
        "prefix_len": prefix_len,
        "suffix_len": suffix_len,
        "scale": scale,
        "pin_memory_requested": args.pin_memory,
        "cpu_key_is_pinned": bool(cpu_key.is_pinned()),
        "cpu_value_is_pinned": bool(cpu_value.is_pinned()),
        "cpu_kv_bytes": int((cpu_key.numel() + cpu_value.numel()) * cpu_key.element_size()),
        "total_stage_copy_bytes": int(total_copy_bytes),
        "total_stage_copy_seconds": total_copy_seconds,
        "total_stage_copy_gbps": gbps(total_copy_bytes, total_copy_seconds),
        "total_stage_attention_seconds": total_attention_seconds,
        "suffix_attention_seconds": suffix_seconds,
        "chunk_reports": chunk_reports,
        "max_output_abs_error": max_output_abs_error,
        "max_lse_abs_error": max_lse_abs_error,
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
    parser.add_argument("--prefix-blocks", type=int, default=4)
    parser.add_argument("--stage-blocks", type=int, default=2)
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument("--warmup-calls", type=int, default=2)
    parser.add_argument("--suffix-causal", action="store_true")
    parser.add_argument("--pin-memory", action="store_true")
    parser.add_argument("--ignore-lse", action="store_true")
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
