#!/usr/bin/env python3
"""Run the CUTLASS all-shape gate with the production NT weight layout.

The sealed R127 harness is reused verbatim except for removing its diagnostic
KxN contiguous copy. This preserves a KxN transposed view over physical,
row-major NxK storage, matching XPUW8A16ScaledMMLinearKernel.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


BASE = Path(__file__).with_name("bench-qwen38-fp8-w8a16-cutlass-fixed-m32.py")
source = BASE.read_text()
old = "weight = weight_nk.t().contiguous().to(device)"
new = "weight = weight_nk.t().to(device)"
if source.count(old) != 1:
    raise RuntimeError(f"expected exactly one sealed weight-layout expression in {BASE}")
source = source.replace(old, new)

SPEC = importlib.util.spec_from_loader("cutlass_production_nt_bench", loader=None)
if SPEC is None:
    raise RuntimeError("cannot construct benchmark module")
BENCH = importlib.util.module_from_spec(SPEC)
BENCH.__file__ = str(BASE)
exec(compile(source, str(BASE), "exec"), BENCH.__dict__)

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
