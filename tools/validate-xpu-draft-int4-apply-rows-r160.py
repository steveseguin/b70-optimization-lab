#!/usr/bin/env python3
"""Fail-closed gate for R160: env-gated fixed-row chunking of the draft INT4 head apply, default off."""
import argparse, ast
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("source", type=Path); a = ap.parse_args()
src = a.source.read_text(encoding="utf-8"); ast.parse(src, a.source)
for frag in ('os.environ.get("VLLM_XPU_DRAFT_LM_HEAD_INT4_APPLY_ROWS", "0")', "if 0 < apply_rows < x2d.shape[0]:", "for i in range(0, x2d.shape[0], apply_rows)", "x2d[i : i + apply_rows]"):
    if frag not in src: raise SystemExit(f"R160 source is missing: {frag!r}")
if src.count("torch.ops._xpu_C.int4_gemm_w4a16(") != 2: raise SystemExit("expected chunked and unchunked INT4 calls")
print("R160 draft INT4 apply-rows gate: ok")
