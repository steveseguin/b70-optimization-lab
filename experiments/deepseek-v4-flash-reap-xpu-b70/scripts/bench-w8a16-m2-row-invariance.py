#!/usr/bin/env python3
"""Verify oneDNN W8A16 row invariance at production verifier widths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

import torch

from vllm.platforms import current_platform


SHAPES = ((1536, 4096), (8192, 1024), (4096, 2048), (1024, 4096))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--width", type=int, choices=(2, 4, 8), default=2)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=40)
    parser.add_argument("--batches", type=int, default=8)
    parser.add_argument("--batch-iterations", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    torch.xpu.set_device(args.device)
    device = torch.device(args.device)
    current_platform.import_kernels()
    rows = []

    def timed_us(call) -> float:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(args.batch_iterations):
            call()
        end.record()
        end.synchronize()
        return start.elapsed_time(end) * 1000.0 / args.batch_iterations

    for shape_index, (n, k) in enumerate(SHAPES):
        torch.manual_seed(20260715 + shape_index)
        x = torch.randn((args.width, k), device=device, dtype=torch.bfloat16)
        weight = torch.randn((n, k), device=device, dtype=torch.float32).to(
            torch.float8_e4m3fn
        )
        scales = (
            torch.rand(
                (k // 128, n // 128), device=device, dtype=torch.float32
            )
            * 0.02
            + 0.002
        )

        mismatch_elements = 0
        max_abs_difference = 0.0
        exact_epochs = 0
        for epoch in range(args.epochs):
            torch.manual_seed(20260715 + shape_index * 1000 + epoch)
            x.copy_(torch.randn_like(x).mul_(0.125 * (1 + epoch % 8)))
            separate = torch.cat(
                [
                    torch.ops._xpu_C.fp8_gemm_w8a16(
                        x[row : row + 1], weight.t(), scales, None
                    )
                    for row in range(args.width)
                ],
                dim=0,
            )
            together = torch.ops._xpu_C.fp8_gemm_w8a16(
                x, weight.t(), scales, None
            )
            torch.xpu.synchronize()
            diff = (separate.float() - together.float()).abs()
            mismatches = int(torch.count_nonzero(separate != together).item())
            mismatch_elements += mismatches
            max_abs_difference = max(
                max_abs_difference, float(diff.max().item())
            )
            exact_epochs += mismatches == 0

        def sequential_m1() -> None:
            for row in range(args.width):
                torch.ops._xpu_C.fp8_gemm_w8a16(
                    x[row : row + 1], weight.t(), scales, None
                )

        def batched() -> None:
            torch.ops._xpu_C.fp8_gemm_w8a16(x, weight.t(), scales, None)

        for _ in range(args.warmup):
            sequential_m1()
            batched()
        torch.xpu.synchronize()
        sequential_m1_us = []
        batched_us = []
        for batch in range(args.batches):
            if batch % 2 == 0:
                sequential_m1_us.append(timed_us(sequential_m1))
                batched_us.append(timed_us(batched))
            else:
                batched_us.append(timed_us(batched))
                sequential_m1_us.append(timed_us(sequential_m1))

        rows.append(
            {
                "shape": {"m": args.width, "n": n, "k": k},
                "exact_epochs": exact_epochs,
                "epochs": args.epochs,
                "mismatch_elements": mismatch_elements,
                "maximum_abs_difference": max_abs_difference,
                "sequential_m1_calls_us": {
                    "median": statistics.median(sequential_m1_us),
                    "samples": sequential_m1_us,
                },
                "one_batched_call_us": {
                    "median": statistics.median(batched_us),
                    "samples": batched_us,
                },
                "batched_speedup_over_sequential_m1": (
                    statistics.median(sequential_m1_us)
                    / statistics.median(batched_us)
                ),
            }
        )

    result = {
        "schema_version": 1,
        "device": args.device,
        "device_name": torch.xpu.get_device_name(device),
        "torch_version": torch.__version__,
        "rows": rows,
        "gate": {
            "passed": all(
                row["exact_epochs"] == row["epochs"] for row in rows
            ),
            "purpose": (
                f"Allow the selective target W8A16 path at M={args.width} so "
                "target "
                "verification uses the same projection arithmetic as M=1."
            ),
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    return 0 if result["gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
