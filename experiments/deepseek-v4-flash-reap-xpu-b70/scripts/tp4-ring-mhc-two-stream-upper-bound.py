#!/usr/bin/env python3
"""Screen whether TP4 ring and MHC work can overlap on two XPU streams."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import time

import torch
import torch.distributed as dist
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


HIDDEN = 4096
HC = 4
HC3 = 24


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collectives", type=int, default=87)
    parser.add_argument("--mhc-boundaries", type=int, default=85)
    parser.add_argument("--warmup", type=int, default=6)
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4:
        raise ValueError(f"requires world_size=4, got {world_size}")

    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group(backend="xccl", device_id=device)
    comm_stream = torch.xpu.current_stream(device)
    mhc_stream = torch.xpu.Stream(device=device)

    base = (
        torch.arange(args.collectives * HIDDEN, device=device)
        .remainder_(23)
        .to(torch.bfloat16)
        .reshape(args.collectives, HIDDEN)
    )
    reduced = [torch.empty_like(base[0]) for _ in range(args.collectives)]

    h = torch.arange(HIDDEN, dtype=torch.float32, device=device)
    k = torch.arange(HC * HIDDEN, dtype=torch.float32, device=device)
    x = (
        torch.sin(h * 0.00091 + rank * 0.017)
        .mul_(1.25)
        .to(torch.bfloat16)
        .unsqueeze(0)
    )
    residual = torch.stack(
        [
            torch.cos(h * (0.00037 * (index + 1)) + rank * 0.011)
            .mul_(index + 0.75)
            .to(torch.bfloat16)
            for index in range(HC)
        ]
    ).unsqueeze(0)
    post = torch.tensor(
        [0.25, -0.5, 0.75, 1.125], dtype=torch.float32, device=device
    ).reshape(1, HC, 1)
    comb = (
        torch.arange(HC * HC, dtype=torch.float32, device=device)
        .reshape(1, HC, HC)
        .mul_(0.017)
        .sub_(0.11)
    )
    fn = torch.stack(
        [
            torch.sin(k * (0.000013 * (index + 1)) + index * 0.071)
            .mul_(0.00035)
            .add_(torch.cos(k * 0.000009 + index * 0.019) * 0.00015)
            for index in range(HC3)
        ]
    )
    scale = torch.tensor([0.7, 0.8, 0.9], dtype=torch.float32, device=device)
    hc_base = torch.linspace(-0.12, 0.13, HC3, dtype=torch.float32, device=device)
    outputs = (
        torch.empty_like(residual),
        torch.empty_like(post),
        torch.empty_like(comb),
        torch.empty_like(x),
    )

    def reset(epoch: int) -> None:
        offset = rank * 3 + epoch % 11
        with torch.xpu.stream(comm_stream):
            for index, tensor in enumerate(reduced):
                tensor.copy_(base[index] + offset)

    def run_collectives() -> None:
        with torch.xpu.stream(comm_stream):
            for tensor in reduced:
                dist.all_reduce(tensor)

    def run_mhc() -> None:
        residual_out, next_post, next_comb, layer_input = outputs
        with torch.xpu.stream(mhc_stream):
            for _ in range(args.mhc_boundaries):
                torch.ops._xpu_C.mhc_post_pre_m1_out(
                    x,
                    residual,
                    post,
                    comb,
                    fn,
                    scale,
                    hc_base,
                    residual_out,
                    next_post,
                    next_comb,
                    layer_input,
                    1e-6,
                    1e-6,
                    1e-6,
                    2.0,
                    20,
                )

    def synchronize() -> None:
        comm_stream.synchronize()
        mhc_stream.synchronize()

    def time_call(call) -> float:
        synchronize()
        dist.barrier()
        started = time.perf_counter()
        call()
        synchronize()
        return (time.perf_counter() - started) * 1000.0

    def serial() -> None:
        run_collectives()
        # Enqueue MHC on the same stream directly behind the ring chain.
        with torch.xpu.stream(comm_stream):
            residual_out, next_post, next_comb, layer_input = outputs
            for _ in range(args.mhc_boundaries):
                torch.ops._xpu_C.mhc_post_pre_m1_out(
                    x,
                    residual,
                    post,
                    comb,
                    fn,
                    scale,
                    hc_base,
                    residual_out,
                    next_post,
                    next_comb,
                    layer_input,
                    1e-6,
                    1e-6,
                    1e-6,
                    2.0,
                    20,
                )

    def parallel_comm_first() -> None:
        run_collectives()
        run_mhc()

    def parallel_mhc_first() -> None:
        run_mhc()
        run_collectives()

    run_mhc()
    synchronize()
    expected_outputs = tuple(tensor.clone() for tensor in outputs)
    for epoch in range(args.warmup):
        reset(epoch)
        parallel_comm_first()
        synchronize()
        reset(epoch + 31)
        serial()
        synchronize()

    names = (
        "collective_only",
        "mhc_only",
        "serial",
        "parallel_comm_first",
        "parallel_mhc_first",
    )
    samples: dict[str, list[float]] = {name: [] for name in names}
    calls = {
        "collective_only": run_collectives,
        "mhc_only": run_mhc,
        "serial": serial,
        "parallel_comm_first": parallel_comm_first,
        "parallel_mhc_first": parallel_mhc_first,
    }
    for epoch in range(args.epochs):
        rotated = names[epoch % len(names) :] + names[: epoch % len(names)]
        for name in rotated:
            reset(epoch + 101)
            synchronize()
            samples[name].append(time_call(calls[name]))

    validation_epoch = args.epochs + 301
    reset(validation_epoch)
    run_collectives()
    run_mhc()
    synchronize()
    expected_reduced = base * world_size + (
        3 * world_size * (world_size - 1) // 2
    ) + world_size * (validation_epoch % 11)
    collective_mismatches = int(
        (torch.stack(reduced) != expected_reduced).sum().item()
    )
    mhc_mismatches = [
        int((actual != expected).sum().item())
        for actual, expected in zip(outputs, expected_outputs)
    ]
    medians = {name: statistics.median(values) for name, values in samples.items()}
    best_parallel = min(
        medians["parallel_comm_first"], medians["parallel_mhc_first"]
    )
    local_result = {
        "rank": rank,
        "device": str(device),
        "collective_mismatches": collective_mismatches,
        "mhc_output_mismatches": mhc_mismatches,
        "wall_ms_medians": medians,
        "wall_ms_samples": samples,
        "best_parallel_wall_ms": best_parallel,
        "hidden_vs_serial_ms": medians["serial"] - best_parallel,
        "parallel_excess_over_max_standalone_ms": best_parallel
        - max(medians["collective_only"], medians["mhc_only"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rank_output = args.output.with_suffix(args.output.suffix + f".rank{rank}.json")
    rank_output.write_text(json.dumps(local_result, indent=2, sort_keys=True) + "\n")
    dist.barrier()

    if rank == 0:
        rows = [
            json.loads(
                args.output.with_suffix(args.output.suffix + f".rank{index}.json")
                .read_text()
            )
            for index in range(world_size)
        ]
        max_rank = {
            name: max(row["wall_ms_medians"][name] for row in rows)
            for name in names
        }
        best_parallel_max_rank = min(
            max_rank["parallel_comm_first"], max_rank["parallel_mhc_first"]
        )
        result = {
            "passed_correctness": all(
                row["collective_mismatches"] == 0
                and all(count == 0 for count in row["mhc_output_mismatches"])
                for row in rows
            ),
            "world_size": world_size,
            "collectives": args.collectives,
            "mhc_boundaries": args.mhc_boundaries,
            "warmup": args.warmup,
            "epochs": args.epochs,
            "max_rank_wall_ms_medians": max_rank,
            "best_parallel_max_rank_wall_ms": best_parallel_max_rank,
            "hidden_vs_serial_max_rank_ms": max_rank["serial"]
            - best_parallel_max_rank,
            "parallel_excess_over_max_standalone_max_rank_ms": (
                best_parallel_max_rank
                - max(max_rank["collective_only"], max_rank["mhc_only"])
            ),
            "integration_gate_hidden_ms": 0.51,
            "rows": rows,
        }
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        args.output.write_text(rendered + "\n")

    dist.barrier()
    dist.destroy_process_group()
    return 0 if collective_mismatches == 0 and not any(mhc_mismatches) else 1


if __name__ == "__main__":
    raise SystemExit(main())
