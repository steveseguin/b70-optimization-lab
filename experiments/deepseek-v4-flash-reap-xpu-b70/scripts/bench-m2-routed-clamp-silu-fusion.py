#!/usr/bin/env python3
"""Gate generic M=2 routed-MoE clamp + SiLU/multiply fusion on B70."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch

import vllm_xpu_kernels._C  # noqa: F401


def summary(samples: list[float]) -> dict[str, float | list[float]]:
    return {
        "median_us": statistics.median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
        "samples_us": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--layers", type=int, default=43)
    parser.add_argument("--required-ms", type=float, default=0.50)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    device = torch.device(args.device)
    rows = 12
    intermediate = 2048
    limit = 10.0
    source = torch.empty(
        (rows, 2 * intermediate), dtype=torch.bfloat16, device=device
    )
    reference_input = torch.empty_like(source)
    candidate_input = torch.empty_like(source)
    reference_output = torch.empty(
        (rows, intermediate), dtype=torch.bfloat16, device=device
    )
    candidate_output = torch.empty_like(reference_output)

    def reference() -> None:
        reference_input[:, :intermediate].clamp_(max=limit)
        reference_input[:, intermediate:].clamp_(min=-limit, max=limit)
        torch.ops._C.silu_and_mul(reference_output, reference_input)

    def candidate() -> None:
        torch.ops._C.silu_and_mul_clamp(candidate_output, candidate_input, limit)

    generator = torch.Generator(device=device).manual_seed(20260716)
    source.copy_(
        torch.randn(
            source.shape,
            dtype=source.dtype,
            device=device,
            generator=generator,
        )
    )
    reference_input.copy_(source)
    candidate_input.copy_(source)
    for _ in range(3):
        reference()
        candidate()
    torch.xpu.synchronize()

    reference_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(reference_graph):
        reference()
    candidate_graph = torch.xpu.XPUGraph()
    with torch.xpu.graph(candidate_graph):
        candidate()
    reference_graph.replay()
    candidate_graph.replay()
    torch.xpu.synchronize()

    scales = (0.125, 1.0, 4.0, 12.0, 32.0)
    correctness_rows = []
    for epoch in range(args.epochs):
        generator.manual_seed(20260716 + 101 * epoch)
        source.copy_(
            torch.randn(
                source.shape,
                dtype=source.dtype,
                device=device,
                generator=generator,
            )
            * scales[epoch % len(scales)]
        )
        # Include exact clamp boundaries and asymmetric extremes explicitly.
        source[0, :8] = torch.tensor(
            [-32.0, -10.0, -9.9375, -0.0, 0.0, 9.9375, 10.0, 32.0],
            dtype=source.dtype,
            device=device,
        )
        source[0, intermediate : intermediate + 8] = torch.tensor(
            [-32.0, -10.0, -9.9375, -0.0, 0.0, 9.9375, 10.0, 32.0],
            dtype=source.dtype,
            device=device,
        )
        reference_input.copy_(source)
        candidate_input.copy_(source)
        reference_graph.replay()
        torch.xpu.synchronize()
        expected = reference_output.clone()
        candidate_graph.replay()
        torch.xpu.synchronize()
        first = candidate_output.clone()
        reference_input.copy_(source)
        reference_graph.replay()
        candidate_graph.replay()
        torch.xpu.synchronize()
        mismatches = int(
            torch.count_nonzero(reference_output != candidate_output).item()
        )
        correctness_rows.append(
            {
                "epoch": epoch,
                "input_scale": scales[epoch % len(scales)],
                "mismatches": mismatches,
                "max_abs_diff": float(
                    (reference_output.float() - candidate_output.float())
                    .abs()
                    .max()
                    .item()
                ),
                "candidate_repeat_exact": torch.equal(first, candidate_output),
                "reference_repeat_exact": torch.equal(expected, reference_output),
            }
        )

    def timed_us(graph: torch.xpu.XPUGraph) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.iterations):
            graph.replay()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.iterations

    for _ in range(args.warmup):
        reference_graph.replay()
        candidate_graph.replay()
    torch.xpu.synchronize()
    reference_samples = []
    candidate_samples = []
    for sample in range(args.samples):
        if sample % 2 == 0:
            reference_samples.append(timed_us(reference_graph))
            candidate_samples.append(timed_us(candidate_graph))
        else:
            candidate_samples.append(timed_us(candidate_graph))
            reference_samples.append(timed_us(reference_graph))
    reference_timing = summary(reference_samples)
    candidate_timing = summary(candidate_samples)
    saved_us = reference_timing["median_us"] - candidate_timing["median_us"]
    projected_ms = saved_us * args.layers / 1000.0
    exact = all(
        row["mismatches"] == 0
        and row["candidate_repeat_exact"]
        and row["reference_repeat_exact"]
        for row in correctness_rows
    )
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_m2_routed_clamp_silu_fusion_gate",
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "shape": {
            "target_rows": 2,
            "topk": 6,
            "routed_slots": rows,
            "gemm1_width": 2 * intermediate,
            "activation_width": intermediate,
            "dtype": str(source.dtype),
            "clamp_limit": limit,
        },
        "correctness": {
            "exact": exact,
            "epochs": args.epochs,
            "rows": correctness_rows,
        },
        "timing": {
            "reference": reference_timing,
            "candidate": candidate_timing,
            "saved_us_per_layer": saved_us,
            "projected_saved_ms_per_cycle": projected_ms,
            "layers_per_verification": args.layers,
        },
        "gate": {
            "required_projected_ms": args.required_ms,
            "passed": exact and projected_ms >= args.required_ms,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    reference_graph.reset()
    candidate_graph.reset()
    torch.xpu.synchronize()
    return 0 if result["gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
