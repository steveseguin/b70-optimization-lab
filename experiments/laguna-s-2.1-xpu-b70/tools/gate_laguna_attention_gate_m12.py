#!/usr/bin/env python3
"""Bitwise and timing gate for the exact Laguna M12 attention-gate fusion."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

import torch
import torch.nn.functional as F


ROWS = 12
HEAD_DIM = 128
HEAD_COUNTS = (12, 18)
SEEDS = 32
WARMUP = 100
TIMING_BLOCKS = 21
CALLS_PER_BLOCK = 200


def raw_bytes(tensor: torch.Tensor) -> bytes:
    return tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()


def baseline(attention: torch.Tensor, gate: torch.Tensor) -> torch.Tensor:
    activated = F.softplus(gate.float()).type_as(attention)
    return (
        attention.view(ROWS, gate.shape[1], HEAD_DIM)
        * activated.unsqueeze(-1)
    ).view_as(attention)


def candidate(
    out: torch.Tensor, attention: torch.Tensor, gate: torch.Tensor
) -> torch.Tensor:
    torch.ops._C.laguna_m12_attention_gate(out, attention, gate)
    return out


def special_gate_values() -> torch.Tensor:
    # All values are finite after BF16 conversion. Include signed zero,
    # subnormal/normal edges, softplus-sensitive negatives, and values around
    # the incumbent threshold of 20.
    values = torch.tensor(
        [
            -3.3895313892515355e38,
            -128.0,
            -32.0,
            -20.0,
            -10.0,
            -2.0,
            -1.0,
            -0.125,
            -0.0,
            0.0,
            9.183549615799121e-41,
            0.125,
            1.0,
            2.0,
            10.0,
            19.75,
            19.875,
            20.0,
            20.125,
            20.25,
            32.0,
            128.0,
            3.3895313892515355e38,
        ],
        dtype=torch.float32,
    )
    return values.to(torch.bfloat16)


def make_inputs(heads: int, seed: int) -> tuple[torch.Tensor, torch.Tensor]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(0xA771000 + heads * 1000 + seed)
    attention = torch.randn(
        (ROWS, heads * HEAD_DIM), generator=generator, dtype=torch.float32
    ).mul_(3.0).to(torch.bfloat16)
    gate = torch.randn(
        (ROWS, heads), generator=generator, dtype=torch.float32
    ).mul_(8.0).to(torch.bfloat16)
    special = special_gate_values()
    flat_gate = gate.view(-1)
    count = min(flat_gate.numel(), special.numel())
    offset = (seed * 17) % flat_gate.numel()
    indices = (torch.arange(count) + offset) % flat_gate.numel()
    flat_gate[indices] = special[:count]
    return attention.xpu(), gate.xpu()


def event_block(callable_fn) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(CALLS_PER_BLOCK):
        callable_fn()
    end.record()
    torch.xpu.synchronize()
    return float(start.elapsed_time(end)) / CALLS_PER_BLOCK


def exhaustive_finite_gate_check() -> dict[str, int | bool]:
    """Prove softplus-to-BF16 parity for every finite BF16 input value."""
    all_values = (
        torch.arange(65536, dtype=torch.int32)
        .to(torch.int16)
        .view(torch.bfloat16)
    )
    finite_values = all_values[torch.isfinite(all_values)]
    heads = 18
    capacity = ROWS * heads
    checked = 0
    mismatches = 0
    attention = torch.ones(
        (ROWS, heads * HEAD_DIM), dtype=torch.bfloat16, device="xpu"
    )
    for start in range(0, finite_values.numel(), capacity):
        chunk = finite_values[start : start + capacity]
        gate_cpu = torch.zeros((ROWS, heads), dtype=torch.bfloat16)
        gate_cpu.view(-1)[: chunk.numel()] = chunk
        gate = gate_cpu.xpu()
        expected = baseline(attention, gate).view(ROWS, heads, HEAD_DIM)
        observed = torch.empty_like(attention)
        candidate(observed, attention, gate)
        torch.xpu.synchronize()
        observed = observed.view(ROWS, heads, HEAD_DIM)
        expected_bits = expected[:, :, 0].reshape(-1)[: chunk.numel()].view(torch.int16)
        observed_bits = observed[:, :, 0].reshape(-1)[: chunk.numel()].view(torch.int16)
        mismatches += int((expected_bits != observed_bits).sum().item())
        checked += chunk.numel()
    return {
        "finite_bf16_values": int(finite_values.numel()),
        "checked": checked,
        "mismatches": mismatches,
        "passed": checked == 65280 and mismatches == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.library.is_file():
        raise SystemExit(f"missing candidate library: {args.library}")
    torch.ops.load_library(str(args.library.resolve()))
    if not torch.xpu.is_available():
        raise SystemExit("XPU is unavailable")

    cases = []
    all_exact = True
    total_mismatches = 0
    digest = hashlib.sha256()
    for heads in HEAD_COUNTS:
        for seed in range(SEEDS):
            attention, gate = make_inputs(heads, seed)
            expected = baseline(attention, gate)
            observed = torch.empty_like(attention)
            candidate(observed, attention, gate)
            torch.xpu.synchronize()
            expected_raw = raw_bytes(expected)
            observed_raw = raw_bytes(observed)
            mismatch_count = int(
                (expected.view(torch.int16) != observed.view(torch.int16))
                .sum()
                .item()
            )
            exact = expected_raw == observed_raw
            all_exact = all_exact and exact
            total_mismatches += mismatch_count
            digest.update(expected_raw)
            digest.update(observed_raw)
            cases.append(
                {
                    "heads": heads,
                    "seed": seed,
                    "exact": exact,
                    "mismatch_count": mismatch_count,
                    "expected_sha256": hashlib.sha256(expected_raw).hexdigest(),
                    "observed_sha256": hashlib.sha256(observed_raw).hexdigest(),
                }
            )

    exhaustive = exhaustive_finite_gate_check() if all_exact else {
        "finite_bf16_values": 65280,
        "checked": 0,
        "mismatches": -1,
        "passed": False,
    }
    all_exact = all_exact and bool(exhaustive["passed"])

    timings = {}
    if all_exact:
        for heads in HEAD_COUNTS:
            attention, gate = make_inputs(heads, 0x5A)
            out = torch.empty_like(attention)
            for _ in range(WARMUP):
                baseline(attention, gate)
                candidate(out, attention, gate)
            torch.xpu.synchronize()
            baseline_ms = [
                event_block(lambda: baseline(attention, gate))
                for _ in range(TIMING_BLOCKS)
            ]
            candidate_ms = [
                event_block(lambda: candidate(out, attention, gate))
                for _ in range(TIMING_BLOCKS)
            ]
            b_med = statistics.median(baseline_ms)
            c_med = statistics.median(candidate_ms)
            timings[str(heads)] = {
                "baseline_block_median_ms_per_call": b_med,
                "candidate_block_median_ms_per_call": c_med,
                "speedup": b_med / c_med,
                "baseline_blocks_ms_per_call": baseline_ms,
                "candidate_blocks_ms_per_call": candidate_ms,
            }

    report = {
        "schema": "laguna-attention-gate-m12-component-v1",
        "library": str(args.library.resolve()),
        "library_sha256": hashlib.sha256(args.library.read_bytes()).hexdigest(),
        "torch_version": torch.__version__,
        "device": torch.xpu.get_device_name(0),
        "shapes": [
            [ROWS, heads * HEAD_DIM, heads] for heads in HEAD_COUNTS
        ],
        "seeds_per_shape": SEEDS,
        "case_count": len(cases),
        "all_raw_bf16_exact": all_exact,
        "total_mismatches": total_mismatches,
        "exhaustive_finite_gate_check": exhaustive,
        "combined_raw_sha256": digest.hexdigest(),
        "timing": {
            "warmup_calls_per_arm": WARMUP,
            "blocks": TIMING_BLOCKS,
            "calls_per_block": CALLS_PER_BLOCK,
            "by_heads": timings,
        },
        "structural_projection": {
            "layers": 48,
            "incumbent_submissions_per_layer": 4,
            "candidate_submissions_per_layer": 1,
            "incumbent_submissions": 192,
            "candidate_submissions": 48,
            "status": "confirmed separately with PyTorch XPU profiler",
        },
        "cases": cases,
        "passed": all_exact and total_mismatches == 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in (
        "case_count", "all_raw_bf16_exact", "total_mismatches",
        "exhaustive_finite_gate_check", "timing", "passed"
    )}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
