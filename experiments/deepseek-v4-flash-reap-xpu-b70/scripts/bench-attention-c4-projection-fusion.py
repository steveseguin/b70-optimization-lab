#!/usr/bin/env python3
"""Gate horizontal fusion of the three C4 attention BF16 projections."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch


def summarize(samples: list[float]) -> dict[str, float | list[float]]:
    return {
        "median_us": statistics.median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
        "samples_us": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmups", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    torch.manual_seed(13)
    device = torch.device("xpu")
    dtype = torch.bfloat16
    hidden = torch.randn((1, 4096), device=device, dtype=dtype) / 16
    output_dims = [2048, 64, 512]
    weights = [
        torch.randn((dim, 4096), device=device, dtype=dtype) for dim in output_dims
    ]
    # This concatenation models a load-time packed parameter, not decode work.
    fused_weight = torch.cat(weights, dim=0).contiguous()
    compressor_weights = torch.cat((weights[0], weights[2]), dim=0).contiguous()
    compressor_and_index_weight = torch.cat((weights[0], weights[1]), dim=0).contiguous()

    def separate_once() -> list[torch.Tensor]:
        return [
            torch.mm(hidden, weights[0].t(), out_dtype=torch.float32),
            torch.mm(hidden, weights[1].t()),
            torch.mm(hidden, weights[2].t(), out_dtype=torch.float32),
        ]

    def fused_once() -> list[torch.Tensor]:
        output = torch.mm(hidden, fused_weight.t(), out_dtype=torch.float32)
        parts = list(output.split(output_dims, dim=-1))
        parts[1] = parts[1].to(dtype)
        return parts

    def fused_compressors_once() -> list[torch.Tensor]:
        output = torch.mm(
            hidden, compressor_weights.t(), out_dtype=torch.float32
        )
        compressor, index_compressor = output.split((2048, 512), dim=-1)
        index_weights = torch.mm(hidden, weights[1].t())
        return [compressor, index_weights, index_compressor]

    def fused_compressor_and_index_once() -> list[torch.Tensor]:
        output = torch.mm(
            hidden, compressor_and_index_weight.t(), out_dtype=torch.float32
        )
        compressor, index_weights_fp32 = output.split((2048, 64), dim=-1)
        index_compressor = torch.mm(
            hidden, weights[2].t(), out_dtype=torch.float32
        )
        return [compressor, index_weights_fp32.to(dtype), index_compressor]

    separate = separate_once()
    candidates = {
        "all_three": fused_once(),
        "two_compressors": fused_compressors_once(),
        "compressor_and_index": fused_compressor_and_index_once(),
    }
    torch.xpu.synchronize()
    correctness = {}
    for name, candidate in candidates.items():
        correctness[name] = {
            "bitwise": [
                torch.equal(expected, actual)
                for expected, actual in zip(separate, candidate, strict=True)
            ],
            "max_abs_diff": [
                (expected - actual).abs().max().item()
                for expected, actual in zip(separate, candidate, strict=True)
            ],
        }

    stream = torch.xpu.current_stream()

    def time_us(fn) -> list[float]:
        for _ in range(args.warmups):
            fn()
        torch.xpu.synchronize()
        samples = []
        for _ in range(args.repeats):
            start = torch.xpu.Event(enable_timing=True)
            end = torch.xpu.Event(enable_timing=True)
            start.record(stream)
            for _ in range(args.iterations):
                fn()
            end.record(stream)
            end.synchronize()
            samples.append(start.elapsed_time(end) * 1000.0 / args.iterations)
        return samples

    separate_timing = summarize(time_us(separate_once))
    candidate_fns = {
        "all_three": fused_once,
        "two_compressors": fused_compressors_once,
        "compressor_and_index": fused_compressor_and_index_once,
    }
    candidate_timings = {}
    for name, fn in candidate_fns.items():
        timing = summarize(time_us(fn))
        saved_us = separate_timing["median_us"] - timing["median_us"]
        exact = all(correctness[name]["bitwise"])
        candidate_timings[name] = {
            "timing": timing,
            "saved_us_per_c4_layer": saved_us,
            "projected_saved_ms_per_token": saved_us * 21 / 1000.0,
            "exact": exact,
        }
    exact_candidates = [
        value for value in candidate_timings.values() if value["exact"]
    ]
    best_exact_ms = max(
        (value["projected_saved_ms_per_token"] for value in exact_candidates),
        default=0.0,
    )
    result = {
        "classification": "deepseek_v4_attention_c4_projection_fusion_microgate",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "shape": {
            "m": 1,
            "k": 4096,
            "separate_n": output_dims,
            "fused_n": sum(output_dims),
            "c4_layers": 21,
        },
        "warmups": args.warmups,
        "iterations": args.iterations,
        "repeats": args.repeats,
        "correctness": correctness,
        "separate": separate_timing,
        "candidates": candidate_timings,
        "best_exact_projected_saved_ms_per_token": best_exact_ms,
        "gate": {
            "required_projected_ms": 0.5,
            "passed": best_exact_ms >= 0.5,
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
