#!/usr/bin/env python3
# idxsplit-1 reset audit (2026-11-13): recomputes, from the engine's formulas (b/: mt_arena_floats, mt_offsets, the
# arena setup in backend_sycl_v41.hpp ~4166-4203, mt_alloc, tpm_index's split path, ix_split, bcs_push) and the
# admitted geometry (model/directory_v41.hpp), the largest offset every idxsplit-1 read / write can reach at the long
# documents, against its allocation. The arena layout is checked against the flag words the binaries printed.
# Usage: python3 -I reset_audit.py  (writes nothing; print to a file)
import re, sys

W = "/home/steve/dsv41-work"
h, mid, qh, hd, ototal, HC_SEG = 5120, 2304, 64, 512, 8192, 8  # directory_v41.hpp (admitted geometry)
MTX = 256; MTB = 2 * MTX; TB = MTB; A = TB + 8                  # OWN41_MTX default 256; OWN_PX_BIG: mtb_n() = 512
dr = 8 * 6 * 32 + 32                                           # dr_arena_floats() (draft.inc)
r16 = lambda v: (v + 15) & ~15
U32 = 2 ** 32

def layout(idx):
    xoa = 1024; xob = xoa + ototal; xact = xob + h; xeng = xact + 7 * mid; base = xeng + 10 * h
    maf = A * (ototal + h + 7 * mid + 10 * h) + dr + A * h + A * qh * hd + (16 + 2 * A * 50 * HC_SEG)  # mt_dsplit on
    if idx: maf += 16 + 8 * 512 * TB
    xhoM = base + A * (ototal + h + 7 * mid + 10 * h) + dr + A * h
    xdsA = r16(xhoM + A * qh * hd); xdsF = xdsA + A * 50 * HC_SEG
    xidxM = r16(xdsF + A * 50 * HC_SEG) if idx else 0
    nf = base + maf; xbf = r16(nf); nfq = xbf + 16 * 6 + 16
    return dict(xdsF_end=xdsF + A * 50 * HC_SEG, xidxM=xidxM, idx_end=xidxM + 8 * 512 * TB if idx else 0,
                nf=nf, xbf=xbf, nfq=nfq)

def logged_xbf(path):
    try:
        m = re.search(r"flags at arena word (\d+)", open(path).read(4096))
        return int(m.group(1)) if m else None
    except OSError:
        return None

def ix_split(M, tp=6):  # equal weights (OWN_IDX_SPLIT_W unset)
    t0, t1, prev, cw, Wt = [], [], 0, 0, tp
    for d in range(tp):
        cw += 1
        e = M if d == tp - 1 else min(M, (M * cw + Wt // 2) // Wt)
        t0.append(prev); prev = max(prev, e); t1.append(prev)
    return t0, t1

def qsel_span(n): return ((n + 1023) // 1024 + 7) // 8 * 8

PX_MIN = 128  # OWN_PX_MIN default (backend_sycl_v41.hpp)
def blocks(n, pblock=512, px_min=PX_MIN):
    out, i = [], 0  # own_run_v41.cpp's loop with px_block_take (OWN_PX_BIG)
    while i < n:
        m = min(pblock, n - i)
        if m > MTX: m = m if (m <= MTB and m % 2 == 0 and m // 2 >= px_min) else MTX
        out.append(m); i += m
    return out

L0, L1 = layout(0), layout(1)
print("== arena (floats; 4-byte words)")
print(f"production (OWN_IDX_SPLIT=0): xbf {L0['xbf']}  arena {L0['nfq']} floats = {L0['nfq'] * 4} bytes")
print(f"idxsplit-1 (OWN_IDX_SPLIT=1): xidxM {L1['xidxM']} (previous region ends {L1['xdsF_end']})  idx region end "
      f"{L1['idx_end']}  nf {L1['nf']}  xbf {L1['xbf']}  arena {L1['nfq']} floats = {L1['nfq'] * 4} bytes")
for tag, p, want in (("lc107b x34k_px (production binary)", f"{W}/runs/lc107b/x34k_px.log", L0['xbf']),
                     ("is1 k512 (OWN_IDX_SPLIT=1)", f"{W}/idxsplit/runs/tr/k512.log", L1['xbf']),
                     ("is1 x34k_on (OWN_IDX_SPLIT=1)", f"{W}/idxsplit/runs/lg/x34k_on.log", L1['xbf'])):
    g = logged_xbf(p)
    print(f"  logged flag word, {tag}: {g}  {'== computed' if g == want else '!= computed ' + str(want)}")
print(f"  idx region inside the arena, before the copy flags: {L1['xidxM'] >= L1['xdsF_end'] and L1['idx_end'] <= L1['xbf']}"
      f" (slack {L1['xbf'] - L1['idx_end']} floats); 64-byte aligned: {L1['xidxM'] % 16 == 0}; "
      f"largest float offset {L1['nfq'] - 1} < 2^32: {L1['nfq'] < U32}; bytes < 2^31: {L1['nfq'] * 4 < 2 ** 31}")
SLOT = 512 * TB
print(f"  slot k = [xidxM + k*{SLOT}, +{SLOT}) floats; slot 7 ends at {L1['xidxM'] + 8 * SLOT} == idx end")

for doc, n in (("x19k", 18692), ("x34k", 33815), ("x95k", 95497)):
    mx = (n + 256 + 1023) // 1024 * 1024  # one.sh's max context
    SS = mx + 64
    bl = blocks(n)
    sizes = sorted(set(bl), reverse=True)
    print(f"\n== {doc}: {n} prompt tokens, max_seq {mx}, score/cand row stride SS {SS}, {len(bl)} blocks {dict((s, bl.count(s)) for s in sizes)}")
    worst_push = 0; worst_cix = 0
    for m in sizes:
        hn = m // 2 if (m % 2 == 0 and PX_MIN <= m // 2 <= MTX) else 0  # px_ok: even, halves of px_min .. MTX
        Ms = [hn] if hn else [m]
        for M in Ms:
            split = M >= 32 and M <= MTX and hn > 0  # long runs: only blocks as halves on the copy engine split
            t0, t1 = ix_split(M)
            sh = [b - a for a, b in zip(t0, t1)]
            for pt in ([0, hn] if hn else [0]):
                for slot in range(8):
                    off = L1['xidxM'] + slot * SLOT + pt * 512
                    for c in range(6):
                        if not split: continue
                        a, b = off + t0[c] * 512, off + t1[c] * 512
                        assert a % 16 == 0 and b % 16 == 0 and a < U32 and b < U32
                        worst_push = max(worst_push, b)
                worst_cix = max(worst_cix, (pt + M) * 512)
            print(f"  block {m}: {'halves of ' + str(hn) if hn else 'plain'}; split {split}; shares {sh} "
                  f"(largest {max(sh)}); push bytes per peer <= {max(sh) * 2048}")
    print(f"  bcs_push: largest destination end {worst_push} (idx region end {L1['idx_end']}): "
          f"{'inside' if worst_push <= L1['idx_end'] else 'OUTSIDE'}; source = the same offsets in the own arena")
    print(f"  cidxm / CidxFillM / selects' lists: largest int index {worst_cix} <= slot {SLOT}: {worst_cix <= SLOT}")
    lmax = n  # layer-20 source (ratio 1): rows after token t = position + 1 <= n
    T_ = (lmax + 31) // 32 * 32
    print(f"  scores: rows < T_ = {T_} < SS {SS}: {T_ < SS}; buffer SS*TB = {SS * TB} floats ({SS * TB * 4} bytes), "
          f"largest index {511 * SS + T_ - 1} < {SS * TB}: {511 * SS + T_ - 1 < SS * TB}")
    print(f"  candidate masks (bytes): largest index {511 * SS + lmax - 1} < {SS * TB}: {511 * SS + lmax - 1 < SS * TB}")
    print(f"  block lists (blm, 2112 ints per token): out[0..2048] -> largest index {511 * 2112 + 2048} < {2112 * TB}: "
          f"{511 * 2112 + 2048 < 2112 * TB}; IndexerScoreBCM reads b[1 + i/8], i < 128*128 -> b[2048]")
    gpt = ((T_) + 127) // 128
    print(f"  IndexerScoreBM: gpt {gpt} (block's lmax), share grid <= 43*gpt*128 = {43 * gpt * 128} items "
          f"(full half: {256 * gpt * 128}); row j = (grp % gpt)*128 + lid <= {gpt * 128 - 1} (int)")
    print(f"  register selects: qr = qsel_span(lmax) = {qsel_span(lmax)} (<= 96: TopKSelMQ, else TopKSelM), "
          f"qb (layer 20) = qsel_span(blocks {(lmax + 7) // 8}) = {qsel_span((lmax + 7) // 8)} (<= 32: TopKSelMBQ)")
    print(f"  rope tables: P = max_seq = {mx} positions; largest entry read (pos+u0+un-1)*32+31 <= {(n - 1) * 32 + 31} < {mx * 32}")
    print(f"  ik mirror rows (layer 20: max_seq + 2 = {mx + 2}): largest row read {lmax - 1}")
