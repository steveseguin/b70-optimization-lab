#!/usr/bin/env python3
"""R162: GDN spec path with a per-sequence mix of accepted-token counts (1 and 2)
inside one call, and arbitrary (non-contiguous, permuted) state-slot ids, versus
the single-sequence call with the same accepted count and slots."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import torch
import vllm_xpu_kernels._xpu_C  # noqa

DEV = torch.device("xpu:0"); DT = torch.float16; NSEQ = 64; T = 2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); a = ap.parse_args()
    torch.manual_seed(20260903)
    nk, nv, dk, dv, tp, width = 16, 48, 128, 128, 2, 4
    lk, lv = nk // tp, nv // tp
    qkvz_w = lk * (2 * dk + 2 * dv * nv // nk); ba_w = lk * (2 * nv // nk); qkv_w = lk * (2 * dk + dv * nv // nk)
    q = torch.randn((NSEQ * T, qkvz_w), dtype=DT, device=DEV); b = torch.randn((NSEQ * T, ba_w), dtype=DT, device=DEV)
    NSLOT = 4 * NSEQ + 16
    conv0 = torch.randn((NSLOT, width - 1, qkv_w), dtype=DT, device=DEV); ssm0 = (torch.randn((NSLOT, lv, dv, dk), device=DEV) * 0.1).to(DT)
    cw = torch.randn((qkv_w, width), dtype=DT, device=DEV) * 0.2; cb = torch.randn((qkv_w,), dtype=DT, device=DEV) * 0.1
    a_log = torch.randn((lv,), dtype=torch.float32, device=DEV); dtb = torch.randn((lv,), dtype=DT, device=DEV)
    g = torch.Generator().manual_seed(3)
    accepted = [1 + int(torch.randint(0, 2, (1,), generator=g)) for _ in range(NSEQ)]
    slot_perm = torch.randperm(NSLOT, generator=g).tolist()
    slots = [[slot_perm[2 * s], slot_perm[2 * s + 1]] for s in range(NSEQ)]  # arbitrary, non-contiguous slot pairs

    def call(seqs):
        B = len(seqs); rows = torch.cat([torch.arange(s * T, s * T + T, device=DEV) for s in seqs]); n = rows.numel()
        out = torch.zeros((n, lv, dv), dtype=DT, device=DEV); z = torch.empty_like(out)
        sp_qs = torch.arange(0, n + 1, T, dtype=torch.int32, device=DEV); sp_tok = torch.arange(n, dtype=torch.int32, device=DEV)
        sp_state = torch.tensor([slots[s] for s in seqs], dtype=torch.int32, device=DEV)
        n_acc = torch.tensor([accepted[s] for s in seqs], dtype=torch.int32, device=DEV)
        conv = conv0.clone(); ssm = ssm0.clone()
        torch.ops._xpu_C.gdn_attention(out, z, q[rows].contiguous(), b[rows].contiguous(), nk, nv, dk, dv, conv, ssm, cw, cb, "silu", a_log, dtb,
                                       0, 0, B, None, None, torch.empty(0, dtype=torch.int32, device=DEV), None, sp_qs, sp_tok, sp_state, n_acc, n, tp, False)
        torch.xpu.synchronize(); return out, z, conv, ssm

    refs = [call([i]) for i in range(NSEQ)]
    rows = []
    for B in (2, 4, 8, 16, 32, 64):
        seqs = list(range(B)); o, z, c, s = call(seqs)
        ok = all(torch.equal(o[k * T:(k + 1) * T], refs[sq][0]) and torch.equal(z[k * T:(k + 1) * T], refs[sq][1]) for k, sq in enumerate(seqs))
        st = all(all(torch.equal(c[sl], refs[sq][2][sl]) and torch.equal(s[sl], refs[sq][3][sl]) for sl in slots[sq]) for sq in seqs)
        perm = torch.randperm(B).tolist(); o3, z3, c3, s3 = call([seqs[p] for p in perm])
        pk = all(torch.equal(o3[k * T:(k + 1) * T], refs[seqs[p]][0]) for k, p in enumerate(perm))
        md = max(float((o[k * T:(k + 1) * T].float() - refs[sq][0].float()).abs().max()) for k, sq in enumerate(seqs))
        rows.append({"B": B, "accepted_mix": sorted(set(accepted[:B])), "out_z_equal_single": ok, "states_equal_single": st, "permuted_equal_single": pk, "max_abs_diff": md})
        print("spec-mixed-accept", rows[-1], flush=True)
    res = {"rows": rows, "all_invariant": all(r["out_z_equal_single"] and r["states_equal_single"] and r["permuted_equal_single"] for r in rows)}
    a.out.write_text(json.dumps(res, indent=1)); print({"all_invariant": res["all_invariant"]})


if __name__ == "__main__":
    main()
