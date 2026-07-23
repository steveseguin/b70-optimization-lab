#!/usr/bin/env python3
"""Fail-closed Laguna M=8 shared-expert XPU auxiliary-stream gate.

The serial reference and auxiliary-stream candidate both execute the incumbent
BF16 arithmetic:

    stride-zero BMM gate
    stride-zero BMM up
    SiLU(gate) * up
    stride-zero BMM down

The candidate differs only in stream placement.  Each epoch forks from the
current stream, records every auxiliary input on the auxiliary stream, runs an
independent same-shape MLP on the current stream, and joins before inspecting
either result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from pathlib import Path
from typing import TypeAlias

import torch
import torch.nn.functional as F


ROWS = 8
HIDDEN_SIZE = 3072
SHARED_INTERMEDIATE_SIZE = 1024
TP_SIZE = 4
LOCAL_INTERMEDIATE_SIZE = SHARED_INTERMEDIATE_SIZE // TP_SIZE
MIN_EPOCHS = 128
WEIGHT_SCALE = 0.02
COMPONENT_NAMES = ("gate", "up", "silu_mul", "down")

MlpInputs: TypeAlias = tuple[
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
]
MlpOutputs: TypeAlias = tuple[
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
]


def raw_sha256(*tensors: torch.Tensor) -> str:
    """Hash the complete raw storage bytes of tensors in their given order."""
    digest = hashlib.sha256()
    for tensor in tensors:
        raw = tensor.detach().cpu().contiguous().view(torch.uint8)
        digest.update(raw.numpy().tobytes())
    return digest.hexdigest()


def make_mlp_inputs(seed: int) -> MlpInputs:
    """Create changing, numerically bounded BF16 input and local TP weights."""
    torch.manual_seed(seed)
    hidden = torch.randn((ROWS, HIDDEN_SIZE), dtype=torch.bfloat16, device="xpu:0")
    gate_weight = torch.randn(
        (LOCAL_INTERMEDIATE_SIZE, HIDDEN_SIZE),
        dtype=torch.bfloat16,
        device="xpu:0",
    ).mul_(WEIGHT_SCALE)
    up_weight = torch.randn(
        (LOCAL_INTERMEDIATE_SIZE, HIDDEN_SIZE),
        dtype=torch.bfloat16,
        device="xpu:0",
    ).mul_(WEIGHT_SCALE)
    down_weight = torch.randn(
        (HIDDEN_SIZE, LOCAL_INTERMEDIATE_SIZE),
        dtype=torch.bfloat16,
        device="xpu:0",
    ).mul_(WEIGHT_SCALE)
    return hidden, gate_weight, up_weight, down_weight


def incumbent_stride_zero_bmm(
    rows: torch.Tensor,
    weight: torch.Tensor,
) -> torch.Tensor:
    """Run the exact incumbent independent-M=1 BF16 BMM representation."""
    if rows.ndim != 2 or weight.ndim != 2:
        raise AssertionError("incumbent BMM requires rank-2 rows and weight")
    if rows.shape[0] != ROWS:
        raise AssertionError(f"incumbent BMM requires M={ROWS}, got {rows.shape[0]}")
    if rows.shape[1] != weight.shape[1]:
        raise AssertionError(
            f"BMM K mismatch: rows={tuple(rows.shape)} weight={tuple(weight.shape)}"
        )
    if rows.dtype != torch.bfloat16 or weight.dtype != torch.bfloat16:
        raise AssertionError("incumbent BMM inputs must both be BF16")
    if rows.device.type != "xpu" or weight.device.type != "xpu":
        raise AssertionError("incumbent BMM inputs must both be on XPU")

    expanded_weight = weight.t().unsqueeze(0).expand(rows.shape[0], -1, -1)
    if expanded_weight.stride(0) != 0:
        raise AssertionError(
            "expanded incumbent weight lost its stride-zero batch dimension"
        )
    output = torch.bmm(rows.unsqueeze(1), expanded_weight).squeeze(1)
    if output.dtype != torch.bfloat16:
        raise AssertionError(f"incumbent BMM returned {output.dtype}, not BF16")
    return output


def incumbent_shared_mlp(inputs: MlpInputs) -> MlpOutputs:
    """Execute the complete local TP shared-expert MLP without substitutions."""
    hidden, gate_weight, up_weight, down_weight = inputs
    gate = incumbent_stride_zero_bmm(hidden, gate_weight)
    up = incumbent_stride_zero_bmm(hidden, up_weight)
    silu_mul = F.silu(gate) * up
    if silu_mul.dtype != torch.bfloat16:
        raise AssertionError(f"SiLU*mul returned {silu_mul.dtype}, not BF16")
    down = incumbent_stride_zero_bmm(silu_mul, down_weight)
    return gate, up, silu_mul, down


def record_aux_inputs(inputs: MlpInputs, aux_stream: torch.xpu.Stream) -> None:
    """Tell the caching allocator every tensor is consumed by the aux stream."""
    for tensor in inputs:
        tensor.record_stream(aux_stream)


def run_aux_only(
    inputs: MlpInputs,
    main_stream: torch.xpu.Stream,
    aux_stream: torch.xpu.Stream,
) -> MlpOutputs:
    """Fork to the auxiliary stream and join it back to the current stream."""
    record_aux_inputs(inputs, aux_stream)
    aux_stream.wait_stream(main_stream)
    with torch.xpu.stream(aux_stream):
        output = incumbent_shared_mlp(inputs)
    main_stream.wait_stream(aux_stream)
    return output


def run_overlapped_pair(
    shared_inputs: MlpInputs,
    interference_inputs: MlpInputs,
    main_stream: torch.xpu.Stream,
    aux_stream: torch.xpu.Stream,
) -> tuple[MlpOutputs, MlpOutputs]:
    """Run shared MLP on aux while independent interference runs on main."""
    record_aux_inputs(shared_inputs, aux_stream)

    # Fork: the aux stream observes input/weight production and all prior main
    # work, but not the independent main-stream work submitted below.
    aux_stream.wait_stream(main_stream)
    with torch.xpu.stream(aux_stream):
        shared_output = incumbent_shared_mlp(shared_inputs)

    # This is deliberately submitted before the join so it can overlap the
    # complete shared-expert gate/up/activation/down chain.
    interference_output = incumbent_shared_mlp(interference_inputs)

    # Join: all later main-stream consumers observe the complete aux result.
    main_stream.wait_stream(aux_stream)
    return shared_output, interference_output


def component_hashes(outputs: MlpOutputs) -> dict[str, str]:
    return {
        name: raw_sha256(tensor)
        for name, tensor in zip(COMPONENT_NAMES, outputs, strict=True)
    }


def compare_outputs(
    reference: MlpOutputs,
    candidate: MlpOutputs,
) -> tuple[dict[str, bool], dict[str, str], dict[str, str]]:
    equal = {
        name: torch.equal(ref, got)
        for name, ref, got in zip(COMPONENT_NAMES, reference, candidate, strict=True)
    }
    reference_hashes = component_hashes(reference)
    candidate_hashes = component_hashes(candidate)
    return equal, reference_hashes, candidate_hashes


def assert_finite(label: str, outputs: MlpOutputs) -> None:
    for name, tensor in zip(COMPONENT_NAMES, outputs, strict=True):
        if not bool(torch.isfinite(tensor).all().item()):
            raise AssertionError(f"{label} {name} contains a non-finite value")


def serial_pair(
    shared_inputs: MlpInputs,
    interference_inputs: MlpInputs,
) -> tuple[MlpOutputs, MlpOutputs]:
    return (
        incumbent_shared_mlp(shared_inputs),
        incumbent_shared_mlp(interference_inputs),
    )


def warm_up(call, iterations: int) -> None:
    result = None
    for _ in range(iterations):
        result = call()
    torch.xpu.synchronize()
    if result is None:
        raise AssertionError("warm-up did not execute")


def timed_sample_ms(call, iterations: int) -> float:
    torch.xpu.synchronize()
    started_ns = time.perf_counter_ns()
    result = None
    for _ in range(iterations):
        result = call()
    torch.xpu.synchronize()
    elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
    if result is None:
        raise AssertionError("timing loop did not execute")
    return elapsed_ms / iterations


def timing_summary(samples: list[float]) -> dict[str, object]:
    if not samples or not all(math.isfinite(value) and value > 0 for value in samples):
        raise AssertionError(f"invalid timing samples: {samples}")
    return {
        "median_ms": statistics.median(samples),
        "mean_ms": statistics.fmean(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "samples_ms": samples,
    }


def collect_timing(
    shared_inputs: MlpInputs,
    interference_inputs: MlpInputs,
    main_stream: torch.xpu.Stream,
    aux_stream: torch.xpu.Stream,
    *,
    warmup_iterations: int,
    timing_iterations: int,
    timing_trials: int,
) -> dict[str, object]:
    calls = {
        "serial_shared": lambda: incumbent_shared_mlp(shared_inputs),
        "aux_shared_fork_join": lambda: run_aux_only(
            shared_inputs, main_stream, aux_stream
        ),
        "main_interference": lambda: incumbent_shared_mlp(interference_inputs),
        "serial_pair": lambda: serial_pair(shared_inputs, interference_inputs),
        "overlapped_pair": lambda: run_overlapped_pair(
            shared_inputs,
            interference_inputs,
            main_stream,
            aux_stream,
        ),
    }
    for call in calls.values():
        warm_up(call, warmup_iterations)

    samples: dict[str, list[float]] = {name: [] for name in calls}
    isolated_names = (
        "serial_shared",
        "aux_shared_fork_join",
        "main_interference",
    )
    for _ in range(timing_trials):
        for name in isolated_names:
            samples[name].append(timed_sample_ms(calls[name], timing_iterations))

    # Alternate pair order to avoid giving either pair a fixed thermal/order
    # advantage.
    for trial in range(timing_trials):
        pair_names = (
            ("serial_pair", "overlapped_pair")
            if trial % 2 == 0
            else ("overlapped_pair", "serial_pair")
        )
        for name in pair_names:
            samples[name].append(timed_sample_ms(calls[name], timing_iterations))

    summaries = {name: timing_summary(values) for name, values in samples.items()}
    serial_shared_ms = summaries["serial_shared"]["median_ms"]
    interference_ms = summaries["main_interference"]["median_ms"]
    serial_pair_ms = summaries["serial_pair"]["median_ms"]
    overlapped_pair_ms = summaries["overlapped_pair"]["median_ms"]
    if not all(
        isinstance(value, float)
        for value in (
            serial_shared_ms,
            interference_ms,
            serial_pair_ms,
            overlapped_pair_ms,
        )
    ):
        raise AssertionError("timing medians are not floats")

    saved_ms = serial_pair_ms - overlapped_pair_ms
    gain_pct = 100.0 * saved_ms / serial_pair_ms
    overlap_capacity_ms = min(serial_shared_ms, interference_ms)
    overlap_efficiency_pct = (
        100.0 * saved_ms / overlap_capacity_ms
        if overlap_capacity_ms > 0
        else float("nan")
    )
    return {
        "warmup_iterations": warmup_iterations,
        "iterations_per_sample": timing_iterations,
        "trials": timing_trials,
        "paths": summaries,
        "overlap": {
            "serial_pair_median_ms": serial_pair_ms,
            "overlapped_pair_median_ms": overlapped_pair_ms,
            "observed_saved_ms": saved_ms,
            "observed_gain_pct": gain_pct,
            "available_overlap_ms": overlap_capacity_ms,
            "observed_overlap_efficiency_pct": overlap_efficiency_pct,
            "ideal_floor_ms": max(serial_shared_ms, interference_ms),
            "observed": saved_ms > 0,
        },
    }


def expanded_weight_stride(weight: torch.Tensor) -> list[int]:
    expanded = weight.t().unsqueeze(0).expand(ROWS, -1, -1)
    return list(expanded.stride())


def run_gate(args: argparse.Namespace) -> dict[str, object]:
    if args.epochs < MIN_EPOCHS:
        raise ValueError(f"--epochs must be at least {MIN_EPOCHS}; got {args.epochs}")
    if args.timing_iterations < 1:
        raise ValueError("--timing-iterations must be positive")
    if args.timing_trials < 3:
        raise ValueError("--timing-trials must be at least 3")
    if args.warmup_iterations < 1:
        raise ValueError("--warmup-iterations must be positive")
    if args.min_overlap_gain_pct < 0:
        raise ValueError("--min-overlap-gain-pct cannot be negative")
    if not torch.xpu.is_available():
        raise RuntimeError("XPU is not available")
    visible_xpus = torch.xpu.device_count()
    if visible_xpus != 1:
        raise RuntimeError(
            "gate requires exactly one visible XPU; "
            f"set rank affinity before launch (visible={visible_xpus})"
        )

    torch.xpu.set_device(0)
    main_stream = torch.xpu.current_stream()
    aux_stream = torch.xpu.Stream()
    if main_stream == aux_stream:
        raise AssertionError("main and auxiliary XPU streams are not distinct")

    epoch_rows: list[dict[str, object]] = []
    input_hashes: set[str] = set()
    weight_hashes: set[str] = set()
    interference_input_hashes: set[str] = set()
    interference_weight_hashes: set[str] = set()
    down_hashes: set[str] = set()
    last_shared_inputs: MlpInputs | None = None
    last_interference_inputs: MlpInputs | None = None

    for epoch in range(args.epochs):
        seed = 820_000 + args.rank * 10_000 + epoch * 2
        shared_inputs = make_mlp_inputs(seed)
        interference_inputs = make_mlp_inputs(seed + 1)

        serial_shared = incumbent_shared_mlp(shared_inputs)
        serial_interference = incumbent_shared_mlp(interference_inputs)
        aux_shared, concurrent_interference = run_overlapped_pair(
            shared_inputs,
            interference_inputs,
            main_stream,
            aux_stream,
        )

        shared_equal, serial_hashes, aux_hashes = compare_outputs(
            serial_shared, aux_shared
        )
        interference_equal, serial_interference_hashes, concurrent_hashes = (
            compare_outputs(
                serial_interference,
                concurrent_interference,
            )
        )
        assert_finite("serial shared", serial_shared)
        assert_finite("aux shared", aux_shared)
        assert_finite("serial interference", serial_interference)
        assert_finite("concurrent interference", concurrent_interference)

        shared_hash_equal = serial_hashes == aux_hashes
        interference_hash_equal = serial_interference_hashes == concurrent_hashes
        if not all(shared_equal.values()) or not shared_hash_equal:
            raise AssertionError(
                f"epoch {epoch} shared MLP differs between serial and aux"
            )
        if not all(interference_equal.values()) or not interference_hash_equal:
            raise AssertionError(
                f"epoch {epoch} main interference changed during overlap"
            )

        input_hash = raw_sha256(shared_inputs[0])
        weights_hash = raw_sha256(*shared_inputs[1:])
        interference_input_hash = raw_sha256(interference_inputs[0])
        interference_weights_hash = raw_sha256(*interference_inputs[1:])
        input_hashes.add(input_hash)
        weight_hashes.add(weights_hash)
        interference_input_hashes.add(interference_input_hash)
        interference_weight_hashes.add(interference_weights_hash)
        down_hashes.add(aux_hashes["down"])
        epoch_rows.append(
            {
                "epoch": epoch,
                "seed": seed,
                "raw_input_sha256": input_hash,
                "raw_weights_sha256": weights_hash,
                "raw_serial_component_sha256": serial_hashes,
                "raw_aux_component_sha256": aux_hashes,
                "torch_equal": shared_equal,
                "raw_hash_equal": shared_hash_equal,
                "interference": {
                    "seed": seed + 1,
                    "raw_input_sha256": interference_input_hash,
                    "raw_weights_sha256": interference_weights_hash,
                    "raw_serial_component_sha256": serial_interference_hashes,
                    "raw_concurrent_component_sha256": concurrent_hashes,
                    "torch_equal": interference_equal,
                    "raw_hash_equal": interference_hash_equal,
                },
            }
        )
        last_shared_inputs = shared_inputs
        last_interference_inputs = interference_inputs

    uniqueness = {
        "shared_inputs": len(input_hashes),
        "shared_weights": len(weight_hashes),
        "shared_down_outputs": len(down_hashes),
        "interference_inputs": len(interference_input_hashes),
        "interference_weights": len(interference_weight_hashes),
    }
    if any(unique_count != args.epochs for unique_count in uniqueness.values()):
        raise AssertionError(
            "changing-input/weight/output uniqueness gate failed: "
            f"{uniqueness}, expected {args.epochs} each"
        )
    if last_shared_inputs is None or last_interference_inputs is None:
        raise AssertionError("no correctness epochs executed")

    timing = collect_timing(
        last_shared_inputs,
        last_interference_inputs,
        main_stream,
        aux_stream,
        warmup_iterations=args.warmup_iterations,
        timing_iterations=args.timing_iterations,
        timing_trials=args.timing_trials,
    )

    # Recheck both streams after sustained repeated timing submissions.
    post_serial_shared, post_serial_interference = serial_pair(
        last_shared_inputs, last_interference_inputs
    )
    post_aux_shared, post_concurrent_interference = run_overlapped_pair(
        last_shared_inputs,
        last_interference_inputs,
        main_stream,
        aux_stream,
    )
    torch.xpu.synchronize()
    post_shared_equal, post_serial_hashes, post_aux_hashes = compare_outputs(
        post_serial_shared, post_aux_shared
    )
    (
        post_interference_equal,
        post_serial_interference_hashes,
        post_concurrent_hashes,
    ) = compare_outputs(
        post_serial_interference,
        post_concurrent_interference,
    )
    post_timing_exact = (
        all(post_shared_equal.values())
        and all(post_interference_equal.values())
        and post_serial_hashes == post_aux_hashes
        and post_serial_interference_hashes == post_concurrent_hashes
    )
    if not post_timing_exact:
        raise AssertionError("post-timing stream race check failed")

    overlap = timing["overlap"]
    if not isinstance(overlap, dict):
        raise AssertionError("missing overlap timing summary")
    observed_gain_pct = overlap["observed_gain_pct"]
    if not isinstance(observed_gain_pct, float):
        raise AssertionError("invalid overlap gain")
    overlap_gate_passed = (
        bool(overlap["observed"]) and observed_gain_pct >= args.min_overlap_gain_pct
    )

    gate_weight = last_shared_inputs[1]
    down_weight = last_shared_inputs[3]
    return {
        "status": "PASS" if overlap_gate_passed else "FAIL",
        "passed": overlap_gate_passed,
        "rank": args.rank,
        "visible_xpus": visible_xpus,
        "device": torch.xpu.get_device_name(0),
        "torch_version": torch.__version__,
        "shape": {
            "rows": ROWS,
            "hidden_size": HIDDEN_SIZE,
            "shared_intermediate_size": SHARED_INTERMEDIATE_SIZE,
            "tp_size": TP_SIZE,
            "local_intermediate_size": LOCAL_INTERMEDIATE_SIZE,
        },
        "arithmetic": {
            "dtype": "torch.bfloat16",
            "gate": "torch.bmm(rows.unsqueeze(1), "
            "weight.t().unsqueeze(0).expand(M,-1,-1)).squeeze(1)",
            "up": "identical stride-zero BF16 BMM",
            "activation": "torch.nn.functional.silu(gate) * up",
            "down": "identical stride-zero BF16 BMM",
            "gate_up_expanded_weight_stride": expanded_weight_stride(gate_weight),
            "down_expanded_weight_stride": expanded_weight_stride(down_weight),
        },
        "stream_protocol": {
            "streams_distinct": True,
            "fork": "aux_stream.wait_stream(main_stream)",
            "aux_input_lifetime": "all hidden/weight tensors record_stream(aux)",
            "concurrent_main_interference": (
                "independent same-shape incumbent BF16 shared MLP"
            ),
            "join": "main_stream.wait_stream(aux_stream)",
        },
        "correctness": {
            "epochs": args.epochs,
            "minimum_epochs": MIN_EPOCHS,
            "component_checks_per_epoch": len(COMPONENT_NAMES) * 2,
            "torch_equal_checks": (
                args.epochs * len(COMPONENT_NAMES) * 2 + len(COMPONENT_NAMES) * 2
            ),
            "all_raw_hash_pairs_equal": True,
            "unique_raw_hashes": uniqueness,
            "post_timing_exact": post_timing_exact,
            "epochs_detail": epoch_rows,
        },
        "timing": timing,
        "overlap_gate": {
            "minimum_gain_pct": args.min_overlap_gain_pct,
            "passed": overlap_gate_passed,
        },
    }


def write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Gate exact Laguna M=8 shared-expert BF16 arithmetic on an "
            "auxiliary XPU stream under concurrent main-stream interference."
        )
    )
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=MIN_EPOCHS)
    parser.add_argument("--warmup-iterations", type=int, default=5)
    parser.add_argument("--timing-iterations", type=int, default=40)
    parser.add_argument("--timing-trials", type=int, default=7)
    parser.add_argument(
        "--min-overlap-gain-pct",
        type=float,
        default=0.0,
        help=(
            "Required median gain versus serialized shared+interference work; "
            "the gate always requires a strictly positive observed gain."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = run_gate(args)
    except Exception as exc:
        failure: dict[str, object] = {
            "status": "FAIL",
            "passed": False,
            "rank": args.rank,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        write_payload(args.out, failure)
        print(json.dumps(failure, sort_keys=True))
        raise

    write_payload(args.out, payload)
    timing = payload["timing"]
    if not isinstance(timing, dict) or not isinstance(timing["overlap"], dict):
        raise AssertionError("malformed timing payload")
    summary = {
        "status": payload["status"],
        "rank": args.rank,
        "epochs": args.epochs,
        "torch_equal_checks": payload["correctness"]["torch_equal_checks"],
        "unique_raw_hashes": payload["correctness"]["unique_raw_hashes"],
        "post_timing_exact": payload["correctness"]["post_timing_exact"],
        "overlap": timing["overlap"],
        "out": str(args.out),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
