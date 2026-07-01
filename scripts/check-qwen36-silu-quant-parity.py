#!/usr/bin/env python3
"""Check XPU fused SiLU+INT8 quant against captured Qwen3.6 MoE windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

import vllm_xpu_kernels._moe_C  # noqa: F401
import vllm_xpu_kernels._xpu_C  # noqa: F401
from vllm_xpu_kernels.fused_moe_interface import fused_moe_activation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--multiwindow-dir",
        default=(
            "data/qwen36-onednn-moe-island-layer9-r1-multiwindow-"
            "20260612bc"
        ),
    )
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--device", default="xpu")
    parser.add_argument(
        "--source",
        choices=("xpu", "onednn"),
        default="xpu",
        help="Use captured XPU GEMM1 output or captured oneDNN GEMM1 output.",
    )
    return parser.parse_args()


def read_meta(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def load_bf16(path: Path, shape: tuple[int, ...], device: str) -> torch.Tensor:
    raw = np.fromfile(path, dtype=np.uint16)
    tensor = torch.from_numpy(raw.copy()).view(torch.bfloat16).view(*shape)
    return tensor.to(device)


def load_int8(path: Path, shape: tuple[int, ...]) -> torch.Tensor:
    raw = np.fromfile(path, dtype=np.int8)
    return torch.from_numpy(raw.copy()).view(*shape)


def load_f32(path: Path, shape: tuple[int, ...]) -> torch.Tensor:
    raw = np.fromfile(path, dtype=np.float32)
    return torch.from_numpy(raw.copy()).view(*shape)


def summarize_tensor_diff(left: torch.Tensor,
                          right: torch.Tensor) -> dict[str, Any]:
    if left.shape != right.shape:
        raise ValueError(f"shape mismatch: {left.shape} vs {right.shape}")
    l = left.detach().cpu()
    r = right.detach().cpu()
    if l.dtype == torch.int8:
        diff = (l != r)
        return {
            "numel": int(l.numel()),
            "raw_equal": bool(not diff.any().item()),
            "raw_diff_count": int(diff.sum().item()),
            "max_abs_diff": int((l.to(torch.int16) -
                                 r.to(torch.int16)).abs().max().item())
            if l.numel() else 0,
        }
    abs_diff = (l.float() - r.float()).abs()
    return {
        "numel": int(l.numel()),
        "raw_equal": bool(torch.equal(l, r)),
        "raw_diff_count": int((l != r).sum().item()),
        "max_abs_diff": float(abs_diff.max().item()) if l.numel() else 0.0,
        "mean_abs_diff": float(abs_diff.mean().item()) if l.numel() else 0.0,
    }


def main() -> int:
    args = parse_args()
    root = Path(args.multiwindow_dir)
    windows = sorted(root.glob("window_*"))
    if not windows:
        raise SystemExit(f"No window_* directories under {root}")

    has_fused_out = hasattr(torch.ops._xpu_C,
                            "silu_and_mul_quant_int8_xpu_out")
    if not has_fused_out and not hasattr(torch.ops._xpu_C,
                                         "silu_and_mul_quant_int8_xpu"):
        raise RuntimeError("Missing _xpu_C.silu_and_mul_quant_int8_xpu")

    results: list[dict[str, Any]] = []
    for window in windows:
        gemm1_meta = read_meta(window / "gemm1.meta")
        gemm2_meta = read_meta(window / "gemm2.meta")
        rows = int(gemm1_meta["total_tokens"])
        gemm1_n = int(gemm1_meta["n"])
        gemm2_k = int(gemm2_meta["k"])
        if gemm1_n != 2 * gemm2_k:
            raise ValueError(f"Unexpected GEMM dimensions in {window}")

        if args.source == "xpu":
            gemm1_path = window / gemm1_meta["xpu_out_path"]
        else:
            gemm1_path = window / "gemm1_onednn_acb_out.bf16.bin"
        gemm1 = load_bf16(gemm1_path, (rows, gemm1_n), args.device)
        expected_q = load_int8(window / gemm2_meta["a_path"],
                               (rows, gemm2_k))
        expected_scales = load_f32(window / gemm2_meta["a_scales_path"],
                                   (rows, 1))

        if has_fused_out:
            q = torch.empty((rows, gemm2_k),
                            device=args.device,
                            dtype=torch.int8)
            scales = torch.empty((rows, 1),
                                 device=args.device,
                                 dtype=torch.float32)
            torch.ops._xpu_C.silu_and_mul_quant_int8_xpu_out(
                gemm1, q, scales)
        else:
            q, scales = torch.ops._xpu_C.silu_and_mul_quant_int8_xpu(gemm1)
        torch.xpu.synchronize()

        # Also compare against the current two-step path to separate fused-kernel
        # drift from captured-fixture drift.
        act = torch.empty((rows, gemm2_k),
                          device=args.device,
                          dtype=torch.bfloat16)
        fused_moe_activation(act, gemm1, "silu")
        q2, scales2 = torch.ops._xpu_C.per_token_quant_int8_xpu(act)
        torch.xpu.synchronize()

        fused_q_diff = summarize_tensor_diff(q, expected_q)
        fused_scale_diff = summarize_tensor_diff(scales, expected_scales)
        twostep_q_diff = summarize_tensor_diff(q2, expected_q)
        twostep_scale_diff = summarize_tensor_diff(scales2, expected_scales)
        fused_vs_twostep_q_diff = summarize_tensor_diff(q, q2)
        fused_vs_twostep_scale_diff = summarize_tensor_diff(scales, scales2)
        results.append({
            "window": window.name,
            "source": args.source,
            "fused_op": "silu_and_mul_quant_int8_xpu_out"
            if has_fused_out else "silu_and_mul_quant_int8_xpu",
            "gemm1_path": str(gemm1_path),
            "rows": rows,
            "gemm1_n": gemm1_n,
            "gemm2_k": gemm2_k,
            "fused_vs_expected_q": fused_q_diff,
            "fused_vs_expected_scales": fused_scale_diff,
            "twostep_vs_expected_q": twostep_q_diff,
            "twostep_vs_expected_scales": twostep_scale_diff,
            "fused_vs_twostep_q": fused_vs_twostep_q_diff,
            "fused_vs_twostep_scales": fused_vs_twostep_scale_diff,
        })

    summary = {
        "kind": "qwen36_silu_quant_parity",
        "multiwindow_dir": str(root),
        "source": args.source,
        "window_count": len(results),
        "all_fused_q_exact": all(
            item["fused_vs_expected_q"]["raw_equal"] for item in results),
        "all_fused_scales_exact": all(
            item["fused_vs_expected_scales"]["raw_equal"] for item in results),
        "all_twostep_q_exact": all(
            item["twostep_vs_expected_q"]["raw_equal"] for item in results),
        "all_twostep_scales_exact": all(
            item["twostep_vs_expected_scales"]["raw_equal"]
            for item in results),
        "max_fused_q_diff_count": max(
            item["fused_vs_expected_q"]["raw_diff_count"]
            for item in results),
        "max_fused_scale_abs_diff": max(
            item["fused_vs_expected_scales"]["max_abs_diff"]
            for item in results),
        "max_twostep_q_diff_count": max(
            item["twostep_vs_expected_q"]["raw_diff_count"]
            for item in results),
        "max_twostep_scale_abs_diff": max(
            item["twostep_vs_expected_scales"]["max_abs_diff"]
            for item in results),
        "max_fused_vs_twostep_q_diff_count": max(
            item["fused_vs_twostep_q"]["raw_diff_count"]
            for item in results),
        "max_fused_vs_twostep_scale_abs_diff": max(
            item["fused_vs_twostep_scales"]["max_abs_diff"]
            for item in results),
        "windows": results,
    }
    Path(args.out_json).write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
