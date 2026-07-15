#!/usr/bin/env python3
"""Feasibility gate for an Xe2 M=1 WQ_B block-FP8 projection epilogue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

from vllm.platforms import current_platform
from vllm.triton_utils import tl, triton


@triton.jit
def _wqb_fp8_bf16_m1_kernel(
    input_ptr,
    weight_ptr,
    scale_ptr,
    output_ptr,
    K: tl.constexpr,
    N: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
    BLOCK_K: tl.constexpr,
    SCALE_BLOCK: tl.constexpr,
):
    pid_n = tl.program_id(0)
    n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    m = tl.arange(0, BLOCK_M)
    accumulator = tl.zeros((BLOCK_M, BLOCK_N), tl.float32)

    for scale_k in tl.static_range(0, K, SCALE_BLOCK):
        partial = tl.zeros((BLOCK_M, BLOCK_N), tl.float32)
        for inner_k in tl.static_range(0, SCALE_BLOCK, BLOCK_K):
            k = scale_k + inner_k + tl.arange(0, BLOCK_K)
            input_row = tl.load(input_ptr + k).to(tl.bfloat16)
            a = tl.where(m[:, None] == 0, input_row[None, :], 0.0).to(
                tl.bfloat16
            )
            # Checkpoint storage is contiguous [N,K]. Form the logical [K,N]
            # DPAS tile without materializing a transposed weight tensor.
            b = tl.load(weight_ptr + n[None, :] * K + k[:, None]).to(
                tl.bfloat16
            )
            partial += tl.dot(a, b, out_dtype=tl.float32)
        scale = tl.load(
            scale_ptr
            + (scale_k // SCALE_BLOCK) * (N // SCALE_BLOCK)
            + n // SCALE_BLOCK
        ).to(tl.float32)
        accumulator += partial * scale[None, :]

    tl.store(
        output_ptr + n[None, :] + m[:, None] * 0,
        accumulator.to(tl.bfloat16),
        mask=(m[:, None] == 0) & (n[None, :] < N),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--k", type=int, default=1024)
    parser.add_argument("--n", type=int, default=8192)
    parser.add_argument("--block-n", type=int, default=64)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-iterations", type=int, default=100)
    parser.add_argument("--layers", type=int, default=43)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.k % 128 or args.n % 128 or args.n % args.block_n:
        raise SystemExit("K/N must be divisible by 128 and N by block-n")
    torch.xpu.set_device(args.device)
    torch.manual_seed(20260715)
    device = torch.device(args.device)
    current_platform.import_kernels()
    x = torch.randn((1, args.k), dtype=torch.bfloat16, device=device)
    weight = torch.randn((args.n, args.k), dtype=torch.float32, device=device).to(
        torch.float8_e4m3fn
    )
    scales = (
        torch.rand(
            (args.k // 128, args.n // 128), dtype=torch.float32, device=device
        )
        * 0.02
        + 0.002
    )
    candidate_out = torch.empty((1, args.n), dtype=torch.bfloat16, device=device)

    def reference() -> torch.Tensor:
        return torch.ops._xpu_C.fp8_gemm_w8a16(x, weight.t(), scales, None)

    def candidate() -> torch.Tensor:
        _wqb_fp8_bf16_m1_kernel[(args.n // args.block_n,)](
            x,
            weight,
            scales,
            candidate_out,
            K=args.k,
            N=args.n,
            BLOCK_M=16,
            BLOCK_N=args.block_n,
            BLOCK_K=32,
            SCALE_BLOCK=128,
            num_warps=4,
        )
        return candidate_out

    changed_rows = []
    for epoch in range(40):
        torch.manual_seed(20260715 + epoch)
        x.copy_(torch.randn_like(x).mul_(0.125 * (1 + epoch % 8)))
        expected = reference()
        got = candidate()
        torch.xpu.synchronize()
        changed_rows.append(
            {
                "epoch": epoch,
                "mismatch_elements": int(
                    torch.count_nonzero(expected != got).item()
                ),
                "max_abs_difference": float(
                    (expected.float() - got.float()).abs().max().item()
                ),
                "mean_abs_difference": float(
                    (expected.float() - got.float()).abs().mean().item()
                ),
            }
        )

    for _ in range(args.warmup):
        reference()
        candidate()
    torch.xpu.synchronize()

    def timed_us(call) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            call()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    reference_us = []
    candidate_us = []
    for batch in range(args.batches):
        if batch % 2 == 0:
            reference_us.append(timed_us(reference))
            candidate_us.append(timed_us(candidate))
        else:
            candidate_us.append(timed_us(candidate))
            reference_us.append(timed_us(reference))

    reference_median = statistics.median(reference_us)
    candidate_median = statistics.median(candidate_us)
    result = {
        "schema_version": 1,
        "device": args.device,
        "shape": {"m": 1, "k": args.k, "n": args.n},
        "weight_dtype": "float8_e4m3fn",
        "activation_dtype": "bfloat16",
        "scale_shape": list(scales.shape),
        "geometry": {
            "block_m": 16,
            "block_n": args.block_n,
            "block_k": 32,
            "num_warps": 4,
        },
        "changed_input_gate": {
            "epochs": len(changed_rows),
            "exact_epochs": sum(r["mismatch_elements"] == 0 for r in changed_rows),
            "total_mismatch_elements": sum(
                r["mismatch_elements"] for r in changed_rows
            ),
            "maximum_abs_difference": max(
                r["max_abs_difference"] for r in changed_rows
            ),
            "maximum_mean_abs_difference": max(
                r["mean_abs_difference"] for r in changed_rows
            ),
            "rows": changed_rows,
        },
        "reference_us": {"median": reference_median, "samples": reference_us},
        "candidate_us": {"median": candidate_median, "samples": candidate_us},
        "speedup": reference_median / candidate_median,
        "projected_projection_only_saved_ms_per_token": (
            (reference_median - candidate_median) * args.layers / 1000.0
        ),
        "interpretation": (
            "Feasibility only. Promotion additionally requires an exact fused "
            "per-head normalization/RoPE epilogue and direct KV insertion."
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
