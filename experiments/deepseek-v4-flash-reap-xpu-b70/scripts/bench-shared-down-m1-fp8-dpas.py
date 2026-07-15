#!/usr/bin/env python3
"""Bounded exact/latency gate for the DeepSeek V4 M=1 shared-down DPAS path."""

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
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--batches", type=int, default=10)
    parser.add_argument("--batch-iterations", type=int, default=200)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--layers", type=int, default=43)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    torch.manual_seed(20260715)
    device = torch.device(args.device)
    current_platform.import_kernels()

    m, n, k = 1, 4096, 512
    activation = torch.randn((m, k), device=device).to(torch.float8_e4m3fn)
    activation_scales = (
        torch.rand((m, k // 128), device=device, dtype=torch.float32) * 0.02
        + 0.002
    )
    weight_nk = torch.randn((n, k), device=device).to(torch.float8_e4m3fn)
    packed_weight = weight_nk.t().contiguous()
    weight_scales = (
        torch.rand((k // 128, n // 128), device=device, dtype=torch.float32)
        * 0.02
        + 0.002
    )
    output = torch.empty((m, n), device=device, dtype=torch.bfloat16)
    empty_bias = torch.Tensor()

    def reference() -> torch.Tensor:
        return torch.ops._xpu_C.fp8_gemm(
            activation,
            weight_nk.t(),
            torch.bfloat16,
            activation_scales,
            weight_scales,
            empty_bias,
        )

    def candidate(tiles_per_item: int) -> torch.Tensor:
        torch.ops._xpu_C.deepseek_shared_down_m1_fp8_dpas_out(
            output,
            activation,
            activation_scales,
            packed_weight,
            weight_scales,
            tiles_per_item,
        )
        return output

    def timed_us(call) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            call()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    variants = []
    for tiles_per_item in (1, 2, 4, 8):
        changed_rows = []
        for epoch in range(args.epochs):
            torch.manual_seed(20260715 + epoch)
            activation.copy_(
                torch.randn_like(activation.float())
                .mul_(0.125 * (1 + epoch % 8))
                .to(torch.float8_e4m3fn)
            )
            activation_scales.copy_(
                torch.rand_like(activation_scales).mul_(0.02).add_(0.002)
            )
            expected = reference()
            got = candidate(tiles_per_item)
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
            candidate(tiles_per_item)
        torch.xpu.synchronize()

        reference_us = []
        candidate_us = []
        for batch in range(args.batches):
            if batch % 2 == 0:
                reference_us.append(timed_us(reference))
                candidate_us.append(
                    timed_us(lambda: candidate(tiles_per_item))
                )
            else:
                candidate_us.append(
                    timed_us(lambda: candidate(tiles_per_item))
                )
                reference_us.append(timed_us(reference))

        reference_median = statistics.median(reference_us)
        candidate_median = statistics.median(candidate_us)
        variants.append(
            {
                "tiles_per_item": tiles_per_item,
                "changed_input_gate": {
                    "epochs": args.epochs,
                    "exact_epochs": sum(
                        row["mismatch_elements"] == 0 for row in changed_rows
                    ),
                    "total_mismatch_elements": sum(
                        row["mismatch_elements"] for row in changed_rows
                    ),
                    "maximum_abs_difference": max(
                        row["max_abs_difference"] for row in changed_rows
                    ),
                    "maximum_mean_abs_difference": max(
                        row["mean_abs_difference"] for row in changed_rows
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
                "candidate_effective_weight_gb_s": (
                    n * k / candidate_median / 1000.0
                ),
                "projected_saved_ms_per_token": (
                    (reference_median - candidate_median) * args.layers / 1000.0
                ),
            }
        )

    best = min(variants, key=lambda row: row["candidate_us"]["median"])
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_shared_down_m1_fp8_dpas_microgate",
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "shape": {"m": m, "n": n, "k": k},
        "layout": {
            "activation": "contiguous [1,K] float8_e4m3fn",
            "packed_weight": "one-time contiguous transpose [K,N]",
            "activation_scales": "FP32 [1,K/128]",
            "weight_scales": "FP32 [K/128,N/128]",
            "output": "BF16 [1,N]",
        },
        "timing": {
            "warmup": args.warmup,
            "batches": args.batches,
            "batch_iterations": args.batch_iterations,
        },
        "variants": variants,
        "best_by_latency": best,
        "gate": {
            "minimum_projected_saved_ms_per_token": 0.5,
            "requires_bitwise_output": True,
            "passes": (
                best["changed_input_gate"]["exact_epochs"] == args.epochs
                and best["projected_saved_ms_per_token"] >= 0.5
            ),
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0 if result["gate"]["passes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
