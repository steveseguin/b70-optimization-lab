#!/usr/bin/env python3
"""Validate and time Qwen27-shaped dynamic tree attention on Intel XPU.

This is a kernel diagnostic, not endpoint throughput. It calls vLLM's unified
attention kernel with a runtime parent-derived query/query bias, compares every
tree row with an independent FP32 path replay, and measures the incremental
cost versus an invalid flattened causal sequence.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Callable

import torch
import torch.nn.functional as F

from vllm.v1.attention.ops.triton_unified_attention import unified_attention


CLASSIFICATION = "diagnostic_tree_attention_not_endpoint_not_localmaxxing"
TREE_SHAPES = {
    "ddtree16": (
        -1,
        0,
        0,
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        5,
        5,
        6,
        7,
        10,
        14,
    ),
    "ddtree33": (
        -1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1,
        1,
        1,
        2,
        2,
        3,
        4,
        5,
        9,
        9,
        10,
        11,
        12,
        14,
        16,
        17,
        17,
        18,
        20,
        23,
        24,
        25,
        28,
        29,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--shape", choices=tuple(TREE_SHAPES), default="ddtree16")
    parser.add_argument("--context-len", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=24)
    parser.add_argument("--num-kv-heads", type=int, default=4)
    parser.add_argument("--head-size", type=int, default=256)
    parser.add_argument("--block-size", type=int, default=32)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--calls-per-sample", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--atol", type=float, default=0.01)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    for name in (
        "context_len",
        "num_heads",
        "num_kv_heads",
        "head_size",
        "block_size",
        "samples",
        "calls_per_sample",
    ):
        if getattr(args, name) <= 0:
            raise SystemExit(f"--{name.replace('_', '-')} must be positive")
    if args.warmup < 0:
        raise SystemExit("--warmup must be non-negative")
    if args.num_heads % args.num_kv_heads:
        raise SystemExit("--num-heads must be divisible by --num-kv-heads")
    if args.atol < 0:
        raise SystemExit("--atol must be non-negative")


def build_tree_bias(parents: tuple[int, ...], device: torch.device) -> torch.Tensor:
    rows = len(parents)
    bias = torch.full((rows, rows), -torch.inf, dtype=torch.float32, device=device)
    for row in range(rows):
        node = row
        while node >= 0:
            bias[row, node] = 0.0
            node = parents[node]
    return bias


def tree_paths(parents: tuple[int, ...]) -> list[list[int]]:
    paths: list[list[int]] = []
    for row in range(len(parents)):
        path: list[int] = []
        node = row
        while node >= 0:
            path.append(node)
            node = parents[node]
        paths.append(list(reversed(path)))
    return paths


def independent_path_attention(
    q: torch.Tensor,
    key_cache: torch.Tensor,
    value_cache: torch.Tensor,
    parents: tuple[int, ...],
    context_len: int,
    scale: float,
) -> torch.Tensor:
    """Replay each query against context plus only its tree ancestors."""

    flat_k = key_cache.reshape(-1, key_cache.shape[-2], key_cache.shape[-1])
    flat_v = value_cache.reshape(-1, value_cache.shape[-2], value_cache.shape[-1])
    num_heads = q.shape[1]
    num_kv_heads = flat_k.shape[1]
    kv_head_for_query = torch.arange(num_heads, device=q.device) // (
        num_heads // num_kv_heads
    )
    context_indices = torch.arange(context_len, device=q.device)
    outputs: list[torch.Tensor] = []
    for row, path in enumerate(tree_paths(parents)):
        tree_indices = context_len + torch.tensor(path, device=q.device)
        indices = torch.cat((context_indices, tree_indices))
        keys = flat_k.index_select(0, indices)[:, kv_head_for_query].float()
        values = flat_v.index_select(0, indices)[:, kv_head_for_query].float()
        query = q[row].float()
        scores = torch.einsum("hd,lhd->hl", query, keys) * scale
        probabilities = torch.softmax(scores, dim=-1)
        outputs.append(torch.einsum("hl,lhd->hd", probabilities, values))
    return torch.stack(outputs).to(q.dtype)


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "p10": percentile(values, 0.10),
        "p90": percentile(values, 0.90),
        "min": min(values),
        "max": max(values),
        "population_stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
    }


def benchmark(
    call: Callable[[], None],
    *,
    device: torch.device,
    warmup: int,
    samples: int,
    calls_per_sample: int,
) -> dict[str, Any]:
    for _ in range(warmup):
        call()
    torch.xpu.synchronize(device)
    samples_ms: list[float] = []
    for _ in range(samples):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(calls_per_sample):
            call()
        end.record()
        end.synchronize()
        samples_ms.append(float(start.elapsed_time(end)) / calls_per_sample)
    return {
        "timer": "XPU event; reusable tensors; allocations excluded",
        "warmup_calls": warmup,
        "samples": samples,
        "calls_per_sample": calls_per_sample,
        "per_call_ms": summarize(samples_ms),
    }


def main() -> int:
    args = parse_args()
    validate_args(args)
    device = torch.device(args.device)
    if device.type != "xpu" or not torch.xpu.is_available():
        raise SystemExit("This diagnostic requires an available XPU device")
    torch.xpu.set_device(device)
    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)

    parents = TREE_SHAPES[args.shape]
    query_rows = len(parents)
    total_kv_tokens = args.context_len + query_rows
    num_blocks = (total_kv_tokens + args.block_size - 1) // args.block_size
    dtype = torch.bfloat16
    q = torch.randn(
        query_rows,
        args.num_heads,
        args.head_size,
        dtype=dtype,
        device=device,
    )
    key_cache = torch.randn(
        num_blocks,
        args.block_size,
        args.num_kv_heads,
        args.head_size,
        dtype=dtype,
        device=device,
    )
    value_cache = torch.randn_like(key_cache)
    tree_out = torch.empty_like(q)
    flat_out = torch.empty_like(q)
    bool_sdpa_out = torch.empty_like(q)
    float_sdpa_out = torch.empty_like(q)
    query_start_loc = torch.tensor([0, query_rows], dtype=torch.int32, device=device)
    seq_lens = torch.tensor([total_kv_tokens], dtype=torch.int32, device=device)
    block_table = torch.arange(num_blocks, dtype=torch.int32, device=device).view(1, -1)
    tree_bias = build_tree_bias(parents, device)
    context_keep = torch.ones(
        (query_rows, args.context_len), dtype=torch.bool, device=device
    )
    bool_keep_mask = torch.cat((context_keep, torch.isfinite(tree_bias)), dim=1).view(
        1, 1, query_rows, total_kv_tokens
    )
    float_additive_mask = torch.where(
        bool_keep_mask,
        torch.tensor(0.0, device=device),
        torch.tensor(-torch.inf, device=device),
    )
    scale = args.head_size**-0.5

    def call(out: torch.Tensor, bias: torch.Tensor | None) -> None:
        unified_attention(
            q=q,
            k=key_cache,
            v=value_cache,
            out=out,
            cu_seqlens_q=query_start_loc,
            max_seqlen_q=query_rows,
            seqused_k=seq_lens,
            max_seqlen_k=total_kv_tokens,
            softmax_scale=scale,
            causal=True,
            window_size=(-1, -1),
            block_table=block_table,
            softcap=0.0,
            q_descale=None,
            k_descale=None,
            v_descale=None,
            qq_bias=bias,
        )

    def call_sdpa(out: torch.Tensor, mask: torch.Tensor) -> None:
        block_ids = block_table[0, :num_blocks]
        keys = key_cache.index_select(0, block_ids).reshape(
            -1, args.num_kv_heads, args.head_size
        )[:total_kv_tokens]
        values = value_cache.index_select(0, block_ids).reshape(
            -1, args.num_kv_heads, args.head_size
        )[:total_kv_tokens]
        result = F.scaled_dot_product_attention(
            q.permute(1, 0, 2).unsqueeze(0),
            keys.permute(1, 0, 2).unsqueeze(0),
            values.permute(1, 0, 2).unsqueeze(0),
            attn_mask=mask,
            dropout_p=0.0,
            is_causal=False,
            scale=scale,
            enable_gqa=args.num_heads != args.num_kv_heads,
        )
        out.copy_(result.squeeze(0).permute(1, 0, 2))

    call(tree_out, tree_bias)
    call(flat_out, None)
    call_sdpa(bool_sdpa_out, bool_keep_mask)
    call_sdpa(float_sdpa_out, float_additive_mask)
    torch.xpu.synchronize(device)
    reference = independent_path_attention(
        q, key_cache, value_cache, parents, args.context_len, scale
    )
    torch.xpu.synchronize(device)

    error = (tree_out.float() - reference.float()).abs()
    bool_sdpa_error = (bool_sdpa_out.float() - reference.float()).abs()
    float_sdpa_error = (float_sdpa_out.float() - reference.float()).abs()
    flat_delta = (flat_out.float() - tree_out.float()).abs()
    max_abs = float(error.max().item())
    mean_abs = float(error.mean().item())
    bool_sdpa_max_abs = float(bool_sdpa_error.max().item())
    bool_sdpa_mean_abs = float(bool_sdpa_error.mean().item())
    float_sdpa_max_abs = float(float_sdpa_error.max().item())
    flat_max_abs = float(flat_delta.max().item())
    correctness_passed = bool(
        torch.isfinite(tree_out).all().item()
        and torch.allclose(tree_out.float(), reference.float(), atol=args.atol, rtol=0)
        and torch.isfinite(bool_sdpa_out).all().item()
        and torch.allclose(
            bool_sdpa_out.float(), reference.float(), atol=args.atol, rtol=0
        )
        and float_sdpa_max_abs > args.atol
        and flat_max_abs > args.atol
    )

    tree_timing = benchmark(
        lambda: call(tree_out, tree_bias),
        device=device,
        warmup=args.warmup,
        samples=args.samples,
        calls_per_sample=args.calls_per_sample,
    )
    flat_timing = benchmark(
        lambda: call(flat_out, None),
        device=device,
        warmup=args.warmup,
        samples=args.samples,
        calls_per_sample=args.calls_per_sample,
    )
    bool_sdpa_timing = benchmark(
        lambda: call_sdpa(bool_sdpa_out, bool_keep_mask),
        device=device,
        warmup=args.warmup,
        samples=args.samples,
        calls_per_sample=args.calls_per_sample,
    )
    float_sdpa_timing = benchmark(
        lambda: call_sdpa(float_sdpa_out, float_additive_mask),
        device=device,
        warmup=args.warmup,
        samples=args.samples,
        calls_per_sample=args.calls_per_sample,
    )
    tree_median = tree_timing["per_call_ms"]["median"]
    flat_median = flat_timing["per_call_ms"]["median"]

    result = {
        "schema": "qwen27_xpu_tree_attention_v2",
        "classification": CLASSIFICATION,
        "benchmark": False,
        "localmaxxing_eligible": False,
        "passed": correctness_passed,
        "device": {
            "requested": args.device,
            "name": torch.xpu.get_device_name(device.index or 0),
            "torch_version": torch.__version__,
        },
        "shape": args.shape,
        "parents": list(parents),
        "tree_paths": tree_paths(parents),
        "config": {
            "context_len": args.context_len,
            "query_rows": query_rows,
            "num_heads": args.num_heads,
            "num_kv_heads": args.num_kv_heads,
            "head_size": args.head_size,
            "block_size": args.block_size,
            "dtype": str(dtype),
            "seed": args.seed,
        },
        "correctness": {
            "reference": "independent FP32 context-plus-root-to-node replay",
            "atol": args.atol,
            "max_abs_diff": max_abs,
            "mean_abs_diff": mean_abs,
            "bool_sdpa_max_abs_diff": bool_sdpa_max_abs,
            "bool_sdpa_mean_abs_diff": bool_sdpa_mean_abs,
            "float_sdpa_max_abs_diff": float_sdpa_max_abs,
            "float_sdpa_expected": "fail: XPU fast SDPA misapplies additive mask",
            "flattened_causal_negative_control_max_abs_diff": flat_max_abs,
            "passed": correctness_passed,
        },
        "tree_timing": tree_timing,
        "flattened_causal_timing": flat_timing,
        "bool_sdpa_paged_gather_timing": bool_sdpa_timing,
        "float_sdpa_invalid_timing": float_sdpa_timing,
        "tree_minus_flat_median_ms": tree_median - flat_median,
        "projected_16_attention_layers_tree_ms": tree_median * 16,
        "projected_16_attention_layers_bool_sdpa_ms": (
            bool_sdpa_timing["per_call_ms"]["median"] * 16
        ),
        "validity": (
            "Dynamic tree mask kernel diagnostic only; no model, endpoint, "
            "generation throughput, or quality claim."
        ),
    }
    encoded = json.dumps(result, indent=2 if args.pretty else None, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if correctness_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
