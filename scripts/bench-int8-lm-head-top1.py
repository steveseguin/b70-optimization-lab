#!/usr/bin/env python3
"""Microbenchmark an experimental fused INT8 LM-head top-1 XPU op.

This is a diagnostic harness only. It does not prove model quality and must not
be used as headline throughput. Its job is to decide whether a fused top-1
kernel is fast enough to justify wiring into the real Qwen3.6 27B serving path.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

import torch


def parse_rows(value: str) -> list[int]:
    return [int(part) for part in value.split(",") if part.strip()]


def median_ms(samples: list[float]) -> float:
    return statistics.median(samples) * 1000.0


def time_op(fn, repeats: int) -> list[float]:
    times: list[float] = []
    for _ in range(repeats):
        torch.xpu.synchronize()
        start = time.perf_counter()
        fn()
        torch.xpu.synchronize()
        times.append(time.perf_counter() - start)
    return times


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--xpu-so",
        required=True,
        help="Path to an isolated _xpu_C*.so built with int8_lm_head_top1_out.",
    )
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--hidden-size", type=int, default=5120)
    parser.add_argument("--vocab-size", type=int, default=248320)
    parser.add_argument("--valid-vocab-size", type=int, default=248320)
    parser.add_argument("--vocab-start", type=int, default=0)
    parser.add_argument("--rows", type=parse_rows, default=parse_rows("1,3,4,8"))
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--dtype", choices=("bf16", "fp16", "fp32"), default="bf16")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    torch.ops.load_library(args.xpu_so)
    if not hasattr(torch.ops._xpu_C, "int8_lm_head_top1_out"):
        raise RuntimeError("loaded _xpu_C does not expose int8_lm_head_top1_out")

    dtype = {
        "bf16": torch.bfloat16,
        "fp16": torch.float16,
        "fp32": torch.float32,
    }[args.dtype]
    device = torch.device(args.device)
    torch.manual_seed(args.seed)

    # Match the Qwen3.6 27B INT8-lm_head storage layout:
    # weight_t is [hidden_size, vocab_size], scales is [vocab_size].
    weight_t = torch.randint(
        -127,
        128,
        (args.hidden_size, args.vocab_size),
        dtype=torch.int8,
        device=device,
    )
    weight_scales = (
        torch.rand((args.vocab_size,), dtype=torch.float32, device=device) * 0.02
        + 0.001
    ).contiguous()

    results: list[dict[str, object]] = []
    for rows in args.rows:
        hidden = torch.randn(
            (rows, args.hidden_size), dtype=dtype, device=device
        ).contiguous()
        top_ids = torch.empty((rows,), dtype=torch.int64, device=device)
        top_scores = torch.empty((rows,), dtype=torch.float32, device=device)

        def baseline():
            x_q, x_scale = torch.ops._xpu_C.per_token_quant_int8_xpu(hidden)
            logits = torch.ops._xpu_C.int8_gemm_w8a8(
                x_q,
                x_scale,
                weight_t,
                weight_scales,
                dtype,
                None,
            )
            return torch.argmax(logits[:, : args.valid_vocab_size], dim=-1)

        def fused():
            return torch.ops._xpu_C.int8_lm_head_top1_out(
                hidden,
                weight_t,
                weight_scales,
                args.valid_vocab_size,
                args.vocab_start,
                top_ids,
                top_scores,
            )

        for _ in range(args.warmup):
            baseline()
            fused()
        torch.xpu.synchronize()

        baseline_ids = baseline()
        fused_ids, _ = fused()
        torch.xpu.synchronize()
        mismatches = int((baseline_ids != fused_ids).sum().item())

        baseline_times = time_op(baseline, args.repeats)
        fused_times = time_op(fused, args.repeats)

        baseline_med = median_ms(baseline_times)
        fused_med = median_ms(fused_times)
        results.append(
            {
                "rows": rows,
                "baseline_ms_median": baseline_med,
                "fused_ms_median": fused_med,
                "speedup": baseline_med / fused_med if fused_med else None,
                "top1_mismatches_vs_baseline": mismatches,
                "baseline_ms_samples": [round(x * 1000.0, 6) for x in baseline_times],
                "fused_ms_samples": [round(x * 1000.0, 6) for x in fused_times],
            }
        )

    payload = {
        "kind": "diagnostic_microbench_only",
        "xpu_so": str(Path(args.xpu_so).resolve()),
        "device": str(device),
        "hidden_size": args.hidden_size,
        "vocab_size": args.vocab_size,
        "valid_vocab_size": args.valid_vocab_size,
        "dtype": args.dtype,
        "warmup": args.warmup,
        "repeats": args.repeats,
        "results": results,
        "note": (
            "Synthetic tensors; useful only for comparing LM-head top-1 kernel "
            "cost. Not a model-quality or fresh-response throughput benchmark."
        ),
    }
    text = json.dumps(payload, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n")


if __name__ == "__main__":
    main()
