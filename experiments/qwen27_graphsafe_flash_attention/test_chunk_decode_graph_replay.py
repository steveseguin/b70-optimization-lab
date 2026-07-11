#!/usr/bin/env python3
"""One-token paged-decode versus graph-safe chunk-attention oracle."""

from __future__ import annotations

import argparse
import json
import os
import time

import torch

from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func


Q_HEADS = 12
KV_HEADS = 2
HEAD_DIM = 256
BLOCK_SIZE = 64
KV_LENGTHS = (128, 1024, 2048)
ATOL = 2e-2
RTOL = 1e-2


def reference(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
    qf = q.float().cpu()
    kf = k.float().cpu().repeat_interleave(Q_HEADS // KV_HEADS, dim=1)
    vf = v.float().cpu().repeat_interleave(Q_HEADS // KV_HEADS, dim=1)
    logits = torch.einsum("qhd,khd->hqk", qf * (HEAD_DIM**-0.5), kf)
    return torch.einsum("hqk,khd->qhd", torch.softmax(logits, -1), vf).half()


def run_case(kv_len: int, mode: str, replays: int, bench_iters: int) -> dict:
    generator = torch.Generator(device="cpu").manual_seed(36000 + kv_len)
    q_cpu = torch.randn(1, Q_HEADS, HEAD_DIM, dtype=torch.float16,
                        generator=generator)
    logical_blocks = (kv_len + BLOCK_SIZE - 1) // BLOCK_SIZE
    num_blocks = logical_blocks + 3
    block_order = torch.randperm(num_blocks, generator=generator)[:logical_blocks]
    k_cpu = torch.randn(num_blocks, BLOCK_SIZE, KV_HEADS, HEAD_DIM,
                        dtype=torch.float16, generator=generator)
    v_cpu = torch.randn(num_blocks, BLOCK_SIZE, KV_HEADS, HEAD_DIM,
                        dtype=torch.float16, generator=generator)

    def logical_kv(length: int) -> tuple[torch.Tensor, torch.Tensor]:
        count = (length + BLOCK_SIZE - 1) // BLOCK_SIZE
        blocks = block_order[:count]
        return (k_cpu[blocks].reshape(-1, KV_HEADS, HEAD_DIM)[:length],
                v_cpu[blocks].reshape(-1, KV_HEADS, HEAD_DIM)[:length])

    current_len = kv_len
    logical_k, logical_v = logical_kv(current_len)
    expected = reference(q_cpu, logical_k, logical_v)
    q, k, v = q_cpu.xpu(), k_cpu.xpu(), v_cpu.xpu()
    cu_q = torch.tensor([0, 1], dtype=torch.int32, device="xpu")
    seqused_k = torch.tensor([current_len], dtype=torch.int32, device="xpu")
    block_table = torch.full((1, logical_blocks), -1,
                             dtype=torch.int32, device="xpu")
    block_table[0].copy_(block_order.to(dtype=torch.int32, device="xpu"))
    out = torch.empty_like(q)

    def launch() -> torch.Tensor:
        return flash_attn_varlen_func(
            q, k, v, 1, cu_q, kv_len, seqused_k=seqused_k,
            softmax_scale=HEAD_DIM**-0.5, causal=False,
            block_table=block_table, out=out, is_mix_batch=False)

    for _ in range(20):
        launch()
    torch.xpu.synchronize()
    direct = launch()
    torch.xpu.synchronize()
    torch.testing.assert_close(direct.cpu(), expected, atol=ATOL, rtol=RTOL)

    start = time.perf_counter()
    for _ in range(bench_iters):
        launch()
    torch.xpu.synchronize()
    direct_us = (time.perf_counter() - start) * 1e6 / bench_iters

    max_abs_diff = float((direct.cpu().float() - expected.float()).abs().max())
    if mode == "chunk":
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            captured = launch()
        if captured.data_ptr() != out.data_ptr():
            raise AssertionError("attention did not honor static output")
        torch.xpu.synchronize()
        mutation_points = {replays // 3, 2 * replays // 3}
        for replay in range(replays):
            if replay in mutation_points:
                if replay == replays // 3 and kv_len > BLOCK_SIZE + 1:
                    current_len = kv_len - BLOCK_SIZE
                    seqused_k.fill_(current_len)
                else:
                    q_cpu.mul_(0.875)
                    q.copy_(q_cpu)
                logical_k, logical_v = logical_kv(current_len)
                expected = reference(q_cpu, logical_k, logical_v)
                torch.xpu.synchronize()
            out.fill_(float("nan"))
            torch.xpu.synchronize()
            graph.replay()
            torch.xpu.synchronize()
            actual = out.cpu()
            if torch.isnan(actual).any():
                raise AssertionError(f"replay {replay} left poisoned output")
            max_abs_diff = max(
                max_abs_diff,
                float((actual.float() - expected.float()).abs().max()),
            )
            torch.testing.assert_close(actual, expected, atol=ATOL, rtol=RTOL)

    return {
        "kv_length": kv_len,
        "mode": mode,
        "direct_us": direct_us,
        "graph_replays": replays if mode == "chunk" else 0,
        "max_abs_diff": max_abs_diff,
        "passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "chunk"), required=True)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--replays", type=int, default=1000)
    parser.add_argument("--bench-iters", type=int, default=1000)
    args = parser.parse_args()
    forced = os.getenv("VLLM_XPU_FA2_FORCE_CHUNK_DECODE", "0") == "1"
    if forced != (args.mode == "chunk"):
        parser.error("mode and VLLM_XPU_FA2_FORCE_CHUNK_DECODE disagree")
    if args.mode == "chunk" and args.replays < 1000:
        parser.error("chunk mode requires at least 1000 graph replays")
    torch.xpu.set_device(args.device)
    result = {
        "passed": True,
        "identity": {
            "dtype": "fp16", "rows": 1, "q_heads_tp2_local": Q_HEADS,
            "kv_heads_tp2_local": KV_HEADS, "head_dim": HEAD_DIM,
            "block_size": BLOCK_SIZE, "kv_lengths": list(KV_LENGTHS),
            "causal": False, "cold_cache_reuse": False,
        },
        "cases": [run_case(k, args.mode, args.replays, args.bench_iters)
                  for k in KV_LENGTHS],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
