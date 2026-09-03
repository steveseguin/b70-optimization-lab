#!/usr/bin/env python3
"""Fail-closed semantic gate for R153b: env-gated Triton RMSNorm route on XPU for
GemmaRMSNorm and RMSNorm, default off, residual add kept as an exact fp16 add."""
from __future__ import annotations
import argparse, ast
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("source", type=Path); a = ap.parse_args()
    src = a.source.read_text(encoding="utf-8"); tree = ast.parse(src, a.source)
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for req in ("_xpu_triton_rmsnorm_enabled", "_xpu_triton_rmsnorm", "_xpu_traced_rmsnorm"):
        if req not in names: raise SystemExit(f"R153b is missing {req}")
    for frag in ('os.environ.get(flag, "0") == "1"', 'def _xpu_traced_rmsnorm(', 'variance = xf.pow(2).mean(dim=-1, keepdim=True)', 'return _xpu_traced_rmsnorm(x, weight, eps)', 'from vllm.third_party.flash_linear_attention.ops.layernorm_guard import',
                 
                 '_xpu_triton_rmsnorm_enabled(\n            "VLLM_XPU_GEMMA_RMSNORM_TRITON"\n        )', '_xpu_triton_rmsnorm_enabled("VLLM_XPU_RMSNORM_TRITON")',
                 'R152 Gemma RMSNorm Triton route armed', 'R152 RMSNorm Triton route armed', 'residual = residual + x'):
        if frag not in src: raise SystemExit(f"R153b source is missing: {frag!r}")
    if src.count("residual = residual + x") != 2: raise SystemExit("expected two exact residual adds")
    print("R153b Triton RMSNorm gate: ok"); return 0


if __name__ == "__main__":
    raise SystemExit(main())
