#!/usr/bin/env python3
"""Compare current XPU W8A8 grouped-GEMM output with oneDNN output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-meta", required=True)
    parser.add_argument("--onednn-output", required=True)
    parser.add_argument("--out-json", required=True)
    return parser.parse_args()


def read_meta(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def bf16_file_to_f32(path: Path) -> np.ndarray:
    raw = np.fromfile(path, dtype=np.uint16)
    expanded = raw.astype(np.uint32) << np.uint32(16)
    return expanded.view(np.float32)


def fp16_file_to_f32(path: Path) -> np.ndarray:
    return np.fromfile(path, dtype=np.float16).astype(np.float32)


def dtype_to_f32(path: Path, dtype_name: str) -> np.ndarray:
    if dtype_name == "bf16":
        return bf16_file_to_f32(path)
    if dtype_name in ("fp16", "f16"):
        return fp16_file_to_f32(path)
    if dtype_name == "f32":
        return np.fromfile(path, dtype=np.float32)
    raise ValueError(dtype_name)


def raw_bits(path: Path, dtype_name: str) -> np.ndarray:
    if dtype_name == "bf16" or dtype_name in ("fp16", "f16"):
        return np.fromfile(path, dtype=np.uint16)
    if dtype_name == "f32":
        return np.fromfile(path, dtype=np.uint32)
    raise ValueError(dtype_name)


def summarize_diff(xpu: np.ndarray, other: np.ndarray) -> dict[str, Any]:
    if xpu.shape != other.shape:
        raise ValueError(f"shape mismatch: {xpu.shape} vs {other.shape}")
    diff = np.abs(xpu - other)
    denom = np.maximum(np.abs(xpu), np.float32(1e-12))
    rel = diff / denom
    max_idx = int(np.argmax(diff)) if diff.size else 0
    return {
        "numel": int(diff.size),
        "max_abs_diff": float(diff[max_idx]) if diff.size else 0.0,
        "mean_abs_diff": float(np.mean(diff)) if diff.size else 0.0,
        "max_rel_diff": float(np.max(rel)) if rel.size else 0.0,
        "nonzero_abs_diff_count": int(np.count_nonzero(diff)),
        "max_abs_index": max_idx,
        "xpu_at_max": float(xpu[max_idx]) if diff.size else 0.0,
        "other_at_max": float(other[max_idx]) if diff.size else 0.0,
    }


def main() -> None:
    args = parse_args()
    meta_path = Path(args.case_meta)
    meta = read_meta(meta_path)
    base = meta_path.parent
    dtype_name = meta["dst_dtype"]
    xpu_raw_path = base / meta["xpu_out_path"]
    xpu_f32_path = base / meta["xpu_out_f32_path"]
    onednn_path = Path(args.onednn_output)

    xpu_raw = raw_bits(xpu_raw_path, dtype_name)
    onednn_raw = raw_bits(onednn_path, dtype_name)
    if xpu_raw.shape != onednn_raw.shape:
        raise ValueError(
            f"raw shape mismatch: {xpu_raw.shape} vs {onednn_raw.shape}"
        )
    raw_equal = bool(np.array_equal(xpu_raw, onednn_raw))
    raw_diff_count = int(np.count_nonzero(xpu_raw != onednn_raw))

    xpu_f32 = np.fromfile(xpu_f32_path, dtype=np.float32)
    onednn_f32 = dtype_to_f32(onednn_path, dtype_name)
    diff = summarize_diff(xpu_f32, onednn_f32)
    result = {
        "case_meta": str(meta_path),
        "onednn_output": str(onednn_path),
        "name": meta.get("name"),
        "total_tokens": int(meta["total_tokens"]),
        "k": int(meta["k"]),
        "n": int(meta["n"]),
        "dst_dtype": dtype_name,
        "raw_equal": raw_equal,
        "raw_diff_count": raw_diff_count,
        **diff,
        "status": "exact" if raw_equal else "different",
    }
    Path(args.out_json).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
