#!/usr/bin/env python3
"""Lever synthesis 3 replay (CPU-only, read-only on the repo; writes only next to this script).

Reuses lever synthesis 2's loader and record metric (analysis/replay_v3.py of packet188, imported read-only):
  elapsed = max(D, R + C + Bd) + max(B, A + offset) + G ; metric = per prompt 99000 / sum(T), median of class medians.

Adds, per interval, from the same receipts / rank-0 streams:
  draft_wall  the draft's publication-observed wall (receipt draft_rows.draft_wall_ms) = the REAL draft completion.
              In the V3 views the op-9 trace duration (model D) equals it (1.59); in the k3trims views the op-9
              duration is only the nonblocking host issue (0.43), so D must be read from draft_wall there.
  export, body, btotal  the rank-0 p150 scopes handoff_export / boundary_body / boundary_total at that position.
Prices every lever as a per-interval delta replay on (a) packet187's 1,188 record intervals and (b) packet188's
in-load V3 views, and (c) rebuilds the k3x counterfactual directly from the measured k3trims intervals.
"""
import importlib.util, json, statistics as st, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2')
P188 = STAGE / 'packet188-twocard-k3-composite'
spec = importlib.util.spec_from_file_location('replay_v3', HERE / 'replay_v3.py')  # packet189's own copy of packet188's loader
rv = importlib.util.module_from_spec(spec); spec.loader.exec_module(rv)
VIEWS = P188 / 'v5/evidence/device-row2-bracket-v3k-k3trims-B-p188/run/views'
RECORD = 60.65951991975228
CHAIN_BAR = RECORD * 1.02


def load_view_plus(view_dir):
    """LS2 rows + draft_wall + boundary scopes joined by position."""
    rows = rv.load_view(view_dir)
    by_pid = defaultdict(list)
    for x in rows:
        by_pid[x['pid']].append(x)
    for pid, part in by_pid.items():
        r = json.loads((Path(view_dir) / pid / 'receipt.json').read_text())
        dw = {d['position']: d['draft_wall_ms'] for d in r['draft_rows'] if d.get('draft_wall_ms') is not None}
        scopes = defaultdict(dict)
        for line in (Path(view_dir) / pid / 'rank0/timings.jsonl').read_text().splitlines():
            if not line.strip():
                continue
            s = json.loads(line)
            seg = s.get('p150_segment')
            if seg in ('handoff_export', 'boundary_body', 'boundary_total') and not s.get('replay'):
                scopes[s['position']][seg] = s['ms']
        for x in part:
            x['draft_wall'] = dw.get(x['position'])
            sc = scopes.get(x['position'], {})
            x['export'] = sc.get('handoff_export'); x['body'] = sc.get('boundary_body'); x['btotal'] = sc.get('boundary_total')
    return rows


def T_of(x, dD=0.0, dBd=0.0, dB=0.0, dA=0.0, dC=0.0, dR=0.0, Dreal=None, Bd=None, G=None):
    """Interval time under deltas. Dreal/Bd override the draft and boundary (per interval callables or None)."""
    D = (Dreal(x) if Dreal else x['D']) + dD
    bd = (Bd(x) if Bd else x['Bd']) + dBd
    ready = max(D, x['R'] + dR + x['C'] + (dC if not x['hit'] else 0.0) + bd)
    race = max(x['B'] + dB(x) if callable(dB) else x['B'] + dB, x['A'] + dA + x['spec_start_offset_ms'])
    return ready + race + (x['G'] if G is None else G(x))


def price(rows, base_rate, label, **kw):
    T = [T_of(x, **kw) for x in rows]
    rate = rv.metric(rows, T)
    pooled = st.mean(T)
    hits = [t for t, x in zip(T, rows) if x['hit']]; miss = [t for t, x in zip(T, rows) if not x['hit']]
    return dict(label=label, rate=rate, gain_pct=100 * (rate / base_rate - 1), pooled_ms=pooled,
                hit_ms=st.mean(hits), miss_ms=st.mean(miss))


def describe(rows, label):
    hits = [x for x in rows if x['hit']]; miss = [x for x in rows if not x['hit']]
    keys = ['elapsed_ms', 'D', 'draft_wall', 'Bd', 'export', 'body', 'btotal', 'B', 'A', 'spec_start_offset_ms', 'R', 'C', 'G', 'ready', 'race']
    m = lambda part, k: st.mean(x[k] for x in part if x.get(k) is not None) if any(x.get(k) is not None for x in part) else None
    return dict(label=label, rate=rv.metric(rows), n=len(rows), hits=len(hits), misses=len(miss),
                hit={k: m(hits, k) for k in keys}, miss={k: m(miss, k) for k in keys})


def compute():
    out = {}
    p187 = rv.load_view(rv.P187 / 'repeat-1')
    assert len(p187) == 1188
    base = rv.metric(p187)
    assert abs(base - RECORD) < 1e-9, base
    out['p187'] = dict(rate=base, **{k: v for k, v in rv.describe(p187).items() if k in ('hit', 'miss', 'hit_fraction')})

    views = {}
    for v in sorted(VIEWS.iterdir()):
        rows = load_view_plus(v)
        assert len(rows) == 1188, (v, len(rows))
        views[v.name] = rows
    out['p188_views'] = {name: describe(rows, name) for name, rows in views.items()}
    v3_views = [views[n] for n in ('00-control', '02-control', '04-control')]
    k3_views = [views[n] for n in ('01-candidate', '03-candidate')]
    v3_rates = [rv.metric(r) for r in v3_views]; k3_rates = [rv.metric(r) for r in k3_views]
    out['p188_rates'] = dict(v3=v3_rates, k3trims=k3_rates)

    # ---- A. decomposition of the layer-26 boundary cost and the miss change ------------------------------------
    hm = lambda rows, k: st.mean(x[k] for x in rows if x['hit'] and x.get(k) is not None)
    mm = lambda rows, k: st.mean(x[k] for x in rows if not x['hit'] and x.get(k) is not None)
    avg = lambda f, vs, k: st.mean(f(r, k) for r in vs)
    A = {}
    for k in ('Bd', 'export', 'body', 'btotal', 'D', 'draft_wall', 'B', 'A', 'C', 'R', 'G', 'elapsed_ms', 'ready', 'race'):
        A[k] = dict(v3_hit=avg(hm, v3_views, k), k3_hit=avg(hm, k3_views, k), v3_miss=avg(mm, v3_views, k), k3_miss=avg(mm, k3_views, k))
        A[k]['d_hit'] = A[k]['k3_hit'] - A[k]['v3_hit']; A[k]['d_miss'] = A[k]['k3_miss'] - A[k]['v3_miss']
    A['export_bytes'] = 4 * 2560 * 2
    A['export_ns_per_byte_k3trims'] = 1e6 * A['export']['k3_hit'] / A['export_bytes']
    A['export_ns_per_byte_v3'] = 1e6 * A['export']['v3_hit'] / A['export_bytes']
    # boundary over the real draft (publication observed), per k3trims hit
    k3h = [x for r in k3_views for x in r if x['hit'] and x['draft_wall'] is not None]
    A['k3trims_hits_Bd_over_draft_wall'] = st.mean(float(x['Bd'] > x['draft_wall']) for x in k3h)
    A['k3trims_hits_Bd_minus_draft_wall_mean'] = st.mean(x['Bd'] - x['draft_wall'] for x in k3h)
    v3h = [x for r in v3_views for x in r if x['hit'] and x['draft_wall'] is not None]
    A['v3_hits_D_minus_draft_wall_mean'] = st.mean(x['D'] - x['draft_wall'] for x in v3h)
    A['v3_hits_draft_wall_minus_Bd'] = dict(mean=st.mean(x['draft_wall'] - x['Bd'] for x in v3h), p5=st.quantiles([x['draft_wall'] - x['Bd'] for x in v3h], n=20)[0])
    # miss arithmetic: elapsed_miss = R + C + Bd + B + G (boundary path binds ready; B binds race)
    A['miss_identity_v3'] = A['R']['v3_miss'] + A['C']['v3_miss'] + A['Bd']['v3_miss'] + A['B']['v3_miss'] + A['G']['v3_miss']
    A['miss_identity_k3'] = A['R']['k3_miss'] + A['C']['k3_miss'] + A['Bd']['k3_miss'] + A['B']['k3_miss'] + A['G']['k3_miss']
    out['A_decomposition'] = A

    # ---- measured deltas used in the replays ---------------------------------------------------------------------
    LAYER26 = A['body']['d_hit']                       # layer-26 GDN kernel body at the boundary (k3trims - V3)
    EXPORT_COPY = A['export']['v3_hit']                # copy-engine export (V3) for the same 20,480 B
    EXPORT_KIO = A['export']['k3_hit']
    BENV_OTHER = (A['btotal']['k3_hit'] - A['body']['k3_hit'] - A['export']['k3_hit']) - (A['btotal']['v3_hit'] - A['body']['v3_hit'] - A['export']['v3_hit'])
    dD_KIO = A['draft_wall']['k3_hit'] - A['draft_wall']['v3_hit']   # rank-1 kernel I/O on the draft (publication observed)
    dB_HIT = A['B']['d_hit']; dB_MISS = A['B']['d_miss']
    dB_KIO_HIT = dB_HIT + LAYER26; dB_KIO_MISS = dB_MISS + LAYER26      # what is left of B's fall after the moved layer
    dA = A['A']['d_hit']; dC = A['C']['d_miss']; dR = A['R']['d_miss']
    out['deltas'] = dict(layer26_body=LAYER26, export_copy=EXPORT_COPY, export_kio=EXPORT_KIO, boundary_envelope_other=BENV_OTHER,
                         dD_kio=dD_KIO, dB_hit=dB_HIT, dB_miss=dB_MISS, dB_kio_hit=dB_KIO_HIT, dB_kio_miss=dB_KIO_MISS, dA_trims=dA, dC_trims=dC, dR=dR)
    Bsplit = lambda h, m: (lambda x: h if x['hit'] else m)

    # ---- B/C. prices on packet187's record intervals -------------------------------------------------------------
    P = []
    P.append(price(p187, base, 'V3 record replay (identity)'))
    P.append(price(p187, base, 'k=2 + kernel_io on rank 1 only (B kio part, draft kio part; export on copy engine)', dD=dD_KIO, dB=Bsplit(dB_KIO_HIT, dB_KIO_MISS)))
    P.append(price(p187, base, 'k=2 + kernel_io on rank 1 only, B part only (no draft part)', dB=Bsplit(dB_KIO_HIT, dB_KIO_MISS)))
    P.append(price(p187, base, 'k=2 + kernel_io on rank 1 only, low (B -0.03, D -0.03)', dD=-0.03, dB=-0.03))
    P.append(price(p187, base, 'k=2 + kernel_io both ranks, export on copy engine, + rank0_prepare=async (kio-x)', dD=dD_KIO, dB=Bsplit(dB_KIO_HIT, dB_KIO_MISS), dA=dA, dC=dC))
    P.append(price(p187, base, 'k=2 + rank0_prepare=async alone (A -0.047)', dA=-0.047))
    P.append(price(p187, base, 'k=2 + all rank-0 trims alone (A -0.142, C -0.098)', dA=dA, dC=dC))
    P.append(price(p187, base, 'k=2 + boundary export removed entirely (Bd -0.053)', dBd=-EXPORT_COPY))
    P.append(price(p187, base, 'k=2 + kernel_io=kernel AS BUILT (export via KioCopy: Bd +0.54) + trims', dD=dD_KIO, dBd=EXPORT_KIO - EXPORT_COPY + BENV_OTHER, dB=Bsplit(dB_KIO_HIT, dB_KIO_MISS), dA=dA, dC=dC))
    P.append(price(p187, base, 'k3 alone (layer 26 moved, no trims, export on copy engine)', dBd=LAYER26, dB=-LAYER26))
    P.append(price(p187, base, 'k3 + trims AS MEASURED (export via KioCopy) [sanity vs 60.38-60.56 in-load]', dD=dD_KIO, dBd=LAYER26 + EXPORT_KIO - EXPORT_COPY + BENV_OTHER, dB=Bsplit(dB_HIT, dB_MISS), dA=dA, dC=dC))
    P.append(price(p187, base, 'k3x: k3 + trims, boundary export on the copy engine (central)', dD=dD_KIO, dBd=LAYER26 + BENV_OTHER, dB=Bsplit(dB_HIT, dB_MISS), dA=dA, dC=dC))
    # sensitivities for k3x
    for lab, kw in (('k3x: export +0.03 slower (0.083)', dict(dBd=LAYER26 + BENV_OTHER + 0.03)),
                    ('k3x: layer-26 body 0.48', dict(dBd=0.48 + BENV_OTHER, dB=Bsplit(dB_HIT - (0.48 - LAYER26), dB_MISS - (0.48 - LAYER26)))),
                    ('k3x: layer-26 body 0.44', dict(dBd=0.44 + BENV_OTHER, dB=Bsplit(dB_HIT + (LAYER26 - 0.44), dB_MISS + (LAYER26 - 0.44)))),
                    ('k3x: draft not faster (dD 0)', dict(dD=0.0)),
                    ('k3x: draft 0.03 slower than measured', dict(dD=dD_KIO + 0.03)),
                    ('k3x: B saving only 0.50/0.45', dict(dB=Bsplit(-0.50, -0.45))),
                    ('k3x: no C trim', dict(dC=0.0)),
                    ('k3x: A trim only 0.105', dict(dA=-0.105)),
                    ('k3x: everything pessimistic (export +0.03, body 0.48, dD +0.03, B -0.50/-0.45, A -0.105)',
                     dict(dBd=0.48 + BENV_OTHER + 0.03, dB=Bsplit(-0.50, -0.45), dD=dD_KIO + 0.03, dA=-0.105)),
                    ('k3x: everything optimistic (body 0.44, B -0.60/-0.55, dD -0.08)',
                     dict(dBd=0.44 + BENV_OTHER, dB=Bsplit(-0.60, -0.55), dD=-0.08))):
        base_kw = dict(dD=dD_KIO, dBd=LAYER26 + BENV_OTHER, dB=Bsplit(dB_HIT, dB_MISS), dA=dA, dC=dC)
        base_kw.update(kw)
        P.append(price(p187, base, lab, **base_kw))
    # headroom on top of k3x
    k3x = dict(dD=dD_KIO, dBd=LAYER26 + BENV_OTHER, dB=Bsplit(dB_HIT, dB_MISS), dA=dA, dC=dC)
    for extra in (0.05, 0.10, 0.20):
        kw = dict(k3x); kw['dA'] = dA - extra
        P.append(price(p187, base, f'k3x + a further {extra} ms off rank-0 A', **kw))
        kw = dict(k3x); kw['dD'] = dD_KIO - extra
        P.append(price(p187, base, f'k3x + a further {extra} ms off the draft', **kw))
        kw = dict(k3x); kw['dBd'] = LAYER26 + BENV_OTHER - extra
        P.append(price(p187, base, f'k3x + a further {extra} ms off the boundary', **kw))
        kw = dict(k3x); kw['dB'] = Bsplit(dB_HIT - extra, dB_MISS - extra)
        P.append(price(p187, base, f'k3x + a further {extra} ms off rank-1 B', **kw))
    # k=4 is illegal (27 is QSA); k=3 with 23 moved instead of 26: A shorter (does not bind), boundary longer
    P.append(price(p187, base, 'split 23-25 instead (QSA 23 to boundary; illegal island): Bd +0.52, A -0.46', dBd=0.52, dA=-0.46))
    out['prices_p187'] = P

    # ---- in-load prices on packet188's V3 views (same deltas) ---------------------------------------------------
    Q = []
    for name, rows in (('00-control', views['00-control']), ('02-control', views['02-control']), ('04-control', views['04-control'])):
        b = rv.metric(rows)
        Q.append(price(rows, b, f'{name}: V3 identity'))
        Q.append(price(rows, b, f'{name}: kio-x (k=2)', dD=dD_KIO, dB=Bsplit(dB_KIO_HIT, dB_KIO_MISS), dA=dA, dC=dC))
        Q.append(price(rows, b, f'{name}: k3x', dD=dD_KIO, dBd=LAYER26 + BENV_OTHER, dB=Bsplit(dB_HIT, dB_MISS), dA=dA, dC=dC))
        Q.append(price(rows, b, f'{name}: k3+trims as measured', dD=dD_KIO, dBd=LAYER26 + EXPORT_KIO - EXPORT_COPY + BENV_OTHER, dB=Bsplit(dB_HIT, dB_MISS), dA=dA, dC=dC))
    out['prices_p188_v3_views'] = Q

    # ---- direct counterfactual from the measured k3trims intervals: only the export is repaired ----------------
    R = []
    v3_in_load_max = max(v3_rates)
    for name in ('01-candidate', '03-candidate'):
        rows = views[name]
        ok = [x for x in rows if x['draft_wall'] is not None and x['export'] is not None]
        assert len(ok) == 1188
        for eps_label, eps in (('guess latency 0.006', 0.006), ('guess latency 0.03', 0.03)):
            for exp_label, exp_fix in (('export -> 0.053 (copy engine)', EXPORT_COPY), ('export -> 0.083', EXPORT_COPY + 0.03)):
                T = [T_of(x, Dreal=lambda x: x['draft_wall'] + eps, Bd=lambda x: x['Bd'] - x['export'] + exp_fix) for x in ok]
                rate = rv.metric(ok, T)
                R.append(dict(view=name, variant=f'k3x from measured k3trims ({eps_label}; {exp_label})', rate=rate,
                              gain_vs_fastest_inload_v3_pct=100 * (rate / v3_in_load_max - 1), gain_vs_min_inload_v3_pct=100 * (rate / min(v3_rates) - 1),
                              hit_ms=st.mean(t for t, x in zip(T, ok) if x['hit']), miss_ms=st.mean(t for t, x in zip(T, ok) if not x['hit']),
                              boundary_over_draft_fraction=st.mean(float(x['Bd'] - x['export'] + exp_fix > x['draft_wall'] + eps) for x in ok if x['hit'])))
        # reproduce the measured k3trims view through the same identity (D := draft_wall) as a check of the model
        T = [T_of(x, Dreal=lambda x: x['draft_wall'] + 0.006) for x in ok]
        R.append(dict(view=name, variant='k3trims as measured, identity with D := draft_wall + 0.006 (model check)', rate=rv.metric(ok, T), measured_rate=rv.metric(ok),
                      hit_ms=st.mean(t for t, x in zip(T, ok) if x['hit']), miss_ms=st.mean(t for t, x in zip(T, ok) if not x['hit'])))
    out['k3x_from_measured_k3trims'] = R

    # ---- bars ---------------------------------------------------------------------------------------------------
    out['bars'] = dict(record=RECORD, chain_bar=CHAIN_BAR, screen_bar_over_inload_v3_max=1.005 * v3_in_load_max, chain_bar_over_inload_v3_max=1.02 * v3_in_load_max)
    return out, dict(base=base, v3_rates=v3_rates, k3_rates=k3_rates, A=A, P=P, Q=Q, R=R)


def main():
    out, w = compute()
    base, v3_rates, k3_rates, A, P, Q, R = w['base'], w['v3_rates'], w['k3_rates'], w['A'], w['P'], w['Q'], w['R']
    (HERE / 'replay-k3x-output.json').write_text(json.dumps(out, indent=1, default=float))

    # ---- print ---------------------------------------------------------------------------------------------------
    print('p187 base', base, '| p188 V3 views', [round(r, 3) for r in v3_rates], 'k3trims', [round(r, 3) for r in k3_rates])
    print('\nA. decomposition (hit means, V3 -> k3trims, delta):')
    for k, d in A.items():
        if isinstance(d, dict) and 'v3_hit' in d:
            print(f"  {k:10s} hit {d['v3_hit']:.4f} -> {d['k3_hit']:.4f} ({d['d_hit']:+.4f})   miss {d['v3_miss']:.4f} -> {d['k3_miss']:.4f} ({d['d_miss']:+.4f})")
        else:
            print(f'  {k}: {d}')
    print('\ndeltas:', {k: round(v, 4) for k, v in out['deltas'].items()})
    print('\nprices on packet187 record intervals (gain vs 60.6595; chain bar 61.873):')
    for p in P:
        print(f"  {p['gain_pct']:+6.2f}%  {p['rate']:.3f}  hit {p['hit_ms']:.3f} miss {p['miss_ms']:.3f}  {p['label']}")
    print('\nin-load V3 views:')
    for q in Q:
        print(f"  {q['gain_pct']:+6.2f}%  {q['rate']:.3f}  hit {q['hit_ms']:.3f} miss {q['miss_ms']:.3f}  {q['label']}")
    print('\nk3x rebuilt from the measured k3trims intervals (export repaired, D := draft_wall):')
    for r in R:
        print('  ', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__':
    main()
