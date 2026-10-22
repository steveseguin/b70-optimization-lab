#!/usr/bin/env python3
"""Lever synthesis 4: k3x critical-path model and prices (CPU-only, read-only on the repo).

Data: packet190's record chain WS128 (build/device-cards01-p190-a/WS128/run/repeat-1, 12 x 99 intervals, the
62.345282 record) and packet189's one-load bracket views (V3 / k3x / V3 / k3x / V3) for cross-checks.

Interval identity (packet85 model + V3 boundary, as lever syntheses 2/3):
    T = max(D, R + C + Bd) + max(B, A + offset) + G
  D   draft completion on rank 1. Under k3x (rank0_prepare=async) the op-9 command returns after the nonblocking host
      issue (0.43 ms), so D := draft_rows.draft_wall_ms (publication observed), never op 9 (packet189 boundary).
  Bd  rank-0 boundary command (op 15): GDN layers 24-26 for the verified token + copy-engine export (20,480 B).
  A   rank-0 next speculative half (layers 0-23, guessed token)      B  rank-1 half: layers 27-47 + full head
  R/C rank-0 rollback / corrected half (misses)                       G  unresolved control gaps
k3x topology: at emission rank 0 runs Bd and rank 1 runs D; both next halves start at ready = max(D, Bd) because rank 1's
B is queued behind the draft on its single in-order queue and rank 0's A needs the guess; on misses rank 0 is serial
(R -> C -> Bd) and rank 1 idles after the draft.

Reuses lever synthesis 2's loader/metric (packet188 analysis/replay_v3.py, imported read-only).
Writes model-k3x-output.json next to this script. Standard library only; run with nice -n 19.
"""
import importlib.util, json, statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2')
spec = importlib.util.spec_from_file_location('replay_v3', STAGE / 'packet188-twocard-k3-composite/analysis/replay_v3.py')
rv = importlib.util.module_from_spec(spec); spec.loader.exec_module(rv)
P190 = STAGE / 'packet190-record-bundle-k3x/build/device-cards01-p190-a/WS128/run'
P189 = STAGE / 'packet189-twocard-k3x/v5/evidence/device-row1-bracket-v3k-k3x-B-p189/run/views'
RECORD = 62.345281904743764
CHAIN_BAR = RECORD * 1.02
SCREEN_BAR = RECORD * 1.005
# layer map: 48 layers, QSA every 4th (3, 7, ..., 47) = 12 QSA, 36 GDN.
GDN_A, QSA_A = 18, 6          # rank-0 half (layers 0-23)
GDN_BD = 3                    # boundary (24-26)
GDN_B, QSA_B = 15, 6          # rank-1 half (27-47)
MISS_RESCUE_P96 = 15 / 256    # packet96: margin<1 flags 58/256, second choice rescues 15 (held-out gain 0%)


def load_plus(view_dir):
    rows = rv.load_view(view_dir)
    by_pid = defaultdict(list)
    for x in rows:
        by_pid[x['pid']].append(x)
    for pid, part in by_pid.items():
        r = json.loads((Path(view_dir) / pid / 'receipt.json').read_text())
        dw, idle = {}, {}
        for d in r['draft_rows']:
            if d.get('draft_wall_ms') is not None:
                dw[d['position']] = d['draft_wall_ms']; idle[d['position']] = d.get('rank0_idle_waiting_for_guess_ms') or 0.0
        scopes = defaultdict(dict)
        r0half = {}
        for line in (Path(view_dir) / pid / 'rank0/timings.jsonl').read_text().splitlines():
            if not line.strip():
                continue
            s = json.loads(line)
            seg = s.get('p150_segment')
            if seg and not s.get('replay'):
                scopes[s['position']][seg] = s['ms']
            elif 'half_completion_ms' in s and s.get('speculative'):
                r0half[s['position']] = s
        r1half = {}
        for line in (Path(view_dir) / pid / 'rank1/timings.jsonl').read_text().splitlines():
            if line.strip():
                s = json.loads(line)
                if 'half_completion_ms' in s:
                    r1half[s['position']] = s
        for x in part:
            p = x['position']
            x['draft_wall'] = dw.get(p); x['idle'] = idle.get(p, 0.0)
            sc = scopes.get(p, {})
            x['export'] = sc.get('handoff_export'); x['body'] = sc.get('boundary_body'); x['btotal'] = sc.get('boundary_total')
            x['snapshot'] = sc.get('snapshot'); x['token_prep'] = sc.get('token_prep'); x['rollback_scope'] = sc.get('rollback')
            # next speculative half's host fields (position p+1), rank-1 half at p
            h0 = r0half.get(p + 1); h1 = r1half.get(p)
            x['A_half_completion'] = h0['half_completion_ms'] if h0 else None
            x['A_prepare'] = h0['prepare_ms'] if h0 else None
            x['A_retire'] = h0['p76_retirement_ms'] if h0 else None
            x['B_half_completion'] = h1['half_completion_ms'] if h1 else None
            x['B_retire'] = h1['p76_retirement_ms'] if h1 else None
    return rows


def T_of(x, dD=0.0, dBd=0.0, dB=0.0, dA=0.0, dC=0.0, dR=0.0, flip=False):
    """Interval time under deltas (ms). dB may be a callable of the row. flip=True treats a miss as a hit (acceptance)."""
    D = x['Dreal'] + dD
    if x['hit'] or flip:
        ready = max(D, x['Bd'] + dBd)
        B = x['Bhit_proxy'] if (flip and not x['hit']) else x['B']
        G = x['Greal'] if x['hit'] else x['Ghit_proxy']
    else:
        ready = max(D, x['R'] + dR + x['C'] + dC + x['Bd'] + dBd)
        B = x['B']; G = x['Greal']
    db = dB(x) if callable(dB) else dB
    race = max(B + db, x['A'] + dA + x['spec_start_offset_ms'])
    return ready + race + G


def price(rows, base, label, **kw):
    T = [T_of(x, **kw) for x in rows]
    rate = rv.metric(rows, T)
    hits = [t for t, x in zip(T, rows) if x['hit']]; miss = [t for t, x in zip(T, rows) if not x['hit']]
    return dict(label=label, rate=rate, gain_pct=100 * (rate / base - 1), pooled_ms=st.mean(T), hit_ms=st.mean(hits), miss_ms=st.mean(miss))


def acceptance_price(rows, base, points, label=None):
    """+points of acceptance: per prompt, flip the expected 0.99*points intervals from miss to hit (uniformly weighted:
    each miss interval is counted as a hit with weight w = flips/n_miss). Uses per-prompt hit proxies for B and G."""
    per = defaultdict(float); cls = {}
    byp = defaultdict(list)
    for x in rows:
        byp[x['pid']].append(x); cls[x['pid']] = x['cls']
    for pid, part in byp.items():
        n_miss = sum(1 for x in part if not x['hit'])
        flips = 0.99 * points
        w = min(1.0, flips / n_miss) if n_miss else 0.0
        tot = 0.0
        for x in part:
            if x['hit']:
                tot += T_of(x)
            else:
                tot += (1 - w) * T_of(x) + w * T_of(x, flip=True)
        per[pid] = tot
    by = defaultdict(list)
    for p, s in per.items():
        by[cls[p]].append(99000 / s)
    rate = st.median(st.median(v) for v in by.values())
    return dict(label=label or f'acceptance +{points} point(s)', rate=rate, gain_pct=100 * (rate / base - 1))


def q(v, n=20):
    v = sorted(v); qs = st.quantiles(v, n=n)
    return dict(mean=st.mean(v), min=v[0], p5=qs[0], p50=st.median(v), p95=qs[-1], max=v[-1], n=len(v))


def prepare(rows):
    """Attach Dreal (draft wall), Greal, and per-prompt hit proxies for the acceptance flip."""
    for x in rows:
        x['Dreal'] = x['draft_wall'] if x['draft_wall'] is not None else x['D']
        if x['hit']:
            ready = max(x['Dreal'], x['Bd'])
        else:
            ready = max(x['Dreal'], x['R'] + x['C'] + x['Bd'])
        race = max(x['B'], x['A'] + x['spec_start_offset_ms'])
        x['ready_real'] = ready; x['race_real'] = race
        x['Greal'] = x['elapsed_ms'] - ready - race
    byp = defaultdict(list)
    for x in rows:
        byp[x['pid']].append(x)
    for pid, part in byp.items():
        hB = st.mean(x['B'] for x in part if x['hit']); hG = st.mean(x['Greal'] for x in part if x['hit'])
        for x in part:
            x['Bhit_proxy'] = hB; x['Ghit_proxy'] = hG
    return rows


def describe(rows, label):
    hits = [x for x in rows if x['hit']]; miss = [x for x in rows if not x['hit']]
    keys = ['elapsed_ms', 'D', 'draft_wall', 'idle', 'Bd', 'body', 'export', 'B', 'A', 'spec_start_offset_ms', 'R', 'C', 'Greal', 'ready_real', 'race_real',
            'snapshot', 'token_prep', 'A_half_completion', 'A_prepare', 'A_retire', 'B_half_completion', 'B_retire']
    m = lambda part, k: (st.mean(x[k] for x in part if x.get(k) is not None) if any(x.get(k) is not None for x in part) else None)
    d = dict(label=label, rate=rv.metric(rows), n=len(rows), hits=len(hits), misses=len(miss), hit_fraction=len(hits) / len(rows),
             hit={k: m(hits, k) for k in keys}, miss={k: m(miss, k) for k in keys})
    # binding analysis, hits
    dm = [x['draft_wall'] - x['Bd'] for x in hits if x['draft_wall'] is not None]
    d['hit_draft_minus_boundary'] = q(dm)
    d['hit_draft_binds_ready_fraction'] = st.mean(float(v > 0) for v in dm)
    rs = [x['A'] + x['spec_start_offset_ms'] - x['B'] for x in hits]
    d['hit_A_minus_B'] = q(rs)
    d['hit_A_binds_race_fraction'] = st.mean(float(v > 0) for v in rs)
    d['hit_slack_if_only_A_cut'] = q([max(0.0, v) for v in rs])      # how much A can fall before B binds
    d['hit_slack_if_only_B_cut'] = q([max(0.0, -v) for v in rs])
    d['hit_slack_if_only_D_cut'] = q([max(0.0, v) for v in dm])      # how much D can fall before Bd binds
    d['hit_slack_if_only_Bd_cut'] = q([max(0.0, -v) for v in dm])
    # misses
    mm = [x['R'] + x['C'] + x['Bd'] - x['draft_wall'] for x in miss if x['draft_wall'] is not None]
    d['miss_serial_minus_draft'] = q(mm)
    rs = [x['B'] - x['A'] - x['spec_start_offset_ms'] for x in miss]
    d['miss_B_minus_A'] = q(rs)
    d['miss_B_binds_race_fraction'] = st.mean(float(v > 0) for v in rs)
    d['miss_rank1_idle_ms'] = st.mean(x['R'] + x['C'] + x['Bd'] - x['draft_wall'] for x in miss if x['draft_wall'] is not None)
    # busy time per rank per hit / miss
    d['hit_rank0_busy'] = st.mean(x['Bd'] + x['A'] for x in hits); d['hit_rank1_busy'] = st.mean(x['draft_wall'] + x['B'] for x in hits if x['draft_wall'] is not None)
    d['miss_rank0_busy'] = st.mean(x['R'] + x['C'] + x['Bd'] + x['A'] for x in miss); d['miss_rank1_busy'] = st.mean(x['draft_wall'] + x['B'] for x in miss if x['draft_wall'] is not None)
    d['G'] = dict(hit=q([x['Greal'] for x in hits]), miss=q([x['Greal'] for x in miss]))
    tot = sum(x['elapsed_ms'] for x in rows)
    d['time_share'] = dict(hits=sum(x['elapsed_ms'] for x in hits) / tot, misses=sum(x['elapsed_ms'] for x in miss) / tot)
    cp = defaultdict(float)
    for x in rows:
        if x['hit']:
            cp['ready: D (draft)' if x['draft_wall'] >= x['Bd'] else 'ready: Bd (boundary)'] += max(x['draft_wall'], x['Bd'])
        else:
            cp['ready: R'] += x['R']; cp['ready: C'] += x['C']; cp['ready: Bd (miss, serial)'] += x['Bd']
        if x['B'] >= x['A'] + x['spec_start_offset_ms']:
            cp['race: B (rank 1 half)'] += x['B']
        else:
            cp['race: A (rank 0 speculative half)'] += x['A'] + x['spec_start_offset_ms']
        cp['G'] += x['Greal']
    d['critical_path_share'] = {k: v / tot for k, v in cp.items()}
    return d


def main():
    out = {}
    rows = prepare(load_plus(P190 / 'repeat-1'))
    assert len(rows) == 1188
    base = rv.metric(rows)
    assert abs(base - RECORD) < 1e-9, base
    model = rv.metric(rows, [T_of(x) for x in rows])
    assert abs(model - RECORD) < 1e-9, model   # identity: T_of with no deltas reproduces every interval (G absorbs)
    out['record'] = dict(rate=base, chain_bar=CHAIN_BAR, screen_bar=SCREEN_BAR)
    out['p190'] = describe(rows, 'packet190 WS128 (record)')
    views = {v.name: prepare(load_plus(v)) for v in sorted(P189.iterdir())}
    out['p189_views'] = {n: describe(r, n) for n, r in views.items()}
    out['p189_rates'] = {n: rv.metric(r) for n, r in views.items()}

    hits = [x for x in rows if x['hit']]
    # ---- per-class / per-layer arithmetic -----------------------------------------------------------------------
    A_body = st.mean(x['A_half_completion'] for x in hits if x['A_half_completion'])    # rank-0 engine half (no envelope)
    B_body = st.mean(x['B_half_completion'] for x in hits if x['B_half_completion'])
    out['per_layer'] = dict(
        rank0_half_completion_hit=A_body, rank0_A_envelope=st.mean(x['A'] for x in hits) - A_body,
        rank1_half_completion_hit=B_body, rank1_B_envelope=st.mean(x['B'] for x in hits) - B_body,
        rank0_ms_per_layer=A_body / 24, boundary_body_per_gdn_layer=st.mean(x['body'] for x in hits) / 3,
        rank1_layers_ms=B_body - 1.4037 - 0.0516, rank1_ms_per_layer=(B_body - 1.4037 - 0.0516) / 21)

    # ---- prices on the record intervals --------------------------------------------------------------------------
    P = []
    P.append(price(rows, base, 'identity'))
    for d in (0.005, 0.01, 0.0164, 0.02, 0.05, 0.1):
        P.append(price(rows, base, f'per-GDN-layer kernel saving {d} ms on every GDN layer (A -18d, C -18d, Bd -3d, B -15d)',
                       dA=-GDN_A * d, dC=-GDN_A * d, dBd=-GDN_BD * d, dB=-GDN_B * d))
    for d in (0.01, 0.02, 0.05, 0.1):
        P.append(price(rows, base, f'per-QSA-layer kernel saving {d} ms (A -6d, C -6d, B -6d)', dA=-QSA_A * d, dC=-QSA_A * d, dB=-QSA_B * d))
    for d in (0.01, 0.02, 0.05, 0.1):
        P.append(price(rows, base, f'per-layer saving {d} ms on all 48 layers', dA=-24 * d, dC=-24 * d, dBd=-3 * d, dB=-21 * d))
    for frac, name, per_layer in ((0.05, 'experts gate/up+down 5%', 0.1113), (0.10, 'experts gate/up+down 10%', 0.1113), (0.15, 'experts 15%', 0.1113),
                                  (0.10, 'route 10%', 0.01875), (0.5, 'route 50%', 0.01875), (0.10, 'recurrence 10%', 0.02396), (0.25, 'recurrence 25%', 0.02396),
                                  (0.10, 'HC gates+norms+low 10%', 0.0838), (0.10, 'dense qkv+z+attention 10%', 0.1549)):
        d = frac * per_layer
        gdn_only = name.startswith('recurrence')
        kw = dict(dA=-(GDN_A + (0 if gdn_only else QSA_A)) * d, dC=-(GDN_A + (0 if gdn_only else QSA_A)) * d, dBd=-GDN_BD * d, dB=-(GDN_B + (0 if gdn_only else QSA_B)) * d)
        P.append(price(rows, base, f'class cut: {name} ({d*1000:.1f} us/layer)', **kw))
    for x_ in (0.02, 0.05, 0.1, 0.2, 0.42, 0.5):
        P.append(price(rows, base, f'draft -{x_} ms (D only)', dD=-x_))
    for x_ in (0.05, 0.1, 0.2, 0.46):
        P.append(price(rows, base, f'boundary -{x_} ms (Bd only)', dBd=-x_))
    for x_ in (0.025, 0.05, 0.1, 0.25, 0.3):
        P.append(price(rows, base, f'rank-0 A -{x_} ms only', dA=-x_))
    for x_ in (0.05, 0.1, 0.38):
        P.append(price(rows, base, f'rank-1 B -{x_} ms only (e.g. head)', dB=-x_))
    for x_ in (0.05, 0.1, 0.2):
        P.append(price(rows, base, f'A and B both -{x_} ms', dA=-x_, dB=-x_))
        P.append(price(rows, base, f'A, B and C all -{x_} ms', dA=-x_, dB=-x_, dC=-x_))
        P.append(price(rows, base, f'A, B, C and D all -{x_} ms', dA=-x_, dB=-x_, dC=-x_, dD=-x_))
    P.append(price(rows, base, 'draft -0.05 + A -0.05 + B -0.05 (balanced trims)', dD=-0.05, dA=-0.05, dB=-0.05))
    P.append(price(rows, base, 'draft -0.05 + A -0.10 + B -0.06 + C -0.05 (every host envelope item at its measured size)', dD=-0.05, dA=-0.10, dB=-0.06, dC=-0.05))
    P.append(price(rows, base, 'miss: all restore R removed (upper bound)', dR=-st.mean(x['R'] for x in rows if not x['hit'])))
    Bwarm = st.mean(x['B'] for x in rows if not x['hit']) - st.mean(x['B'] for x in hits)
    P.append(price(rows, base, f'miss: rank-1 warm-after-idle removed (B_miss -> B_hit, {Bwarm:.3f})', dB=lambda x: 0.0 if x['hit'] else -Bwarm))
    P.append(price(rows, base, 'miss: boundary free on misses (impossible: Bd needs C)', dBd=0.0, dC=-st.mean(x['Bd'] for x in rows if not x['hit'])))
    P.append(price(rows, base, 'miss: C -1.0 ms', dC=-1.0))
    for pts in (1, 2, 3, 5):
        P.append(acceptance_price(rows, base, pts))
    # width-2 at depth 1: second candidate row in A (and in B? no: B runs the verified token; the second candidate only costs rank 0's
    # speculative half, plus its image/bank). cost c on every A; rescue 15/256 of misses (packet96).
    for c in (0.0, 0.5, 1.0, 1.952, 9.21):
        # expected rescued fraction of intervals = 15/256 of misses -> acceptance points = 100 * (15/256) * miss_fraction
        pts = 100 * MISS_RESCUE_P96 * (256 / 1188)
        # price: apply the A cost on every interval, then the acceptance flip
        rr = [dict(x) for x in rows]
        for x in rr:
            x['A'] = x['A'] + c
        rate = acceptance_price(rr, base, pts)['rate']
        P.append(dict(label=f'width-2 at depth 1: second candidate row costs A +{c} ms every interval, rescues 15/256 misses (+{pts:.2f} pts)', rate=rate, gain_pct=100 * (rate / base - 1)))
    out['prices'] = P

    # ---- thresholds for +2% / +0.5% -------------------------------------------------------------------------------
    def solve(fn, target, lo=0.0, hi=5.0):
        for _ in range(60):
            mid = (lo + hi) / 2
            if fn(mid) >= target:
                hi = mid
            else:
                lo = mid
        return hi
    TH = {}
    for bar_name, bar in (('chain +2%', CHAIN_BAR), ('screen +0.5%', SCREEN_BAR)):
        TH[bar_name] = dict(
            per_gdn_layer_ms=solve(lambda d: price(rows, base, '', dA=-GDN_A * d, dC=-GDN_A * d, dBd=-GDN_BD * d, dB=-GDN_B * d)['rate'], bar, 0, 0.2),
            per_layer_all48_ms=solve(lambda d: price(rows, base, '', dA=-24 * d, dC=-24 * d, dBd=-3 * d, dB=-21 * d)['rate'], bar, 0, 0.2),
            symmetric_ABC_ms=solve(lambda d: price(rows, base, '', dA=-d, dB=-d, dC=-d)['rate'], bar, 0, 3),
            symmetric_ABCD_ms=solve(lambda d: price(rows, base, '', dA=-d, dB=-d, dC=-d, dD=-d)['rate'], bar, 0, 3),
            draft_only_ms=(solve(lambda d: price(rows, base, '', dD=-d)['rate'], bar, 0, 3) if price(rows, base, '', dD=-3)['rate'] >= bar else None),
            A_only_ms=(solve(lambda d: price(rows, base, '', dA=-d)['rate'], bar, 0, 5) if price(rows, base, '', dA=-5)['rate'] >= bar else None),
            B_only_ms=(solve(lambda d: price(rows, base, '', dB=-d)['rate'], bar, 0, 5) if price(rows, base, '', dB=-5)['rate'] >= bar else None),
            C_only_ms=(solve(lambda d: price(rows, base, '', dC=-d)['rate'], bar, 0, 12) if price(rows, base, '', dC=-12)['rate'] >= bar else None),
            acceptance_points=solve(lambda p: acceptance_price(rows, base, p)['rate'], bar, 0, 25))
    out['thresholds'] = TH
    # saturation ceilings of single-side cuts
    out['ceilings'] = dict(
        draft_only=price(rows, base, 'draft -> 0', dD=-3)['gain_pct'], A_only=price(rows, base, 'A -> 0', dA=-5)['gain_pct'],
        B_only=price(rows, base, 'B -> 0', dB=-5)['gain_pct'], Bd_only=price(rows, base, 'Bd -> 0', dBd=-1.5)['gain_pct'],
        C_only_1ms=price(rows, base, '', dC=-1.0)['gain_pct'])

    # ---- per-prompt k3x spread (noise) ----------------------------------------------------------------------------
    per = defaultdict(dict)
    for n, r in views.items():
        pp = defaultdict(float)
        for x in r:
            pp[x['pid']] += x['elapsed_ms']
        for pid, s in pp.items():
            per[pid][n] = 99000 / s
    out['p189_per_prompt'] = per
    k1, k3 = '01-candidate', '03-candidate'
    out['p189_k3x_view_spread'] = dict(rates=[out['p189_rates'][k1], out['p189_rates'][k3]],
                                       per_prompt_pct=[100 * (per[p][k3] / per[p][k1] - 1) for p in per],
                                       max_abs_pct=max(abs(100 * (per[p][k3] / per[p][k1] - 1)) for p in per))
    out['p190_vs_p189_k3x_pct'] = 100 * (base / max(out['p189_rates'][k1], out['p189_rates'][k3]) - 1)
    (HERE / 'model-k3x-output.json').write_text(json.dumps(out, indent=1, default=float))

    # ---- print ------------------------------------------------------------------------------------------------------
    d = out['p190']
    print(f"record replay {base:.9f} (stored {RECORD}); model identity ok; chain bar {CHAIN_BAR:.3f} screen bar {SCREEN_BAR:.3f}")
    for part in ('hit', 'miss'):
        print(part, {k: (round(v, 4) if v is not None else None) for k, v in d[part].items()})
    for k in ('hit_draft_minus_boundary', 'hit_draft_binds_ready_fraction', 'hit_A_minus_B', 'hit_A_binds_race_fraction', 'hit_slack_if_only_A_cut', 'hit_slack_if_only_B_cut',
              'hit_slack_if_only_D_cut', 'hit_slack_if_only_Bd_cut', 'miss_serial_minus_draft', 'miss_B_minus_A', 'miss_B_binds_race_fraction', 'miss_rank1_idle_ms',
              'hit_rank0_busy', 'hit_rank1_busy', 'miss_rank0_busy', 'miss_rank1_busy', 'G', 'time_share', 'critical_path_share'):
        v = d[k]
        print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} if isinstance(v, dict) else round(v, 4))
    print('per_layer', {k: round(v, 4) for k, v in out['per_layer'].items()})
    print('\nprices (gain vs 62.345282):')
    for p in P:
        extra = f"  hit {p['hit_ms']:.3f} miss {p['miss_ms']:.3f}" if 'hit_ms' in p else ''
        print(f"  {p['gain_pct']:+6.2f}%  {p['rate']:.3f}{extra}  {p['label']}")
    print('\nthresholds:', json.dumps(TH, indent=1))
    print('ceilings:', {k: round(v, 3) for k, v in out['ceilings'].items()})
    print('p189 rates', {k: round(v, 3) for k, v in out['p189_rates'].items()}, 'k3x view spread max |pct|', round(out['p189_k3x_view_spread']['max_abs_pct'], 3),
          'p190 chain vs p189 best k3x view', round(out['p190_vs_p189_k3x_pct'], 3))


if __name__ == '__main__':
    main()
