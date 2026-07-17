#!/usr/bin/env python3
"""Gate the exact M=2 TP4 publish/reduce/MHC overlap hardware ceiling."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import time

import torch
import torch.distributed as dist
import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C as xpu_extension


ROWS = 2
HIDDEN = 4096
HC = 4
HC3 = 24
EPS = 1e-6


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def libccl_maps() -> list[str]:
    rows = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        if "libccl.so" in line:
            rows.add(line.split()[-1])
    return sorted(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collectives", type=int, default=87)
    parser.add_argument("--mhc-boundaries", type=int, default=85)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--required-hidden-ms", type=float, default=0.50)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.collectives != args.mhc_boundaries + 2:
        raise ValueError("expected one leading and one trailing non-MHC reduction")

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != 4:
        raise ValueError(f"requires world_size=4, got {world_size}")

    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group(backend="xccl", device_id=device)
    comm_stream = torch.xpu.current_stream(device)
    consumer_stream = torch.xpu.Stream(device=device)

    index = torch.arange(
        args.collectives * ROWS * HIDDEN, dtype=torch.int32, device=device
    ).reshape(args.collectives, ROWS, HIDDEN)
    base = index.remainder(13).to(torch.bfloat16)
    local_values = torch.empty_like(base)
    analytic_reduced = torch.empty_like(base)
    reduced = [torch.empty_like(base[0]) for _ in range(args.collectives)]

    h = torch.arange(HIDDEN, dtype=torch.float32, device=device)
    k = torch.arange(HC * HIDDEN, dtype=torch.float32, device=device)
    residual_bank = torch.stack(
        [
            torch.stack(
                [
                    torch.stack(
                        [
                            torch.cos(
                                h * (0.00037 * (channel + 1))
                                + boundary * 0.0013
                                + row * 0.023
                            )
                            .mul_(channel + 0.75)
                            .to(torch.bfloat16)
                            for channel in range(HC)
                        ]
                    )
                    for row in range(ROWS)
                ]
            )
            for boundary in range(args.mhc_boundaries)
        ]
    )
    post_bank = (
        torch.arange(
            args.mhc_boundaries * ROWS * HC,
            dtype=torch.float32,
            device=device,
        )
        .reshape(args.mhc_boundaries, ROWS, HC, 1)
        .mul_(0.003)
        .sub_(0.4)
    )
    comb_bank = (
        torch.arange(
            args.mhc_boundaries * ROWS * HC * HC,
            dtype=torch.float32,
            device=device,
        )
        .reshape(args.mhc_boundaries, ROWS, HC, HC)
        .remainder_(37)
        .mul_(0.007)
        .sub_(0.11)
    )
    base_fn = torch.stack(
        [
            torch.sin(k * (0.000013 * (item + 1)) + item * 0.071)
            .mul_(0.00035)
            .add_(torch.cos(k * 0.000009 + item * 0.019) * 0.00015)
            for item in range(HC3)
        ]
    )
    fn_bank = torch.stack(
        [base_fn + boundary * 0.0000001 for boundary in range(args.mhc_boundaries)]
    )
    scale_bank = torch.stack(
        [
            torch.tensor(
                [0.7, 0.8, 0.9], dtype=torch.float32, device=device
            ).add_(boundary * 0.00001)
            for boundary in range(args.mhc_boundaries)
        ]
    )
    hc_base_bank = torch.stack(
        [
            torch.linspace(
                -0.12 + boundary * 0.00001,
                0.13 + boundary * 0.00001,
                HC3,
                dtype=torch.float32,
                device=device,
            )
            for boundary in range(args.mhc_boundaries)
        ]
    )

    def make_output_bank() -> tuple[torch.Tensor, ...]:
        return (
            torch.empty_like(residual_bank),
            torch.empty_like(post_bank),
            torch.empty_like(comb_bank),
            torch.empty(
                (args.mhc_boundaries, ROWS, HIDDEN),
                dtype=torch.bfloat16,
                device=device,
            ),
        )

    serial_outputs = make_output_bank()
    overlap_outputs = make_output_bank()
    consumer_only_outputs = make_output_bank()
    reference_outputs = make_output_bank()
    completion_witnesses = {
        id(outputs): torch.empty(1, dtype=torch.bfloat16, device=device)
        for outputs in (
            serial_outputs,
            overlap_outputs,
            consumer_only_outputs,
            reference_outputs,
        )
    }

    def prepare(epoch: int) -> None:
        epoch_value = epoch % 7
        local_values.copy_(base + rank * 2 + epoch_value)
        analytic_reduced.copy_(base * world_size + 12 + epoch_value * world_size)

    def publish_reduce() -> None:
        with torch.xpu.stream(comm_stream):
            for source, destination in zip(local_values, reduced, strict=True):
                destination.copy_(source)
                dist.all_reduce(destination)

    def enqueue_consumer(
        stream: torch.xpu.Stream,
        x_bank: torch.Tensor | list[torch.Tensor],
        outputs: tuple[torch.Tensor, ...],
    ) -> None:
        residual_out, next_post, next_comb, layer_input = outputs
        with torch.xpu.stream(stream):
            for boundary in range(args.mhc_boundaries):
                x = x_bank[boundary + 1]
                torch.ops._xpu_C.mhc_post_pre_m2_out(
                    x,
                    residual_bank[boundary],
                    post_bank[boundary],
                    comb_bank[boundary],
                    fn_bank[boundary],
                    scale_bank[boundary],
                    hc_base_bank[boundary],
                    residual_out[boundary],
                    next_post[boundary],
                    next_comb[boundary],
                    layer_input[boundary],
                    EPS,
                    EPS,
                    EPS,
                    2.0,
                    20,
                )
            completion_witnesses[id(outputs)].copy_(
                layer_input[-1].reshape(-1)[:1]
            )

    def consumer_only() -> None:
        enqueue_consumer(consumer_stream, analytic_reduced, consumer_only_outputs)

    def serial_grouped() -> None:
        publish_reduce()
        enqueue_consumer(comm_stream, reduced, serial_outputs)

    def serial_interleaved() -> None:
        with torch.xpu.stream(comm_stream):
            for collective, (source, destination) in enumerate(
                zip(local_values, reduced, strict=True)
            ):
                destination.copy_(source)
                dist.all_reduce(destination)
                if 1 <= collective <= args.mhc_boundaries:
                    boundary = collective - 1
                    residual_out, next_post, next_comb, layer_input = serial_outputs
                    torch.ops._xpu_C.mhc_post_pre_m2_out(
                        destination,
                        residual_bank[boundary],
                        post_bank[boundary],
                        comb_bank[boundary],
                        fn_bank[boundary],
                        scale_bank[boundary],
                        hc_base_bank[boundary],
                        residual_out[boundary],
                        next_post[boundary],
                        next_comb[boundary],
                        layer_input[boundary],
                        EPS,
                        EPS,
                        EPS,
                        2.0,
                        20,
                    )
            completion_witnesses[id(serial_outputs)].copy_(
                serial_outputs[-1][-1].reshape(-1)[:1]
            )

    def oracle_overlap_consumer_first() -> None:
        enqueue_consumer(consumer_stream, analytic_reduced, overlap_outputs)
        publish_reduce()

    def synchronize() -> None:
        comm_stream.synchronize()
        consumer_stream.synchronize()

    def max_rank_time_ms(call) -> tuple[float, float]:
        synchronize()
        dist.barrier()
        started = time.perf_counter()
        call()
        synchronize()
        local_ms = (time.perf_counter() - started) * 1000.0
        local_time = torch.tensor(local_ms, dtype=torch.float64, device=device)
        rank_times = [torch.empty_like(local_time) for _ in range(world_size)]
        dist.all_gather(rank_times, local_time)
        return local_ms, max(float(rank_time.item()) for rank_time in rank_times)

    calls = {
        "publish_reduce_only": publish_reduce,
        "consumer_only": consumer_only,
        "serial_interleaved": serial_interleaved,
        "serial_grouped": serial_grouped,
        "oracle_overlap_consumer_first": oracle_overlap_consumer_first,
    }
    names = tuple(calls)

    prepare(0)
    consumer_only()
    synchronize()
    for epoch in range(args.warmup):
        prepare(epoch + 11)
        serial_interleaved()
        synchronize()
        prepare(epoch + 31)
        oracle_overlap_consumer_first()
        synchronize()

    local_samples: dict[str, list[float]] = {name: [] for name in names}
    max_rank_samples: dict[str, list[float]] = {name: [] for name in names}
    reduced_mismatches: dict[str, list[int]] = {
        name: []
        for name in (
            "publish_reduce_only",
            "serial_interleaved",
            "serial_grouped",
            "oracle_overlap_consumer_first",
        )
    }
    mhc_mismatches: dict[str, list[list[int]]] = {
        name: []
        for name in (
            "consumer_only",
            "serial_interleaved",
            "serial_grouped",
            "oracle_overlap_consumer_first",
        )
    }
    mode_outputs = {
        "consumer_only": consumer_only_outputs,
        "serial_interleaved": serial_outputs,
        "serial_grouped": serial_outputs,
        "oracle_overlap_consumer_first": overlap_outputs,
    }
    for epoch in range(args.epochs):
        prepare(epoch + 101)
        synchronize()
        enqueue_consumer(consumer_stream, analytic_reduced, reference_outputs)
        synchronize()
        rotated = names[epoch % len(names) :] + names[: epoch % len(names)]
        for name in rotated:
            local_ms, max_ms = max_rank_time_ms(calls[name])
            local_samples[name].append(local_ms)
            max_rank_samples[name].append(max_ms)
            if name in reduced_mismatches:
                reduced_mismatches[name].append(
                    int((torch.stack(reduced) != analytic_reduced).sum().item())
                )
            if name in mhc_mismatches:
                mhc_mismatches[name].append(
                    [
                        int((actual != expected).sum().item())
                        for actual, expected in zip(
                            mode_outputs[name], reference_outputs, strict=True
                        )
                    ]
                )

    max_rank_medians = {
        name: statistics.median(values) for name, values in max_rank_samples.items()
    }
    conservative_serial = min(
        max_rank_medians["serial_interleaved"],
        max_rank_medians["serial_grouped"],
    )
    overlap_ms = max_rank_medians["oracle_overlap_consumer_first"]
    hidden_ms = conservative_serial - overlap_ms
    passed_correctness = not any(
        mismatch
        for rows in reduced_mismatches.values()
        for mismatch in rows
    ) and not any(
        mismatch
        for epochs in mhc_mismatches.values()
        for row in epochs
        for mismatch in row
    )
    extension_path = Path(xpu_extension.__file__).resolve()
    local_result = {
        "rank": rank,
        "device": str(device),
        "device_name": torch.xpu.get_device_name(device),
        "torch": torch.__version__,
        "xpu_extension": str(extension_path),
        "xpu_extension_sha256": sha256(extension_path),
        "libccl_maps": libccl_maps(),
        "local_wall_ms_samples": local_samples,
        "reduced_mismatches_by_mode_and_epoch": reduced_mismatches,
        "mhc_output_mismatches_by_mode_and_epoch": mhc_mismatches,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rank_output = args.output.with_suffix(args.output.suffix + f".rank{rank}.json")
    rank_output.write_text(json.dumps(local_result, indent=2, sort_keys=True) + "\n")
    dist.barrier()

    if rank == 0:
        rank_rows = [
            json.loads(
                args.output.with_suffix(args.output.suffix + f".rank{item}.json")
                .read_text()
            )
            for item in range(world_size)
        ]
        result = {
            "classification": "deepseek_v4_mtp1_m2_tp4_publish_reduce_mhc_overlap_upper_bound",
            "scope": "dependency-relaxed finite two-stream ceiling; not an integrated candidate",
            "passed_correctness": passed_correctness,
            "passed_upper_bound": passed_correctness
            and hidden_ms >= args.required_hidden_ms,
            "world_size": world_size,
            "rows_per_collective": ROWS,
            "collectives": args.collectives,
            "mhc_boundaries": args.mhc_boundaries,
            "warmup": args.warmup,
            "epochs": args.epochs,
            "max_rank_wall_ms_samples": max_rank_samples,
            "max_rank_wall_ms_medians": max_rank_medians,
            "conservative_serial_ms": conservative_serial,
            "oracle_overlap_consumer_first_ms": overlap_ms,
            "hidden_vs_conservative_serial_ms": hidden_ms,
            "overlap_excess_over_max_standalone_ms": overlap_ms
            - max(
                max_rank_medians["publish_reduce_only"],
                max_rank_medians["consumer_only"],
            ),
            "required_hidden_ms": args.required_hidden_ms,
            "correctness": {
                "reduced_mismatches_by_mode_and_epoch": reduced_mismatches,
                "mhc_output_mismatches_by_mode_and_epoch": mhc_mismatches,
            },
            "ranks": rank_rows,
        }
        rendered = json.dumps(result, indent=2, sort_keys=True)
        print(rendered)
        args.output.write_text(rendered + "\n")

    dist.barrier()
    dist.destroy_process_group()
    return 0 if passed_correctness else 1


if __name__ == "__main__":
    raise SystemExit(main())
