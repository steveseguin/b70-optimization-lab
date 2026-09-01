#!/usr/bin/env python3
"""Check exact TP4 selective-UVA FP8 PLE lookup under XPU graph replay."""

import argparse
import hashlib
import json
import os
import time

import torch
import torch.distributed as dist

from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor


def fp8_values(rows: torch.Tensor, columns: torch.Tensor) -> torch.Tensor:
    values = ((rows * 17 + columns * 31) % 241 - 120).to(torch.float32) / 32
    return values.to(torch.float8_e4m3fn)


def ids_for(replay: int, rows: int, heads: int, global_vocab: int) -> torch.Tensor:
    count = rows * heads
    return (
        (torch.arange(count, dtype=torch.int64) * 7919 + replay * 104729 + 17)
        % global_vocab
    ).reshape(rows, heads)


def digest(tensor: torch.Tensor) -> str:
    raw = tensor.contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1)
    parser.add_argument("--heads", type=int, default=16)
    parser.add_argument("--head-dim", type=int, default=160)
    parser.add_argument("--local-vocab", type=int, default=65536)
    parser.add_argument("--replays", type=int, default=100)
    args = parser.parse_args()
    if min(args.rows, args.heads, args.head_dim, args.local_vocab) <= 0:
        raise ValueError("all dimensions must be positive")
    if not 2 <= args.replays <= 1000:
        raise ValueError("replays must be in [2, 1000]")

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4 or rank != local_rank:
        raise RuntimeError("probe requires one local TP4 process per XPU")

    device = torch.device(f"xpu:{local_rank}")
    torch.xpu.set_device(device)
    dist.init_process_group("xccl")
    try:
        global_vocab = args.local_vocab * world_size
        global_start = rank * args.local_vocab
        local_rows = torch.arange(args.local_vocab, dtype=torch.int64).unsqueeze(1)
        columns = torch.arange(args.head_dim, dtype=torch.int64).unsqueeze(0)
        host_weight = fp8_values(global_start + local_rows, columns).pin_memory()
        uva_weight = get_accelerator_view_from_cpu_tensor(host_weight)

        global_ids = torch.empty(
            (args.rows, args.heads), dtype=torch.int64, device=device
        )
        output = torch.empty(
            (args.rows, args.heads, args.head_dim),
            dtype=torch.float8_e4m3fn,
            device=device,
        )
        global_ids.copy_(ids_for(10_000, args.rows, args.heads, global_vocab))

        graph = torch.xpu.XPUGraph()
        dist.barrier(device_ids=[rank])
        torch.xpu.synchronize()
        with torch.xpu.graph(graph):
            input_mask = (global_ids < global_start) | (
                global_ids >= global_start + args.local_vocab
            )
            local_ids = (global_ids - global_start).masked_fill(input_mask, 0)
            torch.index_select(
                uva_weight,
                0,
                local_ids.reshape(-1),
                out=output.reshape(-1, args.head_dim),
            )
            output.view(torch.int8).masked_fill_(input_mask.unsqueeze(-1), 0)
            dist.all_reduce(output.view(torch.int8), op=dist.ReduceOp.SUM)
        torch.xpu.synchronize()

        hashes: list[str] = []
        dist.barrier(device_ids=[rank])
        torch.xpu.synchronize()
        started = time.perf_counter_ns()
        for replay in range(args.replays):
            ids_cpu = ids_for(replay, args.rows, args.heads, global_vocab)
            global_ids.copy_(ids_cpu)
            graph.replay()
            torch.xpu.synchronize()
            actual = output.cpu().view(torch.int8)
            expected = (
                fp8_values(ids_cpu.reshape(-1, 1), columns)
                .reshape(args.rows, args.heads, args.head_dim)
                .view(torch.int8)
            )
            if not torch.equal(actual, expected):
                raise AssertionError(f"PLE graph mismatch at replay {replay}")
            hashes.append(digest(actual))
        elapsed_us = (time.perf_counter_ns() - started) / 1000

        if len(set(hashes)) != args.replays:
            raise AssertionError("PLE output hashes are not replay-unique")
        print(
            json.dumps(
                {
                    "classification": "ple_uva_fp8_xpu_graph_exact",
                    "graph_mean_us_inclusive": elapsed_us / args.replays,
                    "head_dim": args.head_dim,
                    "heads": args.heads,
                    "local_vocab": args.local_vocab,
                    "rank": rank,
                    "replays": args.replays,
                    "rows": args.rows,
                    "storage": "pinned_cpu_with_accelerator_uva_view",
                    "unique_output_hashes": len(set(hashes)),
                    "world_size": world_size,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        dist.barrier(device_ids=[rank])
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
