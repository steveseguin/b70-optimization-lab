#!/usr/bin/env python3
"""Batch-invariance census (R151e) of the remaining per-row ops on XPU:
Gemma RMSNorm (vllm ir.ops.rms_norm / fused_add_rms_norm, hidden 5120), the q/k
head RMSNorm (head_dim 256), the GDN gated RMSNorm (Triton rmsnorm_fn, head_v_dim
128, with gate z), and the paged flash-attention prefill path. Each row's result
must be bitwise equal to the single-row (single-sequence) call."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import torch
from vllm import ir
from vllm.third_party.flash_linear_attention.ops.layernorm_guard import rmsnorm_fn
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func

DEV = torch.device("xpu:0"); DT = torch.float16
ROWS = [1, 2, 3, 4, 8, 16, 17, 24, 31, 32, 33, 48, 64, 128, 256]


def eq(a, b): return bool(torch.equal(a, b))


def rowwise(name, fn, x, extra=None):
    ref = torch.cat([fn(x[i:i + 1], None if extra is None else extra[i:i + 1]) for i in range(x.shape[0])])
    rows = []
    for M in ROWS:
        o = fn(x[:M], None if extra is None else extra[:M]); o2 = fn(x[:M], None if extra is None else extra[:M])
        rows.append({"M": M, "equal_single": eq(o, ref[:M]), "repeat_equal": eq(o, o2), "max_abs_diff": float((o.float() - ref[:M].float()).abs().max())})
    res = {"op": name, "rows": rows, "all_batch_invariant": all(r["equal_single"] for r in rows), "all_repeat_exact": all(r["repeat_equal"] for r in rows),
           "first_failing_M": next((r["M"] for r in rows if not r["equal_single"]), None)}
    print(name, {k: res[k] for k in ("all_batch_invariant", "all_repeat_exact", "first_failing_M")}, [r["M"] for r in rows if not r["equal_single"]], flush=True)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); a = ap.parse_args()
    torch.manual_seed(20260902)
    out = {}
    H = 5120
    x = torch.randn((256, H), dtype=DT, device=DEV) * 2; res = torch.randn((256, H), dtype=DT, device=DEV)
    w = (torch.randn(H, dtype=torch.float32, device=DEV) * 0.1) + 1.0
    out["gemma_rms_norm"] = rowwise("gemma rms_norm(hidden 5120, fp32 weight)", lambda t, _: ir.ops.rms_norm(t, w, 1e-6), x)
    def fused(t, r):
        t2 = t.clone(); r2 = r.clone(); o, rr = ir.ops.fused_add_rms_norm(t2, r2, w, 1e-6); return torch.cat([o, rr], dim=-1)
    out["gemma_fused_add_rms_norm"] = rowwise("gemma fused_add_rms_norm(hidden 5120)", fused, x, res)
    wq = torch.randn(256, dtype=DT, device=DEV) * 0.1 + 1.0
    xq = torch.randn((256 * 12, 256), dtype=DT, device=DEV)
    out["qk_head_rms_norm"] = rowwise("q/k head rms_norm(256)", lambda t, _: ir.ops.rms_norm(t, wq, 1e-6), xq)
    wg = torch.randn(128, dtype=DT, device=DEV) * 0.1 + 1.0
    xg = torch.randn((256 * 24, 128), dtype=DT, device=DEV); zg = torch.randn((256 * 24, 128), dtype=DT, device=DEV)
    for nbg in (True, False):
        out[f"gdn_gated_rms_norm_nbg_{nbg}"] = rowwise(f"gdn gated rmsnorm_fn(128, z, norm_before_gate={nbg})",
            lambda t, z, nbg=nbg: rmsnorm_fn(t, wg, None, z=z, eps=1e-6, group_size=None, norm_before_gate=nbg, activation="silu"), xg, zg)
    # ---- FA prefill (paged, causal, q len == kv len) ----
    heads, kv_heads, hd, block = 12, 2, 256, 64; NSEQ = 64
    lens = [24 + (i % 17) for i in range(NSEQ)]; bps = 1
    nblocks = NSEQ * bps + 4
    kc = torch.randn((nblocks, block, kv_heads, hd), dtype=DT, device=DEV); vc = torch.randn((nblocks, block, kv_heads, hd), dtype=DT, device=DEV)
    qs = [torch.randn((L, heads, hd), dtype=DT, device=DEV) for L in lens]
    table = torch.arange(NSEQ * bps, dtype=torch.int32, device=DEV).view(NSEQ, bps); scale = 1.0 / math.sqrt(hd)
    def fa(seqs):
        q = torch.cat([qs[s] for s in seqs]); cu = torch.tensor([0] + [sum(lens[s] for s in seqs[:k + 1]) for k in range(len(seqs))], dtype=torch.int32, device=DEV)
        used = torch.tensor([lens[s] for s in seqs], dtype=torch.int32, device=DEV); o = torch.empty_like(q)
        flash_attn_varlen_func(q=q, k=kc, v=vc, out=o, cu_seqlens_q=cu, max_seqlen_q=int(used.max()), seqused_k=used, max_seqlen_k=int(used.max()),
                               softmax_scale=scale, causal=True, block_table=table[torch.tensor(seqs, device=DEV)].contiguous(), fa_version=2)
        torch.xpu.synchronize(); return o
    refs = [fa([i]) for i in range(NSEQ)]
    rows = []
    for B in [1, 2, 4, 8, 16, 17, 24, 31, 32, 33, 48, 64]:
        seqs = list(range(B)); o = fa(seqs); o2 = fa(seqs); off = 0; ok = True
        for s in seqs:
            ok &= eq(o[off:off + lens[s]], refs[s]); off += lens[s]
        rows.append({"B": B, "tokens": sum(lens[:B]), "equal_single": bool(ok), "repeat_equal": eq(o, o2)})
    out["fa_prefill_paged"] = {"op": "flash_attn_varlen_func prefill (paged, causal)", "rows": rows, "all_batch_invariant": all(r["equal_single"] for r in rows),
                              "all_repeat_exact": all(r["repeat_equal"] for r in rows), "first_failing_B": next((r["B"] for r in rows if not r["equal_single"]), None)}
    print("fa prefill", {k: out["fa_prefill_paged"][k] for k in ("all_batch_invariant", "all_repeat_exact", "first_failing_B")}, flush=True)
    a.out.write_text(json.dumps(out, indent=1)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
