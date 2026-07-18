#!/usr/bin/env python3
"""Time the five TP4 DeepSeek V4 block-FP8 dense projection shapes on XPU."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch

# Importing vLLM registers torch.ops._C.per_token_group_fp8_quant and the XPU
# extension registers torch.ops._xpu_C.fp8_gemm.
import vllm  # noqa: F401
import vllm._custom_ops  # noqa: F401
import vllm_xpu_kernels  # noqa: F401


SHAPES = {
    "fused_wqa_wkv": (1, 1536, 4096),
    "wq_b": (1, 8192, 1024),
    "wo_b": (1, 4096, 2048),
    "shared_gate_up": (1, 1024, 4096),
    "shared_down": (1, 4096, 512),
    "mtp_e_h": (1, 4096, 4096),
}


def time_us(fn, warmups: int, iterations: int, repeats: int) -> list[float]:
    for _ in range(warmups):
        fn()
    torch.xpu.synchronize()

    samples = []
    for _ in range(repeats):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(iterations):
            fn()
        end.record()
        end.synchronize()
        samples.append(start.elapsed_time(end) * 1000.0 / iterations)
    return samples


def summarize(samples: list[float]) -> dict[str, float | list[float]]:
    return {
        "median_us": statistics.median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
        "samples_us": samples,
    }


def bench_shape(
    name: str,
    shape: tuple[int, int, int],
    warmups: int,
    iterations: int,
    repeats: int,
) -> dict:
    m, n, k = shape
    group = 128
    device = torch.device("xpu")

    x = torch.randn((m, k), device=device, dtype=torch.bfloat16) / 10
    q = torch.empty_like(x, dtype=torch.float8_e4m3fn)
    a_scale = torch.empty((m, k // group), device=device, dtype=torch.float32)

    # Match vLLM storage: [N,K] contiguous weight, passed to oneDNN as an NT
    # [K,N] view.  The prepacked scale grid is [K/128,N/128].
    weight_nk = (
        torch.randn((n, k), device=device, dtype=torch.bfloat16) / 10
    ).to(torch.float8_e4m3fn)
    weight_kn = weight_nk.t()
    b_scale = torch.ones(
        (k // group, n // group), device=device, dtype=torch.float32
    )
    old_b_scale = b_scale.t().contiguous()
    empty_bias = torch.Tensor()

    def quant_kernel():
        torch.ops._C.per_token_group_fp8_quant(
            x,
            q,
            a_scale,
            group,
            1e-10,
            -448.0,
            448.0,
            False,
            False,
            False,
        )

    quant_kernel()
    torch.xpu.synchronize()

    def gemm_kernel():
        return torch.ops._xpu_C.fp8_gemm(
            q,
            weight_kn,
            torch.bfloat16,
            a_scale,
            b_scale,
            empty_bias,
        )

    def w8a16_kernel():
        return torch.ops._xpu_C.fp8_gemm_w8a16(
            x,
            weight_kn,
            b_scale,
            empty_bias,
        )

    def old_scale_copy():
        old_b_scale.t().contiguous()

    def chained():
        quant_kernel()
        return gemm_kernel()

    w8a8_output = gemm_kernel()
    w8a16_output = w8a16_kernel()
    torch.xpu.synchronize()
    output_abs_diff = (w8a8_output.float() - w8a16_output.float()).abs()

    result = {
        "name": name,
        "m": m,
        "n": n,
        "k": k,
        "weight_bytes": n * k,
        "a_scale_shape": list(a_scale.shape),
        "b_scale_shape": list(b_scale.shape),
        "weight_shape_stored": list(weight_nk.shape),
        "weight_shape_op": list(weight_kn.shape),
        "weight_stride_op": list(weight_kn.stride()),
        "quant": summarize(time_us(quant_kernel, warmups, iterations, repeats)),
        "gemm": summarize(time_us(gemm_kernel, warmups, iterations, repeats)),
        "w8a16_gemm": summarize(
            time_us(w8a16_kernel, warmups, iterations, repeats)
        ),
        "quant_plus_gemm": summarize(
            time_us(chained, warmups, iterations, repeats)
        ),
        "old_scale_copy": summarize(
            time_us(old_scale_copy, warmups, iterations, repeats)
        ),
        "w8a16_vs_w8a8": {
            "max_abs": output_abs_diff.max().item(),
            "mean_abs": output_abs_diff.mean().item(),
        },
    }
    result["gemm_effective_weight_gb_s"] = (
        result["weight_bytes"] / result["gemm"]["median_us"] / 1000.0
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--width",
        type=int,
        choices=(1, 2, 4, 8),
        default=1,
        help="Override the token width of every selected production shape.",
    )
    parser.add_argument("--warmups", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--shape", action="append", choices=sorted(SHAPES))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    selected = args.shape or list(SHAPES)
    rows = [
        bench_shape(
            name,
            (args.width, SHAPES[name][1], SHAPES[name][2]),
            args.warmups,
            args.iterations,
            args.repeats,
        )
        for name in selected
    ]
    out = {
        "classification": "deepseek_v4_tp4_exact_fp8_dense_shape_microbench",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "warmups": args.warmups,
        "iterations": args.iterations,
        "repeats": args.repeats,
        "width": args.width,
        "rows": rows,
        "weighted_per_token_us": {
            "quant": sum(row["quant"]["median_us"] * 43 for row in rows),
            "gemm": sum(row["gemm"]["median_us"] * 43 for row in rows),
            "w8a16_gemm": sum(
                row["w8a16_gemm"]["median_us"] * 43 for row in rows
            ),
            "quant_plus_gemm": sum(
                row["quant_plus_gemm"]["median_us"] * 43 for row in rows
            ),
            "old_scale_copy": sum(
                row["old_scale_copy"]["median_us"] * 43 for row in rows
            ),
        },
    }
    rendered = json.dumps(out, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
