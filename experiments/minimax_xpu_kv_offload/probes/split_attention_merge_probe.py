#!/usr/bin/env python3
"""Validate chunked attention merge math for CPU-paged attention R&D.

This is intentionally independent of vLLM. It checks the core idea needed for
exact CPU-paged attention:

1. compute attention over all K/V at once
2. compute attention over K/V chunks separately, returning output + LSE
3. merge the chunk outputs with log-sum-exp weights

If the merged result matches the full result, then the math behind a staged
GPU-scratch implementation is sound. Kernel integration and scheduler work are
separate problems.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch


def attention_out_lse(
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    scale: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return attention output and per-head/per-query LSE.

    query: [num_queries, num_heads, head_size]
    key: [num_kv_tokens, num_heads, head_size]
    value: [num_kv_tokens, num_heads, head_size]
    output: [num_queries, num_heads, head_size]
    lse: [num_heads, num_queries]
    """
    q = query.float()
    k = key.float()
    v = value.float()
    scores = torch.einsum("qhd,khd->hqk", q, k) * scale
    lse = torch.logsumexp(scores, dim=-1)
    probs = torch.softmax(scores, dim=-1)
    output = torch.einsum("hqk,khd->qhd", probs, v)
    return output, lse


def merge_attention_states(
    left_output: torch.Tensor,
    left_lse: torch.Tensor,
    right_output: torch.Tensor,
    right_lse: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Merge two attention partials exactly using their LSE values."""
    merged_lse = torch.logaddexp(left_lse, right_lse)
    left_weight = torch.exp(left_lse - merged_lse).transpose(0, 1).unsqueeze(-1)
    right_weight = torch.exp(right_lse - merged_lse).transpose(0, 1).unsqueeze(-1)
    merged_output = (left_output * left_weight) + (right_output * right_weight)
    return merged_output, merged_lse


def split_sizes(total: int, chunks: int) -> list[int]:
    base = total // chunks
    rem = total % chunks
    return [base + (1 if idx < rem else 0) for idx in range(chunks)]


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    torch.manual_seed(args.seed)

    device = torch.device(args.device)
    dtype = getattr(torch, args.dtype)
    scale = args.scale if args.scale is not None else args.head_size**-0.5

    query = torch.randn(
        args.queries,
        args.heads,
        args.head_size,
        device=device,
        dtype=dtype,
    )
    key = torch.randn(
        args.kv_tokens,
        args.heads,
        args.head_size,
        device=device,
        dtype=dtype,
    )
    value = torch.randn(
        args.kv_tokens,
        args.heads,
        args.head_size,
        device=device,
        dtype=dtype,
    )

    full_output, full_lse = attention_out_lse(query, key, value, scale)

    offset = 0
    merged_output: torch.Tensor | None = None
    merged_lse: torch.Tensor | None = None
    chunk_reports: list[dict[str, Any]] = []
    for chunk_index, size in enumerate(split_sizes(args.kv_tokens, args.chunks)):
        if size == 0:
            continue
        chunk_key = key[offset : offset + size]
        chunk_value = value[offset : offset + size]
        chunk_output, chunk_lse = attention_out_lse(
            query,
            chunk_key,
            chunk_value,
            scale,
        )
        chunk_reports.append(
            {
                "chunk_index": chunk_index,
                "start": offset,
                "tokens": size,
            }
        )
        if merged_output is None:
            merged_output = chunk_output
            merged_lse = chunk_lse
        else:
            assert merged_lse is not None
            merged_output, merged_lse = merge_attention_states(
                merged_output,
                merged_lse,
                chunk_output,
                chunk_lse,
            )
        offset += size

    assert merged_output is not None
    assert merged_lse is not None

    output_diff = (full_output - merged_output).abs()
    lse_diff = (full_lse - merged_lse).abs()
    max_output = full_output.abs().max().item()
    max_lse = full_lse.abs().max().item()
    max_output_abs_error = output_diff.max().item()
    max_lse_abs_error = lse_diff.max().item()

    return {
        "ok": bool(
            max_output_abs_error <= args.output_tolerance
            and max_lse_abs_error <= args.lse_tolerance
        ),
        "device": str(device),
        "dtype": args.dtype,
        "seed": args.seed,
        "queries": args.queries,
        "heads": args.heads,
        "head_size": args.head_size,
        "kv_tokens": args.kv_tokens,
        "chunks": args.chunks,
        "scale": scale,
        "chunk_reports": chunk_reports,
        "max_output_abs_error": max_output_abs_error,
        "max_output_relative_error": max_output_abs_error / max(max_output, 1e-12),
        "max_lse_abs_error": max_lse_abs_error,
        "max_lse_relative_error": max_lse_abs_error / max(max_lse, 1e-12),
        "output_tolerance": args.output_tolerance,
        "lse_tolerance": args.lse_tolerance,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--dtype", default="float32")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--queries", type=int, default=4)
    parser.add_argument("--heads", type=int, default=8)
    parser.add_argument("--head-size", type=int, default=128)
    parser.add_argument("--kv-tokens", type=int, default=4096)
    parser.add_argument("--chunks", type=int, default=8)
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument("--output-tolerance", type=float, default=1e-5)
    parser.add_argument("--lse-tolerance", type=float, default=1e-5)
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
