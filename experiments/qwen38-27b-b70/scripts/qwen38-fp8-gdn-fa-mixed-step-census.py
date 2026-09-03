#!/usr/bin/env python3
"""Mixed-step census (R155): one GDN call carrying P prefill sequences and D decode
sequences at once, and one FA varlen call carrying prefill and single-token rows
together. The decode rows' outputs and states must equal the pure-decode call, and
the prefill rows must equal the pure-prefill call, for every (P, D) mix."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import torch
import vllm_xpu_kernels._xpu_C  # noqa
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func

DEV = torch.device("xpu:0"); DT = torch.float16
MIXES = [(1, 1), (2, 2), (4, 4), (8, 8), (16, 16), (1, 31), (31, 1), (17, 15), (16, 32), (32, 32)]


def eq(a, b): return bool(torch.equal(a, b))


def gdn():
    torch.manual_seed(20260903)
    nk, nv, dk, dv, tp, width = 16, 48, 128, 128, 2, 4
    lk, lv = nk // tp, nv // tp
    qkvz_w = lk * (2 * dk + 2 * dv * nv // nk); ba_w = lk * (2 * nv // nk); qkv_w = lk * (2 * dk + dv * nv // nk)
    NS = 64; lens = [24 + (i % 17) for i in range(NS)]
    starts = [0]
    for L in lens: starts.append(starts[-1] + L)
    pq = torch.randn((starts[-1], qkvz_w), dtype=DT, device=DEV); pb = torch.randn((starts[-1], ba_w), dtype=DT, device=DEV)
    dq = torch.randn((NS, qkvz_w), dtype=DT, device=DEV); db = torch.randn((NS, ba_w), dtype=DT, device=DEV)
    conv0 = torch.randn((256, width - 1, qkv_w), dtype=DT, device=DEV); ssm0 = (torch.randn((256, lv, dv, dk), device=DEV) * 0.1).to(DT)
    cw = torch.randn((qkv_w, width), dtype=DT, device=DEV) * 0.2; cb = torch.randn((qkv_w,), dtype=DT, device=DEV) * 0.1
    a_log = torch.randn((lv,), dtype=torch.float32, device=DEV); dtb = torch.randn((lv,), dtype=DT, device=DEV)

    def call(dec: list[int], pre: list[int]):
        # vLLM layout: decode tokens first, then prefill tokens; state indices decode slots then prefill slots
        rows_q = [dq[dec]] if dec else []; rows_b = [db[dec]] if dec else []
        if pre:
            idx = torch.cat([torch.arange(starts[s], starts[s + 1], device=DEV) for s in pre]); rows_q.append(pq[idx]); rows_b.append(pb[idx])
        q = torch.cat(rows_q).contiguous(); b = torch.cat(rows_b).contiguous(); n = q.shape[0]
        out = torch.zeros((n, lv, dv), dtype=DT, device=DEV); z = torch.empty_like(out)
        qs = [0] + [k + 1 for k in range(len(dec))]
        for s in pre: qs.append(qs[-1] + lens[s])
        qs = torch.tensor(qs, dtype=torch.int32, device=DEV)
        his = torch.tensor([True] * len(dec) + [False] * len(pre), dtype=torch.bool, device=DEV)
        sidx = torch.tensor(dec + [32 + s for s in pre], dtype=torch.int32, device=DEV)  # prefill slots 32.. to avoid overlap
        conv = conv0.clone(); ssm = ssm0.clone()
        torch.ops._xpu_C.gdn_attention(out, z, q, b, nk, nv, dk, dv, conv, ssm, cw, cb, "silu", a_log, dtb,
                                       len(pre), len(dec), 0, his, qs, None, sidx, None, None, None, None, n, tp, False)
        torch.xpu.synchronize(); return out, z, conv, ssm

    rows = []
    for P, D in MIXES:
        dec = list(range(D)); pre = list(range(P))
        om, zm, cm, sm = call(dec, pre)
        od, zd, cd, sd = call(dec, []); op, zp, cp, sp = call([], pre)
        d_ok = eq(om[:D], od) and eq(zm[:D], zd) and eq(sm[:D], sd[:D]) and eq(cm[:D], cd[:D])
        p_ok = eq(om[D:], op) and eq(zm[D:], zp) and all(eq(sm[32 + s], sp[32 + s]) and eq(cm[32 + s], cp[32 + s]) for s in pre)
        rel = float((om[:D].float() - od.float()).abs().max() / (od.float().abs().max() + 1e-6))
        rows.append({"prefills": P, "decodes": D, "decode_rows_equal_pure_decode": d_ok, "prefill_rows_equal_pure_prefill": p_ok,
                     "decode_out_max_abs_diff": float((om[:D].float() - od.float()).abs().max()), "decode_out_max_rel_diff": rel,
                     "decode_z_equal": eq(zm[:D], zd), "decode_conv_state_equal": eq(cm[:D], cd[:D]), "decode_ssm_state_equal": eq(sm[:D], sd[:D]),
                     "decode_ssm_max_abs_diff": float((sm[:D].float() - sd[:D].float()).abs().max())})
        print("gdn-mixed", rows[-1], flush=True)
    return {"rows": rows, "all_mixed_invariant": all(r["decode_rows_equal_pure_decode"] and r["prefill_rows_equal_pure_prefill"] for r in rows)}


def fa():
    torch.manual_seed(20260903)
    heads, kv_heads, hd, block = 12, 2, 256, 64; NS = 64
    plen = [24 + (i % 17) for i in range(NS)]; dlen = [40 + 3 * i for i in range(NS)]
    kc = torch.randn((NS * 4 + NS + 8, block, kv_heads, hd), dtype=DT, device=DEV); vc = torch.randn_like(kc)
    pq = [torch.randn((L, heads, hd), dtype=DT, device=DEV) for L in plen]; dq = torch.randn((NS, heads, hd), dtype=DT, device=DEV)
    dtab = torch.arange(NS * 4, dtype=torch.int32, device=DEV).view(NS, 4); ptab = (NS * 4 + torch.arange(NS, dtype=torch.int32, device=DEV)).view(NS, 1)
    scale = 1.0 / math.sqrt(hd)

    def call(dec, pre):
        qs = ([dq[dec]] if dec else []) + [pq[s] for s in pre]; q = torch.cat(qs).contiguous()
        cu = [0] + [k + 1 for k in range(len(dec))]
        for s in pre: cu.append(cu[-1] + plen[s])
        cu = torch.tensor(cu, dtype=torch.int32, device=DEV)
        used = torch.tensor([dlen[s] for s in dec] + [plen[s] for s in pre], dtype=torch.int32, device=DEV)
        tab = torch.zeros((len(dec) + len(pre), 4), dtype=torch.int32, device=DEV)
        if dec: tab[:len(dec)] = dtab[dec]
        for k, s in enumerate(pre): tab[len(dec) + k, 0] = ptab[s, 0]
        out = torch.empty_like(q)
        flash_attn_varlen_func(q=q, k=kc, v=vc, out=out, cu_seqlens_q=cu, max_seqlen_q=max(1, max([plen[s] for s in pre], default=1)), seqused_k=used,
                               max_seqlen_k=int(used.max()), softmax_scale=scale, causal=True, block_table=tab, fa_version=2)
        torch.xpu.synchronize(); return out

    rows = []
    for P, D in MIXES:
        dec = list(range(D)); pre = list(range(P))
        om = call(dec, pre); od = call(dec, []); op = call([], pre)
        rows.append({"prefills": P, "decodes": D, "decode_rows_equal_pure_decode": eq(om[:D], od), "prefill_rows_equal_pure_prefill": eq(om[D:], op)})
        print("fa-mixed", rows[-1], flush=True)
    return {"rows": rows, "all_mixed_invariant": all(r["decode_rows_equal_pure_decode"] and r["prefill_rows_equal_pure_prefill"] for r in rows)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); a = ap.parse_args()
    res = {"gdn_mixed": gdn(), "fa_mixed": fa()}
    a.out.write_text(json.dumps(res, indent=1)); print({k: v["all_mixed_invariant"] for k, v in res.items()})


if __name__ == "__main__":
    main()
