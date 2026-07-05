#!/usr/bin/env python3
"""Microbenchmark experimental INT8 LM-head top-1 + candidate-score XPU op.

Diagnostic only. This compares a native candidate-max primitive against the
current dense-logits path for Qwen3.6 27B real LM-head shapes. It is not a
model-quality benchmark and must not be used as headline throughput.
"""

from __future__ import annotations

import argparse
import json
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
            "Optional path to isolated _xpu_C*.so built with "
            "int8_lm_head_candidate_max_w8a8."
        ),
    )
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--hidden-size", type=int, default=5120)
    parser.add_argument("--vocab-size", type=int, default=248320)
    parser.add_argument("--valid-vocab-size", type=int, default=248320)
    parser.add_argument("--rows", type=parse_rows, default=parse_rows("1,2,3,4"))
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--scale-dtype", choices=("bf16", "fp32"), default="bf16")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.xpu_so:
        torch.ops.load_library(args.xpu_so)
    else:
        import vllm_xpu_kernels._xpu_C  # noqa: F401
    if not hasattr(torch.ops._xpu_C, "int8_lm_head_candidate_max_w8a8"):
        raise RuntimeError(
            "loaded _xpu_C does not expose int8_lm_head_candidate_max_w8a8")
    has_atomic = hasattr(
        torch.ops._xpu_C, "int8_lm_head_candidate_max_atomic_w8a8")

    dtype = {"bf16": torch.bfloat16, "fp16": torch.float16}[args.dtype]
    scale_dtype = torch.bfloat16 if args.scale_dtype == "bf16" else torch.float32
    device = torch.device(args.device)
    torch.manual_seed(args.seed)

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
        candidate_ids = torch.randint(
            0,
            args.valid_vocab_size,
            (rows,),
            dtype=torch.int64,
            device=device,
        ).contiguous()

        def quantize_hidden():
            return torch.ops._xpu_C.per_token_quant_int8_xpu(hidden)

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
            valid_logits = logits[:, : args.valid_vocab_size]
            top_vals, top_ids = torch.max(valid_logits, dim=-1)
            candidate_vals = valid_logits.gather(1, candidate_ids[:, None])[:, 0]
            candidate_is_top = candidate_ids == top_ids
            return (
                top_ids,
                top_vals.float(),
                candidate_vals.float(),
                candidate_is_top,
            )

        def candidate_max():
            x_q, x_scale = quantize_hidden()
            return torch.ops._xpu_C.int8_lm_head_candidate_max_w8a8(
                x_q,
                x_scale,
                weight_t,
                weight_scales,
                candidate_ids,
                dtype,
                args.valid_vocab_size,
            )

        def candidate_max_atomic():
            x_q, x_scale = quantize_hidden()
            return torch.ops._xpu_C.int8_lm_head_candidate_max_atomic_w8a8(
                x_q,
                x_scale,
                weight_t,
                weight_scales,
                candidate_ids,
                dtype,
                args.valid_vocab_size,
            )

        for _ in range(args.warmup):
            baseline()
            candidate_max()
            if has_atomic:
                candidate_max_atomic()
        torch.xpu.synchronize()

        base_ids, base_vals, base_candidate_vals, base_candidate_is_top = baseline()
        cand_ids, cand_vals, cand_candidate_vals, cand_candidate_is_top = (
            candidate_max()
        )
        if has_atomic:
            (
                atomic_ids,
                atomic_vals,
                atomic_candidate_vals,
                atomic_candidate_is_top,
            ) = candidate_max_atomic()
        else:
            atomic_ids = atomic_vals = atomic_candidate_vals = atomic_candidate_is_top = None
        torch.xpu.synchronize()

        id_mismatches = int((base_ids != cand_ids).sum().item())
        candidate_flag_mismatches = int(
            (base_candidate_is_top != cand_candidate_is_top).sum().item()
        )
        max_top_abs_diff = float(
            torch.max(torch.abs(base_vals - cand_vals)).detach().cpu().item()
        )
        max_candidate_abs_diff = float(
            torch.max(torch.abs(base_candidate_vals - cand_candidate_vals))
            .detach()
            .cpu()
            .item()
        )
        if has_atomic:
            atomic_id_mismatches = int((base_ids != atomic_ids).sum().item())
            atomic_candidate_flag_mismatches = int(
                (base_candidate_is_top != atomic_candidate_is_top).sum().item()
            )
            atomic_max_top_abs_diff = float(
                torch.max(torch.abs(base_vals - atomic_vals)).detach().cpu().item()
            )
            atomic_max_candidate_abs_diff = float(
                torch.max(torch.abs(base_candidate_vals - atomic_candidate_vals))
                .detach()
                .cpu()
                .item()
            )
        else:
            atomic_id_mismatches = None
            atomic_candidate_flag_mismatches = None
            atomic_max_top_abs_diff = None
            atomic_max_candidate_abs_diff = None

        baseline_times = time_op(baseline, args.repeats)
        candidate_times = time_op(candidate_max, args.repeats)
        atomic_times = (
            time_op(candidate_max_atomic, args.repeats) if has_atomic else []
        )
        baseline_med = median_ms(baseline_times)
        candidate_med = median_ms(candidate_times)
        atomic_med = median_ms(atomic_times) if atomic_times else None

        results.append(
            {
                "rows": rows,
                "baseline_ms_median": baseline_med,
                "candidate_max_ms_median": candidate_med,
                "candidate_max_atomic_ms_median": atomic_med,
                "speedup": baseline_med / candidate_med if candidate_med else None,
                "atomic_speedup": (
                    baseline_med / atomic_med if atomic_med else None
                ),
                "top_id_mismatches_vs_baseline": id_mismatches,
                "candidate_is_top_mismatches": candidate_flag_mismatches,
                "max_top_value_abs_diff": max_top_abs_diff,
                "max_candidate_value_abs_diff": max_candidate_abs_diff,
                "atomic_top_id_mismatches_vs_baseline": atomic_id_mismatches,
                "atomic_candidate_is_top_mismatches": (
                    atomic_candidate_flag_mismatches
                ),
                "atomic_max_top_value_abs_diff": atomic_max_top_abs_diff,
                "atomic_max_candidate_value_abs_diff": (
                    atomic_max_candidate_abs_diff
                ),
                "candidate_ids": candidate_ids.detach().cpu().tolist(),
                "baseline_ids": base_ids.detach().cpu().tolist(),
                "candidate_max_ids": cand_ids.detach().cpu().tolist(),
                "candidate_max_atomic_ids": (
                    atomic_ids.detach().cpu().tolist() if has_atomic else None
                ),
                "baseline_ms_samples": [
                    round(sample * 1000.0, 6) for sample in baseline_times
                ],
                "candidate_max_ms_samples": [
                    round(sample * 1000.0, 6) for sample in candidate_times
                ],
                "candidate_max_atomic_ms_samples": [
                    round(sample * 1000.0, 6) for sample in atomic_times
                ],
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
        "has_atomic_candidate_max": has_atomic,
        "results": results,
        "promotion_rule": (
            "Do not integrate unless exact and clearly faster than dense logits, "
            "roughly <2.3 ms or >1.10x on rows 1-4."
        ),
        "note": (
            "Synthetic tensors; useful only for LM-head primitive cost. Not a "
            "model-quality or fresh-response throughput benchmark."
        ),
    }
    text = json.dumps(payload, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n")


if __name__ == "__main__":
    main()
