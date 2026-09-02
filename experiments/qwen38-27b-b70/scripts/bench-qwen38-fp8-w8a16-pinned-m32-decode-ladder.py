#!/usr/bin/env python3
"""Time all production W8A16 shapes at MTP1 decode row counts.

This reuses the sealed R123 harness and changes only the shape inventory and
timing points.  A fresh process is run with either natural oneDNN selection or
the frozen source-M32 strategy; aggregation is performed outside the process.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


BASE = Path(__file__).with_name("bench-qwen38-fp8-w8a16-pinned-jit-strategy.py")
spec = importlib.util.spec_from_file_location("r135_pinned_m32_base", BASE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {BASE}")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

bench.SHAPES = {
    "gdn_in_proj_qkvz": (5120, 8192),
    "gdn_out_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
    "attn_o_proj": (3072, 5120),
    "mlp_gate_up_proj": (5120, 17408),
    "mlp_down_proj": (8704, 5120),
}
bench.TIMED_MS = [2, 4, 8, 16, 32, 64, 128, 168, 256]


if __name__ == "__main__":
    raise SystemExit(bench.main())
