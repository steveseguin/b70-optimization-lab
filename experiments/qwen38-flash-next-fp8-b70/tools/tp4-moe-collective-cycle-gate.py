#!/usr/bin/env python3
"""Measure exact Flash-Next TP4 MoE dispatch/combine collective cycles."""

import argparse
import hashlib
import json
import os
import statistics

import torch
import torch.distributed as dist


def tensor_hash(tensors: list[torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for tensor in tensors:
        digest.update(tensor.contiguous().view(torch.uint8).cpu().numpy().tobytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, choices=(1, 4, 64), default=1)
    parser.add_argument("--hidden", type=int, default=2560)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--scale-columns", type=int, default=20)
    parser.add_argument("--layers", type=int, default=48)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--batches", type=int, default=11)
    parser.add_argument("--stability-repeats", type=int, default=20)
    parser.add_argument(
        "--mode",
        choices=("allocating", "preallocated", "direct-rs"),
        required=True,
    )
    args = parser.parse_args()
    if not 1 <= args.layers <= 256:
        raise ValueError("layers must be between 1 and 256")
    if not 0 <= args.warmups <= 20:
        raise ValueError("warmups must be between 0 and 20")
    if not 3 <= args.batches <= 25:
        raise ValueError("batches must be between 3 and 25")
    if not 1 <= args.stability_repeats <= 100:
        raise ValueError("stability-repeats must be between 1 and 100")

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world = int(os.environ["WORLD_SIZE"])
    if world != 4:
        raise ValueError(f"this exact gate requires world size 4, got {world}")
    device = torch.device(f"xpu:{local_rank}")
    torch.xpu.set_device(device)
    dist.init_process_group("xccl")

    rows, hidden, topk = args.rows, args.hidden, args.topk
    try:
        activation_values = (
            (
                torch.arange(rows * hidden, dtype=torch.int64)
                .mul_(17)
                .add_(rank * 31)
                .remainder_(97)
                .sub_(48)
            )
            .to(torch.float32)
            .div_(16)
        )
        activation = (
            activation_values.to(torch.float8_e4m3fn).reshape(rows, hidden).to(device)
        )
        topk_weights = (
            torch.arange(rows * topk, dtype=torch.float32)
            .reshape(rows, topk)
            .add_(rank * 100)
            .div_(1024)
            .to(device)
        )
        topk_ids = (
            torch.arange(rows * topk, dtype=torch.int32)
            .reshape(rows, topk)
            .add_(rank * 1000)
        )
        topk_ids[0, -1] = -1
        topk_ids = topk_ids.to(device)
        activation_scales = (
            torch.arange(rows * args.scale_columns, dtype=torch.float32)
            .reshape(rows, args.scale_columns)
            .add_(rank * 10000)
            .div_(4096)
            .to(device)
        )
        combine_input = torch.full(
            (world * rows, hidden),
            rank + 1,
            dtype=torch.bfloat16,
            device=device,
        )

        inputs = [activation, topk_weights, topk_ids, activation_scales]
        gathered = [
            torch.empty(
                (world * tensor.shape[0], *tensor.shape[1:]),
                dtype=tensor.dtype,
                device=device,
            )
            for tensor in inputs
        ]
        rs_output = torch.empty((rows, hidden), dtype=torch.bfloat16, device=device)
        final_output = torch.empty_like(rs_output)

        def cycle() -> list[torch.Tensor]:
            nonlocal gathered, rs_output, final_output
            if args.mode == "allocating":
                gathered = [
                    torch.empty(
                        (world * tensor.shape[0], *tensor.shape[1:]),
                        dtype=tensor.dtype,
                        device=device,
                    )
                    for tensor in inputs
                ]
                rs_output = torch.empty_like(final_output)
            for output, tensor in zip(gathered, inputs):
                dist.all_gather([output], tensor)
            if args.mode == "direct-rs":
                dist.reduce_scatter_tensor(final_output, combine_input)
            else:
                dist.reduce_scatter_tensor(rs_output, combine_input)
                final_output.copy_(rs_output)
            return [*gathered, final_output]

        cycle_outputs = cycle()
        torch.xpu.synchronize()
        expected_gathered = []
        for source in inputs:
            rank_inputs = []
            for source_rank in range(world):
                if source.dtype == torch.float8_e4m3fn:
                    values = (
                        (
                            torch.arange(rows * hidden, dtype=torch.int64)
                            .mul_(17)
                            .add_(source_rank * 31)
                            .remainder_(97)
                            .sub_(48)
                        )
                        .to(torch.float32)
                        .div_(16)
                        .to(torch.float8_e4m3fn)
                        .reshape(rows, hidden)
                    )
                elif source.dtype == torch.int32:
                    values = (
                        torch.arange(rows * topk, dtype=torch.int32)
                        .reshape(rows, topk)
                        .add_(source_rank * 1000)
                    )
                    values[0, -1] = -1
                elif source.shape[1] == topk:
                    values = (
                        torch.arange(rows * topk, dtype=torch.float32)
                        .reshape(rows, topk)
                        .add_(source_rank * 100)
                        .div_(1024)
                    )
                else:
                    values = (
                        torch.arange(
                            rows * args.scale_columns,
                            dtype=torch.float32,
                        )
                        .reshape(rows, args.scale_columns)
                        .add_(source_rank * 10000)
                        .div_(4096)
                    )
                rank_inputs.append(values)
            expected_gathered.append(torch.cat(rank_inputs))
        for actual, expected in zip(cycle_outputs[:-1], expected_gathered):
            if not torch.equal(actual.cpu(), expected):
                raise RuntimeError("all-gather output failed the rank-order oracle")
        expected_rs = torch.full((rows, hidden), 10, dtype=torch.bfloat16)
        if not torch.equal(cycle_outputs[-1].cpu(), expected_rs):
            raise RuntimeError("reduce-scatter output failed the exact oracle")

        for _ in range(args.warmups):
            for _ in range(args.layers):
                cycle()
        torch.xpu.synchronize()

        local_batch_ms = []
        for _ in range(args.batches):
            dist.barrier(device_ids=[local_rank])
            start = torch.xpu.Event(enable_timing=True)
            end = torch.xpu.Event(enable_timing=True)
            start.record()
            for _ in range(args.layers):
                cycle()
            end.record()
            end.synchronize()
            local_batch_ms.append(start.elapsed_time(end))

        local_timing = torch.tensor(local_batch_ms, dtype=torch.float64, device=device)
        all_timing = torch.empty(
            world * args.batches,
            dtype=torch.float64,
            device=device,
        )
        dist.all_gather([all_timing], local_timing)
        timing_by_rank = all_timing.cpu().reshape(world, args.batches)
        max_rank_ms = timing_by_rank.max(dim=0).values.tolist()

        hashes = []
        for _ in range(args.stability_repeats):
            hashes.append(tensor_hash(cycle()))
        unique_hashes = sorted(set(hashes))
        if len(unique_hashes) != 1:
            raise RuntimeError(f"collective output drifted: {unique_hashes}")

        result = {
            "status": "pass",
            "mode": args.mode,
            "rank": rank,
            "world_size": world,
            "rows_per_rank": rows,
            "hidden": hidden,
            "topk": topk,
            "scale_columns": args.scale_columns,
            "layers_per_batch": args.layers,
            "batches": args.batches,
            "stability_repeats": args.stability_repeats,
            "output_sha256": unique_hashes[0],
            "unique_output_sha256": len(unique_hashes),
            "local_batch_ms": local_batch_ms,
        }
        if rank == 0:
            result.update(
                timing_by_rank_ms=timing_by_rank.tolist(),
                max_rank_batch_ms=max_rank_ms,
                max_rank_median_ms=statistics.median(max_rank_ms),
                max_rank_min_ms=min(max_rank_ms),
                max_rank_max_ms=max(max_rank_ms),
                max_rank_us_per_layer=(
                    statistics.median(max_rank_ms) * 1000.0 / args.layers
                ),
            )
        print(json.dumps(result, sort_keys=True), flush=True)
        dist.barrier(device_ids=[local_rank])
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
