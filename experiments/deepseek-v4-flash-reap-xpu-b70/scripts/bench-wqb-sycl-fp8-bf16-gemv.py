#!/usr/bin/env python3
"""Bounded geometry gate for the native Xe2 M=1 WQ_B FP8 GEMV proof."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

from vllm.platforms import current_platform


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--k", type=int, default=1024)
    parser.add_argument("--n", type=int, default=8192)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--batches", type=int, default=8)
    parser.add_argument("--batch-iterations", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--layers", type=int, default=43)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    torch.manual_seed(20260715)
    device = torch.device(args.device)
    current_platform.import_kernels()

    x = torch.randn((1, args.k), dtype=torch.bfloat16, device=device)
    weight = torch.randn(
        (args.n, args.k), dtype=torch.float32, device=device
    ).to(torch.float8_e4m3fn)
    scales = (
        torch.rand(
            (args.k // 128, args.n // 128),
            dtype=torch.float32,
            device=device,
        )
        * 0.02
        + 0.002
    )
    candidate_out = torch.empty(
        (1, args.n), dtype=torch.bfloat16, device=device
    )

    def reference() -> torch.Tensor:
        return torch.ops._xpu_C.fp8_gemm_w8a16(x, weight.t(), scales, None)

    def candidate(outputs_per_sg: int, local_size: int) -> torch.Tensor:
        torch.ops._xpu_C.deepseek_wqb_m1_fp8_gemv_out(
            candidate_out,
            x,
            weight,
            scales,
            outputs_per_sg,
            local_size,
        )
        return candidate_out

    def timed_us(call) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            call()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    variants = [
        (outputs_per_sg, local_size)
        for outputs_per_sg in (1, 2, 4, 8)
        for local_size in (128, 256, 512)
    ]
    results = []
    for outputs_per_sg, local_size in variants:
        changed_rows = []
        for epoch in range(args.epochs):
            torch.manual_seed(20260715 + epoch)
            x.copy_(torch.randn_like(x).mul_(0.125 * (1 + epoch % 8)))
            expected = reference()
            got = candidate(outputs_per_sg, local_size)
            torch.xpu.synchronize()
            diff = (expected.float() - got.float()).abs()
            changed_rows.append(
                {
                    "epoch": epoch,
                    "mismatch_elements": int(
                        torch.count_nonzero(expected != got).item()
                    ),
                    "max_abs_difference": float(diff.max().item()),
                    "mean_abs_difference": float(diff.mean().item()),
                }
            )

        for _ in range(args.warmup):
            reference()
            candidate(outputs_per_sg, local_size)
        torch.xpu.synchronize()

        reference_us = []
        candidate_us = []
        for batch in range(args.batches):
            if batch % 2 == 0:
                reference_us.append(timed_us(reference))
                candidate_us.append(
                    timed_us(lambda: candidate(outputs_per_sg, local_size))
                )
            else:
                candidate_us.append(
                    timed_us(lambda: candidate(outputs_per_sg, local_size))
                )
                reference_us.append(timed_us(reference))

        reference_median = statistics.median(reference_us)
        candidate_median = statistics.median(candidate_us)
        results.append(
            {
                "geometry": {
                    "outputs_per_subgroup": outputs_per_sg,
                    "local_size": local_size,
                    "subgroup_size": 16,
                },
                "changed_input_gate": {
                    "epochs": len(changed_rows),
                    "exact_epochs": sum(
                        r["mismatch_elements"] == 0 for r in changed_rows
                    ),
                    "total_mismatch_elements": sum(
                        r["mismatch_elements"] for r in changed_rows
                    ),
                    "maximum_abs_difference": max(
                        r["max_abs_difference"] for r in changed_rows
                    ),
                    "maximum_mean_abs_difference": max(
                        r["mean_abs_difference"] for r in changed_rows
                    ),
                },
                "reference_us": {
                    "median": reference_median,
                    "samples": reference_us,
                },
                "candidate_us": {
                    "median": candidate_median,
                    "samples": candidate_us,
                },
                "speedup": reference_median / candidate_median,
                "projected_projection_only_saved_ms_per_token": (
                    (reference_median - candidate_median)
                    * args.layers
                    / 1000.0
                ),
            }
        )

    result = {
        "schema_version": 1,
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "shape": {"m": 1, "k": args.k, "n": args.n},
        "weight_dtype": "float8_e4m3fn",
        "activation_dtype": "bfloat16",
        "scale_shape": list(scales.shape),
        "timing": {
            "warmup": args.warmup,
            "batches": args.batches,
            "batch_iterations": args.batch_iterations,
        },
        "variants": results,
        "best_by_latency": min(
            results, key=lambda row: row["candidate_us"]["median"]
        ),
        "gate": {
            "projection_latency_target_us": 35.0,
            "promotion_requires_bitwise_exactness": True,
            "interpretation": (
                "Projection feasibility only. Model integration is forbidden "
                "unless a successor also fuses per-head Q RMSNorm/RoPE and "
                "direct FP8 KV insertion while preserving the strict gates."
            ),
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
