#!/usr/bin/env python3
"""Measure TP4 count-2560 collective-cycle sensitivity to CPU affinity."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
from typing import Any


WORLD_SIZE = 4
COLLECTIVES = 97
HIDDEN = 2560
WARMUP = 8
CYCLES = 60
EXPECTED_LIBCCL_SHA256 = (
    "ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3"
)
EXPECTED_LIBSYCL_SHA256 = (
    "0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f"
)
FULL_AFFINITY = tuple(range(32))
PINNED_AFFINITY = {
    0: (0, 1, 2, 3, 16, 17, 18, 19),
    1: (4, 5, 6, 7, 20, 21, 22, 23),
    2: (8, 9, 10, 11, 24, 25, 26, 27),
    3: (12, 13, 14, 15, 28, 29, 30, 31),
}
CONTROL_WORKER_AFFINITY = "31,30,29,28"
PINNED_WORKER_AFFINITY = "19,23,27,31"
CONTROL_WORKER_CPUS = (31, 30, 29, 28)
PINNED_WORKER_CPUS = (19, 23, 27, 31)


class GateError(RuntimeError):
    """Raised when the frozen component contract is not satisfied."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_sha256(tensor: Any) -> str:
    import torch

    raw = tensor.contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(probability * len(ordered)) - 1)]


def latency_summary(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "median_ms": statistics.median(values),
        "p90_ms": percentile(values, 0.90),
        "minimum_ms": min(values),
        "maximum_ms": max(values),
    }


def mapped_library(stem: str) -> dict[str, str]:
    paths = {
        Path(line.split()[-1]).resolve()
        for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines()
        if len(line.split()) >= 6 and stem in Path(line.split()[-1]).name
    }
    paths = {path for path in paths if path.is_file()}
    if len(paths) != 1:
        raise GateError(f"expected one mapped {stem}, found {sorted(paths)}")
    path = next(iter(paths))
    return {"path": str(path), "sha256": sha256_file(path)}


def extract_protocol_names(trace: Path) -> list[str]:
    document = json.loads(trace.read_text(encoding="utf-8"))
    return sorted(
        {
            str(event.get("name", ""))
            for event in document.get("traceEvents", [])
            if event.get("ph") == "X"
            and any(
                token in str(event.get("name", ""))
                for token in ("Rt64_128_PCIE", "Rt64_PCIE", "oneccl_allreduce")
            )
        }
    )


def parse_cpu_list(value: str) -> tuple[int, ...]:
    cpus: list[int] = []
    for item in value.split(","):
        bounds = item.split("-", maxsplit=1)
        start = int(bounds[0])
        stop = int(bounds[-1])
        cpus.extend(range(start, stop + 1))
    return tuple(cpus)


def thread_affinity_receipt() -> list[dict[str, Any]]:
    receipt: list[dict[str, Any]] = []
    for task in sorted(
        Path("/proc/self/task").iterdir(), key=lambda item: int(item.name)
    ):
        try:
            status = task.joinpath("status").read_text(encoding="utf-8")
            comm = task.joinpath("comm").read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            continue
        fields = {
            key: value.strip()
            for line in status.splitlines()
            if ":" in line
            for key, value in [line.split(":", maxsplit=1)]
        }
        allowed_text = fields.get("Cpus_allowed_list")
        if not allowed_text:
            raise GateError(f"task {task.name} lacks Cpus_allowed_list")
        receipt.append(
            {
                "tid": int(task.name),
                "comm": comm,
                "cpus_allowed_list": allowed_text,
                "cpus_allowed": parse_cpu_list(allowed_text),
            }
        )
    if not receipt:
        raise GateError("thread-affinity receipt is empty")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("control", "pinned"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != WORLD_SIZE:
        raise GateError(f"requires world size {WORLD_SIZE}, got {world_size}")
    if rank != local_rank:
        raise GateError(
            f"requires single-node rank==local_rank, got {rank}/{local_rank}"
        )
    inherited_affinity = tuple(sorted(os.sched_getaffinity(0)))
    if inherited_affinity != FULL_AFFINITY:
        raise GateError(f"inherited CPU affinity drifted: {inherited_affinity}")
    if args.mode == "pinned":
        os.sched_setaffinity(0, PINNED_AFFINITY[rank])
    effective_affinity = tuple(sorted(os.sched_getaffinity(0)))
    expected_affinity = (
        FULL_AFFINITY if args.mode == "control" else PINNED_AFFINITY[rank]
    )
    if effective_affinity != expected_affinity:
        raise GateError(
            f"effective affinity {effective_affinity} != {expected_affinity}"
        )
    expected_worker_env = (
        CONTROL_WORKER_AFFINITY if args.mode == "control" else PINNED_WORKER_AFFINITY
    )
    actual_worker_env = os.environ.get("CCL_WORKER_AFFINITY")
    if actual_worker_env != expected_worker_env:
        raise GateError(
            f"CCL_WORKER_AFFINITY {actual_worker_env!r} != {expected_worker_env!r}"
        )
    expected_worker_cpu = (
        CONTROL_WORKER_CPUS[rank]
        if args.mode == "control"
        else PINNED_WORKER_CPUS[rank]
    )

    # Import only after the rank affinity is fixed. oneCCL's worker has its own
    # explicit affinity contract and is verified independently below.
    import torch
    import torch.distributed as dist

    output_dir = args.output_dir.resolve()
    rank_json = output_dir / f"rank-{rank}.json"
    trace = output_dir / f"rank-{rank}.kineto.json"
    if rank_json.exists() or trace.exists():
        raise GateError("refusing to overwrite rank evidence")
    output_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device(f"xpu:{local_rank}")
    torch.xpu.set_device(device)
    dist.init_process_group("xccl", device_id=device)
    try:
        libccl = mapped_library("libccl.so.1")
        libsycl = mapped_library("libsycl.so")
        if libccl["sha256"] != EXPECTED_LIBCCL_SHA256:
            raise GateError(f"libccl drift: {libccl}")
        if libsycl["sha256"] != EXPECTED_LIBSYCL_SHA256:
            raise GateError(f"libsycl drift: {libsycl}")
        # Force lazy collective/executor initialization before inspecting the
        # oneCCL worker's independently assigned CPU.
        dist.barrier(device_ids=[local_rank])
        torch.xpu.synchronize()
        thread_affinity = thread_affinity_receipt()
        if args.mode == "pinned":
            rank_cpu_set = set(PINNED_AFFINITY[rank])
            outside = [
                item
                for item in thread_affinity
                if not set(item["cpus_allowed"]).issubset(rank_cpu_set)
            ]
            if outside:
                raise GateError(f"pinned runtime threads escaped rank set: {outside}")
        worker_receipts = [
            item
            for item in thread_affinity
            if tuple(item["cpus_allowed"]) == (expected_worker_cpu,)
        ]
        if not worker_receipts:
            raise GateError(
                f"no oneCCL worker receipt pinned to CPU {expected_worker_cpu}: "
                f"{thread_affinity}"
            )

        index = torch.arange(
            COLLECTIVES * HIDDEN, dtype=torch.int32, device=device
        ).reshape(COLLECTIVES, 1, HIDDEN)
        local = torch.empty(
            (COLLECTIVES, 1, HIDDEN), dtype=torch.bfloat16, device=device
        )
        oracle = torch.empty_like(local)

        def prepare(epoch: int) -> None:
            local.copy_(
                ((index * 17 + rank * 7 + epoch * 11) % 127 - 63).to(torch.bfloat16)
            )
            expected = torch.zeros_like(index)
            for source_rank in range(WORLD_SIZE):
                expected.add_((index * 17 + source_rank * 7 + epoch * 11) % 127 - 63)
            oracle.copy_(expected.to(torch.bfloat16))
            torch.xpu.synchronize()

        def cycle() -> list[torch.Tensor]:
            outputs = []
            for item in local:
                output = item.clone()
                dist.all_reduce(output, op=dist.ReduceOp.SUM)
                outputs.append(output)
            return outputs

        for epoch in range(WARMUP):
            prepare(epoch + 11)
            cycle()
            torch.xpu.synchronize()

        latency_ms: list[float] = []
        mismatches: list[int] = []
        outputs: list[torch.Tensor] = []
        for epoch in range(CYCLES):
            prepare(epoch + 101)
            dist.barrier(device_ids=[local_rank])
            torch.xpu.synchronize()
            started = time.perf_counter_ns()
            outputs = cycle()
            torch.xpu.synchronize()
            latency_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)
            mismatches.append(int((torch.stack(outputs) != oracle).sum().item()))

        prepare(701)
        receipt = local[0].clone()
        dist.barrier(device_ids=[local_rank])
        torch.xpu.synchronize()
        activities = [
            torch.profiler.ProfilerActivity.CPU,
            torch.profiler.ProfilerActivity.XPU,
        ]
        with torch.profiler.profile(activities=activities) as profile:
            dist.all_reduce(receipt, op=dist.ReduceOp.SUM)
            torch.xpu.synchronize()
        profile.export_chrome_trace(str(trace))
        protocol_names = extract_protocol_names(trace)
        if not any("Rt64_128_PCIE" in name for name in protocol_names):
            raise GateError(f"missing Rt64_128_PCIE receipt: {protocol_names}")
        if any("Rt64_PCIE" in name for name in protocol_names):
            raise GateError(f"unexpected Rt64_PCIE receipt: {protocol_names}")
        receipt_mismatches = int((receipt != oracle[0]).sum().item())
        payload = {
            "schema_version": 1,
            "rank": rank,
            "local_rank": local_rank,
            "world_size": world_size,
            "mode": args.mode,
            "inherited_affinity": inherited_affinity,
            "effective_affinity": effective_affinity,
            "ccl_worker_affinity": actual_worker_env,
            "expected_worker_cpu": expected_worker_cpu,
            "thread_affinity": thread_affinity,
            "device": torch.xpu.get_device_name(device),
            "collectives_per_cycle": COLLECTIVES,
            "shape": [1, HIDDEN],
            "dtype": "bfloat16",
            "warmup": WARMUP,
            "cycles": CYCLES,
            "latency_ms": latency_ms,
            "mismatches_by_cycle": mismatches,
            "receipt_mismatches": receipt_mismatches,
            "final_output_sha256": tensor_sha256(torch.stack(outputs)),
            "protocol_names": protocol_names,
            "trace_sha256": sha256_file(trace),
            "libccl": libccl,
            "libsycl": libsycl,
        }
        rank_json.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        dist.barrier(device_ids=[local_rank])

        if rank == 0:
            ranks = [
                json.loads((output_dir / f"rank-{item}.json").read_text())
                for item in range(WORLD_SIZE)
            ]
            if any(any(item["mismatches_by_cycle"]) for item in ranks):
                raise GateError("one or more measured cycles failed the oracle")
            if any(item["receipt_mismatches"] for item in ranks):
                raise GateError("one or more protocol receipts failed the oracle")
            hashes = {item["final_output_sha256"] for item in ranks}
            if len(hashes) != 1:
                raise GateError(f"rank output hashes differ: {hashes}")
            slowest = [
                max(float(item["latency_ms"][cycle]) for item in ranks)
                for cycle in range(CYCLES)
            ]
            summary = {
                "schema_version": 1,
                "status": "passed",
                "classification": "tp4_count2560_collective_cycle_cpu_affinity_arm",
                "mode": args.mode,
                "world_size": WORLD_SIZE,
                "collectives_per_cycle": COLLECTIVES,
                "shape": [1, HIDDEN],
                "dtype": "bfloat16",
                "cycles": CYCLES,
                "output_sha256": next(iter(hashes)),
                "slowest_rank_latency": latency_summary(slowest),
                "slowest_rank_latency_ms": slowest,
                "ranks": ranks,
            }
            summary_path = output_dir / "summary.json"
            if summary_path.exists():
                raise GateError("refusing to overwrite arm summary")
            summary_path.write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(summary, sort_keys=True), flush=True)

        dist.barrier(device_ids=[local_rank])
    finally:
        dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
