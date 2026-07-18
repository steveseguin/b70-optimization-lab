#!/usr/bin/env python3
"""Gate the width-aware split-FP8 attention geometry in graph replay."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics

os.environ["VLLM_XPU_V4_SPLIT_FP8_MWIDTH_GEOMETRY"] = "1"

import torch  # noqa: E402

from vllm.models.deepseek_v4.xpu.xpu_sparse_decode_fp8 import (  # noqa: E402
    split_fp8_sparse_attention,
)


def make_cache(
    num_rows: int, block_size: int, device: torch.device
) -> torch.Tensor:
    num_blocks = (num_rows + block_size - 1) // block_size
    cache = torch.empty(
        (num_blocks, block_size, 584), dtype=torch.uint8, device=device
    )
    flat = cache.view(num_blocks, -1)
    fp8 = (
        torch.randn(
            (num_blocks, block_size, 448),
            dtype=torch.float32,
            device=device,
        )
        .clamp_(-2.0, 2.0)
        .to(torch.float8_e4m3fn)
        .view(torch.uint8)
    )
    rope = (
        torch.randn(
            (num_blocks, block_size, 64),
            dtype=torch.bfloat16,
            device=device,
        )
        .div_(8)
        .view(torch.uint8)
    )
    token_data = torch.cat((fp8, rope), dim=2)
    flat[:, : block_size * 576].copy_(token_data.view(num_blocks, -1))
    flat[:, block_size * 576 :].fill_(127)
    return cache


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ep-rank", type=int, choices=range(4), required=True)
    parser.add_argument("--width", type=int, choices=(4, 7, 8), required=True)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--required-ms", type=float, default=0.50)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    torch.manual_seed(20260718 + args.ep_rank)
    torch.xpu.manual_seed_all(20260718 + args.ep_rank)
    device = torch.device("xpu:0")
    width = args.width
    heads = 64
    compressed_width = 256
    swa_width = 128
    block_size = 256
    num_rows = width * compressed_width
    compressed_cache = make_cache(num_rows, block_size, device)
    swa_cache = make_cache(num_rows, block_size, device)
    compressed_indices = torch.empty(
        (width, compressed_width), dtype=torch.int32, device=device
    )
    swa_indices = torch.empty(
        (width, swa_width), dtype=torch.int32, device=device
    )
    compressed_lens = torch.full(
        (width,), 128, dtype=torch.int32, device=device
    )
    swa_lens = torch.full((width,), 128, dtype=torch.int32, device=device)
    q = torch.randn((width, heads, 512), dtype=torch.bfloat16, device=device)
    sink = torch.linspace(-1.0, 1.0, heads, dtype=torch.float32, device=device)
    reference = torch.empty_like(q)
    candidate = torch.empty_like(q)

    def set_indices(family: str) -> None:
        def rows(index_width: int) -> torch.Tensor:
            base = torch.arange(index_width, dtype=torch.int32, device=device)
            if family == "identical":
                return base.unsqueeze(0).repeat(width, 1)
            if family == "shifted":
                return torch.stack([base + row for row in range(width)])
            return torch.stack(
                [base + row * index_width for row in range(width)]
            )

        compressed_indices.copy_(rows(compressed_width))
        swa_indices.copy_(rows(swa_width))

    def run(out: torch.Tensor, candidate_geometry: bool) -> None:
        kwargs = {} if candidate_geometry else {
            "block_h": 4,
            "qk_num_warps": 16,
            "pv_num_warps": 4,
        }
        split_fp8_sparse_attention(
            q,
            compressed_cache,
            compressed_indices,
            compressed_lens,
            swa_cache,
            swa_indices,
            swa_lens,
            sink,
            512**-0.5,
            out,
            **kwargs,
        )

    def reference_call() -> None:
        run(reference, False)

    def candidate_call() -> None:
        run(candidate, True)

    def capture(callable_) -> torch.xpu.XPUGraph:
        for _ in range(3):
            callable_()
        torch.xpu.synchronize()
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            callable_()
        graph.replay()
        torch.xpu.synchronize()
        return graph

    set_indices("shifted")
    reference_graph = capture(reference_call)
    candidate_graph = capture(candidate_call)

    cases = []
    patterns = ("identical", "shifted", "disjoint")
    lengths = (4, 32, 128, 256)
    for pattern_index, pattern in enumerate(patterns):
        set_indices(pattern)
        for length in lengths:
            compressed_lens.fill_(length)
            swa_lens.fill_(min(length, swa_width))
            for epoch in range(args.epochs):
                generator = torch.Generator(device=device).manual_seed(
                    20260718
                    + args.ep_rank * 10000
                    + pattern_index * 1000
                    + length * 10
                    + epoch
                )
                q.copy_(
                    torch.randn(
                        q.shape,
                        dtype=q.dtype,
                        device=device,
                        generator=generator,
                    )
                )
                reference_graph.replay()
                candidate_graph.replay()
                torch.xpu.synchronize()
                exact = torch.equal(reference, candidate)
                cases.append(
                    {
                        "pattern": pattern,
                        "compressed_len": length,
                        "swa_len": min(length, swa_width),
                        "epoch": epoch,
                        "exact": exact,
                        "max_abs_diff": float(
                            (reference.float() - candidate.float())
                            .abs()
                            .max()
                            .item()
                        ),
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

    timing = []
    for pattern in patterns:
        set_indices(pattern)
        for length in lengths:
            compressed_lens.fill_(length)
            swa_lens.fill_(min(length, swa_width))
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
            reference_us = statistics.median(reference_samples)
            candidate_us = statistics.median(candidate_samples)
            timing.append(
                {
                    "pattern": pattern,
                    "compressed_len": length,
                    "swa_len": min(length, swa_width),
                    "reference_median_us": reference_us,
                    "candidate_median_us": candidate_us,
                    "speedup": reference_us / candidate_us,
                    "projected_saved_ms_per_43_layers": (
                        reference_us - candidate_us
                    )
                    * 43
                    / 1000.0,
                    "reference_samples_us": reference_samples,
                    "candidate_samples_us": candidate_samples,
                }
            )

    exact = all(case["exact"] for case in cases)
    minimum_saved_ms = min(
        row["projected_saved_ms_per_43_layers"] for row in timing
    )
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_split_fp8_mwidth_geometry_gate",
        "device": torch.xpu.get_device_name(device),
        "ep_rank": args.ep_rank,
        "shape": {
            "m": width,
            "heads": heads,
            "compressed_width": compressed_width,
            "swa_width": swa_width,
        },
        "reference_geometry": {"block_h": 4, "qk_warps": 16, "pv_warps": 4},
        "candidate_geometry": {"block_h": 4, "qk_warps": 8, "pv_warps": 4},
        "correctness": {
            "cases": len(cases),
            "exact_cases": sum(case["exact"] for case in cases),
            "passed": exact,
            "rows": cases,
        },
        "timing": {
            "selection_rule": "minimum across index families and runtime lengths",
            "rows": timing,
            "selected_minimum_saved_ms_per_43_layers": minimum_saved_ms,
            "required_ms": args.required_ms,
            "clears_integration_gate": minimum_saved_ms >= args.required_ms,
        },
        "passed": exact and minimum_saved_ms >= args.required_ms,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "ep_rank": args.ep_rank,
                "width": width,
                "exact_cases": result["correctness"]["exact_cases"],
                "cases": result["correctness"]["cases"],
                "minimum_saved_ms_per_43_layers": minimum_saved_ms,
                "passed": result["passed"],
            },
            indent=2,
        )
    )
    reference_graph.reset()
    candidate_graph.reset()
    torch.xpu.synchronize()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
