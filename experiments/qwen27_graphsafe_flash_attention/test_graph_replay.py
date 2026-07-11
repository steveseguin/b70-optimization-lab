#!/usr/bin/env python3
"""FP16 Qwen27 packed-MTP3 chunk-prefill XPU graph replay probe."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import torch

from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func


ROWS = 4
Q_HEADS = 12
KV_HEADS = 2
HEAD_DIM = 256
KV_LENGTHS = (128, 1024, 2048)
MIN_REPLAYS = 1000
ATOL = 2e-2
RTOL = 1e-2


BLOCK_SIZE = 64


def reference(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
    qf = q.float().cpu()
    kf = k.float().cpu().repeat_interleave(Q_HEADS // KV_HEADS, dim=1)
    vf = v.float().cpu().repeat_interleave(Q_HEADS // KV_HEADS, dim=1)
    logits = torch.einsum("qhd,khd->hqk", qf * (HEAD_DIM**-0.5), kf)
    q_positions = torch.arange(k.size(0) - ROWS, k.size(0))
    k_positions = torch.arange(k.size(0))
    causal_mask = k_positions[None, :] > q_positions[:, None]
    logits.masked_fill_(causal_mask[None, :, :], float("-inf"))
    probs = torch.softmax(logits, dim=-1)
    return torch.einsum("hqk,khd->qhd", probs, vf).half()


def run_case(kv_len: int, replays: int) -> dict[str, Any]:
    generator = torch.Generator(device="cpu").manual_seed(27000 + kv_len)
    q_cpu = torch.randn(
        ROWS, Q_HEADS, HEAD_DIM, dtype=torch.float16, generator=generator
    )
    logical_blocks = (kv_len + BLOCK_SIZE - 1) // BLOCK_SIZE
    num_blocks = logical_blocks + 3
    block_order = torch.randperm(num_blocks, generator=generator)[:logical_blocks]
    k_cache_cpu = torch.randn(
        num_blocks, BLOCK_SIZE, KV_HEADS, HEAD_DIM,
        dtype=torch.float16, generator=generator,
    )
    v_cache_cpu = torch.randn(
        num_blocks, BLOCK_SIZE, KV_HEADS, HEAD_DIM,
        dtype=torch.float16, generator=generator,
    )

    def logical_kv(length: int) -> tuple[torch.Tensor, torch.Tensor]:
        blocks = block_order[: (length + BLOCK_SIZE - 1) // BLOCK_SIZE]
        logical_k = k_cache_cpu[blocks].reshape(-1, KV_HEADS, HEAD_DIM)[:length]
        logical_v = v_cache_cpu[blocks].reshape(-1, KV_HEADS, HEAD_DIM)[:length]
        return logical_k, logical_v

    current_len = kv_len
    logical_k, logical_v = logical_kv(current_len)
    expected = reference(q_cpu, logical_k, logical_v)

    q = q_cpu.xpu()
    k = k_cache_cpu.xpu()
    v = v_cache_cpu.xpu()
    cu_q = torch.tensor([0, ROWS], dtype=torch.int32, device="xpu")
    seqused_k = torch.tensor([current_len], dtype=torch.int32, device="xpu")
    block_table = torch.full(
        (1, logical_blocks), -1, dtype=torch.int32, device="xpu"
    )
    block_table[0].copy_(block_order.to(dtype=torch.int32, device="xpu"))

    def launch(out: torch.Tensor | None = None) -> torch.Tensor:
        return flash_attn_varlen_func(
            q,
            k,
            v,
            ROWS,
            cu_q,
            kv_len,
            seqused_k=seqused_k,
            softmax_scale=HEAD_DIM**-0.5,
            causal=True,
            block_table=block_table,
            out=out,
            is_mix_batch=True,
        )

    for _ in range(3):
        direct = launch()
    torch.xpu.synchronize()
    torch.testing.assert_close(direct.cpu(), expected, atol=ATOL, rtol=RTOL)

    graph_out = torch.empty_like(q)
    graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(graph):
        captured_out = launch(graph_out)
    if captured_out.data_ptr() != graph_out.data_ptr():
        raise AssertionError("FlashAttention did not honor the static out tensor")
    torch.xpu.synchronize()

    max_abs_diff = 0.0
    mutation_points = {replays // 3, (2 * replays) // 3}
    for replay in range(replays):
        if replay in mutation_points:
            if replay == replays // 3 and kv_len > BLOCK_SIZE + ROWS:
                current_len = kv_len - BLOCK_SIZE
                seqused_k.fill_(current_len)
            else:
                q_cpu.mul_(0.875)
                q.copy_(q_cpu)
            logical_k, logical_v = logical_kv(current_len)
            expected = reference(q_cpu, logical_k, logical_v)
            torch.xpu.synchronize()
        graph_out.fill_(float("nan"))
        torch.xpu.synchronize()
        graph.replay()
        torch.xpu.synchronize()
        actual = graph_out.cpu()
        if torch.isnan(actual).any():
            raise AssertionError(
                f"KV length {kv_len} replay {replay} left poisoned output"
            )
        diff = float((actual.float() - expected.float()).abs().max().item())
        max_abs_diff = max(max_abs_diff, diff)
        try:
            torch.testing.assert_close(actual, expected, atol=ATOL, rtol=RTOL)
        except AssertionError as error:
            raise AssertionError(
                f"KV length {kv_len} failed graph replay {replay}"
            ) from error

    return {
        "kv_length": kv_len,
        "replays": replays,
        "paged_kv": True,
        "block_size": BLOCK_SIZE,
        "dynamic_input_mutations": len(mutation_points),
        "max_abs_diff": max_abs_diff,
        "passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replays", type=int, default=MIN_REPLAYS)
    parser.add_argument("--device", type=int, default=0)
    args = parser.parse_args()
    if args.replays < MIN_REPLAYS:
        parser.error(f"--replays must be at least {MIN_REPLAYS}")

    if not torch.xpu.is_available():
        raise RuntimeError("XPU is unavailable")
    if not hasattr(torch.xpu, "XPUGraph") or not hasattr(torch.xpu, "graph"):
        raise RuntimeError("This PyTorch build lacks torch.xpu graph support")

    torch.xpu.set_device(args.device)
    cases = [run_case(kv_len, args.replays) for kv_len in KV_LENGTHS]
    result = {
        "passed": True,
        "identity": {
            "dtype": "fp16",
            "rows": ROWS,
            "q_heads_tp2_local": Q_HEADS,
            "kv_heads_tp2_local": KV_HEADS,
            "head_dim": HEAD_DIM,
            "kv_lengths": list(KV_LENGTHS),
            "causal": True,
            "packed_mtp_depth": ROWS - 1,
        },
        "command_graph_replays_per_shape": args.replays,
        "total_command_graph_replays": args.replays * len(KV_LENGTHS),
        "cases": cases,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
