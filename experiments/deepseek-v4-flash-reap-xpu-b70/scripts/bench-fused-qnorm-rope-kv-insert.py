#!/usr/bin/env python3
"""Exact and timing gate for the M=1 fused QNorm/RoPE/KV-insert boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

from vllm.models.deepseek_v4.xpu.xpu_qnorm_rope_kv_fp8_insert import (
    xpu_qnorm_rope_kv_fp8_insert,
    xpu_qnorm_rope_kv_fp8_insert_fused,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--heads", type=int, default=16)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-iterations", type=int, default=100)
    parser.add_argument("--layers", type=int, default=43)
    parser.add_argument("--gate-ms-per-token", type=float, default=0.50)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    torch.manual_seed(20260715)
    device = torch.device(args.device)
    head_dim = 512
    rope_dim = 64
    cache_token_bytes = 576
    cache_scale_bytes = 8
    num_blocks = 4
    block_stride = args.block_size * (cache_token_bytes + cache_scale_bytes)
    eps = 1e-6

    q_seed = torch.randn(
        (1, args.heads, head_dim), dtype=torch.bfloat16, device=device
    )
    kv_seed = torch.randn((1, head_dim), dtype=torch.bfloat16, device=device)
    positions = torch.tensor([137], dtype=torch.int64, device=device)
    slots = torch.tensor([137], dtype=torch.int64, device=device)
    cos_sin = torch.randn((1024, rope_dim), dtype=torch.float32, device=device)

    def make_cache() -> torch.Tensor:
        return torch.zeros(
            (num_blocks, block_stride), dtype=torch.uint8, device=device
        )

    def reference(q: torch.Tensor, kv: torch.Tensor, cache: torch.Tensor) -> None:
        xpu_qnorm_rope_kv_fp8_insert(
            q,
            kv,
            cache,
            slots,
            positions,
            cos_sin,
            eps,
            args.block_size,
        )

    def candidate(q: torch.Tensor, kv: torch.Tensor, cache: torch.Tensor) -> None:
        xpu_qnorm_rope_kv_fp8_insert_fused(
            q,
            kv,
            cache,
            slots,
            positions,
            cos_sin,
            eps,
            args.block_size,
        )

    changed_rows = []
    for epoch in range(40):
        torch.manual_seed(20260715 + epoch)
        scale = 0.125 * (1 + epoch % 8)
        q_input = torch.randn_like(q_seed).mul_(scale)
        kv_input = torch.randn_like(kv_seed).mul_(scale)
        q_ref, q_got = q_input.clone(), q_input.clone()
        cache_ref, cache_got = make_cache(), make_cache()
        reference(q_ref, kv_input, cache_ref)
        candidate(q_got, kv_input, cache_got)
        torch.xpu.synchronize()
        changed_rows.append(
            {
                "epoch": epoch,
                "q_mismatch_elements": int(
                    torch.count_nonzero(q_ref != q_got).item()
                ),
                "cache_mismatch_bytes": int(
                    torch.count_nonzero(cache_ref != cache_got).item()
                ),
                "q_max_abs_difference": float(
                    (q_ref.float() - q_got.float()).abs().max().item()
                ),
            }
        )

    q_ref, q_got = q_seed.clone(), q_seed.clone()
    cache_ref, cache_got = make_cache(), make_cache()
    for _ in range(args.warmup):
        reference(q_ref, kv_seed, cache_ref)
        candidate(q_got, kv_seed, cache_got)
    torch.xpu.synchronize()

    def timed_us(call) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            call()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    reference_us = []
    candidate_us = []
    for batch in range(args.batches):
        if batch % 2 == 0:
            reference_us.append(timed_us(lambda: reference(q_ref, kv_seed, cache_ref)))
            candidate_us.append(timed_us(lambda: candidate(q_got, kv_seed, cache_got)))
        else:
            candidate_us.append(timed_us(lambda: candidate(q_got, kv_seed, cache_got)))
            reference_us.append(timed_us(lambda: reference(q_ref, kv_seed, cache_ref)))

    q_graph = q_seed.clone()
    kv_graph = kv_seed.clone()
    cache_graph = make_cache()
    graph = torch.xpu.XPUGraph()
    graph_rows = []
    try:
        candidate(q_graph, kv_graph, cache_graph)
        torch.xpu.synchronize()
        with torch.xpu.graph(graph):
            candidate(q_graph, kv_graph, cache_graph)
        previous_q = None
        for replay in range(8):
            torch.manual_seed(20260815 + replay)
            scale = 0.125 * (1 + replay)
            q_input = torch.randn_like(q_seed).mul_(scale)
            kv_input = torch.randn_like(kv_seed).mul_(scale)
            q_graph.copy_(q_input)
            kv_graph.copy_(kv_input)
            cache_graph.zero_()
            graph.replay()
            torch.xpu.synchronize()
            q_snapshot = q_graph.clone()
            cache_snapshot = cache_graph.clone()
            q_expected = q_input.clone()
            cache_expected = make_cache()
            reference(q_expected, kv_input, cache_expected)
            torch.xpu.synchronize()
            graph_rows.append(
                {
                    "replay": replay,
                    "q_changed": previous_q is None
                    or not torch.equal(previous_q, q_snapshot),
                    "q_mismatch_elements": int(
                        torch.count_nonzero(q_expected != q_snapshot).item()
                    ),
                    "cache_mismatch_bytes": int(
                        torch.count_nonzero(cache_expected != cache_snapshot).item()
                    ),
                }
            )
            previous_q = q_snapshot
    finally:
        graph.reset()
        torch.xpu.synchronize()

    reference_median = statistics.median(reference_us)
    candidate_median = statistics.median(candidate_us)
    projected_ms = (reference_median - candidate_median) * args.layers / 1000.0
    exact_changed = sum(
        row["q_mismatch_elements"] == 0 and row["cache_mismatch_bytes"] == 0
        for row in changed_rows
    )
    exact_graph = sum(
        row["q_mismatch_elements"] == 0 and row["cache_mismatch_bytes"] == 0
        for row in graph_rows
    )
    result = {
        "schema_version": 1,
        "device": args.device,
        "shape": {"tokens": 1, "heads": args.heads, "head_dim": head_dim},
        "cache": {
            "dtype": "fp8_ds_mla",
            "block_size": args.block_size,
            "block_stride": block_stride,
        },
        "changed_input_gate": {
            "epochs": len(changed_rows),
            "exact_epochs": exact_changed,
            "rows": changed_rows,
        },
        "graph_replay_gate": {
            "replays": len(graph_rows),
            "exact_replays": exact_graph,
            "changed_replays": sum(row["q_changed"] for row in graph_rows),
            "rows": graph_rows,
        },
        "reference_us": {
            "median": reference_median,
            "samples": reference_us,
        },
        "candidate_us": {
            "median": candidate_median,
            "samples": candidate_us,
        },
        "speedup": reference_median / candidate_median,
        "projected_saved_ms_per_token": projected_ms,
        "gate_ms_per_token": args.gate_ms_per_token,
        "passes_integration_gate": exact_changed == 40
        and exact_graph == 8
        and projected_ms >= args.gate_ms_per_token,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0 if exact_changed == 40 and exact_graph == 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
