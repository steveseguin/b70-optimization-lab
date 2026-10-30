#!/usr/bin/env python3
"""Best existing exact multi-row kernel per site at M = 2..4 (research/decode-site-census-2026-10-30). CPU only.

  tiles.py RUN --out results/rank<r>-tiles.json

RUN is a census_driver.py --trace --cycle run: PREFILL call i (all calls, prefix chunks included, counted from process
start) uses tile configuration i % 6 of the dense token-row kernels (reuse2, OWNRT_PREFILL_REUSE2_CYCLE: five tiles, index
5 = the existing one-row kernel's token-row path) and i % 3 of the expert-grouped kernels (xgroup,
OWNRT_PREFILL_EXPERTS_CYCLE: two tiles, index 2 = the existing per-slot kernel). For every site role and M the median
device time per configuration is reported, and the best configuration against the one-row decode time."""
import argparse, collections, json, re, statistics
from pathlib import Path

REUSE2 = ['1x32', '4x8', '1x4 (GRF128)', '1x1 (GRF128)', '2x16 tile-major', 'existing kernel']
XGROUP = ['2x4', '1x4', 'existing per-slot kernel']
LAYER = re.compile(r'^blk\.\d+\.(.*)$')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--decode', help='analyze.py sites JSON of a traced run of the same rank (one-row decode reference)')
    ap.add_argument('--out')
    a = ap.parse_args()
    run = Path(a.run)
    s = json.loads((run / 'summary.json').read_text())
    if not s.get('cycle'):
        raise SystemExit('not a --cycle run')
    K = s['prefix']
    pcalls = [c for c in s['calls'] if c[0] == 15]
    small = [i for i, c in enumerate(pcalls) if c[2] <= 8]
    phases, ev = [], collections.defaultdict(lambda: collections.defaultdict(float))
    with open(run / f"rank{s['rank']}" / 'site-trace.jsonl') as f:
        for line in f:
            d = json.loads(line)
            if 'phase' in d:
                if d['kind'] == 'prefill':
                    phases.append(d)
            else:
                m = LAYER.match(d['c'])
                ev[d['p']][m.group(1) if m else d['c']] += (d['e'] - d['s']) / 1000.0
    if len(phases) != len(small):
        raise SystemExit(f'{len(phases)} traced prefill phases vs {len(small)} PREFILL calls of at most 8 rows')
    data = collections.defaultdict(lambda: collections.defaultdict(list))   # (M, role) -> config -> [us]
    span = collections.defaultdict(lambda: collections.defaultdict(list))
    for ph, i in zip(phases, small):
        if ph['position'] < K + 8:
            continue
        M, cr, cx = ph['rows'], i % 6, i % 3
        for role, us in ev[ph['phase']].items():
            key = cx if role in ('expsgate', 'expsup', 'expsdown') else cr
            data[(M, role)][key].append(us)
        span[M][(cr, cx)].append(sum(ev[ph['phase']].values()))
    dec = json.loads(Path(a.decode).read_text())['modes']['d']['half']['roles'] if a.decode else {}
    out = dict(run=str(run), rank=s['rank'], configs=dict(reuse2=REUSE2, xgroup=XGROUP), sites=[], busy_by_config={})
    for (M, role), byc in sorted(data.items()):
        names = XGROUP if role in ('expsgate', 'expsup', 'expsdown') else REUSE2
        med = {names[c]: statistics.median(v) for c, v in sorted(byc.items())}
        best = min(med, key=med.get)
        t1 = dec.get(role, {}).get('us')
        out['sites'].append(dict(rows=M, role=role, by_config_us=med, best=best, best_us=med[best], decode_us=t1,
                                 best_vs_decode1=(med[best] / t1) if t1 else None, samples={names[c]: len(v) for c, v in byc.items()}))
    for M, by in sorted(span.items()):
        out['busy_by_config'][str(M)] = {f'{REUSE2[cr]} | {XGROUP[cx]}': statistics.median(v) for (cr, cx), v in sorted(by.items())}
    # best-of per role summed: the chunk an exact per-site choice of existing kernels would give (device busy)
    for M in sorted({r['rows'] for r in out['sites']}):
        rows = [r for r in out['sites'] if r['rows'] == M]
        out.setdefault('best_choice_busy_us', {})[str(M)] = sum(r['best_us'] for r in rows)
    txt = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(txt)
    for M, v in out['best_choice_busy_us'].items():
        print(f'M={M}: per-site best existing kernels, summed busy {v:.0f} us')
    for r in out['sites']:
        if r['decode_us'] and r['decode_us'] > 100:
            print(f"M={r['rows']} {r['role']:16s} decode {r['decode_us']:7.0f} best {r['best_us']:7.0f} ({r['best']}) x{r['best_vs_decode1']:.2f}  "
                  + ' '.join(f'{k}:{v:.0f}' for k, v in r['by_config_us'].items()))


if __name__ == '__main__':
    main()
