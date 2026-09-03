#!/usr/bin/env python3
"""Batch-invariance census of the two per-sequence decode kernels on XPU.

Operator diagnostic (R151). For the GDN decode kernel (torch.ops._xpu_C.gdn_attention,
non-spec decode path) and the full-attention paged decode kernel
(flash_attn_varlen_func, q len 1), build 64 independent sequences with fixed seeds,
take each sequence's single-sequence call as its reference, then check for batch
sizes B in 1..64 that every sequence's output (and, for GDN, its updated conv and
SSM state) is bitwise equal to its reference, that a permuted batch maps back
exactly, and that repeats are bitwise identical. Production per-rank TP2 shapes
from the Qwen3.8-27B config; float16 as served.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import torch
import vllm_xpu_kernels._xpu_C  # noqa: F401
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func

DEV = torch.device("xpu:0")
DT = torch.float16
NSEQ = 64
BATCHES = [1, 2, 4, 8, 16, 24, 31, 32, 33, 40, 48, 64]


def eq(a, b):
    return bool(torch.equal(a, b))


def maxdiff(a, b):
    return float((a.float() - b.float()).abs().max()) if a.numel() else 0.0


# ---------------- GDN decode ----------------
def gdn_census(seed: int) -> dict:
    torch.manual_seed(seed)
    nk, nv, dk, dv, tp, width = 16, 48, 128, 128, 2, 4
    lk, lv = nk // tp, nv // tp
    qkvz_w = lk * (2 * dk + 2 * dv * nv // nk)
    ba_w = lk * (2 * nv // nk)
    qkv_w = lk * (2 * dk + dv * nv // nk)
    cache = 256
    qkvz = torch.randn((NSEQ, qkvz_w), dtype=DT, device=DEV)
    ba = torch.randn((NSEQ, ba_w), dtype=DT, device=DEV)
    conv0 = torch.randn((cache, width - 1, qkv_w), dtype=DT, device=DEV)
    ssm0 = (torch.randn((cache, lv, dv, dk), dtype=torch.float32, device=DEV) * 0.1).to(DT)
    conv_w = torch.randn((qkv_w, width), dtype=DT, device=DEV) * 0.2
    conv_b = torch.randn((qkv_w,), dtype=DT, device=DEV) * 0.1
    a_log = torch.randn((lv,), dtype=torch.float32, device=DEV)
    dt_bias = torch.randn((lv,), dtype=DT, device=DEV)

    def call(idx: torch.Tensor, conv, ssm):
        B = idx.numel()
        out = torch.zeros((B, lv, dv), dtype=DT, device=DEV)
        z = torch.empty_like(out)
        qs = torch.arange(B + 1, dtype=torch.int32, device=DEV)
        his = torch.ones(B, dtype=torch.bool, device=DEV)
        torch.ops._xpu_C.gdn_attention(
            out, z, qkvz[idx].contiguous(), ba[idx].contiguous(), nk, nv, dk, dv,
            conv, ssm, conv_w, conv_b, "silu", a_log, dt_bias,
            0, B, 0, his, qs, None, idx.to(torch.int32).contiguous(), None, None, None, None, B, tp, False)
        torch.xpu.synchronize()
        return out, z

    ref_out = torch.empty((NSEQ, lv, dv), dtype=DT, device=DEV)
    ref_z = torch.empty_like(ref_out)
    ref_conv = torch.empty((NSEQ, width - 1, qkv_w), dtype=DT, device=DEV)
    ref_ssm = torch.empty((NSEQ, lv, dv, dk), dtype=DT, device=DEV)
    for i in range(NSEQ):
        conv = conv0.clone(); ssm = ssm0.clone()
        o, z = call(torch.tensor([i], device=DEV), conv, ssm)
        ref_out[i] = o[0]; ref_z[i] = z[0]; ref_conv[i] = conv[i]; ref_ssm[i] = ssm[i]
    rows = []
    for B in BATCHES:
        idx = torch.arange(B, device=DEV)
        conv = conv0.clone(); ssm = ssm0.clone()
        o, z = call(idx, conv, ssm)
        conv2 = conv0.clone(); ssm2 = ssm0.clone()
        o2, z2 = call(idx, conv2, ssm2)
        perm = torch.randperm(B, device=DEV)
        conv3 = conv0.clone(); ssm3 = ssm0.clone()
        o3, z3 = call(idx[perm], conv3, ssm3)
        rows.append({
            "B": B,
            "out_equal_single": eq(o, ref_out[:B]), "z_equal_single": eq(z, ref_z[:B]),
            "conv_state_equal_single": eq(conv[:B], ref_conv[:B]), "ssm_state_equal_single": eq(ssm[:B], ref_ssm[:B]),
            "repeat_equal": eq(o, o2) and eq(z, z2) and eq(conv[:B], conv2[:B]) and eq(ssm[:B], ssm2[:B]),
            "permuted_equal_single": eq(o3, ref_out[:B][perm]) and eq(ssm3[:B][perm], ref_ssm[:B][perm]),
            "max_abs_diff_out": maxdiff(o, ref_out[:B]), "max_abs_diff_ssm": maxdiff(ssm[:B], ref_ssm[:B]),
        })
        print("gdn", rows[-1], flush=True)
    return {"kernel": "torch.ops._xpu_C.gdn_attention (non-spec decode)", "rows": rows,
            "all_batch_invariant": all(r["out_equal_single"] and r["z_equal_single"] and r["conv_state_equal_single"] and r["ssm_state_equal_single"] and r["permuted_equal_single"] for r in rows),
            "all_repeat_exact": all(r["repeat_equal"] for r in rows),
            "first_failing_B": next((r["B"] for r in rows if not (r["out_equal_single"] and r["ssm_state_equal_single"])), None)}


# ---------------- full-attention paged decode ----------------
def fa_census(seed: int, num_splits: int) -> dict:
    torch.manual_seed(seed)
    heads, kv_heads, hd, block = 12, 2, 256, 64
    kv_lens = [40 + 3 * i for i in range(NSEQ)]  # 40..229 tokens, spans 1-4 blocks
    blocks_per_seq = 4
    nblocks = NSEQ * blocks_per_seq + 8
    kc = torch.randn((nblocks, block, kv_heads, hd), dtype=DT, device=DEV)
    vc = torch.randn((nblocks, block, kv_heads, hd), dtype=DT, device=DEV)
    q = torch.randn((NSEQ, heads, hd), dtype=DT, device=DEV)
    table = torch.arange(NSEQ * blocks_per_seq, dtype=torch.int32, device=DEV).view(NSEQ, blocks_per_seq)
    scale = 1.0 / math.sqrt(hd)

    def call(idx: torch.Tensor):
        B = idx.numel()
        out = torch.empty((B, heads, hd), dtype=DT, device=DEV)
        seqused = torch.tensor([kv_lens[int(i)] for i in idx.tolist()], dtype=torch.int32, device=DEV)
        flash_attn_varlen_func(q=q[idx].contiguous(), k=kc, v=vc, out=out,
                               cu_seqlens_q=torch.arange(B + 1, dtype=torch.int32, device=DEV), max_seqlen_q=1,
                               seqused_k=seqused, max_seqlen_k=int(seqused.max()), softmax_scale=scale, causal=True,
                               block_table=table[idx].contiguous(), num_splits=num_splits, fa_version=2)
        torch.xpu.synchronize()
        return out

    ref = torch.empty((NSEQ, heads, hd), dtype=DT, device=DEV)
    for i in range(NSEQ):
        ref[i] = call(torch.tensor([i], device=DEV))[0]
    rows = []
    for B in BATCHES:
        idx = torch.arange(B, device=DEV)
        o = call(idx); o2 = call(idx)
        perm = torch.randperm(B, device=DEV); o3 = call(idx[perm])
        rows.append({"B": B, "out_equal_single": eq(o, ref[:B]), "repeat_equal": eq(o, o2),
                     "permuted_equal_single": eq(o3, ref[:B][perm]), "max_abs_diff_out": maxdiff(o, ref[:B])})
        print("fa", num_splits, rows[-1], flush=True)
    return {"kernel": f"flash_attn_varlen_func paged decode (fa_version=2, num_splits={num_splits})", "rows": rows,
            "all_batch_invariant": all(r["out_equal_single"] and r["permuted_equal_single"] for r in rows),
            "all_repeat_exact": all(r["repeat_equal"] for r in rows),
            "first_failing_B": next((r["B"] for r in rows if not r["out_equal_single"]), None)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20260902)
    a = ap.parse_args()
    res = {"schema": "qwen38-fp8-gdn-attention-decode-batch-census.v1", "device": torch.xpu.get_device_name(0),
           "torch": torch.__version__, "batches": BATCHES, "sequences": NSEQ}
    res["gdn_decode"] = gdn_census(a.seed)
    res["fa_decode_num_splits_0"] = fa_census(a.seed, 0)
    res["fa_decode_num_splits_1"] = fa_census(a.seed, 1)
    a.out.write_text(json.dumps(res, indent=1))
    print({k: (v["all_batch_invariant"], v["all_repeat_exact"], v["first_failing_B"]) for k, v in res.items() if isinstance(v, dict) and "rows" in v})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
