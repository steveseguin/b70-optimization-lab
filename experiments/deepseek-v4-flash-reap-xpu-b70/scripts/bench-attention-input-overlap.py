#!/usr/bin/env python3
"""Measure DeepSeek V4 attention input-projection overlap on one B70.

This is a scheduling feasibility gate.  It reproduces the M=1 projection
shapes submitted by ``DeepseekV4Attention.attn_gemm_parallel_execute`` for
the K160 TP4 record lane.  The default stream runs the promoted W8A16
``fused_wqa_wkv`` projection while the independent compressor/indexer
projections run on auxiliary streams.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Callable

import torch

import vllm  # noqa: F401 - registers XPU operators
import vllm._custom_ops  # noqa: F401
import vllm_xpu_kernels  # noqa: F401


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

    torch.manual_seed(11)
    device = torch.device("xpu")
    dtype = torch.bfloat16
    hidden_size = 4096
    block_size = 128
    hidden = torch.randn((1, hidden_size), device=device, dtype=dtype) / 16
    empty_bias = torch.Tensor()

    # Promoted selective-W8A16 fused_wqa_wkv: [1,4096] x [4096,1536].
    main_weight = torch.randn(
        (1536, hidden_size), device=device, dtype=dtype
    ).to(torch.float8_e4m3fn)
    main_scale = torch.ones(
        (hidden_size // block_size, 1536 // block_size),
        device=device,
        dtype=torch.float8_e8m0fnu,
    )

    def default_projection() -> torch.Tensor:
        return torch.ops._xpu_C.fp8_gemm_w8a16(
            hidden, main_weight.t(), main_scale, empty_bias
        )

    # C128 layers have only the MLA compressor [4096 -> 1024].  C4 layers
    # additionally run index weights [4096 -> 64] and the index compressor
    # [4096 -> 512], while their MLA compressor is [4096 -> 2048].
    aux_weights = {
        "c128": [
            torch.randn((1024, hidden_size), device=device, dtype=dtype),
        ],
        "c4": [
            torch.randn((2048, hidden_size), device=device, dtype=dtype),
            torch.randn((64, hidden_size), device=device, dtype=dtype),
            torch.randn((512, hidden_size), device=device, dtype=dtype),
        ],
    }
    main_stream = torch.xpu.current_stream()
    aux_streams = [torch.xpu.Stream() for _ in range(3)]

    def measure_ratio(ratio: str) -> dict[str, object]:
        weights = aux_weights[ratio]
        aux_fns: list[Callable[[], torch.Tensor]] = [
            lambda weight=weight: torch.mm(
                hidden, weight.t(), out_dtype=torch.float32
            )
            for weight in weights
        ]

        def sequential_once() -> tuple[torch.Tensor, list[torch.Tensor]]:
            main = default_projection()
            aux = [fn() for fn in aux_fns]
            return main, aux

        def overlapped_once() -> tuple[torch.Tensor, list[torch.Tensor]]:
            aux_results: list[torch.Tensor] = []
            for stream, fn in zip(
                aux_streams[: len(aux_fns)], aux_fns, strict=True
            ):
                stream.wait_stream(main_stream)
                with torch.xpu.stream(stream):
                    aux_results.append(fn())
            main = default_projection()
            for stream in aux_streams[: len(aux_fns)]:
                main_stream.wait_stream(stream)
            return main, aux_results

        seq_main, seq_aux = sequential_once()
        torch.xpu.synchronize()
        seq_main_ref = seq_main.clone()
        seq_aux_ref = [value.clone() for value in seq_aux]
        ov_main, ov_aux = overlapped_once()
        torch.xpu.synchronize()
        correctness = {
            "main_bitwise": torch.equal(seq_main_ref, ov_main),
            "aux_bitwise": [
                torch.equal(expected, actual)
                for expected, actual in zip(seq_aux_ref, ov_aux, strict=True)
            ],
        }

        def time_us(fn) -> list[float]:
            for _ in range(args.warmups):
                fn()
            torch.xpu.synchronize()
            samples = []
            for _ in range(args.repeats):
                start = torch.xpu.Event(enable_timing=True)
                end = torch.xpu.Event(enable_timing=True)
                start.record(main_stream)
                for _ in range(args.iterations):
                    fn()
                end.record(main_stream)
                end.synchronize()
                samples.append(start.elapsed_time(end) * 1000.0 / args.iterations)
            return samples

        sequential = summarize(time_us(sequential_once))
        overlapped = summarize(time_us(overlapped_once))
        saved_us = sequential["median_us"] - overlapped["median_us"]
        layer_count = 20 if ratio == "c128" else 21
        exact = correctness["main_bitwise"] and all(correctness["aux_bitwise"])
        return {
            "ratio": ratio,
            "layer_count": layer_count,
            "aux_output_dims": [weight.shape[0] for weight in weights],
            "correctness": correctness,
            "sequential": sequential,
            "overlapped": overlapped,
            "saved_us_per_layer": saved_us,
            "projected_saved_ms": saved_us * layer_count / 1000.0,
            "exact": exact,
        }

    c128 = measure_ratio("c128")
    c4 = measure_ratio("c4")
    total_saved_ms = c128["projected_saved_ms"] + c4["projected_saved_ms"]
    result = {
        "classification": "deepseek_v4_attention_input_overlap_microgate",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "shape": {
            "m": 1,
            "hidden_size": hidden_size,
            "default_output_dim": 1536,
            "c128_layers": 20,
            "c4_layers": 21,
            "swa_only_layers_excluded": 2,
        },
        "warmups": args.warmups,
        "iterations": args.iterations,
        "repeats": args.repeats,
        "c128": c128,
        "c4": c4,
        "projected_saved_ms_per_token": total_saved_ms,
        "gate": {
            "required_projected_ms": 0.5,
            "passed": bool(c128["exact"] and c4["exact"] and total_saved_ms >= 0.5),
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if c128["exact"] and c4["exact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
