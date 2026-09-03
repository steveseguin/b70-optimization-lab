#!/usr/bin/env python3
"""Operator probe: is the FP16 lm_head F.linear row-invariant inside its M<=32
class, and does <=32-row chunking reproduce the small-M arithmetic for M up to 256?

Diagnostic only, one card, synthetic weights of the production per-rank shape
(K=5120, N=124160). Motivated by R147: the c1-c64 ladder on the row-invariant
W8A16 image is exact through 32 verify rows and misses above, matching the
FP16 lm_head row-class boundary at M=32/33 found by the determinism sweep.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn.functional as F

K, N = 5120, 124160
CHUNK = 32
MS = [1, 2, 3, 4, 8, 16, 24, 31, 32, 33, 40, 48, 64, 96, 128, 168, 200, 256]


def chunked(a, w):
    return torch.cat([F.linear(a[i:i + CHUNK], w) for i in range(0, a.shape[0], CHUNK)], 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20260902)
    ap.add_argument("--repeats", type=int, default=5)
    a = ap.parse_args()
    torch.manual_seed(a.seed)
    dev = torch.device("xpu")
    w = (torch.randn(N, K, dtype=torch.float32) * 0.02).to(torch.float16).to(dev)
    x = (torch.randn(256, K, dtype=torch.float32) * 1.0).to(torch.float16).to(dev)
    single = torch.stack([F.linear(x[i:i + 1], w)[0] for i in range(256)])  # per-row M=1 reference
    torch.xpu.synchronize()
    rows = []
    for m in MS:
        full = F.linear(x[:m], w); torch.xpu.synchronize()
        rep = all(torch.equal(F.linear(x[:m], w), full) for _ in range(a.repeats))
        rows_equal_single = torch.equal(full, single[:m])
        ch = chunked(x[:m], w)
        chunk_equal_single = torch.equal(ch, single[:m])
        perm = torch.randperm(m, device=dev)
        chunk_perm_equal = torch.equal(chunked(x[:m][perm], w), single[:m][perm])
        rows.append({"M": m, "repeat_exact": rep, "full_rows_equal_M1": rows_equal_single,
                     "chunked32_rows_equal_M1": chunk_equal_single, "chunked32_permuted_equal_M1": chunk_perm_equal,
                     "max_abs_diff_full_vs_M1": float((full.float() - single[:m].float()).abs().max())})
        print(rows[-1], flush=True)
    res = {"schema": "qwen38-fp16-lm-head-chunk-invariance-probe.v1", "K": K, "N": N, "chunk": CHUNK,
           "rows": rows,
           "class_le32_row_invariant": all(r["full_rows_equal_M1"] for r in rows if r["M"] <= CHUNK),
           "chunked32_invariant_all_M": all(r["chunked32_rows_equal_M1"] and r["chunked32_permuted_equal_M1"] for r in rows),
           "all_repeat_exact": all(r["repeat_exact"] for r in rows)}
    a.out.write_text(json.dumps(res, indent=1))
    print({k: res[k] for k in ("class_le32_row_invariant", "chunked32_invariant_all_M", "all_repeat_exact")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
