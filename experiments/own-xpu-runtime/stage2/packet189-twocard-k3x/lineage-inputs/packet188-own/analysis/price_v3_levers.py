#!/usr/bin/env python3
"""Price the next two-card levers on the V3 record line (packet187, 60.659520 tok/s). CPU-only, read-only.

Replays the 1,188 retained WS128 intervals (replay_v3.py reproduces 60.65951991975228 exactly) through the record
metric (per prompt 99000/sum(T), median of class medians). Base identity per interval (ms):
    T = max(D, R + C + Bd) + max(B, A + offset) + G
Every lever below edits only the components it touches, per interval. Inputs are labelled:
    measured     = a retained receipt on the V3 line (packet186 bracket / packet187 chain) or this line's ledger
    transferred  = a receipt from another identity (older line, micro, other lane)
    assumed      = engineering assumption, with a stated range
Writes price-v3-output.json next to this script.
"""
import importlib.util, io, contextlib, itertools, json, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('rv', HERE / 'replay_v3.py')
rv = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(rv)
ROWS = rv.load_view(rv.P187 / 'repeat-1')
assert len(ROWS) == 1188
BASE = rv.metric(ROWS)
assert abs(BASE - 60.65951991975228) < 1e-9
HITS = [x for x in ROWS if x['hit']]
MISS = [x for x in ROWS if not x['hit']]
out = dict(base=BASE, hits=len(HITS), misses=len(MISS),
           pooled_mean_interval_ms=st.mean(x['elapsed_ms'] for x in ROWS), metric_equivalent_ms=1000 / BASE)


def T(x, D=None, R=None, C=None, Bd=None, B=None, A=None, G=None):
    D = x['D'] if D is None else D; R = x['R'] if R is None else R; C = x['C'] if C is None else C
    Bd = x['Bd'] if Bd is None else Bd; B = x['B'] if B is None else B; A = x['A'] if A is None else A
    G = x['G'] if G is None else G
    return max(D, R + C + Bd) + max(B, A + x['spec_start_offset_ms']) + G


assert max(abs(T(x) - x['elapsed_ms']) for x in ROWS) < 1e-9


def gain(f):
    return 100 * (rv.metric(ROWS, [f(x) for x in ROWS]) / BASE - 1)


def solve(fn, lo, hi, target=2.0):
    """Smallest parameter in [lo, hi] reaching target gain (fn increasing); None if unreachable."""
    if fn(hi) < target:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if fn(mid) >= target:
            hi = mid
        else:
            lo = mid
    return hi


# ---------------- thresholds for +2 % on the V3 line ----------------
thr = {}
thr['B_only_ms_per_half'] = solve(lambda c: gain(lambda x: T(x, B=x['B'] - c)), 0, 3)
thr['B_only_saturation_gain_pct'] = gain(lambda x: T(x, B=x['B'] - 5))
thr['B_only_curve_pct'] = {str(c): round(gain(lambda x: T(x, B=x['B'] - c)), 3) for c in (0.05, 0.1, 0.177, 0.2, 0.3, 0.356, 0.384, 0.463, 0.6)}
thr['D_only_ms_per_hit'] = solve(lambda c: gain(lambda x: T(x, D=x['D'] - c) if x['hit'] else T(x)), 0, 1.6)
thr['D_only_saturation_gain_pct'] = gain(lambda x: T(x, D=0) if x['hit'] else T(x))
thr['C_only_ms_per_miss'] = solve(lambda c: gain(lambda x: T(x, C=max(0, x['C'] - c))), 0, 11)
thr['A_only_gain_pct_at_1ms'] = gain(lambda x: T(x, A=x['A'] - 1.0))
thr['symmetric_ms_per_half_A_B_C'] = solve(lambda c: gain(lambda x: T(x, A=x['A'] - c, B=x['B'] - c, C=max(0, x['C'] - c))), 0, 3)
mean_hit_like = {}


def rescue(f):
    # convert a uniform fraction f of misses into hits: no R/C on the ready side, same B/A/Bd/D/G
    def g(x):
        if x['hit']:
            return T(x)
        return f * T(x, R=0.0, C=0.0) + (1 - f) * T(x)
    return gain(g)


thr['miss_rescue_fraction'] = solve(rescue, 0, 1)
out['thresholds_for_2pct'] = thr

# ---------------- slack budgets (measured, packet187 WS128) ----------------
slack = [x['B'] - x['A'] - x['spec_start_offset_ms'] for x in HITS]
win = [x['D'] - x['Bd'] for x in HITS]
out['rank0_budget_per_hit_ms'] = dict(race_slack_mean=st.mean(slack), draft_window_mean=st.mean(win),
                                      total_idle_mean=st.mean(s + w for s, w in zip(slack, win)),
                                      rank1_busy=st.mean(x['D'] + x['B'] for x in HITS), rank0_busy=st.mean(x['Bd'] + x['A'] for x in HITS))
# ideal balance bound: equalise the two ranks' per-hit busy time, no dependency loss, misses unchanged
def ideal(x):
    if not x['hit']:
        return T(x)
    r1, r0 = x['D'] + x['B'], x['Bd'] + x['A'] + x['spec_start_offset_ms']
    return max((r1 + r0) / 2, x['D']) + x['G']
out['ideal_rebalance_ceiling_pct'] = gain(ideal)

# ---------------- (1) V3 split variants ----------------
S1, S1_LO, S1_HI = 0.463, 0.43, 0.49          # measured packet186 (B_u - B_v3)/2; range assumed +-7 %
C0_MEAS, C0_BD = 0.483, 0.513                  # measured rank-0 layer_body (packet186 anchor) / Bd per layer incl. fixed part


def k3(x, s1=S1, c0=C0_BD, a_cut=0.0):
    # layers 24-26 on rank 0: one more GDN layer (26) moves from rank 1's B to rank 0's boundary
    return T(x, Bd=x['Bd'] + c0, B=x['B'] - s1, A=x['A'] - a_cut)


v = {}
for s1, c0 in itertools.product((S1_LO, S1, S1_HI), (C0_MEAS, C0_BD, 0.55)):
    v[f's1={s1} c0={c0}'] = round(gain(lambda x: k3(x, s1, c0)), 3)
out['k3_24_26_grid'] = v
out['k3_central'] = gain(lambda x: k3(x))
out['k3_hit_saving_ms'] = st.mean(x['elapsed_ms'] - k3(x) for x in HITS)
out['k3_miss_change_ms'] = st.mean(k3(x) - x['elapsed_ms'] for x in MISS)
out['k3_rank0_binds_fraction'] = st.mean(float(x['B'] - S1 < x['A'] + x['spec_start_offset_ms']) for x in HITS)
out['k3_ready_bound_by_boundary_fraction'] = st.mean(float(x['Bd'] + C0_BD > x['D']) for x in HITS)
out['k3_plus_rank0_A_cut_for_2pct_ms'] = solve(lambda a: gain(lambda x: k3(x, a_cut=a)), 0, 1)
out['k3_plus_rank0_A_cut_curve'] = {str(a): round(gain(lambda x: k3(x, a_cut=a)), 3) for a in (0.05, 0.1, 0.15, 0.2, 0.3)}
# k=4 (24-27) is not available: layer 27 is QSA (36 GDN + 12 QSA, every 4th layer) and the boundary island forbids QSA.
out['k4_24_27_if_it_were_gdn'] = gain(lambda x: T(x, Bd=x['Bd'] + 2 * C0_BD, B=x['B'] - 2 * S1))
# 23-25: layer 23 (QSA) leaves the speculative half A (and C on misses) and joins the boundary; rank 1 unchanged
def k23(x, a23=0.50, b23=0.55):
    return T(x, A=x['A'] - a23, C=max(0, x['C'] - a23) if not x['hit'] else 0.0, Bd=x['Bd'] + b23)
out['split_23_25'] = {f'a23={a} b23={b}': round(gain(lambda x: k23(x, a, b)), 3) for a, b in ((0.45, 0.50), (0.50, 0.55), (0.55, 0.65))}
# k=1 (back to layer 25 only) for completeness
out['k1_25_only'] = gain(lambda x: T(x, Bd=x['Bd'] - C0_BD, B=x['B'] + S1))

# ---------------- (2) rank-1 half levers ----------------
# (2a) draft head (80,128 rows + argmax) to rank 0; trunk stays on rank 1
DH = 0.445348 + 0.026355   # transferred: packet158 cyclic replay head_gemv + argmax_publication (ms)
XFER = 0.050               # measured legs: 22.7-25.5 us per synchronous copy (packet165 two-card p105-transfers), export+import


def drafthead(x, dh=DH, xfer=XFER):
    off = x['spec_start_offset_ms']
    if x['hit']:
        trunk = x['D'] - dh
        sB = max(trunk, x['Bd'])
        sA = max(x['Bd'], trunk + xfer) + dh
        return max(sB + x['B'], sA + x['A'] + off) + x['G']
    ready = x['R'] + x['C'] + x['Bd']
    sB = max(x['D'] - dh, ready)
    sA = max(ready, x['D'] - dh + xfer) + dh
    return max(sB + x['B'], sA + x['A'] + off) + x['G']


out['drafthead_to_rank0'] = {f'dh={dh:.3f} xfer={xf}': round(gain(lambda x: drafthead(x, dh, xf)), 3)
                             for dh, xf in ((DH, XFER), (DH, 0.10), (0.40, 0.05), (0.52, 0.05))}
out['drafthead_plus_k3'] = gain(lambda x: drafthead(dict(x, Bd=x['Bd'] + C0_BD, B=x['B'] - S1)))
# (2b) target head on rank 1: packet93 head-transpose (block-transposed packed Q6_K head, un-split era)
out['head_transpose'] = {'measured lane-B engine transfer 0.177 ms': gain(lambda x: T(x, B=x['B'] - 0.177)),
                         'microbench 100% 0.384 ms (1.417 -> 1.033)': gain(lambda x: T(x, B=x['B'] - 0.384)),
                         'lane-A measured (record cards 0+1)': 'loss -2.369% / -2.8171% vs stronger control (packet93x, review15)'}
# (2c) draft line closure gaps (packet158): sum of positive gaps 0.48 ms; 20 % lab transfer
out['draft_gaps'] = {'100% (0.48 ms/hit)': gain(lambda x: T(x, D=x['D'] - 0.48) if x['hit'] else T(x)),
                     '20% (0.096 ms/hit)': gain(lambda x: T(x, D=x['D'] - 0.096) if x['hit'] else T(x)),
                     'host batching ceiling +0.9% (packet158) re-priced: 0.19 ms/hit': gain(lambda x: T(x, D=x['D'] - 0.19) if x['hit'] else T(x))}
# (2d) receipt / round-trip path: kernel foreground I/O port (no merge exists under V3)
RT = 0.023 - 0.005   # measured synchronous round trip 22.7-25.5 us; kernel store/stamp 5 us assumed


def kio(x, nd=2, nb=3, nbd=1, nc=2, na=1):
    if x['hit']:
        return T(x, D=x['D'] - nd * RT, B=x['B'] - nb * RT, Bd=x['Bd'] - nbd * RT, A=x['A'] - na * RT)
    return T(x, C=x['C'] - nc * RT, B=x['B'] - nb * RT, Bd=x['Bd'] - nbd * RT, A=x['A'] - na * RT)


out['kernel_io_v3'] = {'central (D2 B3 Bd1 C2 A1)': gain(kio), 'generous (D3 B5 Bd2 C4 A2)': gain(lambda x: kio(x, 3, 5, 2, 4, 2))}

# ---------------- (3) miss path ----------------
miss = {}
miss['remove all restore R (upper bound)'] = gain(lambda x: T(x, R=0.0))
miss['rank-1 B on misses = B on hits (warming upper bound, 0.223 ms)'] = gain(lambda x: T(x, B=x['B'] - (st.mean(m['B'] for m in MISS) - st.mean(h['B'] for h in HITS))) if not x['hit'] else T(x))
miss['boundary overlapped with C (impossible: Bd needs layer 23 of C) upper bound'] = gain(lambda x: T(x, Bd=0.0) if not x['hit'] else T(x))
miss['fuse C+Bd into one command (-0.02 ms dispatch, assumed)'] = gain(lambda x: T(x, Bd=x['Bd'] - 0.02) if not x['hit'] else T(x))
# packet144: 20 of 256 record misses have actual ids outside the 80,128-row prefix (same draft, same proposals on V3)
f20 = 20 / 256
miss['free rescue of the 20 out-of-prefix misses (packet144 upper bound)'] = rescue(f20)
out['miss_path'] = miss

# ---------------- (4) static snapshot: already in packet187 ----------------
out['static_snapshot'] = 'bundled (snapshot_host=static in packet187 selection); no further gain to price'
(HERE / 'price-v3-output.json').write_text(json.dumps(out, indent=1, default=float))
print(json.dumps(out, indent=1, default=float))
