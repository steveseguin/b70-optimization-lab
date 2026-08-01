#!/usr/bin/env python3
"""Bounded TP4 latency gate for Laguna's twelve draft body reductions."""

from __future__ import annotations

import datetime
import json
import os
import statistics
import sys
import time
from pathlib import Path

import torch
import torch.distributed as dist


def main() -> int:
    rank = int(os.environ["RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    output_root = Path(os.environ["LAGUNA_COLLECTIVE_GATE_ROOT"])
    projection_gate_path = Path(os.environ["LAGUNA_PROJECTION_GATE_JSON"])
    if world_size != 4:
        raise RuntimeError(f"sealed gate requires world_size=4, got {world_size}")
    if output_root.exists() and not output_root.is_dir():
        raise RuntimeError(f"output root is not a directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    projection_gate = json.loads(projection_gate_path.read_text())
    if (
        projection_gate.get("status") != "PASS"
        or projection_gate.get("raw_parity")
        != {
            "down_proj": True,
            "gate_proj": True,
            "o_proj": True,
            "qkv_proj": True,
            "up_proj": True,
        }
    ):
        raise RuntimeError("projection gate is not a complete raw-parity pass")
    extra_projection_ms = float(
        projection_gate["six_layer_extra_projection_ms"]
    )

    device = torch.device(f"xpu:{rank}")
    torch.xpu.set_device(device)
    dist.init_process_group(
        backend="xccl",
        rank=rank,
        world_size=world_size,
        timeout=datetime.timedelta(seconds=90),
    )
    payload = torch.empty((12, 3072), dtype=torch.bfloat16, device=device)

    def reduction_batch() -> None:
        for _ in range(12):
            payload.fill_(rank + 1)
            dist.all_reduce(payload)
            torch.xpu.synchronize()

    for _ in range(10):
        reduction_batch()
    dist.barrier()
    torch.xpu.synchronize()

    samples = []
    for _ in range(51):
        start = time.perf_counter_ns()
        reduction_batch()
        samples.append((time.perf_counter_ns() - start) / 1_000_000)
    valid = bool(torch.count_nonzero(payload != 10).item() == 0)
    record = {
        "rank": rank,
        "valid": valid,
        "samples": len(samples),
        "median_12_reductions_ms": statistics.median(samples),
        "mean_12_reductions_ms": statistics.fmean(samples),
        "minimum_12_reductions_ms": min(samples),
        "maximum_12_reductions_ms": max(samples),
        "median_per_reduction_us": statistics.median(samples) * 1000 / 12,
    }
    (output_root / f"rank{rank}.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    )

    dist.barrier()
    if rank == 0:
        ranks = [
            json.loads((output_root / f"rank{index}.json").read_text())
            for index in range(4)
        ]
        max_rank_median = max(row["median_12_reductions_ms"] for row in ranks)
        required_gross_ms = extra_projection_ms + 1.4
        summary = {
            "schema": "laguna-tp4-collective-latency-gate-v1",
            "status": "PASS" if all(row["valid"] for row in ranks) else "FAIL",
            "rows": 12,
            "hidden_size": 3072,
            "dtype": "bfloat16",
            "reductions_per_cycle": 12,
            "synchronize_each_reduction": True,
            "rank_records": ranks,
            "max_rank_median_12_reductions_ms": max_rank_median,
            "projection_gate": str(projection_gate_path),
            "measured_extra_local_projection_ms": extra_projection_ms,
            "required_net_saving_ms": 1.4,
            "required_gross_collective_ms": required_gross_ms,
            "can_clear_component_gate_before_extra_attention": (
                max_rank_median >= required_gross_ms
            ),
            "authorizes_endpoint": False,
        }
        (output_root / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
        print(json.dumps(summary, indent=2, sort_keys=True), flush=True)

    dist.barrier()
    dist.destroy_process_group()
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
