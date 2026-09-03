#!/usr/bin/env python3
"""Stale-slot census (R157): does a prefill with has_initial_state=False, or a decode
with has_initial_state=True, depend on stale bytes left in its conv/SSM slot by a
previous occupant? Compare outputs and resulting states across (a) zeroed slots,
(b) random stale slots, (c) a slot previously used by another sequence's prefill,
for pure prefill and pure decode calls at B in 1..32."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import torch
import vllm_xpu_kernels._xpu_C  # noqa

DEV = torch.device("xpu:0"); DT = torch.float16


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); a = ap.parse_args()
    torch.manual_seed(20260903)
    nk, nv, dk, dv, tp, width = 16, 48, 128, 128, 2, 4
    lk, lv = nk // tp, nv // tp
    qkvz_w = lk * (2 * dk + 2 * dv * nv // nk); ba_w = lk * (2 * nv // nk); qkv_w = lk * (2 * dk + dv * nv // nk)
    NS = 32; lens = [24 + (i % 17) for i in range(NS)]; starts = [0]
    for L in lens: starts.append(starts[-1] + L)
    pq = torch.randn((starts[-1], qkvz_w), dtype=DT, device=DEV); pb = torch.randn((starts[-1], ba_w), dtype=DT, device=DEV)
    dq = torch.randn((NS, qkvz_w), dtype=DT, device=DEV); db = torch.randn((NS, ba_w), dtype=DT, device=DEV)
    cw = torch.randn((qkv_w, width), dtype=DT, device=DEV) * 0.2; cb = torch.randn((qkv_w,), dtype=DT, device=DEV) * 0.1
    a_log = torch.randn((lv,), dtype=torch.float32, device=DEV); dtb = torch.randn((lv,), dtype=DT, device=DEV)
    cache = 64

    def prefill(seqs, conv, ssm):
        rows = torch.cat([torch.arange(starts[s], starts[s + 1], device=DEV) for s in seqs]); n = rows.numel(); B = len(seqs)
        out = torch.zeros((n, lv, dv), dtype=DT, device=DEV); z = torch.empty_like(out)
        qs = torch.tensor([0] + [sum(lens[s] for s in seqs[:k + 1]) for k in range(B)], dtype=torch.int32, device=DEV)
        his = torch.zeros(B, dtype=torch.bool, device=DEV); idx = torch.tensor(seqs, dtype=torch.int32, device=DEV)
        torch.ops._xpu_C.gdn_attention(out, z, pq[rows].contiguous(), pb[rows].contiguous(), nk, nv, dk, dv, conv, ssm, cw, cb, "silu", a_log, dtb,
                                       B, 0, 0, his, qs, None, idx, None, None, None, None, n, tp, False)
        torch.xpu.synchronize(); return out, z

    def decode(seqs, conv, ssm):
        B = len(seqs); idx = torch.tensor(seqs, dtype=torch.int32, device=DEV)
        out = torch.zeros((B, lv, dv), dtype=DT, device=DEV); z = torch.empty_like(out)
        torch.ops._xpu_C.gdn_attention(out, z, dq[seqs].contiguous(), db[seqs].contiguous(), nk, nv, dk, dv, conv, ssm, cw, cb, "silu", a_log, dtb,
                                       0, B, 0, torch.ones(B, dtype=torch.bool, device=DEV), torch.arange(B + 1, dtype=torch.int32, device=DEV), None, idx, None, None, None, None, B, tp, False)
        torch.xpu.synchronize(); return out, z

    res = {}
    for B in (1, 2, 8, 16, 32):
        seqs = list(range(B))
        # (a) zero slots
        c0 = torch.zeros((cache, width - 1, qkv_w), dtype=DT, device=DEV); s0 = torch.zeros((cache, lv, dv, dk), dtype=DT, device=DEV)
        oa, za = prefill(seqs, c0, s0); ca, sa = c0.clone(), s0.clone()
        # (b) random stale slots
        c1 = torch.randn((cache, width - 1, qkv_w), dtype=DT, device=DEV); s1 = torch.randn((cache, lv, dv, dk), dtype=DT, device=DEV)
        ob, zb = prefill(seqs, c1, s1)
        # (c) slots previously written by other sequences' prefill (realistic reuse)
        c2 = torch.zeros_like(c0); s2 = torch.zeros_like(s0); prefill([(s + 7) % NS for s in seqs], c2, s2)  # other occupants into the same slot ids? use same idx: remap
        # remap: run other sequences into slots seqs by calling prefill with those seqs but idx=seqs -> emulate by temporarily aliasing
        rows_other = [(s + 7) % NS for s in seqs]
        c2 = torch.zeros_like(c0); s2 = torch.zeros_like(s0)
        # write other sequences' states into slot ids `seqs`
        n = sum(lens[s] for s in rows_other); rows = torch.cat([torch.arange(starts[s], starts[s + 1], device=DEV) for s in rows_other])
        out_t = torch.zeros((n, lv, dv), dtype=DT, device=DEV); z_t = torch.empty_like(out_t)
        qs = torch.tensor([0] + [sum(lens[s] for s in rows_other[:k + 1]) for k in range(B)], dtype=torch.int32, device=DEV)
        torch.ops._xpu_C.gdn_attention(out_t, z_t, pq[rows].contiguous(), pb[rows].contiguous(), nk, nv, dk, dv, c2, s2, cw, cb, "silu", a_log, dtb,
                                       B, 0, 0, torch.zeros(B, dtype=torch.bool, device=DEV), qs, None, torch.tensor(seqs, dtype=torch.int32, device=DEV), None, None, None, None, n, tp, False)
        torch.xpu.synchronize()
        oc, zc = prefill(seqs, c2, s2)
        pre = {"zero_vs_random_stale_out_equal": bool(torch.equal(oa, ob)), "zero_vs_random_stale_states_equal": bool(torch.equal(c0[:B], c1[:B]) and torch.equal(s0[:B], s1[:B])),
               "zero_vs_reused_slot_out_equal": bool(torch.equal(oa, oc)), "zero_vs_reused_slot_states_equal": bool(torch.equal(c0[:B], c2[:B]) and torch.equal(s0[:B], s2[:B])),
               "max_abs_diff_random_stale": float((oa.float() - ob.float()).abs().max()), "max_abs_diff_reused": float((oa.float() - oc.float()).abs().max())}
        # decode from identical states but different bytes in *other* slots / padding
        cd0 = c0.clone(); sd0 = s0.clone(); cd1 = c0.clone(); sd1 = s0.clone(); cd1[B:] = torch.randn_like(cd1[B:]); sd1[B:] = torch.randn_like(sd1[B:])
        od0, _ = decode(seqs, cd0, sd0); od1, _ = decode(seqs, cd1, sd1)
        dec = {"decode_other_slots_garbage_equal": bool(torch.equal(od0, od1)) and bool(torch.equal(cd0[:B], cd1[:B])) and bool(torch.equal(sd0[:B], sd1[:B]))}
        res[f"B{B}"] = {"prefill": pre, "decode": dec}; print(B, res[f"B{B}"], flush=True)
    a.out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
