#!/usr/bin/env python3
"""Run the R127-R129 CUTLASS identity/latency gate on all production shapes."""

from __future__ import annotations

import importlib.util
from pathlib import Path


BASE = Path(__file__).with_name("bench-qwen38-fp8-w8a16-cutlass-fixed-m32.py")
SPEC = importlib.util.spec_from_file_location("cutlass_fixed_m32_bench", BASE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load benchmark module from {BASE}")
BENCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH)

BENCH.SHAPES = {
    "gdn_in_proj_qkvz": (5120, 8192),
    "gdn_out_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
    "attn_o_proj": (3072, 5120),
    "mlp_gate_up_proj": (5120, 17408),
    "mlp_down_proj": (8704, 5120),
}


if __name__ == "__main__":
    raise SystemExit(BENCH.main())
