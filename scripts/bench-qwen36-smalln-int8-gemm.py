#!/usr/bin/env python3
"""Direct microbench for the Qwen3.6 XPU W8A8 small-N GEMM candidate."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-prefix", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--reps", type=int, default=300)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sys.path.insert(0, args.candidate_prefix)

    import torch
    import vllm_xpu_kernels._xpu_C as xpu_c  # noqa: F401

    torch.manual_seed(1234)
    device = args.device

    def sync() -> None:
        torch.xpu.synchronize()

    def timed(fn, reps: int | None = None) -> float:
        actual_reps = args.reps if reps is None else reps
        for _ in range(args.warmup):
            fn()
        sync()
        t0 = time.perf_counter()
        for _ in range(actual_reps):
            fn()
        sync()
        return (time.perf_counter() - t0) * 1e6 / actual_reps

    def make_inputs(m: int, k: int, n: int) -> tuple[Any, ...]:
        x = torch.randn((m, k), device=device, dtype=torch.bfloat16)
        q, s = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
        b = torch.randint(-127, 128, (k, n), device=device, dtype=torch.int8)
        bs = torch.rand((n,), device=device, dtype=torch.float32) * 0.01
        sync()
        return q, s, b, bs

    records: list[dict[str, Any]] = []
    for m in (1, 2, 8, 18, 64):
        for n in (16, 2048):
            q, s, b, bs = make_inputs(m, 2048, n)

            os.environ["VLLM_XPU_INT8_GEMM_SMALL_N"] = "0"
            baseline = torch.ops._xpu_C.int8_gemm_w8a8(
                q, s, b, bs, torch.bfloat16, None
            )
            sync()
            baseline_us = timed(
                lambda: torch.ops._xpu_C.int8_gemm_w8a8(
                    q, s, b, bs, torch.bfloat16, None
                ),
                reps=max(60, args.reps // 2) if m == 64 else None,
            )

            os.environ["VLLM_XPU_INT8_GEMM_SMALL_N"] = "1"
            candidate = torch.ops._xpu_C.int8_gemm_w8a8(
                q, s, b, bs, torch.bfloat16, None
            )
            sync()
            candidate_us = timed(
                lambda: torch.ops._xpu_C.int8_gemm_w8a8(
                    q, s, b, bs, torch.bfloat16, None
                ),
                reps=max(60, args.reps // 2) if m == 64 else None,
            )

            diff = (baseline.float() - candidate.float()).abs()
            records.append(
                {
                    "m": m,
                    "k": 2048,
                    "n": n,
                    "baseline_us": baseline_us,
                    "candidate_us": candidate_us,
                    "speedup": baseline_us / candidate_us
                    if candidate_us > 0
                    else None,
                    "exact": bool(torch.equal(baseline, candidate)),
                    "max_abs_diff": float(diff.max().item()),
                    "nonzero_diff": int((diff != 0).sum().item()),
                }
            )

    out = {
        "candidate_prefix": args.candidate_prefix,
        "candidate_module": getattr(xpu_c, "__file__", None),
        "env": {
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
        },
        "records": records,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
