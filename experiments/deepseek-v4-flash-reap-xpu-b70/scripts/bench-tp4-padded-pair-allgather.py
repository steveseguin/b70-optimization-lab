#!/usr/bin/env python3
"""Sweep padded Markov winner-pair all-gathers on four B70s.

The production DSpark W2 path gathers 32,320 BF16 logits from every rank seven
times per speculative cycle.  The unpadded two-FP32 pair fell onto a slow tiny
collective route.  This gate finds whether padding the pair to a proven oneCCL
message class can retain the small logical payload while restoring the fast
device collective path.  It measures communication only; integration still
requires native strided winner selection and full-cycle exactness.
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


WORLD = 4
STEPS = 7
CONTROL_ELEMENTS = 32320


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    weight = position - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "min_us": min(values),
        "p10_us": percentile(values, 0.10),
        "median_us": statistics.median(values),
        "mean_us": statistics.fmean(values),
        "p90_us": percentile(values, 0.90),
        "max_us": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmups", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument(
        "--pad-elements",
        default="2,16,64,256,1024,2048,4096,8192,16384",
        help="comma-separated FP32 elements per rank, including score/token",
    )
    args = parser.parse_args()

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world = int(os.environ["WORLD_SIZE"])
    if world != WORLD:
        raise RuntimeError(f"requires world size {WORLD}, got {world}")
    pads = [int(value) for value in args.pad_elements.split(",")]
    if any(value < 2 for value in pads):
        raise ValueError("every padded payload must hold score and token")

    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group("xccl", device_id=device)

    control_inputs = [
        torch.full(
            (CONTROL_ELEMENTS,),
            float(rank + step),
            dtype=torch.bfloat16,
            device=device,
        )
        for step in range(STEPS)
    ]
    control_outputs = [
        torch.empty(WORLD * CONTROL_ELEMENTS, dtype=torch.bfloat16, device=device)
        for _ in range(STEPS)
    ]
    candidate_inputs: dict[int, list[torch.Tensor]] = {}
    candidate_outputs: dict[int, list[torch.Tensor]] = {}
    for pad in pads:
        candidate_inputs[pad] = []
        candidate_outputs[pad] = []
        for step in range(STEPS):
            payload = torch.zeros(pad, dtype=torch.float32, device=device)
            payload[0] = float(rank * 100 + step)
            payload[1] = float(rank * CONTROL_ELEMENTS + step)
            candidate_inputs[pad].append(payload)
            candidate_outputs[pad].append(
                torch.empty(WORLD * pad, dtype=torch.float32, device=device)
            )
    torch.xpu.synchronize()

    def control() -> None:
        for step in range(STEPS):
            dist.all_gather_into_tensor(control_outputs[step], control_inputs[step])

    def candidate(pad: int) -> None:
        for step in range(STEPS):
            dist.all_gather_into_tensor(
                candidate_outputs[pad][step], candidate_inputs[pad][step]
            )

    exact: dict[int, bool] = {}
    for pad in pads:
        candidate(pad)
        torch.xpu.synchronize()
        passed = True
        for step in range(STEPS):
            output = candidate_outputs[pad][step].view(WORLD, pad)
            expected_scores = torch.tensor(
                [peer * 100 + step for peer in range(WORLD)],
                dtype=torch.float32,
                device=device,
            )
            expected_tokens = torch.tensor(
                [peer * CONTROL_ELEMENTS + step for peer in range(WORLD)],
                dtype=torch.float32,
                device=device,
            )
            passed = passed and bool(torch.equal(output[:, 0], expected_scores))
            passed = passed and bool(torch.equal(output[:, 1], expected_tokens))
        exact[pad] = passed

    def timed(fn) -> list[float]:
        for _ in range(args.warmups):
            fn()
        torch.xpu.synchronize()
        samples = []
        for _ in range(args.iterations):
            dist.barrier()
            torch.xpu.synchronize()
            started = time.perf_counter_ns()
            fn()
            torch.xpu.synchronize()
            samples.append((time.perf_counter_ns() - started) / 1000.0)
        return samples

    control_a = timed(control)
    candidates = {pad: timed(lambda pad=pad: candidate(pad)) for pad in pads}
    control_b = timed(control)
    local = {
        "rank": rank,
        "device": local_rank,
        "control_a": summarize(control_a),
        "control_b": summarize(control_b),
        "candidates": {
            str(pad): {
                "input_bytes_per_rank": pad * 4,
                "exact": exact[pad],
                "timing": summarize(candidates[pad]),
                "saved_us_vs_faster_control": min(
                    statistics.median(control_a), statistics.median(control_b)
                )
                - statistics.median(candidates[pad]),
            }
            for pad in pads
        },
    }
    gathered: list[dict | None] = [None] * WORLD
    dist.all_gather_object(gathered, local)

    if rank == 0:
        rows = [row for row in gathered if row is not None]
        result = {
            "schema_version": 1,
            "classification": "deepseek_v4_tp4_padded_pair_allgather_sweep",
            "scope": "seven sequential communication operations only",
            "world_size": WORLD,
            "steps": STEPS,
            "control": {
                "dtype": "bfloat16",
                "elements_per_rank": CONTROL_ELEMENTS,
                "input_bytes_per_rank": CONTROL_ELEMENTS * 2,
            },
            "warmups": args.warmups,
            "iterations": args.iterations,
            "ranks": rows,
            "pads": {},
        }
        for pad in pads:
            timings = [
                row["candidates"][str(pad)]["timing"]["median_us"]
                for row in rows
            ]
            controls = [
                min(
                    row["control_a"]["median_us"],
                    row["control_b"]["median_us"],
                )
                for row in rows
            ]
            result["pads"][str(pad)] = {
                "input_bytes_per_rank": pad * 4,
                "exact_all_ranks": all(
                    row["candidates"][str(pad)]["exact"] for row in rows
                ),
                "slowest_rank_median_us": max(timings),
                "slowest_rank_control_median_us": max(controls),
                "conservative_saved_us": min(
                    row["candidates"][str(pad)]["saved_us_vs_faster_control"]
                    for row in rows
                ),
            }
        eligible = [
            (int(pad), row)
            for pad, row in result["pads"].items()
            if row["exact_all_ranks"] and row["conservative_saved_us"] > 0
        ]
        result["best_pad_elements"] = (
            min(eligible, key=lambda item: item[1]["slowest_rank_median_us"])[0]
            if eligible
            else None
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, indent=2, sort_keys=True))

    dist.barrier()
    dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
