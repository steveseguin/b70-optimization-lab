#!/usr/bin/env python3
"""Autotune an M=1 BF16-to-FP32 GEMV for DeepSeek V4 compressors."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch

from vllm.triton_utils import tl, triton


@triton.jit
def _bf16_fp32_gemv_kernel(
    x_ptr,
    weight_ptr,
    out_ptr,
    n: tl.constexpr,
    k: tl.constexpr,
    stride_weight_n: tl.constexpr,
    block_n: tl.constexpr,
    block_k: tl.constexpr,
):
    n_offsets = tl.program_id(0) * block_n + tl.arange(0, block_n)
    accumulator = tl.zeros((block_n,), dtype=tl.float32)
    for k_start in range(0, k, block_k):
        k_offsets = k_start + tl.arange(0, block_k)
        x = tl.load(x_ptr + k_offsets, mask=k_offsets < k, other=0.0)
        weight = tl.load(
            weight_ptr + n_offsets[:, None] * stride_weight_n + k_offsets[None, :],
            mask=(n_offsets[:, None] < n) & (k_offsets[None, :] < k),
            other=0.0,
        )
        accumulator += tl.sum(
            weight.to(tl.float32) * x[None, :].to(tl.float32), axis=1
        )
    tl.store(out_ptr + n_offsets, accumulator, mask=n_offsets < n)


def summarize(samples: list[float]) -> dict[str, float | list[float]]:
    return {
        "median_us": statistics.median(samples),
        "min_us": min(samples),
        "max_us": max(samples),
        "samples_us": samples,
    }


def time_us(fn, warmups: int, iterations: int, repeats: int) -> list[float]:
    for _ in range(warmups):
        fn()
    torch.xpu.synchronize()
    stream = torch.xpu.current_stream()
    samples = []
    for _ in range(repeats):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record(stream)
        for _ in range(iterations):
            fn()
        end.record(stream)
        end.synchronize()
        samples.append(start.elapsed_time(end) * 1000.0 / iterations)
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmups", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--n", type=int, action="append")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    torch.manual_seed(19)
    device = torch.device("xpu")
    k = 4096
    x = torch.randn((k,), device=device, dtype=torch.bfloat16) / 16
    configs = [
        (block_n, block_k, num_warps)
        for block_n in (1, 2)
        for block_k in (16, 32, 64, 128, 256, 512, 1024)
        for num_warps in (4,)
    ]
    rows = []
    for n in args.n or (512, 1024, 2048, 2624):
        weight = torch.randn((n, k), device=device, dtype=torch.bfloat16) / 16
        reference = torch.mm(x.view(1, k), weight.t(), out_dtype=torch.float32).view(
            n
        )
        torch.xpu.synchronize()

        def torch_mm():
            return torch.mm(
                x.view(1, k), weight.t(), out_dtype=torch.float32
            )

        torch_timing = summarize(
            time_us(torch_mm, args.warmups, args.iterations, args.repeats)
        )
        candidates = []
        for block_n, block_k, num_warps in configs:
            output = torch.empty((n,), device=device, dtype=torch.float32)

            def candidate():
                _bf16_fp32_gemv_kernel[(triton.cdiv(n, block_n),)](
                    x,
                    weight,
                    output,
                    n=n,
                    k=k,
                    stride_weight_n=weight.stride(0),
                    block_n=block_n,
                    block_k=block_k,
                    num_warps=num_warps,
                )
                return output

            candidate()
            torch.xpu.synchronize()
            abs_diff = (reference - output).abs()
            timing = summarize(
                time_us(candidate, args.warmups, args.iterations, args.repeats)
            )
            candidates.append(
                {
                    "block_n": block_n,
                    "block_k": block_k,
                    "num_warps": num_warps,
                    "timing": timing,
                    "max_abs_diff": abs_diff.max().item(),
                    "mean_abs_diff": abs_diff.mean().item(),
                    "bitwise": torch.equal(reference, output),
                    "matching_elements": (reference == output).sum().item(),
                    "allclose": torch.allclose(
                        reference, output, rtol=1e-4, atol=1e-4
                    ),
                }
            )
        candidates.sort(key=lambda item: item["timing"]["median_us"])
        best = candidates[0]
        rows.append(
            {
                "n": n,
                "k": k,
                "weight_bytes": n * k * 2,
                "torch_mm": torch_timing,
                "best": best,
                "speedup": torch_timing["median_us"]
                / best["timing"]["median_us"],
                "top_candidates": candidates[:8],
            }
        )

    result = {
        "classification": "deepseek_v4_bf16_fp32_gemv_triton_microgate",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "warmups": args.warmups,
        "iterations": args.iterations,
        "repeats": args.repeats,
        "rows": rows,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
