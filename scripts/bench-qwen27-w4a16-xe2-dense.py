#!/usr/bin/env python3
"""Compare oneDNN and Xe2 DPAS W4A16 kernels at Qwen27 decode shapes.

This is a synthetic kernel diagnostic, not an endpoint or LocalMaxxing result.
The Xe2 grouped-MoE kernel is exercised as a one-expert dense GEMM after a
one-time conversion from AutoRound's zero-point-8 uint4 representation to the
kernel's two's-complement int4 representation.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


GROUP_SIZE = 128
PROJECTIONS = (
    ("gdn_qkvz", 5120, 16384, 48),
    ("gdn_out", 6144, 5120, 48),
    ("mlp_gateup", 5120, 34816, 64),
    ("mlp_down", 17408, 5120, 64),
    ("full_attention_qkvgate", 5120, 14336, 16),
    ("full_attention_out", 6144, 5120, 16),
)


def parse_rows(value: str) -> list[int]:
    rows = [int(item) for item in value.split(",") if item.strip()]
    if not rows or any(row <= 0 for row in rows):
        raise argparse.ArgumentTypeError("rows must be positive integers")
    return rows


def summary(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)

    def pct(q: float) -> float:
        pos = (len(ordered) - 1) * q
        lo = int(pos)
        hi = min(lo + 1, len(ordered) - 1)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)

    return {
        "count": len(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "p10": pct(0.10),
        "p90": pct(0.90),
        "min": min(values),
        "max": max(values),
    }


def measure(torch, operation, warmup: int, iterations: int, calls: int):
    for _ in range(warmup):
        operation()
    torch.xpu.synchronize()
    event_ms: list[float] = []
    wall_ms: list[float] = []
    for _ in range(iterations):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        wall_start = time.perf_counter_ns()
        start.record()
        for _ in range(calls):
            operation()
        end.record()
        end.synchronize()
        event_ms.append(float(start.elapsed_time(end)) / calls)
        wall_ms.append((time.perf_counter_ns() - wall_start) / 1e6 / calls)
    return {"xpu_event_ms": summary(event_ms), "wall_ms": summary(wall_ms)}


def to_signed_int4(packed_u4):
    # AutoRound stores q in [0,15] with zero point 8. CUTLASS int4_t uses
    # ordinary two's-complement nibbles, so (q - 8) is encoded by toggling the
    # sign bit of each nibble. This is a one-time weight-load conversion.
    return (packed_u4 ^ 0x88).contiguous()


def run_case(torch, dense_op, xe2_op, name, k, n, rows, args, seed):
    device = args.device
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)
    packed_u4 = torch.randint(
        0, 256, (n, k // 2), dtype=torch.uint8, device=device, generator=generator
    ).contiguous()
    # AutoRound/INC exposes contiguous [N,K/8] int32 backing as [K/8,N]
    # with stride (1,K/8) to oneDNN.
    dense_weight = packed_u4.view(torch.int32).t()
    scales = (
        torch.rand(
            (k // GROUP_SIZE, n),
            dtype=torch.bfloat16,
            device=device,
            generator=generator,
        )
        * 0.02
        + 0.001
    ).contiguous()
    zero = torch.tensor([8], dtype=torch.int8, device=device)
    xe2_weight = to_signed_int4(packed_u4).unsqueeze(0)
    xe2_scales = scales.t().unsqueeze(0).contiguous()

    row_results = []
    for row_count in rows:
        hidden = torch.randn(
            (row_count, k),
            dtype=torch.bfloat16,
            device=device,
            generator=generator,
        ).contiguous()
        xe2_output = torch.empty(
            (row_count, n), dtype=torch.bfloat16, device=device
        )
        rows_per_expert = torch.tensor(
            [row_count], dtype=torch.int32, device=device
        )

        def dense():
            return dense_op(
                hidden, dense_weight, None, scales, zero, GROUP_SIZE, None
            )

        def xe2():
            return xe2_op(
                hidden,
                xe2_weight,
                xe2_scales,
                None,
                xe2_output,
                rows_per_expert,
                n,
                k,
                1,
                True,
                False,
            )

        dense_result = dense()
        xe2_result = xe2()
        torch.xpu.synchronize()
        diff = (dense_result.float() - xe2_result.float()).abs()
        dense_timing = measure(
            torch, dense, args.warmup, args.iterations, args.calls_per_sample
        )
        xe2_timing = measure(
            torch, xe2, args.warmup, args.iterations, args.calls_per_sample
        )
        dense_median = dense_timing["xpu_event_ms"]["median"]
        xe2_median = xe2_timing["xpu_event_ms"]["median"]
        row_results.append(
            {
                "rows": row_count,
                "dense": dense_timing,
                "xe2": xe2_timing,
                "speedup": dense_median / xe2_median,
                "delta_ms": xe2_median - dense_median,
                "comparison": {
                    "max_abs": float(diff.max().item()),
                    "mean_abs": float(diff.mean().item()),
                    "dense_max_abs": float(dense_result.float().abs().max().item()),
                    "all_finite": bool(
                        torch.isfinite(dense_result).all().item()
                        and torch.isfinite(xe2_result).all().item()
                    ),
                },
            }
        )
    return {
        "name": name,
        "k": k,
        "n": n,
        "calls_per_target_step": args_projection_calls(name),
        "rows": row_results,
    }


def args_projection_calls(name: str) -> int:
    return next(calls for item, _, _, calls in PROJECTIONS if item == name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=parse_rows, default=[4, 16])
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=40)
    parser.add_argument("--calls-per-sample", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument(
        "--kernel-prefix", default="/home/steve/src/vllm-xpu-kernels"
    )
    parser.add_argument("--output-json")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(args.kernel_prefix).resolve()))
    import torch

    extension = importlib.import_module("vllm_xpu_kernels._xpu_C")
    dense_op = torch.ops._xpu_C.int4_gemm_w4a16
    xe2_op = torch.ops._xpu_C.cutlass_grouped_gemm_interface
    torch.xpu.set_device(torch.device(args.device))

    results = []
    for index, projection in enumerate(PROJECTIONS):
        name, k, n, _ = projection
        print(f"[{index + 1}/{len(PROJECTIONS)}] {name}", file=sys.stderr)
        results.append(
            run_case(
                torch,
                dense_op,
                xe2_op,
                name,
                k,
                n,
                args.rows,
                args,
                args.seed + index * 1009,
            )
        )

    projected = []
    for row_count in args.rows:
        dense_ms = 0.0
        xe2_ms = 0.0
        for projection in results:
            row = next(item for item in projection["rows"] if item["rows"] == row_count)
            calls = projection["calls_per_target_step"]
            dense_ms += row["dense"]["xpu_event_ms"]["median"] * calls
            xe2_ms += row["xe2"]["xpu_event_ms"]["median"] * calls
        projected.append(
            {
                "rows": row_count,
                "dense_projected_ms": dense_ms,
                "xe2_projected_ms": xe2_ms,
                "delta_ms": xe2_ms - dense_ms,
                "speedup": dense_ms / xe2_ms,
            }
        )

    document = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "diagnostic_microbenchmark_not_endpoint_not_localmaxxing",
        "purpose": "Test Xe2 DPAS grouped W4A16 as a one-expert dense Qwen27 kernel",
        "runtime": {
            "torch": torch.__version__,
            "extension": str(Path(extension.__file__).resolve()),
            "device": args.device,
            "xe2_m16_n_tile": os.environ.get("VLLM_XPU_W4A16_M16_N_TILE", "64"),
        },
        "arguments": vars(args),
        "results": results,
        "projected_target_step": projected,
    }
    payload = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        output = Path(args.output_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
