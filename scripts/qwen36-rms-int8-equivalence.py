#!/usr/bin/env python3
"""Compare fused RMSNorm+INT8 quant against the unfused XPU reference path."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

import vllm_xpu_kernels._C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401


def ref_rms_quant(
    x: torch.Tensor,
    weight: torch.Tensor,
    eps: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    x32 = x.to(torch.float32)
    variance = x32.pow(2).mean(dim=-1, keepdim=True)
    y = x32 * torch.rsqrt(variance + eps)
    y = (y.to(weight.dtype) * weight).to(x.dtype).contiguous()
    return torch.ops._xpu_C.per_token_quant_int8_xpu(y)


def compare_rows(rows: int, hidden_size: int, eps: float) -> dict[str, object]:
    torch.manual_seed(1000 + rows)
    x = torch.randn(rows, hidden_size, device="xpu", dtype=torch.bfloat16)
    weight = torch.randn(hidden_size, device="xpu", dtype=torch.float32) * 0.2 + 1.0

    q_ref, s_ref = ref_rms_quant(x, weight, eps)
    q_new = torch.empty_like(q_ref)
    s_new = torch.empty_like(s_ref)
    torch.ops._C.rms_norm_dynamic_per_token_quant(
        q_new, x.contiguous(), weight, s_new, eps, None, None
    )
    torch.xpu.synchronize()

    diff = (q_ref.cpu().to(torch.int16) - q_new.cpu().to(torch.int16)).abs()
    scale_abs = (s_ref.cpu() - s_new.cpu()).abs()
    return {
        "rows": rows,
        "q_exact": bool((diff == 0).all().item()),
        "q_match_pct": float((diff == 0).float().mean().item() * 100),
        "q_max_abs_diff": int(diff.max().item()),
        "q_nonzero": int((diff != 0).sum().item()),
        "scale_max_abs_diff": float(scale_abs.max().item()),
        "scale_mean_abs_diff": float(scale_abs.mean().item()),
    }


def time_path(rows: int, hidden_size: int, eps: float, iters: int) -> dict[str, object]:
    torch.manual_seed(9000 + rows)
    x = torch.randn(rows, hidden_size, device="xpu", dtype=torch.bfloat16)
    weight = torch.randn(hidden_size, device="xpu", dtype=torch.float32) * 0.2 + 1.0
    q = torch.empty((rows, hidden_size), device="xpu", dtype=torch.int8)
    s = torch.empty((rows, 1), device="xpu", dtype=torch.float32)

    for _ in range(20):
        torch.ops._C.rms_norm_dynamic_per_token_quant(
            q, x.contiguous(), weight, s, eps, None, None
        )
    torch.xpu.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        torch.ops._C.rms_norm_dynamic_per_token_quant(
            q, x.contiguous(), weight, s, eps, None, None
        )
    torch.xpu.synchronize()
    fused_ms = (time.perf_counter() - t0) * 1000 / iters

    for _ in range(20):
        ref_rms_quant(x, weight, eps)
    torch.xpu.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_rms_quant(x, weight, eps)
    torch.xpu.synchronize()
    ref_ms = (time.perf_counter() - t0) * 1000 / iters

    return {
        "micro_rows": rows,
        "fused_ms": fused_ms,
        "reference_ms": ref_ms,
        "speedup": ref_ms / fused_ms if fused_ms else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--hidden-size", type=int, default=2048)
    parser.add_argument("--eps", type=float, default=1e-6)
    parser.add_argument("--rows", type=int, nargs="+", default=[1, 2, 4, 18, 32, 128, 257])
    parser.add_argument("--timing-rows", type=int, default=18)
    parser.add_argument("--timing-iters", type=int, default=200)
    args = parser.parse_args()

    result = {
        "torch": torch.__version__,
        "xpu_device_count": torch.xpu.device_count(),
        "hidden_size": args.hidden_size,
        "eps": args.eps,
        "comparisons": [
            compare_rows(rows, args.hidden_size, args.eps) for rows in args.rows
        ],
        "timing": time_path(args.timing_rows, args.hidden_size, args.eps, args.timing_iters),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
