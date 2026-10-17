#!/usr/bin/env python3
"""Is a one-launch MTP check bitwise equal to plain one-token decoding, at every context length?

The server's `b70-fa-verify-rows` overlay computes the q_len rows of a check step as q_len separate one-token decode
calls (each shortened to its own length), so every row equals plain decoding. vllm-xpu-kernels' "spec-decode fast
path" does the same rows in one launch, but the split-K decode kernel then picks its number of key splits for a
batch of q_len pseudo-sequences (`get_num_splits`, flash_api.cpp), where a plain decode picks it for a batch of one.
Each row's key partition is ceil(its key tiles / splits), so a different split count is different arithmetic.

Arms per length L (the newest row's key count; row j has L - (q_len - 1 - j) keys):
  rows      the overlay: q_len one-token calls, each with its own seqused_k and max_seqlen_k (the reference)
  fast      the kernel's fast path as the server would get it without the overlay
  pinned    one launch like the fast path, with the split count a plain decode of the rows picks, passed explicitly;
            only where all q_len rows pick the same count (elsewhere an overlay would fall back to `rows`)
Recorded per L: rows of `fast` and `pinned` equal to `rows`, and the predicted split counts. 12 query heads, 2
key/value heads, head size 256, FP16 paged cache (pages of each of `--pages`), one card.
"""
import argparse
import json
import time

import torch
from vllm_xpu_kernels import flash_attn_interface as fai
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func

ap = argparse.ArgumentParser()
ap.add_argument("--ranges", default="1537:30000:7,30000:34000:61,99000:99600:13,199000:199300:17,245000:245300:29")
ap.add_argument("--pages", default="832,1280")
ap.add_argument("--qlen", type=int, default=6)
ap.add_argument("--overlay", default="", help="b70_fa_verify_rows.py: take the one-launch split counts from its "
                                              "_lone_splits (the code under test) instead of the mirror here")
ap.add_argument("--out", required=True)
a = ap.parse_args()

HQ, HKV, D = 12, 2, 256
dev = "xpu"
torch.manual_seed(0)
CORES = fai._infer_num_xe_cores(torch.device(dev))
_props = torch.xpu.get_device_properties(0)
PROPS = {k: getattr(_props, k) for k in dir(_props) if not k.startswith("_")
         and isinstance(getattr(_props, k), (int, str, bool))}
print("xe cores (interface):", CORES, "properties:", json.dumps(PROPS), flush=True)


def splits(batch, max_k, block):  # mirror of flash_api.cpp get_num_splits
    kv_tile, sg, cap = (16, 1, 16) if block == 16 else (32, 2, 32) if block == 32 else (64, 4, 64)
    tiles = (max_k + kv_tile - 1) // kv_tile
    if tiles < 16:
        return 1
    slots = CORES * 4 // sg
    wgs = batch * HKV
    if wgs >= slots and tiles < 64:
        return 1
    s = max(max(1, (4 * slots + wgs - 1) // wgs), max(1, tiles // 12))
    s = min(s, max(2, 128 * CORES // max(1, batch * HQ)))
    return max(1, min(s, max(1, tiles // 4), 32, cap))


lone = lambda max_k, block: splits(1, max_k, block)
if a.overlay:
    import importlib.util
    _spec = importlib.util.spec_from_file_location("b70_fa_verify_rows", a.overlay)
    _ov = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_ov)
    lone = lambda max_k, block: _ov._lone_splits(max_k, block, CORES, HQ, HKV)
    print("one-launch split counts from", a.overlay, flush=True)

lengths = []
for rng in a.ranges.split(","):
    lo, hi, step = (int(x) for x in rng.split(":"))
    lengths += list(range(lo, hi, step))
q = torch.randn(a.qlen, HQ, D, dtype=torch.float16, device=dev)
one = torch.tensor([0, 1], dtype=torch.int32, device=dev)
cuq = torch.tensor([0, a.qlen], dtype=torch.int32, device=dev)
cu_spec = torch.arange(a.qlen + 1, dtype=torch.int32, device=dev)
back = (a.qlen - 1 - torch.arange(a.qlen, device=dev)).to(torch.int32)


def census(page):
    nblk = (max(lengths) + page - 1) // page
    kc = torch.randn(nblk, page, HKV, D, dtype=torch.float16, device=dev)
    vc = torch.randn(nblk, page, HKV, D, dtype=torch.float16, device=dev)
    bt = torch.arange(nblk, dtype=torch.int32, device=dev).view(1, nblk)
    bt_spec = bt.repeat_interleave(a.qlen, dim=0)

    def rows_ref(L):
        out = torch.empty_like(q)
        for j in range(a.qlen):
            n = L - (a.qlen - 1 - j)
            flash_attn_varlen_func(out=out[j:j + 1], q=q[j:j + 1], k=kc, v=vc, cu_seqlens_q=one,
                                   seqused_k=torch.tensor([n], dtype=torch.int32, device=dev), max_seqlen_q=1,
                                   max_seqlen_k=n, softmax_scale=D ** -0.5, causal=True, block_table=bt,
                                   window_size=(-1, -1))
        return out

    def fast(L):
        out = torch.empty_like(q)
        flash_attn_varlen_func(out=out, q=q, k=kc, v=vc, cu_seqlens_q=cuq,
                               seqused_k=torch.tensor([L], dtype=torch.int32, device=dev), max_seqlen_q=a.qlen,
                               max_seqlen_k=L, softmax_scale=D ** -0.5, causal=True, block_table=bt,
                               window_size=(-1, -1))
        return out

    def pinned(L, ns):  # the call b70_fa_verify_rows 0.2.0 makes (B70_FA_VERIFY_ROWS_ONE_LAUNCH=1)
        out = torch.empty_like(q)
        flash_attn_varlen_func(out=out, q=q, k=kc, v=vc, cu_seqlens_q=cu_spec,
                               seqused_k=torch.tensor([L], dtype=torch.int32, device=dev) - back, max_seqlen_q=1,
                               max_seqlen_k=L, softmax_scale=D ** -0.5, causal=True, block_table=bt_spec,
                               window_size=(-1, -1), num_splits_kv=ns)
        return out

    rows, t0 = [], time.time()
    summ = dict(page=page, points=0, fast_all_equal=0, fast_prediction_right=0, pinned_used=0, pinned_all_equal=0)
    for L in lengths:
        ref = rows_ref(L)
        s_rows = [lone(L - (a.qlen - 1 - j), page) for j in range(a.qlen)]
        s_fast = splits(a.qlen, L, page)
        f = fast(L)
        fe = sum(bool(torch.equal(f[j], ref[j])) for j in range(a.qlen))
        r = dict(L=L, splits_plain_rows=s_rows, splits_fast=s_fast, fast_rows_equal=fe)
        if len(set(s_rows)) == 1:
            p = pinned(L, s_rows[0])
            r["pinned_rows_equal"] = sum(bool(torch.equal(p[j], ref[j])) for j in range(a.qlen))
            summ["pinned_used"] += 1
            summ["pinned_all_equal"] += r["pinned_rows_equal"] == a.qlen
        summ["points"] += 1
        summ["fast_all_equal"] += fe == a.qlen
        # predicted: fast equals the rows exactly when every row's plain split count is the fast path's count
        summ["fast_prediction_right"] += (fe == a.qlen) == all(s == s_fast for s in s_rows)
        rows.append(r)
    summ["seconds"] = round(time.time() - t0, 1)
    print(json.dumps(summ), flush=True)
    bad = [r for r in rows if r.get("pinned_rows_equal", a.qlen) != a.qlen]
    print("pinned mismatches:", json.dumps(bad[:10]), flush=True)
    del kc, vc
    torch.xpu.empty_cache()
    return dict(summary=summ, rows=rows)


results = [census(int(p)) for p in a.pages.split(",")]
json.dump(dict(device=torch.xpu.get_device_name(0), xe_cores=CORES, properties=PROPS, qlen=a.qlen,
               missing_kernel_fallback=sorted(fai._warned_missing_configs), pages=results), open(a.out, "w"))
