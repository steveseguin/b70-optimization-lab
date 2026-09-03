#!/usr/bin/env python3
"""Fail-closed gate for R156: env-gated split of mixed GDN steps into pure decode,
prefill, and spec calls inside _gdn_attention_core_xpu_impl; default off."""
import argparse, ast
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("source", type=Path); a = ap.parse_args()
src = a.source.read_text(encoding="utf-8"); ast.parse(src, a.source)
for frag in ('os.environ.get("VLLM_XPU_GDN_SPLIT_MIXED", "0") == "1"', "R156 GDN split-mixed step executed", "def _kernel(out, zz, qkvz, ba, n_prefills, n_decodes, n_spec, his, ns_qs,",
             "dec_mask = (lens == 1) & his", "core_attn_out[st] = out_s", "core_attn_out[tok] = out_p", "(non_spec_query_start_loc[d:] - d).to(torch.int32).contiguous()"):
    if frag not in src: raise SystemExit(f"R156 source is missing: {frag!r}")
if src.count("torch.ops._xpu_C.gdn_attention(") != 2: raise SystemExit("expected the helper and the original kernel call")
print("R156 GDN split-mixed gate: ok")
