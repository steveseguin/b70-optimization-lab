#!/usr/bin/env python3
"""Spec-path batch census (R158): the GDN kernel's speculative decode path
(num_spec_decodes=B, two tokens per sequence, MTP1 verify) at B in 1..64 versus
the single-sequence spec call: outputs, z, and resulting states must be bitwise
equal; also repeat and permutation checks."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import torch
import vllm_xpu_kernels._xpu_C  # noqa

DEV = torch.device("xpu:0"); DT = torch.float16
NSEQ = 64; T = 2  # num_spec + 1 tokens per spec sequence
BATCHES = [1, 2, 4, 8, 16, 17, 24, 31, 32, 33, 48, 64]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); ap.add_argument("--accepted", type=int, default=1); a = ap.parse_args()
    torch.manual_seed(20260903)
    nk, nv, dk, dv, tp, width = 16, 48, 128, 128, 2, 4
    lk, lv = nk // tp, nv // tp
    qkvz_w = lk * (2 * dk + 2 * dv * nv // nk); ba_w = lk * (2 * nv // nk); qkv_w = lk * (2 * dk + dv * nv // nk)
    q = torch.randn((NSEQ * T, qkvz_w), dtype=DT, device=DEV); b = torch.randn((NSEQ * T, ba_w), dtype=DT, device=DEV)
    conv0 = torch.randn((2 * NSEQ + 8, width - 1, qkv_w), dtype=DT, device=DEV); ssm0 = (torch.randn((2 * NSEQ + 8, lv, dv, dk), device=DEV) * 0.1).to(DT)
    cw = torch.randn((qkv_w, width), dtype=DT, device=DEV) * 0.2; cb = torch.randn((qkv_w,), dtype=DT, device=DEV) * 0.1
    a_log = torch.randn((lv,), dtype=torch.float32, device=DEV); dtb = torch.randn((lv,), dtype=DT, device=DEV)

    def call(seqs: list[int]):
        B = len(seqs); rows = torch.cat([torch.arange(s * T, s * T + T, device=DEV) for s in seqs]); n = rows.numel()
        out = torch.zeros((n, lv, dv), dtype=DT, device=DEV); z = torch.empty_like(out)
        sp_qs = torch.arange(0, n + 1, T, dtype=torch.int32, device=DEV)
        sp_tok = torch.arange(n, dtype=torch.int32, device=DEV)
        sp_state = torch.tensor([[2 * s, 2 * s + 1] for s in seqs], dtype=torch.int32, device=DEV)
        n_acc = torch.full((B,), a.accepted, dtype=torch.int32, device=DEV)
        conv = conv0.clone(); ssm = ssm0.clone()
        torch.ops._xpu_C.gdn_attention(out, z, q[rows].contiguous(), b[rows].contiguous(), nk, nv, dk, dv, conv, ssm, cw, cb, "silu", a_log, dtb,
                                       0, 0, B, None, None, torch.empty(0, dtype=torch.int32, device=DEV), None, sp_qs, sp_tok, sp_state, n_acc, n, tp, False)
        torch.xpu.synchronize(); return out, z, conv, ssm

    refs = [call([i]) for i in range(NSEQ)]
    rows = []
    for B in BATCHES:
        seqs = list(range(B)); o, z, c, s = call(seqs); o2, z2, c2, s2 = call(seqs)
        perm = torch.randperm(B).tolist(); o3, z3, c3, s3 = call([seqs[p] for p in perm])
        ok = all(torch.equal(o[k * T:(k + 1) * T], refs[sq][0]) and torch.equal(z[k * T:(k + 1) * T], refs[sq][1]) for k, sq in enumerate(seqs))
        st_ok = all(torch.equal(c[2 * sq:2 * sq + 2], refs[sq][2][2 * sq:2 * sq + 2]) and torch.equal(s[2 * sq:2 * sq + 2], refs[sq][3][2 * sq:2 * sq + 2]) for sq in seqs)
        perm_ok = all(torch.equal(o3[k * T:(k + 1) * T], refs[seqs[p]][0]) for k, p in enumerate(perm))
        md = max(float((o[k * T:(k + 1) * T].float() - refs[sq][0].float()).abs().max()) for k, sq in enumerate(seqs))
        rows.append({"B": B, "rows": B * T, "out_z_equal_single": ok, "states_equal_single": st_ok, "permuted_equal_single": perm_ok, "repeat_equal": bool(torch.equal(o, o2) and torch.equal(s, s2)), "max_abs_diff_out": md})
        print("spec", rows[-1], flush=True)
    res = {"accepted_tokens": a.accepted, "rows": rows, "all_batch_invariant": all(r["out_z_equal_single"] and r["states_equal_single"] and r["permuted_equal_single"] for r in rows),
           "first_failing_B": next((r["B"] for r in rows if not (r["out_z_equal_single"] and r["states_equal_single"])), None)}
    a.out.write_text(json.dumps(res, indent=1)); print({k: res[k] for k in ("all_batch_invariant", "first_failing_B")})


if __name__ == "__main__":
    main()
