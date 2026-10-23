#!/usr/bin/env python3
"""Per-prompt / per-class spread of the k3x counterfactual (uncertainty of the record metric), read-only."""
import importlib.util, json, statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('replay_k3x', HERE / 'replay_k3x.py')
rk = importlib.util.module_from_spec(spec); spec.loader.exec_module(rk)
rv = rk.rv


def per_prompt(rows, T):
    per, cls = defaultdict(float), {}
    for x, t in zip(rows, T):
        per[x['pid']] += t; cls[x['pid']] = x['cls']
    return {p: (cls[p], 99000 / s) for p, s in per.items()}


def main():
    d = json.loads((HERE / 'replay-k3x-output.json').read_text())['deltas']
    Bsplit = lambda h, m: (lambda x: h if x['hit'] else m)
    k3x = dict(dD=d['dD_kio'], dBd=d['layer26_body'] + d['boundary_envelope_other'], dB=Bsplit(d['dB_hit'], d['dB_miss']), dA=d['dA_trims'], dC=d['dC_trims'])
    out = {}
    for name in ('00-control', '02-control', '04-control'):
        rows = rk.load_view_plus(rk.VIEWS / name)
        base = per_prompt(rows, [x['elapsed_ms'] for x in rows])
        cf = per_prompt(rows, [rk.T_of(x, **k3x) for x in rows])
        gains = {p: 100 * (cf[p][1] / base[p][1] - 1) for p in base}
        bycls = defaultdict(list)
        for p, (c, r) in cf.items():
            bycls[c].append((p, base[p][1], r, gains[p]))
        out[name] = dict(per_prompt_gain_pct=gains, min=min(gains.values()), max=max(gains.values()), mean=st.mean(gains.values()),
                         class_medians_base={c: st.median(b for _, b, _, _ in v) for c, v in bycls.items()},
                         class_medians_k3x={c: st.median(r for _, _, r, _ in v) for c, v in bycls.items()})
        print(name, 'k3x per-prompt gain % min/mean/max', round(out[name]['min'], 2), round(out[name]['mean'], 2), round(out[name]['max'], 2))
        for c, v in sorted(bycls.items()):
            print('   class', c, [(p, round(b, 2), round(r, 2), round(g, 2)) for p, b, r, g in sorted(v)])
    # measured k3trims per-prompt vs V3 (how much do the two candidate views differ per prompt?)
    v1 = rk.load_view_plus(rk.VIEWS / '01-candidate'); v3 = rk.load_view_plus(rk.VIEWS / '03-candidate')
    a = per_prompt(v1, [x['elapsed_ms'] for x in v1]); b = per_prompt(v3, [x['elapsed_ms'] for x in v3])
    diff = {p: 100 * (b[p][1] / a[p][1] - 1) for p in a}
    print('measured k3trims view 3 vs view 1 per-prompt %:', {p: round(v, 2) for p, v in diff.items()})
    out['k3trims_view3_vs_view1_pct'] = diff
    (HERE / 'k3x-spread-output.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
