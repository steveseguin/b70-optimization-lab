#!/usr/bin/env python3
"""Price V3 on packet185's MEASURED intervals (per-interval replay, class-balanced metric).

Input: analysis/p185-intervals.json.gz (extract_p185_intervals.py; packet185 lane-B views,
2026-10-22). V3 is constructed interval by interval from the two UNSPLIT views (full target head on
rank 1, no merge, no rank-0 suffix service: exactly V3's head placement), and compared with the
three split-head (bundle 8) control views' measured class-balanced rates.

Per interval (packet85 model, vendored: elapsed = ready + race + G):
  unsplit (measured):   ready = max(D, R + C)                race = max(B, A + offset)
  V3:                   ready = max(D, R + C' + acc + bnd)   race = max(B - 2*s1, A' + offset)
    bnd = 2*c0 + x      (rank 0 runs layers 24-25 for the verified token, then exports layer-25 streams)
    A'  = A - x - dS    (the speculative half no longer exports; dS = static-snapshot saving if bundled)
    C'  = C - x         (the corrected half no longer exports; misses only)
    acc = measured rank-0 accept scope per cycle (host-only; ~0.3 us)
    x   = measured rank-0 handoff_export scope per cycle (same readback, moved into the boundary)
  G (unresolved control gaps) is kept per interval. A = 0 (no guess) keeps race = B - 2*s1.
Rates: per prompt 99 / sum(first 99 T); class-balanced = median over classes of the class median.
Self-check: the identity replay (s1 = c0 = x = 0, no boundary) reproduces each view's rate to 1e-7 (intervals stored at 1 ns).
"""
import gzip, json, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads(gzip.open(HERE / 'p185-intervals.json.gz', 'rt').read())
RECORD = 58.798108759182306


def class_rate(per_prompt):
    groups = {}
    for cls, rate in per_prompt:
        groups.setdefault(cls, []).append(rate)
    return st.median(st.median(v) for v in groups.values())


def per_cycle(view, scope):
    total = sum(p['scope_ms'][scope] for p in view['prompts'])
    cycles = sum(len(p['intervals']) for p in view['prompts'])
    return total / cycles


def replay(view, s1=0.0, c0=0.0, x=None, ds=0.0, identity=False, k=2, extra=0.0):
    x = per_cycle(view, 'handoff_export') if x is None else x
    acc = per_cycle(view, 'accept')
    rates, hits, misses = [], [], []
    for p in view['prompts']:
        total = 0.0
        for hit, D, A, B, R, C, off, elapsed, G in p['intervals']:
            if identity:
                t = elapsed
            else:
                bnd = k * c0 + x + extra
                ready = max(D, (0.0 if hit else R + max(0.0, C - x)) + acc + bnd)
                a = max(0.0, A - x - ds) if A > 0 else 0.0
                race = max(B - k * s1, a + off) if A > 0 else B - k * s1
                t = ready + race + G
            total += t
            (hits if hit else misses).append(t)
        rates.append((p['prompt_class'], 99 / total * 1000))
    return dict(rate=class_rate(rates), hit_ms=st.mean(hits), miss_ms=st.mean(misses), hits=len(hits), misses=len(misses))


def main():
    controls = [v for v in DATA['views'] if v['variant'] == 'production']
    unsplit = [v for v in DATA['views'] if v['variant'] == 'unsplit']
    for v in DATA['views']:
        got = replay(v, identity=True)['rate']
        assert abs(got - v["rate"]) < 1e-7, (v['name'], got, v['rate'])
    c_rates = [v['rate'] for v in controls]
    best, mean_c = max(c_rates), st.mean(c_rates)
    scopes = {s: [per_cycle(v, s) for v in DATA['views']] for s in ('handoff_export', 'accept', 'snapshot', 'rollback', 'layer_body')}
    layer_body_per_half = [sum(p['scope_ms']['layer_body'] for p in v['prompts']) / sum(p['scope_counts']['layer_body'] for p in v['prompts']) for v in DATA['views']]

    def case(**kw):
        rows = [replay(v, **kw) for v in unsplit]
        rate = min(r['rate'] for r in rows)
        return dict(v3_rate_per_unsplit_view=[r['rate'] for r in rows], v3_rate_min=rate,
                    gain_vs_best_control_pct=100 * (rate / best - 1), gain_vs_mean_control_pct=100 * (rate / mean_c - 1),
                    clears_record_bar=rate >= 1.02 * RECORD,
                    hit_ms=st.mean(r['hit_ms'] for r in rows), miss_ms=st.mean(r['miss_ms'] for r in rows))

    cases = {
        'central (s1 0.48, c0 0.55)': case(s1=0.48, c0=0.55),
        'corner c0 = 0.73 (coordinator)': case(s1=0.48, c0=0.73),
        'corner s1 = 0.39 (coordinator)': case(s1=0.39, c0=0.55),
        'both corners (s1 0.39, c0 0.73)': case(s1=0.39, c0=0.73),
        'central + 0.05 ms extra boundary round trip': case(s1=0.48, c0=0.55, extra=0.05),
        'central + static snapshot (dS 0.335, p153 merge-wait growth)': case(s1=0.48, c0=0.55, ds=0.335),
        'central + static snapshot (dS 0.404, p153 host scope)': case(s1=0.48, c0=0.55, ds=0.404),
        'both corners + static (dS 0.335)': case(s1=0.39, c0=0.73, ds=0.335),
        's1 0.55 + static (dS 0.335)': case(s1=0.55, c0=0.55, ds=0.335),
        's1 0.55, no static': case(s1=0.55, c0=0.55),
        'k=1 (one layer) central': case(s1=0.48, c0=0.55, k=1),
        # Anchored on the measured rank-0 layer_body (11.59 ms / 24 layers = 0.483 ms/layer, packet185 receipts,
        # same kernels on identical cards): s1 = c0 = 0.483, plus 0.05 ms per boundary command (launch + drain).
        'anchored (s1 = c0 = 0.483, +0.05 command)': case(s1=0.483, c0=0.483, extra=0.05),
        'anchored + static (dS 0.335)': case(s1=0.483, c0=0.483, extra=0.05, ds=0.335),
        'consistent low (s1 = c0 = 0.39, +0.05)': case(s1=0.39, c0=0.39, extra=0.05),
        'consistent high (s1 = c0 = 0.55, +0.05)': case(s1=0.55, c0=0.55, extra=0.05),
        'consistent high + static': case(s1=0.55, c0=0.55, extra=0.05, ds=0.335),
    }

    def solve(f, lo, hi, target):
        flo = f(lo)
        for _ in range(60):
            mid = (lo + hi) / 2
            if (f(mid) >= target) == (flo >= target):
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    g = lambda **kw: case(**kw)['gain_vs_best_control_pct']
    breakeven = {
        'c0 at +2% vs best control (s1 0.48)': solve(lambda c: g(s1=0.48, c0=c), 0.3, 2.0, 2.0),
        's1 at +2% vs best control (c0 0.55)': solve(lambda s: g(s1=s, c0=0.55), 0.0, 0.8, 2.0),
        's1 at +0.5% vs best control (c0 0.55)': solve(lambda s: g(s1=s, c0=0.55), 0.0, 0.8, 0.5),
        'extra boundary latency at +2% (central)': solve(lambda e: g(s1=0.48, c0=0.55, extra=e), 0.0, 2.0, 2.0),
    }
    out = dict(schema='packet186.v3-measured-price.v1', source='analysis/p185-intervals.json.gz (packet185 lane-B receipts)',
               control_rates=c_rates, best_control=best, mean_control=mean_c, unsplit_rates=[v['rate'] for v in unsplit],
               record=RECORD, record_bar=1.02 * RECORD, measured_scopes_ms_per_cycle=scopes, rank0_layer_body_ms_per_half=layer_body_per_half,
               rank0_ms_per_layer_measured=[x / 24 for x in layer_body_per_half], cases=cases, breakeven=breakeven,
               model=__doc__.strip().splitlines()[0])
    (HERE / 'price-v3-measured.json').write_text(json.dumps(out, indent=1) + '\n')
    print('controls', [round(x, 3) for x in c_rates], 'unsplit', [round(v['rate'], 3) for v in unsplit])
    print('scopes per cycle (ms):', {k: [round(x, 4) for x in v] for k, v in scopes.items()})
    for k, v in cases.items():
        print(f"{k:62s} V3 {v['v3_rate_min']:.3f}  {v['gain_vs_best_control_pct']:+.2f}% (vs mean {v['gain_vs_mean_control_pct']:+.2f}%)"
              f"  hit {v['hit_ms']:.3f} miss {v['miss_ms']:.3f}  record-bar {'YES' if v['clears_record_bar'] else 'no'}")
    for k, v in breakeven.items():
        print(f'{k}: {v:.3f} ms')


if __name__ == '__main__':
    main()
