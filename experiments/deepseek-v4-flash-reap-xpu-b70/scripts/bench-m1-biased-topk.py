#!/usr/bin/env python3
"""Bounded M=1 DeepSeek-V4 biased top-k hardware gate."""

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
    parser.add_argument("--experts", type=int, default=160)
    parser.add_argument("--topk", type=int, default=6)
    parser.add_argument("--layers", type=int, default=40)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--batches", type=int, default=10)
    parser.add_argument("--batch-iterations", type=int, default=200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    torch.manual_seed(20260715)
    device = torch.device(args.device)
    current_platform.import_kernels()

    scores = torch.empty((1, args.experts), dtype=torch.float32, device=device)
    bias = torch.randn((args.experts,), dtype=torch.float32, device=device)
    bias.mul_(0.02).add_(8.08)
    candidate_weights = torch.empty(
        (1, args.topk), dtype=torch.float32, device=device
    )
    candidate_ids = torch.empty(
        (1, args.topk), dtype=torch.int32, device=device
    )

    def reference() -> tuple[torch.Tensor, torch.Tensor]:
        _, ids = torch.topk(scores + bias, k=args.topk, dim=-1, sorted=True)
        return scores.gather(1, ids), ids.to(torch.int32)

    def candidate() -> tuple[torch.Tensor, torch.Tensor]:
        torch.ops._xpu_C.deepseek_m1_biased_topk_out(
            candidate_weights, candidate_ids, scores, bias
        )
        return candidate_weights, candidate_ids

    changed_rows = []
    for epoch in range(args.epochs):
        generator = torch.Generator(device=device)
        generator.manual_seed(20260715 + epoch)
        scores.copy_(
            torch.randn(
                scores.shape,
                dtype=scores.dtype,
                device=device,
                generator=generator,
            )
            * (0.25 + 0.125 * (epoch % 7))
        )
        expected_weights, expected_ids = reference()
        got_weights, got_ids = candidate()
        torch.xpu.synchronize()
        changed_rows.append(
            {
                "epoch": epoch,
                "id_mismatches": int(
                    torch.count_nonzero(expected_ids != got_ids).item()
                ),
                "weight_mismatches": int(
                    torch.count_nonzero(expected_weights != got_weights).item()
                ),
                "max_abs_weight_difference": float(
                    (expected_weights - got_weights).abs().max().item()
                ),
            }
        )

    def timed_us(call) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            call()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    for _ in range(args.warmup):
        reference()
        candidate()
    torch.xpu.synchronize()

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
    projected_saved_ms = (
        (reference_median - candidate_median) * args.layers / 1000.0
    )
    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_m1_biased_topk_microgate",
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "shape": {"m": 1, "experts": args.experts, "topk": args.topk},
        "changed_input_gate": {
            "epochs": args.epochs,
            "exact_id_epochs": sum(r["id_mismatches"] == 0 for r in changed_rows),
            "exact_weight_epochs": sum(
                r["weight_mismatches"] == 0 for r in changed_rows
            ),
            "total_id_mismatches": sum(r["id_mismatches"] for r in changed_rows),
            "total_weight_mismatches": sum(
                r["weight_mismatches"] for r in changed_rows
            ),
            "maximum_abs_weight_difference": max(
                r["max_abs_weight_difference"] for r in changed_rows
            ),
        },
        "timing": {
            "warmup": args.warmup,
            "batches": args.batches,
            "batch_iterations": args.batch_iterations,
            "reference_us": {
                "median": reference_median,
                "samples": reference_us,
            },
            "candidate_us": {
                "median": candidate_median,
                "samples": candidate_us,
            },
            "speedup": reference_median / candidate_median,
            "projected_saved_ms_per_token": projected_saved_ms,
        },
        "gate": {
            "minimum_projected_saved_ms_per_token": 0.5,
            "requires_bitwise_ids": True,
            "requires_bitwise_raw_weights": True,
            "passes": (
                all(r["id_mismatches"] == 0 for r in changed_rows)
                and all(r["weight_mismatches"] == 0 for r in changed_rows)
                and projected_saved_ms >= 0.5
            ),
            "scope": (
                "Bias + sorted top-k + unbiased-score gather only; existing "
                "sqrt-softplus and normalization remain unchanged."
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
