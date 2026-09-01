#!/usr/bin/env python3
"""Check an ordered target-step-sized XCCL sequence under XPU graph replay."""

import argparse
import hashlib
import json
import os
import time

import torch
import torch.distributed as dist


def input_for(rank: int, replay: int, collective: int, hidden: int) -> torch.Tensor:
    cols = torch.arange(hidden, dtype=torch.int64)
    values = ((cols * 13 + rank * 29 + replay * 7 + collective * 11) % 127) - 63
    return values.to(torch.bfloat16).reshape(1, hidden)


def expected_for(
    replay: int, collective: int, hidden: int, world_size: int
) -> torch.Tensor:
    return torch.stack(
        [input_for(rank, replay, collective, hidden) for rank in range(world_size)]
    ).sum(dim=0)


def composite_digest(outputs: list[torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for output in outputs:
        digest.update(output.contiguous().view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def validate_outputs(
    tensors: list[torch.Tensor],
    replay: int,
    hidden: int,
    world_size: int,
) -> str:
    outputs = [tensor.cpu() for tensor in tensors]
    for collective, output in enumerate(outputs):
        expected = expected_for(replay, collective, hidden, world_size)
        if not torch.equal(output, expected):
            raise AssertionError(
                f"graph mismatch at replay {replay}, collective {collective}"
            )
    return composite_digest(outputs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hidden", type=int, default=2560)
    parser.add_argument("--collectives", type=int, default=97)
    parser.add_argument("--replays", type=int, default=100)
    args = parser.parse_args()
    if args.hidden <= 0:
        raise ValueError("hidden must be positive")
    if not 2 <= args.collectives <= 256:
        raise ValueError("collectives must be in [2, 256]")
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
        tensors = [
            torch.empty((1, args.hidden), dtype=torch.bfloat16, device=device)
            for _ in range(args.collectives)
        ]
        for collective, tensor in enumerate(tensors):
            tensor.copy_(input_for(rank, 10_000, collective, args.hidden))

        graph = torch.xpu.XPUGraph()
        dist.barrier(device_ids=[rank])
        torch.xpu.synchronize()
        with torch.xpu.graph(graph):
            for tensor in tensors:
                dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
        torch.xpu.synchronize()

        hashes: list[str] = []
        dist.barrier(device_ids=[rank])
        torch.xpu.synchronize()
        started = time.perf_counter_ns()
        for replay in range(args.replays):
            for collective, tensor in enumerate(tensors):
                tensor.copy_(input_for(rank, replay, collective, args.hidden))
            graph.replay()
            torch.xpu.synchronize()
            hashes.append(validate_outputs(tensors, replay, args.hidden, world_size))
        elapsed_us = (time.perf_counter_ns() - started) / 1000

        if len(set(hashes)) != args.replays:
            raise AssertionError("composite output hashes are not replay-unique")
        print(
            json.dumps(
                {
                    "classification": "xpu_graph_xccl_target_step_sequence",
                    "collectives_per_graph": args.collectives,
                    "dtype": "bfloat16",
                    "hidden": args.hidden,
                    "mean_us_per_graph": elapsed_us / args.replays,
                    "mean_us_per_collective_inclusive": (
                        elapsed_us / args.replays / args.collectives
                    ),
                    "rank": rank,
                    "replays": args.replays,
                    "unique_composite_hashes": len(set(hashes)),
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
