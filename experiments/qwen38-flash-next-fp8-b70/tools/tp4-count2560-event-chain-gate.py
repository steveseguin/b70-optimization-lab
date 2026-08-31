#!/usr/bin/env python3
"""Gate the Qwen Flash-Next fixed-shape TP4 oneCCL event chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
from typing import Any, Callable

import torch
import torch.distributed as dist
import vllm_xpu_kernels._xpu_C as xpu_extension  # noqa: F401

from vllm.models.qwen4_exp.amd.ops.hc import hc_combine, hc_combine_norm


WORLD_SIZE = 4
COLLECTIVES = 97
HIDDEN = 2560
HC_COUNT = 4
CONSUMERS = 96
NORM_CONSUMERS = 95
EPS = 1e-6
WARMUP = 8
EPOCHS = 40
REQUIRED_SAVE_MS = 4.0
REQUIRED_P90_SAVE_MS = 3.0
REQUIRED_PERCENT = 10.0
REQUIRED_POSITIVE_PAIRS = 32
REQUIRED_ORDER_STRATUM_SAVE_MS = 3.0
EXPECTED_LIBCCL_SHA256 = (
    "164091ac6aced05bfc658ae1e1cd722153f099714e9cee6f437c62bdd3731c1c"
)
EXPECTED_XPU_EXTENSION_SHA256 = (
    "776a080846bfe26c92f10ecb80982f45137802cf10af4a7d66b9c0d6af1cd339"
)


class GateError(RuntimeError):
    """Raised when the frozen component contract is not satisfied."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_sha256(tensor: torch.Tensor) -> str:
    raw = tensor.contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def mapped_libraries(token: str) -> list[dict[str, str]]:
    paths = {
        Path(line.split()[-1]).resolve()
        for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines()
        if token in line and line.split()[-1].startswith("/")
    }
    return [
        {"path": str(path), "sha256": sha256_file(path)}
        for path in sorted(paths)
        if path.is_file()
    ]


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("B70_ONECCL_ENABLE_Q38_COUNT2560_EVENT_CHAIN") != "1":
        raise GateError("the default-off Qwen event-chain flag must equal 1")
    sidecars = [
        args.output.with_suffix(args.output.suffix + f".rank{rank}.json")
        for rank in range(WORLD_SIZE)
    ]
    traces = [
        args.output.with_suffix(args.output.suffix + f".rank{rank}.kineto.json")
        for rank in range(WORLD_SIZE)
    ]
    existing = [
        str(path) for path in (args.output, *sidecars, *traces) if path.exists()
    ]
    if existing:
        raise GateError(f"refusing to overwrite evidence: {existing}")

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != WORLD_SIZE:
        raise GateError(f"requires world size {WORLD_SIZE}, got {world_size}")
    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group("xccl", device_id=device)
    stream = torch.xpu.current_stream(device)
    extension_path = Path(xpu_extension.__file__).resolve()
    extension_sha256 = sha256_file(extension_path)
    if extension_sha256 != EXPECTED_XPU_EXTENSION_SHA256:
        raise GateError(
            f"XPU extension drift: {extension_sha256} != "
            f"{EXPECTED_XPU_EXTENSION_SHA256}"
        )
    libccl_maps = mapped_libraries("libccl.so.1")
    if len(libccl_maps) != 1:
        raise GateError(f"expected one mapped libccl, found {libccl_maps}")
    if libccl_maps[0]["sha256"] != EXPECTED_LIBCCL_SHA256:
        raise GateError(
            f"libccl drift: {libccl_maps[0]['sha256']} != {EXPECTED_LIBCCL_SHA256}"
        )

    index = torch.arange(
        COLLECTIVES * HIDDEN, dtype=torch.int32, device=device
    ).reshape(COLLECTIVES, 1, HIDDEN)
    local = torch.empty((COLLECTIVES, 1, HIDDEN), dtype=torch.bfloat16, device=device)
    analytic = torch.empty_like(local)
    residual_index = torch.arange(
        CONSUMERS * HC_COUNT * HIDDEN, dtype=torch.int32, device=device
    ).reshape(CONSUMERS, 1, HC_COUNT * HIDDEN)
    residual = torch.empty(
        (CONSUMERS, 1, HC_COUNT * HIDDEN),
        dtype=torch.bfloat16,
        device=device,
    )
    injection_index = torch.arange(
        CONSUMERS * HC_COUNT, dtype=torch.int32, device=device
    ).reshape(CONSUMERS, 1, HC_COUNT)
    injection = torch.empty(
        (CONSUMERS, 1, HC_COUNT), dtype=torch.bfloat16, device=device
    )
    norm_weight = (
        torch.linspace(-0.125, 0.125, HIDDEN, dtype=torch.float32)
        .to(torch.bfloat16)
        .to(device)
    )

    def prepare(epoch: int) -> None:
        local.copy_(
            ((index * 17 + rank * 7 + epoch * 11) % 127 - 63).to(torch.bfloat16)
        )
        expected = torch.zeros_like(index)
        for source_rank in range(WORLD_SIZE):
            expected.add_((index * 17 + source_rank * 7 + epoch * 11) % 127 - 63)
        analytic.copy_(expected.to(torch.bfloat16))
        residual.copy_(
            (((residual_index * 13 + epoch * 5) % 257 - 128).float() / 256).to(
                torch.bfloat16
            )
        )
        injection.copy_(
            (((injection_index * 7 + epoch * 3) % 61 - 30).float() / 64).to(
                torch.bfloat16
            )
        )
        stream.synchronize()

    def consume(
        output: torch.Tensor, ordinal: int, witnesses: list[torch.Tensor]
    ) -> None:
        boundary = ordinal - 1
        if ordinal == 2:
            witnesses.append(
                hc_combine(residual[boundary], output, injection[boundary], HC_COUNT)
            )
        else:
            combined, normalized = hc_combine_norm(
                residual[boundary],
                output,
                injection[boundary],
                norm_weight,
                EPS,
                HC_COUNT,
            )
            witnesses.extend((combined, normalized))

    def baseline() -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        outputs: list[torch.Tensor] = []
        witnesses: list[torch.Tensor] = []
        for ordinal, item in enumerate(local):
            # This clone is the exact current XpuCommunicator out-of-place
            # implementation, not extra benchmark-only work.
            output = item.clone()
            dist.all_reduce(output, op=dist.ReduceOp.SUM)
            outputs.append(output)
            if ordinal:
                consume(output, ordinal, witnesses)
        return outputs, witnesses

    def candidate() -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        outputs: list[torch.Tensor] = []
        witnesses: list[torch.Tensor] = []
        for ordinal, item in enumerate(local):
            output = torch.ops._xpu_C.q38_tp4_oneccl_allreduce_count2560(item)
            outputs.append(output)
            if ordinal:
                consume(output, ordinal, witnesses)
        return outputs, witnesses

    def synchronize() -> None:
        stream.synchronize()

    def timed(call: Callable[[], tuple[list[torch.Tensor], list[torch.Tensor]]]):
        synchronize()
        dist.barrier(device_ids=[local_rank])
        started = time.perf_counter()
        result = call()
        synchronize()
        local_ms = (time.perf_counter() - started) * 1000.0
        local_time = torch.tensor(local_ms, dtype=torch.float64, device=device)
        rank_times = [torch.empty_like(local_time) for _ in range(WORLD_SIZE)]
        dist.all_gather(rank_times, local_time)
        return result, local_ms, max(float(item.item()) for item in rank_times)

    # The normal collective captures the exact communicator and stream used by
    # the default-off bridge. It is outside every timed window.
    prepare(701)
    prime = local[0].clone()
    dist.all_reduce(prime, op=dist.ReduceOp.SUM)
    synchronize()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    trace_path = traces[rank]
    with torch.profiler.profile(
        activities=[
            torch.profiler.ProfilerActivity.CPU,
            torch.profiler.ProfilerActivity.XPU,
        ]
    ) as profile:
        receipt = torch.ops._xpu_C.q38_tp4_oneccl_allreduce_count2560(local[0])
        synchronize()
    profile.export_chrome_trace(str(trace_path))
    protocol_names = extract_protocol_names(trace_path)
    if not any("Rt64_128_PCIE" in name for name in protocol_names):
        raise GateError(f"candidate trace lacks Rt64_128_PCIE: {protocol_names}")
    if any("Rt64_PCIE" in name for name in protocol_names):
        raise GateError(f"candidate trace used neutral Rt64_PCIE: {protocol_names}")
    if int((receipt != analytic[0]).sum().item()) != 0:
        raise GateError("protocol receipt differs from the analytic SUM oracle")

    for epoch in range(WARMUP):
        prepare(epoch + 11)
        order = (baseline, candidate) if epoch % 2 == 0 else (candidate, baseline)
        for call in order:
            call()
            synchronize()

    names = ("baseline", "candidate")
    calls = {"baseline": baseline, "candidate": candidate}
    local_samples = {name: [] for name in names}
    max_rank_samples = {name: [] for name in names}
    collective_mismatches: list[int] = []
    baseline_oracle_mismatches: list[int] = []
    candidate_oracle_mismatches: list[int] = []
    consumer_mismatches: list[int] = []
    final_results: dict[str, tuple[list[torch.Tensor], list[torch.Tensor]]] = {}
    for epoch in range(EPOCHS):
        prepare(epoch + 101)
        order = names if epoch % 2 == 0 else tuple(reversed(names))
        epoch_results = {}
        for name in order:
            result, local_ms, max_rank_ms = timed(calls[name])
            epoch_results[name] = result
            local_samples[name].append(local_ms)
            max_rank_samples[name].append(max_rank_ms)
        final_results = epoch_results
        baseline_outputs, baseline_consumers = epoch_results["baseline"]
        candidate_outputs, candidate_consumers = epoch_results["candidate"]
        collective_mismatches.append(
            sum(
                int((actual != expected).sum().item())
                for actual, expected in zip(
                    candidate_outputs, baseline_outputs, strict=True
                )
            )
        )
        baseline_oracle_mismatches.append(
            int((torch.stack(baseline_outputs) != analytic).sum().item())
        )
        candidate_oracle_mismatches.append(
            int((torch.stack(candidate_outputs) != analytic).sum().item())
        )
        consumer_mismatches.append(
            sum(
                int((actual != expected).sum().item())
                for actual, expected in zip(
                    candidate_consumers, baseline_consumers, strict=True
                )
            )
        )

    baseline_summary = latency_summary(max_rank_samples["baseline"])
    candidate_summary = latency_summary(max_rank_samples["candidate"])
    saved_ms = float(baseline_summary["median_ms"]) - float(
        candidate_summary["median_ms"]
    )
    p90_saved_ms = float(baseline_summary["p90_ms"]) - float(
        candidate_summary["p90_ms"]
    )
    saved_percent = saved_ms / float(baseline_summary["median_ms"]) * 100.0
    paired_saved_ms = [
        baseline - candidate
        for baseline, candidate in zip(
            max_rank_samples["baseline"],
            max_rank_samples["candidate"],
            strict=True,
        )
    ]
    paired_median_saved_ms = statistics.median(paired_saved_ms)
    positive_pairs = sum(delta > 0 for delta in paired_saved_ms)
    baseline_first_median_saved_ms = statistics.median(paired_saved_ms[0::2])
    candidate_first_median_saved_ms = statistics.median(paired_saved_ms[1::2])
    local_correctness = (
        not any(collective_mismatches)
        and not any(baseline_oracle_mismatches)
        and not any(candidate_oracle_mismatches)
        and not any(consumer_mismatches)
    )
    correctness_failure = torch.tensor(
        0 if local_correctness else 1, dtype=torch.int32, device=device
    )
    dist.all_reduce(correctness_failure, op=dist.ReduceOp.MAX)
    passed_correctness = int(correctness_failure.item()) == 0
    passed_performance = (
        saved_ms >= REQUIRED_SAVE_MS
        and paired_median_saved_ms >= REQUIRED_SAVE_MS
        and p90_saved_ms >= REQUIRED_P90_SAVE_MS
        and saved_percent >= REQUIRED_PERCENT
        and positive_pairs >= REQUIRED_POSITIVE_PAIRS
        and baseline_first_median_saved_ms >= REQUIRED_ORDER_STRATUM_SAVE_MS
        and candidate_first_median_saved_ms >= REQUIRED_ORDER_STRATUM_SAVE_MS
    )
    baseline_outputs, baseline_consumers = final_results["baseline"]
    candidate_outputs, candidate_consumers = final_results["candidate"]
    rank_payload: dict[str, Any] = {
        "rank": rank,
        "device": str(device),
        "device_name": torch.xpu.get_device_name(device),
        "torch": torch.__version__,
        "xpu_extension": str(extension_path),
        "xpu_extension_sha256": extension_sha256,
        "libccl_maps": libccl_maps,
        "protocol_names": protocol_names,
        "protocol_trace": str(trace_path),
        "protocol_trace_sha256": sha256_file(trace_path),
        "local_correctness": local_correctness,
        "collective_mismatches_by_epoch": collective_mismatches,
        "baseline_oracle_mismatches_by_epoch": baseline_oracle_mismatches,
        "candidate_oracle_mismatches_by_epoch": candidate_oracle_mismatches,
        "consumer_mismatches_by_epoch": consumer_mismatches,
        "local_wall_ms_samples": local_samples,
        "final_collective_hashes": {
            "baseline": tensor_sha256(torch.stack(baseline_outputs)),
            "candidate": tensor_sha256(torch.stack(candidate_outputs)),
        },
        "final_consumer_hashes": {
            "baseline": [tensor_sha256(item) for item in baseline_consumers],
            "candidate": [tensor_sha256(item) for item in candidate_consumers],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rank_output = args.output.with_suffix(args.output.suffix + f".rank{rank}.json")
    rank_output.write_text(
        json.dumps(rank_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    dist.barrier(device_ids=[local_rank])

    if rank == 0:
        ranks = [
            json.loads(
                args.output.with_suffix(
                    args.output.suffix + f".rank{item}.json"
                ).read_text(encoding="utf-8")
            )
            for item in range(WORLD_SIZE)
        ]
        result = {
            "schema_version": 1,
            "status": "passed"
            if passed_correctness and passed_performance
            else "failed",
            "classification": "qwen38_flash_next_tp4_count2560_event_chain_component",
            "scope": "combined eager clone-elision plus event-chain 97-collective component A/B; not model throughput",
            "shape": [1, HIDDEN],
            "dtype": "bfloat16",
            "world_size": WORLD_SIZE,
            "collectives": COLLECTIVES,
            "consumers": CONSUMERS,
            "norm_consumers": NORM_CONSUMERS,
            "warmup": WARMUP,
            "epochs": EPOCHS,
            "passed_correctness": passed_correctness,
            "passed_performance_gate": passed_performance,
            "collective_mismatches_by_epoch": collective_mismatches,
            "baseline_oracle_mismatches_by_epoch": baseline_oracle_mismatches,
            "candidate_oracle_mismatches_by_epoch": candidate_oracle_mismatches,
            "consumer_mismatches_by_epoch": consumer_mismatches,
            "slowest_rank_wall_ms": {
                "baseline": baseline_summary,
                "candidate": candidate_summary,
            },
            "saved_ms": saved_ms,
            "p90_saved_ms": p90_saved_ms,
            "saved_percent": saved_percent,
            "paired_saved_ms": paired_saved_ms,
            "paired_median_saved_ms": paired_median_saved_ms,
            "positive_pairs": positive_pairs,
            "baseline_first_median_saved_ms": baseline_first_median_saved_ms,
            "candidate_first_median_saved_ms": candidate_first_median_saved_ms,
            "required_save_ms": REQUIRED_SAVE_MS,
            "required_p90_save_ms": REQUIRED_P90_SAVE_MS,
            "required_percent": REQUIRED_PERCENT,
            "required_positive_pairs": REQUIRED_POSITIVE_PAIRS,
            "required_order_stratum_save_ms": REQUIRED_ORDER_STRATUM_SAVE_MS,
            "ranks": ranks,
        }
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, sort_keys=True), flush=True)

    dist.barrier(device_ids=[local_rank])
    dist.destroy_process_group()
    return 0 if passed_correctness and passed_performance else 1


if __name__ == "__main__":
    raise SystemExit(main())
