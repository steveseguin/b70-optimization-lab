#!/usr/bin/env python3
"""Bounded TP4 BF16 allreduce threshold microbenchmark.

The ``rank`` command is intended to be launched by torchrun.  The ``summarize``
command is CPU-only and combines independently launched process-group trials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any


EXPECTED_LIBCCL_SHA256 = (
    "ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3"
)
EXPECTED_WORLD_SIZE = 4
EXPECTED_ROWS = 1
EXPECTED_HIDDEN = 2560
EXPECTED_BYTES = EXPECTED_ROWS * EXPECTED_HIDDEN * 2
THRESHOLDS = {4096: "Rt64_128_PCIE", 8192: "Rt64_PCIE"}


class BenchmarkContractError(RuntimeError):
    """Raised when a benchmark identity or evidence contract is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def raw_tensor_sha256(tensor: Any) -> str:
    raw = tensor.contiguous().view(__import__("torch").uint8).cpu().numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def nearest_rank_percentile(values: list[float], probability: float) -> float:
    if not values:
        raise BenchmarkContractError("cannot summarize an empty latency series")
    if not 0 < probability <= 1:
        raise ValueError("probability must be in (0, 1]")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(probability * len(ordered)) - 1)]


def latency_summary(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "median_us": statistics.median(values),
        "p95_us": nearest_rank_percentile(values, 0.95),
        "p99_us": nearest_rank_percentile(values, 0.99),
        "max_us": max(values),
    }


def extract_kernel_names(trace: Path) -> list[str]:
    document = json.loads(trace.read_text(encoding="utf-8"))
    names = {
        str(event.get("name", ""))
        for event in document.get("traceEvents", [])
        if event.get("ph") == "X"
        and any(
            token in str(event.get("name", ""))
            for token in ("Rt64_PCIE", "Rt64_128_PCIE", "oneccl_allreduce")
        )
    }
    return sorted(names)


def _require_keys(payload: dict[str, Any], keys: set[str], label: str) -> None:
    missing = sorted(keys - payload.keys())
    if missing:
        raise BenchmarkContractError(f"{label} is missing fields: {missing}")


def summarize_rank_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    if len(payloads) != EXPECTED_WORLD_SIZE:
        raise BenchmarkContractError(
            f"expected {EXPECTED_WORLD_SIZE} rank payloads, found {len(payloads)}"
        )
    required = {
        "rank",
        "world_size",
        "rows",
        "hidden",
        "bytes",
        "threshold_bytes",
        "expected_kernel_token",
        "output_sha256",
        "oracle_sha256",
        "oracle_match",
        "latency_us",
        "kernel_names",
        "loaded_libccl_path",
        "loaded_libccl_sha256",
    }
    for index, payload in enumerate(payloads):
        _require_keys(payload, required, f"rank payload {index}")

    ranks = sorted(int(payload["rank"]) for payload in payloads)
    if ranks != list(range(EXPECTED_WORLD_SIZE)):
        raise BenchmarkContractError(f"rank set is not exact: {ranks}")
    singleton_fields = (
        "world_size",
        "rows",
        "hidden",
        "bytes",
        "threshold_bytes",
        "expected_kernel_token",
        "output_sha256",
        "oracle_sha256",
        "loaded_libccl_sha256",
    )
    identities = {
        field: {json.dumps(payload[field], sort_keys=True) for payload in payloads}
        for field in singleton_fields
    }
    divergent = {
        field: values for field, values in identities.items() if len(values) != 1
    }
    if divergent:
        raise BenchmarkContractError(f"rank identities diverge: {divergent}")

    first = payloads[0]
    if int(first["world_size"]) != EXPECTED_WORLD_SIZE:
        raise BenchmarkContractError("world size is not four")
    if (int(first["rows"]), int(first["hidden"]), int(first["bytes"])) != (
        EXPECTED_ROWS,
        EXPECTED_HIDDEN,
        EXPECTED_BYTES,
    ):
        raise BenchmarkContractError("tensor shape is not frozen BF16 [1,2560]")
    threshold = int(first["threshold_bytes"])
    if threshold not in THRESHOLDS:
        raise BenchmarkContractError(f"unregistered threshold: {threshold}")
    if first["expected_kernel_token"] != THRESHOLDS[threshold]:
        raise BenchmarkContractError("kernel expectation does not match threshold")
    if first["loaded_libccl_sha256"] != EXPECTED_LIBCCL_SHA256:
        raise BenchmarkContractError("loaded libccl identity is not frozen")
    if first["output_sha256"] != first["oracle_sha256"]:
        raise BenchmarkContractError("allreduce output hash differs from oracle")
    if not all(payload["oracle_match"] for payload in payloads):
        raise BenchmarkContractError("one or more ranks failed the output oracle")

    latency_lengths = {len(payload["latency_us"]) for payload in payloads}
    if (
        len(latency_lengths) != 1
        or not latency_lengths
        or next(iter(latency_lengths)) < 1
    ):
        raise BenchmarkContractError("rank latency series lengths differ or are empty")
    expected_kernel = THRESHOLDS[threshold]
    for payload in payloads:
        names = payload["kernel_names"]
        if not names or not any(expected_kernel in name for name in names):
            raise BenchmarkContractError(
                f"rank {payload['rank']} lacks {expected_kernel} kernel receipt"
            )
        if threshold == 8192 and any("Rt64_128_PCIE" in name for name in names):
            raise BenchmarkContractError("candidate unexpectedly used Rt64_128_PCIE")

    ordered_payloads = sorted(payloads, key=lambda payload: int(payload["rank"]))
    iteration_count = next(iter(latency_lengths))
    slowest = [
        max(float(payload["latency_us"][index]) for payload in ordered_payloads)
        for index in range(iteration_count)
    ]
    return {
        "schema_version": 1,
        "status": "passed",
        "classification": "isolated_tp4_bf16_allreduce_component",
        "shape": [EXPECTED_ROWS, EXPECTED_HIDDEN],
        "dtype": "bfloat16",
        "bytes": EXPECTED_BYTES,
        "threshold_bytes": threshold,
        "expected_kernel_token": expected_kernel,
        "world_size": EXPECTED_WORLD_SIZE,
        "iterations": iteration_count,
        "output_sha256": first["output_sha256"],
        "loaded_libccl_sha256": first["loaded_libccl_sha256"],
        "loaded_libccl_paths": sorted(
            {str(payload["loaded_libccl_path"]) for payload in payloads}
        ),
        "rank_latency": {
            str(payload["rank"]): latency_summary(
                [float(value) for value in payload["latency_us"]]
            )
            for payload in ordered_payloads
        },
        "slowest_rank_latency": latency_summary(slowest),
        "slowest_rank_latency_us": slowest,
        "kernel_names_by_rank": {
            str(payload["rank"]): payload["kernel_names"]
            for payload in ordered_payloads
        },
    }


def summarize_trials(summary_paths: list[Path], output: Path) -> dict[str, Any]:
    trials = [json.loads(path.read_text(encoding="utf-8")) for path in summary_paths]
    if not trials:
        raise BenchmarkContractError("no trial summaries supplied")
    for index, trial in enumerate(trials):
        if trial.get("status") != "passed":
            raise BenchmarkContractError(f"trial {index} did not pass")
        if trial.get("shape") != [EXPECTED_ROWS, EXPECTED_HIDDEN]:
            raise BenchmarkContractError(f"trial {index} shape drifted")
        if trial.get("loaded_libccl_sha256") != EXPECTED_LIBCCL_SHA256:
            raise BenchmarkContractError(f"trial {index} libccl drifted")

    thresholds = {int(trial["threshold_bytes"]) for trial in trials}
    if thresholds != set(THRESHOLDS):
        raise BenchmarkContractError(
            f"expected thresholds 4096 and 8192, found {thresholds}"
        )
    hashes = {trial["output_sha256"] for trial in trials}
    if len(hashes) != 1:
        raise BenchmarkContractError(
            "output hashes differ across process starts or arms"
        )

    arms: dict[str, Any] = {}
    trial_counts = []
    for threshold in sorted(THRESHOLDS):
        arm_trials = [
            trial for trial in trials if int(trial["threshold_bytes"]) == threshold
        ]
        trial_counts.append(len(arm_trials))
        combined = [
            float(value)
            for trial in arm_trials
            for value in trial["slowest_rank_latency_us"]
        ]
        arms[str(threshold)] = {
            "fresh_process_trials": len(arm_trials),
            "expected_kernel_token": THRESHOLDS[threshold],
            "slowest_rank_latency": latency_summary(combined),
            "trial_summaries": [
                str(path)
                for path, trial in zip(summary_paths, trials)
                if int(trial["threshold_bytes"]) == threshold
            ],
        }
    if len(set(trial_counts)) != 1:
        raise BenchmarkContractError(f"arm trial counts differ: {trial_counts}")

    control = float(arms["4096"]["slowest_rank_latency"]["median_us"])
    candidate = float(arms["8192"]["slowest_rank_latency"]["median_us"])
    result = {
        "schema_version": 1,
        "status": "passed",
        "classification": "isolated_tp4_bf16_allreduce_threshold_ab",
        "shape": [EXPECTED_ROWS, EXPECTED_HIDDEN],
        "dtype": "bfloat16",
        "bytes": EXPECTED_BYTES,
        "world_size": EXPECTED_WORLD_SIZE,
        "output_sha256": next(iter(hashes)),
        "loaded_libccl_sha256": EXPECTED_LIBCCL_SHA256,
        "arms": arms,
        "candidate_over_control_median_ratio": candidate / control,
        "candidate_median_speedup_fraction": (control - candidate) / control,
        "interpretation": "component_only_not_endpoint_performance_evidence",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise BenchmarkContractError(f"refusing to overwrite {output}")
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def _loaded_library_path(stem: str) -> Path:
    matches: set[Path] = set()
    for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 6 and stem in Path(fields[-1]).name:
            matches.add(Path(fields[-1]).resolve())
    if len(matches) != 1:
        raise BenchmarkContractError(
            f"expected one loaded {stem}, found {sorted(matches)}"
        )
    return next(iter(matches))


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def run_rank(args: argparse.Namespace) -> None:
    import torch
    import torch.distributed as dist

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != EXPECTED_WORLD_SIZE:
        raise BenchmarkContractError(f"world size must be {EXPECTED_WORLD_SIZE}")
    threshold = int(os.environ.get("CCL_SYCL_ALLREDUCE_LL_THRESHOLD", "-1"))
    if threshold != args.threshold_bytes or threshold not in THRESHOLDS:
        raise BenchmarkContractError("live oneCCL threshold does not match the arm")
    if args.rows != EXPECTED_ROWS or args.hidden != EXPECTED_HIDDEN:
        raise BenchmarkContractError("only BF16 [1,2560] is permitted")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device(f"xpu:{local_rank}")
    torch.xpu.set_device(device)
    dist.init_process_group("xccl")
    try:
        indices = torch.arange(args.rows * args.hidden, dtype=torch.int64)
        local_integer = ((indices * 17 + rank * 3) % 9) - 4
        base = (
            local_integer.to(torch.bfloat16).reshape(args.rows, args.hidden).to(device)
        )
        oracle_integer = sum(
            ((indices * 17 + other_rank * 3) % 9) - 4
            for other_rank in range(world_size)
        )
        oracle = oracle_integer.to(torch.bfloat16).reshape(args.rows, args.hidden)

        for _ in range(args.warmup):
            value = base.clone()
            dist.all_reduce(value, op=dist.ReduceOp.SUM)
            torch.xpu.synchronize()

        latencies: list[float] = []
        value = base.clone()
        for _ in range(args.iterations):
            value = base.clone()
            dist.barrier(device_ids=[local_rank])
            torch.xpu.synchronize()
            start = time.perf_counter_ns()
            dist.all_reduce(value, op=dist.ReduceOp.SUM)
            torch.xpu.synchronize()
            latencies.append((time.perf_counter_ns() - start) / 1000.0)

        trace_path = output_dir / f"kineto-rank-{rank}.json"
        activities = [
            torch.profiler.ProfilerActivity.CPU,
            torch.profiler.ProfilerActivity.XPU,
        ]
        with torch.profiler.profile(activities=activities) as profile:
            receipt_value = base.clone()
            dist.barrier(device_ids=[local_rank])
            torch.xpu.synchronize()
            dist.all_reduce(receipt_value, op=dist.ReduceOp.SUM)
            torch.xpu.synchronize()
        profile.export_chrome_trace(str(trace_path))
        kernel_names = extract_kernel_names(trace_path)

        output_cpu = value.cpu()
        output_hash = raw_tensor_sha256(output_cpu)
        oracle_hash = raw_tensor_sha256(oracle)
        libccl = _loaded_library_path("libccl.so.1")
        libsycl = _loaded_library_path("libsycl.so")
        payload = {
            "schema_version": 1,
            "rank": rank,
            "local_rank": local_rank,
            "world_size": world_size,
            "rows": args.rows,
            "hidden": args.hidden,
            "bytes": EXPECTED_BYTES,
            "dtype": "bfloat16",
            "warmup": args.warmup,
            "iterations": args.iterations,
            "threshold_bytes": threshold,
            "expected_kernel_token": THRESHOLDS[threshold],
            "output_sha256": output_hash,
            "oracle_sha256": oracle_hash,
            "oracle_match": bool(torch.equal(output_cpu, oracle)),
            "latency_us": latencies,
            "kernel_trace": str(trace_path),
            "kernel_names": kernel_names,
            "loaded_libccl_path": str(libccl),
            "loaded_libccl_sha256": sha256_file(libccl),
            "loaded_libsycl_path": str(libsycl),
            "loaded_libsycl_sha256": sha256_file(libsycl),
            "torch_version": torch.__version__,
            "python": sys.executable,
        }
        _atomic_json(output_dir / f"rank-{rank}.json", payload)
        dist.barrier(device_ids=[local_rank])
        if rank == 0:
            rank_payloads = [
                json.loads(
                    (output_dir / f"rank-{item}.json").read_text(encoding="utf-8")
                )
                for item in range(world_size)
            ]
            summary = summarize_rank_payloads(rank_payloads)
            summary["warmup"] = args.warmup
            _atomic_json(output_dir / "summary.json", summary)
    finally:
        dist.destroy_process_group()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    rank = subparsers.add_parser("rank")
    rank.add_argument("--output-dir", type=Path, required=True)
    rank.add_argument(
        "--threshold-bytes", type=int, choices=sorted(THRESHOLDS), required=True
    )
    rank.add_argument("--rows", type=int, default=EXPECTED_ROWS)
    rank.add_argument("--hidden", type=int, default=EXPECTED_HIDDEN)
    rank.add_argument("--warmup", type=int, default=50)
    rank.add_argument("--iterations", type=int, default=500)

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--output", type=Path, required=True)
    summarize.add_argument("summaries", type=Path, nargs="+")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "rank":
        if not 1 <= args.warmup <= 200:
            raise BenchmarkContractError("warmup must be in [1,200]")
        if not 20 <= args.iterations <= 2000:
            raise BenchmarkContractError("iterations must be in [20,2000]")
        run_rank(args)
    else:
        result = summarize_trials(args.summaries, args.output)
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
