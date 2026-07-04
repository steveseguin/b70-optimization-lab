#!/usr/bin/env python3
"""Microbenchmark an experimental compact INT8 LM-head top-1 XPU op.

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
        default=None,
        help=(
            "Optional path to an isolated _xpu_C*.so built with "
            "int8_lm_head_top1_w8a8. If omitted, import vllm_xpu_kernels._xpu_C."
        ),
    )
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--hidden-size", type=int, default=5120)
    parser.add_argument("--vocab-size", type=int, default=248320)
    parser.add_argument("--valid-vocab-size", type=int, default=248320)
    parser.add_argument("--vocab-start", type=int, default=0)
    parser.add_argument("--rows", type=parse_rows, default=parse_rows("1,3,4,8"))
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument(
        "--scale-dtype",
        choices=("bf16", "fp32"),
        default="bf16",
        help="LM-head per-output scale dtype to test.",
    )
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.xpu_so:
        torch.ops.load_library(args.xpu_so)
    else:
        import vllm_xpu_kernels._xpu_C  # noqa: F401
    if not hasattr(torch.ops._xpu_C, "int8_lm_head_top1_w8a8"):
        raise RuntimeError(
            "loaded _xpu_C does not expose int8_lm_head_top1_w8a8")

    dtype = {
        "bf16": torch.bfloat16,
        "fp16": torch.float16,
    }[args.dtype]
    scale_dtype = torch.bfloat16 if args.scale_dtype == "bf16" else torch.float32
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
    weight_scales_f32 = (
        torch.rand((args.vocab_size,), dtype=torch.float32, device=device) * 0.02
        + 0.001
    ).contiguous()
    weight_scales = weight_scales_f32.to(scale_dtype).contiguous()

    results: list[dict[str, object]] = []
    for rows in args.rows:
        hidden = torch.randn(
            (rows, args.hidden_size), dtype=dtype, device=device
        ).contiguous()
        def quantize_hidden():
            x_q, x_scale = torch.ops._xpu_C.per_token_quant_int8_xpu(hidden)
            return x_q, x_scale

        def baseline():
            x_q, x_scale = quantize_hidden()
            logits = torch.ops._xpu_C.int8_gemm_w8a8(
                x_q,
                x_scale,
                weight_t,
                weight_scales,
                dtype,
                None,
            )
            return torch.argmax(logits[:, : args.valid_vocab_size], dim=-1)

        def compact():
            x_q, x_scale = quantize_hidden()
            return torch.ops._xpu_C.int8_lm_head_top1_w8a8(
                x_q,
                x_scale,
                weight_t,
                weight_scales,
                dtype,
                args.valid_vocab_size,
            )

        for _ in range(args.warmup):
            baseline()
            compact()
        torch.xpu.synchronize()

        baseline_ids = baseline()
        compact_ids, compact_scores = compact()
        torch.xpu.synchronize()
        mismatches = int((baseline_ids != compact_ids).sum().item())

        baseline_times = time_op(baseline, args.repeats)
        compact_times = time_op(compact, args.repeats)

        baseline_med = median_ms(baseline_times)
        compact_med = median_ms(compact_times)
        results.append(
            {
                "rows": rows,
                "baseline_ms_median": baseline_med,
                "compact_ms_median": compact_med,
                "speedup": baseline_med / compact_med if compact_med else None,
                "top1_mismatches_vs_baseline": mismatches,
                "baseline_ids": baseline_ids.detach().cpu().tolist(),
                "compact_ids": compact_ids.detach().cpu().tolist(),
                "compact_scores": [
                    float(x) for x in compact_scores.detach().cpu().tolist()
                ],
                "baseline_ms_samples": [round(x * 1000.0, 6) for x in baseline_times],
                "compact_ms_samples": [round(x * 1000.0, 6) for x in compact_times],
            }
        )

    payload = {
        "kind": "diagnostic_microbench_only",
        "xpu_so": str(Path(args.xpu_so).resolve()) if args.xpu_so else None,
        "device": str(device),
        "hidden_size": args.hidden_size,
        "vocab_size": args.vocab_size,
        "valid_vocab_size": args.valid_vocab_size,
        "dtype": args.dtype,
        "scale_dtype": args.scale_dtype,
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
