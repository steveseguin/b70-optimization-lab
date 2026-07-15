#!/usr/bin/env python3
"""Price oneCCL's recording-path overhead across 87 TP4 reductions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import time

import torch
import torch.distributed as dist


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collectives", type=int, default=87)
    parser.add_argument("--hidden-size", type=int, default=4096)
    parser.add_argument("--warmup", type=int, default=8)
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

    base = (
        torch.arange(args.collectives * args.hidden_size, device=device)
        .remainder_(23)
        .to(torch.bfloat16)
        .reshape(args.collectives, args.hidden_size)
    )
    tensors = [torch.empty_like(base[0]) for _ in range(args.collectives)]

    def reset(epoch: int) -> None:
        offset = rank * 3 + epoch % 11
        for index, tensor in enumerate(tensors):
            tensor.copy_(base[index] + offset)

    def expected(epoch: int) -> torch.Tensor:
        rank_offset_sum = 3 * world_size * (world_size - 1) // 2
        return base * world_size + rank_offset_sum + world_size * (epoch % 11)

    def run_chain() -> None:
        for tensor in tensors:
            dist.all_reduce(tensor)

    for epoch in range(args.warmup):
        reset(epoch)
        run_chain()
    torch.xpu.synchronize()
    dist.barrier()

    device_ms: list[float] = []
    wall_ms: list[float] = []
    mismatch_epochs = 0
    first_mismatch = None
    for epoch in range(args.epochs):
        reset(epoch + 101)
        torch.xpu.synchronize()
        dist.barrier()
        start_event = torch.xpu.Event(enable_timing=True)
        end_event = torch.xpu.Event(enable_timing=True)
        wall_start = time.perf_counter()
        start_event.record()
        run_chain()
        end_event.record()
        end_event.synchronize()
        wall_ms.append((time.perf_counter() - wall_start) * 1000.0)
        device_ms.append(start_event.elapsed_time(end_event))

        actual = torch.stack(tensors)
        want = expected(epoch + 101)
        if not torch.equal(actual, want):
            mismatch_epochs += 1
            if first_mismatch is None:
                diff = (actual.float() - want.float()).abs()
                flat = diff.reshape(-1).nonzero().reshape(-1)
                first_index = int(flat[0].item())
                first_mismatch = {
                    "epoch": epoch,
                    "flat_index": first_index,
                    "actual": float(actual.reshape(-1)[first_index].item()),
                    "expected": float(want.reshape(-1)[first_index].item()),
                    "mismatch_elements": int(flat.numel()),
                    "max_abs": float(diff.max().item()),
                }

    loaded_ccl_paths = sorted(
        {
            line.rsplit(maxsplit=1)[-1]
            for line in Path("/proc/self/maps").read_text().splitlines()
            if "libccl.so" in line and line.rsplit(maxsplit=1)[-1].startswith("/")
        }
    )
    local_result = {
        "rank": rank,
        "device": str(device),
        "force_recording_path": os.environ.get(
            "CCL_SYCL_FORCE_RECORDING_PATH", "unset"
        ),
        "loaded_ccl_paths": loaded_ccl_paths,
        "mismatch_epochs": mismatch_epochs,
        "first_mismatch": first_mismatch,
        "device_ms_median_87": statistics.median(device_ms),
        "device_ms_p10_87": sorted(device_ms)[max(0, int(len(device_ms) * 0.1) - 1)],
        "device_ms_min_87": min(device_ms),
        "device_us_per_collective_median": statistics.median(device_ms)
        * 1000.0
        / args.collectives,
        "wall_ms_median_87": statistics.median(wall_ms),
        "device_ms_samples": device_ms,
        "wall_ms_samples": wall_ms,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rank_output = args.output.with_suffix(args.output.suffix + f".rank{rank}.json")
    rank_output.write_text(json.dumps(local_result, indent=2, sort_keys=True) + "\n")
    # CCL_SYCL_FORCE_RECORDING_PATH applies process-wide.  Object collectives
    # use a non-SYCL path that intentionally rejects forced graph recording,
    # so aggregate the tiny timing records through rank-local files instead.
    dist.barrier()

    if rank == 0:
        rows = [
            json.loads(
                args.output.with_suffix(args.output.suffix + f".rank{index}.json")
                .read_text()
            )
            for index in range(world_size)
        ]
        result = {
            "passed": len(rows) == world_size
            and all(row["mismatch_epochs"] == 0 for row in rows),
            "world_size": world_size,
            "collectives": args.collectives,
            "hidden_size": args.hidden_size,
            "dtype": "bfloat16",
            "warmup": args.warmup,
            "epochs": args.epochs,
            "force_recording_path": os.environ.get(
                "CCL_SYCL_FORCE_RECORDING_PATH", "unset"
            ),
            "max_rank_device_ms_median_87": max(
                row["device_ms_median_87"] for row in rows
            ),
            "max_rank_wall_ms_median_87": max(
                row["wall_ms_median_87"] for row in rows
            ),
            "ranks": rows,
        }
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        args.output.write_text(rendered + "\n")

    dist.barrier()
    dist.destroy_process_group()
    return 0 if mismatch_epochs == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
