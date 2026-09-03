#!/usr/bin/env python3
"""Batch-invariance census of the XPU GDN *prefill* path (R151c).

B sequences of 24-40 prompt tokens each prefill in one gdn_attention call
(num_prefills=B, no initial state). Every sequence's core output rows and its
resulting conv/SSM state must be bitwise equal to the single-sequence call.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import torch
import vllm_xpu_kernels._xpu_C  # noqa: F401

DEV = torch.device("xpu:0"); DT = torch.float16; NSEQ = 64
BATCHES = [1, 2, 4, 8, 16, 17, 24, 31, 32, 33, 40, 48, 64]


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); ap.add_argument("--seed", type=int, default=20260902)
    a = ap.parse_args(); torch.manual_seed(a.seed)
    nk, nv, dk, dv, tp, width = 16, 48, 128, 128, 2, 4
    lk, lv = nk // tp, nv // tp
    qkvz_w = lk * (2 * dk + 2 * dv * nv // nk); ba_w = lk * (2 * nv // nk); qkv_w = lk * (2 * dk + dv * nv // nk)
    lens = [24 + (i % 17) for i in range(NSEQ)]
    starts = [0]
    for L in lens: starts.append(starts[-1] + L)
    T = starts[-1]
    qkvz = torch.randn((T, qkvz_w), dtype=DT, device=DEV); ba = torch.randn((T, ba_w), dtype=DT, device=DEV)
    conv_w = torch.randn((qkv_w, width), dtype=DT, device=DEV) * 0.2; conv_b = torch.randn((qkv_w,), dtype=DT, device=DEV) * 0.1
    a_log = torch.randn((lv,), dtype=torch.float32, device=DEV); dt_bias = torch.randn((lv,), dtype=DT, device=DEV)
    cache = 256

    def call(seqs: list[int]):
        rows = torch.cat([torch.arange(starts[s], starts[s + 1], device=DEV) for s in seqs])
        B = len(seqs); n = rows.numel()
        out = torch.zeros((n, lv, dv), dtype=DT, device=DEV); z = torch.empty_like(out)
        qs = torch.tensor([0] + [sum(lens[s] for s in seqs[:k + 1]) for k in range(B)], dtype=torch.int32, device=DEV)
        conv = torch.zeros((cache, width - 1, qkv_w), dtype=DT, device=DEV); ssm = torch.zeros((cache, lv, dv, dk), dtype=DT, device=DEV)
        his = torch.zeros(B, dtype=torch.bool, device=DEV)
        idx = torch.tensor(seqs, dtype=torch.int32, device=DEV)
        torch.ops._xpu_C.gdn_attention(out, z, qkvz[rows].contiguous(), ba[rows].contiguous(), nk, nv, dk, dv, conv, ssm, conv_w, conv_b, "silu", a_log, dt_bias,
                                       B, 0, 0, his, qs, None, idx, None, None, None, None, n, tp, False)
        torch.xpu.synchronize()
        return out, z, conv, ssm

    refs = []
    for i in range(NSEQ):
        o, z, c, s = call([i]); refs.append((o, z, c[i].clone(), s[i].clone()))
    res = []
    for B in BATCHES:
        seqs = list(range(B)); o, z, c, s = call(seqs); o2, z2, c2, s2 = call(seqs)
        perm = torch.randperm(B).tolist(); o3, z3, c3, s3 = call([seqs[p] for p in perm])
        off = 0; out_ok = z_ok = st_ok = True
        for k, sq in enumerate(seqs):
            L = lens[sq]; out_ok &= torch.equal(o[off:off + L], refs[sq][0]); z_ok &= torch.equal(z[off:off + L], refs[sq][1])
            st_ok &= torch.equal(c[sq], refs[sq][2]) and torch.equal(s[sq], refs[sq][3]); off += L
        off = 0; perm_ok = True
        for p in perm:
            sq = seqs[p]; L = lens[sq]; perm_ok &= torch.equal(o3[off:off + L], refs[sq][0]) and torch.equal(s3[sq], refs[sq][3]); off += L
        row = {"B": B, "tokens": sum(lens[:B]), "out_equal_single": bool(out_ok), "z_equal_single": bool(z_ok), "states_equal_single": bool(st_ok),
               "permuted_equal_single": bool(perm_ok), "repeat_equal": bool(torch.equal(o, o2) and torch.equal(s[:B], s2[:B]))}
        res.append(row); print("gdn-prefill", row, flush=True)
    summary = {"kernel": "torch.ops._xpu_C.gdn_attention (prefill, no initial state)", "rows": res,
               "all_batch_invariant": all(r["out_equal_single"] and r["states_equal_single"] and r["permuted_equal_single"] for r in res),
               "all_repeat_exact": all(r["repeat_equal"] for r in res), "first_failing_B": next((r["B"] for r in res if not (r["out_equal_single"] and r["states_equal_single"])), None)}
    a.out.write_text(json.dumps(summary, indent=1)); print({k: summary[k] for k in ("all_batch_invariant", "all_repeat_exact", "first_failing_B")}); return 0


if __name__ == "__main__":
    raise SystemExit(main())
