#!/usr/bin/env python3
"""Four-B70 exactness/performance gate for the fixed M8 target builder.

The control is the production sequence of position/length preparation, token
assembly, block-table gather, and slot-mapping kernels. The candidate uses one
fixed-geometry Triton command while retaining the same persistent outputs.
This is a component gate only; endpoint integration must additionally prove
that the surrounding host preparation path is actually bypassed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import time

import torch
import torch.distributed as dist

from vllm.v1.worker.gpu.block_table import BlockTables
from vllm.v1.worker.gpu.input_batch import (
    InputBuffers,
    combine_sampled_and_draft_tokens,
    prepare_pos_seq_lens,
)


M = 8
N_DRAFT = 7
BLOCK_SIZES = [64, 128, 256]
MAX_BLOCKS = [32, 24, 16]


def median_us(fn, iterations: int) -> float:
    samples = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        fn()
        torch.xpu.synchronize()
        samples.append((time.perf_counter_ns() - started) / 1000.0)
    return statistics.median(samples)


def make_tables(device: torch.device) -> BlockTables:
    tables = BlockTables(
        block_sizes=BLOCK_SIZES,
        max_num_reqs=1,
        max_num_batched_tokens=256,
        max_num_blocks_per_group=MAX_BLOCKS,
        device=device,
        kernel_block_sizes=BLOCK_SIZES,
    )
    for group, table in enumerate(tables.block_tables):
        count = MAX_BLOCKS[group]
        values = torch.arange(
            1000 * (group + 1),
            1000 * (group + 1) + count,
            dtype=torch.int32,
            device=device,
        )
        table.gpu[0, :count].copy_(values)
        tables.num_blocks.gpu[group, 0] = count
    return tables


def snapshot(
    buffers: InputBuffers,
    logits: torch.Tensor,
    tables: BlockTables,
) -> dict[str, object]:
    return {
        "input_ids": buffers.input_ids[:M].cpu().tolist(),
        "positions": buffers.positions[:M].cpu().tolist(),
        "seq_lens": buffers.seq_lens[:1].cpu().tolist(),
        "query_start_loc": buffers.query_start_loc[:2].cpu().tolist(),
        "logits_indices": logits.cpu().tolist(),
        "block_tables": [
            table[0].cpu().tolist() for table in tables.input_block_tables
        ],
        "slot_mappings": tables.slot_mappings[:, :M].cpu().tolist(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--graph-replays", type=int, default=70)
    parser.add_argument("--timing-iterations", type=int, default=100)
    args = parser.parse_args()

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world = int(os.environ["WORLD_SIZE"])
    if world != 4:
        raise RuntimeError(f"requires four ranks, got {world}")
    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group("xccl", device_id=device)

    control_buffers = InputBuffers(1, 256, device)
    candidate_buffers = InputBuffers(1, 256, device)
    control_tables = make_tables(device)
    candidate_tables = make_tables(device)
    idx = torch.zeros(1, dtype=torch.int32, device=device)
    num_computed = torch.zeros(1, dtype=torch.int32, device=device)
    last_sampled = torch.zeros((1, 1), dtype=torch.int64, device=device)
    draft_tokens = torch.zeros((1, N_DRAFT), dtype=torch.int64, device=device)
    prefill_len = torch.ones(1, dtype=torch.int32, device=device)
    cu_num_logits = torch.tensor([0, M], dtype=torch.int32, device=device)
    control_buffers.query_start_loc[:2] = torch.tensor(
        [0, M], dtype=torch.int32, device=device
    )
    candidate_buffers.query_start_loc[:2] = torch.tensor(
        [0, M], dtype=torch.int32, device=device
    )
    control_logits = torch.empty(M, dtype=torch.int64, device=device)
    candidate_logits = torch.empty_like(control_logits)

    def control() -> None:
        prepare_pos_seq_lens(
            idx,
            control_buffers.query_start_loc[:2],
            num_computed,
            control_buffers.positions,
            control_buffers.seq_lens,
        )
        combine_sampled_and_draft_tokens(
            control_buffers.input_ids,
            idx,
            last_sampled,
            control_buffers.query_start_loc[:2],
            control_buffers.seq_lens[:1],
            prefill_len,
            draft_tokens,
            cu_num_logits,
            M,
            logits_indices=control_logits,
        )
        control_tables.gather_block_tables(idx, num_reqs_padded=1)
        control_tables.compute_slot_mappings(
            idx,
            control_buffers.query_start_loc[:2],
            control_buffers.positions[:M],
            num_tokens_padded=M,
        )

    def candidate() -> None:
        candidate_tables.prepare_fixed_m8_decode(
            candidate_buffers.input_ids,
            candidate_buffers.positions,
            candidate_buffers.seq_lens,
            candidate_buffers.query_start_loc[:2],
            candidate_logits,
            idx,
            num_computed,
            last_sampled,
            draft_tokens,
        )

    num_computed.fill_(29)
    last_sampled.fill_(1073)
    draft_tokens.copy_(
        torch.arange(437, 437 + N_DRAFT, dtype=torch.int64, device=device).view(1, -1)
    )
    for _ in range(4):
        control()
        candidate()
    torch.xpu.synchronize()

    control_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(control_graph):
        control()
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        candidate()
    torch.xpu.synchronize()

    eager_exact = 0
    graph_exact = 0
    mismatches: list[dict[str, object]] = []

    def set_epoch(epoch: int) -> None:
        position = [28, 58, 127, 255, 511, 1023][epoch % 6]
        num_computed.fill_(position)
        last_sampled.fill_(1073 + rank * 17 + epoch)
        draft_tokens.copy_(
            (
                torch.arange(N_DRAFT, dtype=torch.int64, device=device)
                + 437
                + rank * 101
                + epoch * 13
            ).view(1, -1)
        )

    for epoch in range(args.epochs):
        set_epoch(epoch)
        control()
        candidate()
        torch.xpu.synchronize()
        expected = snapshot(control_buffers, control_logits, control_tables)
        actual = snapshot(candidate_buffers, candidate_logits, candidate_tables)
        if expected == actual:
            eager_exact += 1
        else:
            mismatches.append({"mode": "eager", "epoch": epoch})

    for epoch in range(args.graph_replays):
        set_epoch(1000 + epoch)
        control_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        expected = snapshot(control_buffers, control_logits, control_tables)
        actual = snapshot(candidate_buffers, candidate_logits, candidate_tables)
        if expected == actual:
            graph_exact += 1
        else:
            mismatches.append({"mode": "graph", "epoch": epoch})

    for _ in range(10):
        control_graph.replay()
        candidate_graph.replay()
    torch.xpu.synchronize()
    control_eager_us = median_us(control, args.timing_iterations)
    candidate_eager_us = median_us(candidate, args.timing_iterations)
    control_graph_us = median_us(control_graph.replay, args.timing_iterations)
    candidate_graph_us = median_us(candidate_graph.replay, args.timing_iterations)

    local = {
        "rank": rank,
        "device": local_rank,
        "eager_exact": eager_exact,
        "graph_exact": graph_exact,
        "mismatches": mismatches[:8],
        "control_eager_us": control_eager_us,
        "candidate_eager_us": candidate_eager_us,
        "control_graph_us": control_graph_us,
        "candidate_graph_us": candidate_graph_us,
    }
    gathered: list[dict[str, object] | None] = [None] * world
    dist.all_gather_object(gathered, local)
    if rank == 0:
        rows = [row for row in gathered if row is not None]
        result = {
            "schema_version": 1,
            "classification": "deepseek_v4_fixed_m8_target_builder_gate",
            "world_size": world,
            "epochs": args.epochs,
            "graph_replays": args.graph_replays,
            "exact_all_ranks": all(
                row["eager_exact"] == args.epochs
                and row["graph_exact"] == args.graph_replays
                for row in rows
            ),
            "slowest_rank": {
                "control_eager_us": max(row["control_eager_us"] for row in rows),
                "candidate_eager_us": max(
                    row["candidate_eager_us"] for row in rows
                ),
                "control_graph_us": max(row["control_graph_us"] for row in rows),
                "candidate_graph_us": max(
                    row["candidate_graph_us"] for row in rows
                ),
            },
            "ranks": rows,
        }
        result["slowest_rank"]["eager_saved_us"] = (
            result["slowest_rank"]["control_eager_us"]
            - result["slowest_rank"]["candidate_eager_us"]
        )
        result["slowest_rank"]["graph_saved_us"] = (
            result["slowest_rank"]["control_graph_us"]
            - result["slowest_rank"]["candidate_graph_us"]
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, indent=2, sort_keys=True))

    dist.barrier()
    dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
