#!/usr/bin/env python3
"""Validate the native XPU paged TreeAttention DDTree kernel.

This is a kernel diagnostic, not a headline throughput benchmark. It compares
the native op against PyTorch math SDPA, verifies that one captured XPU graph
observes updated seq_len/tree-mask tensors, and reports direct operator latency.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--library",
        type=Path,
        default=Path(
            "/home/steve/src/vllm-xpu-kernels/build/"
            "qwen27-replayssm-transaction-20260710/_xpu_C.abi3.so"
        ),
    )
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--block-size", type=int, default=64)
    parser.add_argument("--num-blocks", type=int, default=16)
    parser.add_argument("--graph-ops", type=int, default=1)
    parser.add_argument("--atol", type=float, default=0.015625)
    parser.add_argument("--rtol", type=float, default=0.02)
    parser.add_argument("--require-graph", action="store_true")
    return parser.parse_args()


def tree_bias_from_parents(torch: Any, parents: list[int], device: Any) -> Any:
    size = len(parents)
    bias = torch.full((size, size), -torch.inf, dtype=torch.float32)
    for row in range(size):
        cursor = row
        seen = 0
        while cursor >= 0:
            bias[row, cursor] = 0.0
            cursor = parents[cursor]
            seen += 1
            if seen > size:
                raise ValueError("parent cycle")
    return bias.to(device=device)


def gather_cache(torch: Any, cache: Any, block_table: Any, seq_len: int) -> Any:
    block_size = cache.shape[1]
    blocks = math.ceil(seq_len / block_size)
    ids = block_table[0, :blocks].to(torch.long)
    return cache.index_select(0, ids).reshape(-1, cache.shape[2], cache.shape[3])[
        :seq_len
    ]


def reference(
    torch: Any,
    query: Any,
    key_cache: Any,
    value_cache: Any,
    block_table: Any,
    seq_len: int,
    tree_bias: Any,
    scale: float,
) -> Any:
    import torch.nn.functional as F

    query_len = query.shape[0]
    context_len = seq_len - query_len
    keys = gather_cache(torch, key_cache, block_table, seq_len)
    values = gather_cache(torch, value_cache, block_table, seq_len)
    context_keep = torch.ones(
        (query_len, context_len), dtype=torch.bool, device=query.device
    )
    tree_keep = torch.isfinite(tree_bias)
    keep = torch.cat((context_keep, tree_keep), dim=1).view(
        1, 1, query_len, seq_len
    )
    q = query.permute(1, 0, 2).unsqueeze(0)
    k = keys.permute(1, 0, 2).unsqueeze(0)
    v = values.permute(1, 0, 2).unsqueeze(0)
    with torch.nn.attention.sdpa_kernel(torch.nn.attention.SDPBackend.MATH):
        result = F.scaled_dot_product_attention(
            q,
            k,
            v,
            attn_mask=keep,
            dropout_p=0.0,
            is_causal=False,
            scale=scale,
            enable_gqa=q.shape[1] != k.shape[1],
        )
    return result.squeeze(0).permute(1, 0, 2).contiguous()


def compare(torch: Any, candidate: Any, expected: Any, atol: float, rtol: float) -> dict:
    delta = (candidate.float() - expected.float()).abs()
    return {
        "passed": bool(torch.allclose(candidate, expected, atol=atol, rtol=rtol)),
        "max_abs": float(delta.max().item()),
        "mean_abs": float(delta.mean().item()),
        "p99_abs": float(torch.quantile(delta.flatten(), 0.99).item()),
        "candidate_checksum": float(candidate.float().sum().item()),
        "expected_checksum": float(expected.float().sum().item()),
    }


def main() -> int:
    args = parse_args()
    import torch

    if not args.library.is_file():
        raise FileNotFoundError(args.library)
    torch.ops.load_library(str(args.library))
    torch.manual_seed(args.seed)
    device = torch.device("xpu:0")
    dtype = torch.bfloat16
    query_len, query_heads, kv_heads, head_size = 16, 24, 4, 256
    block_size, num_blocks = args.block_size, args.num_blocks
    if block_size < query_len or num_blocks < 1 or args.graph_ops < 1:
        raise ValueError("block-size, num-blocks, and graph-ops must cover the query")
    scale = head_size**-0.5

    query = torch.randn(
        query_len, query_heads, head_size, dtype=dtype, device=device
    )
    # Interleave K/V planes so each cache view is strided like vLLM's NHD
    # cache while retaining a contiguous head dimension.
    kv_storage = torch.randn(
        num_blocks,
        block_size,
        kv_heads,
        2,
        head_size,
        dtype=dtype,
        device=device,
    )
    key_cache = kv_storage[:, :, :, 0, :]
    value_cache = kv_storage[:, :, :, 1, :]
    block_order = torch.randperm(num_blocks, dtype=torch.int32, device=device).view(
        1, -1
    )
    seq_lens = torch.tensor([query_len], dtype=torch.int32, device=device)
    parents_a = [-1] + [max(0, (index - 1) // 2) for index in range(1, query_len)]
    parents_b = [-1] + [index - 1 for index in range(1, query_len)]
    tree_bias = tree_bias_from_parents(torch, parents_a, device)
    output = torch.empty_like(query)

    max_seq_len = block_size * num_blocks
    case_lengths = sorted(
        {
            query_len,
            min(29, max_seq_len),
            min(max(query_len, block_size - 1), max_seq_len),
            min(block_size + 1, max_seq_len),
            min(2 * block_size - 1, max_seq_len),
        }
    )
    cases = []
    for case_index, seq_len in enumerate(case_lengths):
        parents = parents_a if case_index % 2 == 0 else parents_b
        live_bias = tree_bias_from_parents(torch, parents, device)
        seq_lens.fill_(seq_len)
        tree_bias.copy_(live_bias)
        torch.ops._xpu_C.paged_tree_attention_xpu(
            output,
            query,
            key_cache,
            value_cache,
            block_order,
            seq_lens,
            tree_bias,
            scale,
        )
        expected = reference(
            torch,
            query,
            key_cache,
            value_cache,
            block_order,
            seq_len,
            tree_bias,
            scale,
        )
        torch.xpu.synchronize()
        comparison = compare(torch, output, expected, args.atol, args.rtol)
        comparison["seq_len"] = seq_len
        comparison["multi_page"] = seq_len > block_size
        cases.append(comparison)

    graph_result: dict[str, Any]
    if hasattr(torch.xpu, "XPUGraph") and hasattr(torch.xpu, "graph"):
        seq_lens.fill_(127)
        tree_bias.copy_(tree_bias_from_parents(torch, parents_a, device))
        for _ in range(3):
            for _ in range(args.graph_ops):
                torch.ops._xpu_C.paged_tree_attention_xpu(
                    output,
                    query,
                    key_cache,
                    value_cache,
                    block_order,
                    seq_lens,
                    tree_bias,
                    scale,
                )
        torch.xpu.synchronize()
        graph = torch.xpu.XPUGraph()
        try:
            with torch.xpu.graph(graph):
                for _ in range(args.graph_ops):
                    torch.ops._xpu_C.paged_tree_attention_xpu(
                        output,
                        query,
                        key_cache,
                        value_cache,
                        block_order,
                        seq_lens,
                        tree_bias,
                        scale,
                    )
            torch.xpu.synchronize()
            replay_seq_len = min(max_seq_len, block_size + 511)
            seq_lens.fill_(replay_seq_len)
            tree_bias.copy_(tree_bias_from_parents(torch, parents_b, device))
            expected = reference(
                torch,
                query,
                key_cache,
                value_cache,
                block_order,
                replay_seq_len,
                tree_bias,
                scale,
            )
            output.zero_()
            torch.xpu.synchronize()
            graph.replay()
            torch.xpu.synchronize()
            graph_result = compare(torch, output, expected, args.atol, args.rtol)
            graph_result["status"] = "executed"
            graph_result["dynamic_seq_len"] = replay_seq_len
            graph_result["dynamic_tree"] = True
            graph_result["captured_ops"] = args.graph_ops
        except Exception as exc:  # noqa: BLE001 - diagnostic captures failure.
            graph_result = {
                "status": "error",
                "passed": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
    else:
        graph_result = {"status": "unsupported", "passed": not args.require_graph}

    seq_lens.fill_(511)
    tree_bias.copy_(tree_bias_from_parents(torch, parents_a, device))
    for _ in range(args.warmup):
        torch.ops._xpu_C.paged_tree_attention_xpu(
            output,
            query,
            key_cache,
            value_cache,
            block_order,
            seq_lens,
            tree_bias,
            scale,
        )
    torch.xpu.synchronize()
    start = time.perf_counter()
    for _ in range(args.repeats):
        torch.ops._xpu_C.paged_tree_attention_xpu(
            output,
            query,
            key_cache,
            value_cache,
            block_order,
            seq_lens,
            tree_bias,
            scale,
        )
    torch.xpu.synchronize()
    latency_ms = (time.perf_counter() - start) * 1000.0 / args.repeats

    result = {
        "library": str(args.library.resolve()),
        "device": torch.xpu.get_device_name(0),
        "torch": torch.__version__,
        "dtype": str(dtype),
        "shape": {
            "query_len": query_len,
            "query_heads": query_heads,
            "kv_heads": kv_heads,
            "head_size": head_size,
            "block_size": block_size,
            "num_blocks": num_blocks,
            "graph_ops": args.graph_ops,
            "cache_contiguous": key_cache.is_contiguous(),
            "cache_stride": list(key_cache.stride()),
        },
        "tolerance": {"atol": args.atol, "rtol": args.rtol},
        "cases": cases,
        "graph_replay": graph_result,
        "latency_ms_seq511": latency_ms,
    }
    result["passed"] = all(case["passed"] for case in cases) and bool(
        graph_result["passed"]
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
