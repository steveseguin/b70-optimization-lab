#!/usr/bin/env python3
"""Card c's four-card prefill work measured on one card (research/tp/prefill-tp-overhead-2026-10-30), CPU only.
Inputs: probe arms (probe build, mode probe0 / probe1: OWNRT_TP_SHAPE_PROBE=c, one card, --timing class, OWNRT_SITE_TRACE=1,
the same prompt and steps as the one-card M1 arm) and the one-card M1 class file (results/m-r<r>-one256-classes.json).
Every prefill site is its own class (its label); a class is the label without "blk.N.". The probe runs exactly card c's
TP kernels, rows, heads and slots, so per class: one card (all the work) vs card c (its TP share). Outputs after the
first split site are not the model's (the peer's rows are never written): routes, and so the expert tiles, come from
perturbed rows; replicated classes show how far that moves their times.
Kinds: split (TP halves it), replicated (both cards do all of it), tp-only (TP's own sites, e.g. route compaction), and
excluded (draft.*, and commit.final, where the rank-0 draft chunk's events land; the TP wall excludes the draft command).
Usage: analyze_probe.py RANK CHUNKS ONE_CARD_JSON PROBE0_RUN PROBE1_RUN [--json OUT]"""
import json, re, sys
from pathlib import Path
rank, chunks, one_path, p0, p1 = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
out_path = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
SPLIT = {'gdn.qkv', 'gdn.z', 'gdn.a', 'gdn.b', 'gdn.conv', 'gdn.recurrence', 'gdn.gated', 'attention', 'qsa.qgate', 'qsa.k', 'qsa.v',
         'qsa.prepare', 'qsa.pool', 'qsa.attention', 'expsgate', 'expsup', 'expsact', 'expsdown', 'expsgate.check', 'expsup.check', 'expsdown.check'}
def cls_of(label):
    m = re.match(r'blk\.\d+\.(.*)$', label)
    return m.group(1) if m else label
def kind(k):
    if k.startswith('draft.') or k == 'commit.final': return 'excluded'
    if 'tp_' in k or '#tp' in k: return 'tp-only'
    return 'split' if k in SPLIT else 'replicated'
def pick(run, name):  # a harness run (RUN/rank<r>/name) or its kept evidence (flat)
    f = run / f'rank{rank}' / name
    return f if f.exists() else run / name
def load(run):
    d = json.loads(pick(run, 'class-times.json').read_text()); agg = {}
    for c in d['classes']:
        k = cls_of(c['class']); a = agg.setdefault(k, [0.0, 0]); a[0] += c['device_ms'] / chunks; a[1] += c['launches']
    return agg
one = {k: [v['ms_per_chunk'], v['launches']] for k, v in json.loads(one_path.read_text())['classes'].items()}
one = {('draft.' + k[6:] if k.startswith('draft:') else k): v for k, v in one.items()}  # analyze_class_times keys draft classes 'draft:'
probes = [load(p0), load(p1)]
probe_meta = [json.loads(pick(p, 'tp-shape-probe.json').read_text()) for p in (p0, p1)]
keys = sorted(set(one) | set(probes[0]) | set(probes[1]), key=lambda k: -max(one.get(k, [0])[0], probes[0].get(k, [0])[0]))
rows, tot = [], {}
for k in keys:
    kd = kind(k); o = one.get(k, [0.0, 0])[0]; c0 = probes[0].get(k, [0.0, 0])[0]; c1 = probes[1].get(k, [0.0, 0])[0]
    rows.append(dict(cls=k, kind=kd, one_card_ms=o, card0_ms=c0, card1_ms=c1, card_over_one=[c0 / o if o else None, c1 / o if o else None],
                     nonhalving_ms=[c0 - o / 2, c1 - o / 2] if kd == 'split' else None))
    t = tot.setdefault(kd, dict(one_card_ms=0.0, card_ms=[0.0, 0.0])); t['one_card_ms'] += o; t['card_ms'][0] += c0; t['card_ms'][1] += c1
busy = [sum(tot[k]['card_ms'][c] for k in tot if k != 'excluded') for c in (0, 1)]
one_total = sum(tot[k]['one_card_ms'] for k in tot if k != 'excluded')
res = dict(rank=int(rank), chunks=chunks, one_card=str(one_path), probes=[str(p0), str(p1)], probe_files=probe_meta,
           one_card_ms=one_total, perfect_split_ms=one_total / 2, card_busy_ms=busy, totals=tot,
           split_nonhalving_ms=[tot.get('split', {}).get('card_ms', [0, 0])[c] - tot.get('split', {}).get('one_card_ms', 0) / 2 for c in (0, 1)],
           replicated_change_ms=[tot.get('replicated', {}).get('card_ms', [0, 0])[c] - tot.get('replicated', {}).get('one_card_ms', 0) for c in (0, 1)],
           classes=rows)
if out_path: Path(out_path).write_text(json.dumps(res, indent=1) + '\n')
print(f"rank {rank}: one card {one_total:.1f} ms per chunk (perfect split {one_total / 2:.1f}); probe card busy card0/card1 {busy[0]:.1f}/{busy[1]:.1f}")
for kd, t in tot.items():
    print(f"  {kd:10s} one card {t['one_card_ms']:8.2f}  card0 {t['card_ms'][0]:8.2f}  card1 {t['card_ms'][1]:8.2f}")
print(f"  split work not halving card0/card1 {res['split_nonhalving_ms'][0]:.1f}/{res['split_nonhalving_ms'][1]:.1f}; replicated change "
      f"{res['replicated_change_ms'][0]:+.1f}/{res['replicated_change_ms'][1]:+.1f}")
for r in rows:
    if max(r['one_card_ms'], r['card0_ms'], r['card1_ms']) >= 0.5:
        nh = '' if r['nonhalving_ms'] is None else f"  not halving {r['nonhalving_ms'][0]:+6.2f}/{r['nonhalving_ms'][1]:+6.2f}"
        print(f"  {r['cls']:26s} {r['kind']:10s} one {r['one_card_ms']:8.2f}  card0 {r['card0_ms']:8.2f}  card1 {r['card1_ms']:8.2f}{nh}")
