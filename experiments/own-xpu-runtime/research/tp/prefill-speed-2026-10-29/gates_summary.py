#!/usr/bin/env python3
"""All rank-harness comparisons of research/tp/prefill-speed-2026-10-29 (logs/*-compare.txt, written by compare_phase.sh)
into results/gates.json: per comparison the phase, ranks/runs, buffer counts and the verdict. CPU only."""
import json, re
from pathlib import Path
D = Path(__file__).resolve().parent
A = '/mnt/raid-models/ownrt-experiment-archives/2026-10-29/'
rows = []
for f in sorted((D / 'logs').glob('*-compare.txt')):
    for l in f.read_text().splitlines():
        if not l.startswith('rank'): continue
        head, body = l.split(': ', 1); j = json.loads(body)
        rank, a, _, b = head.split(' ', 3)
        r = dict(phase=f.name[:-len('-compare.txt')], kind='cross-context' if rank.startswith('rankx') else 'bitwise', rank=int(rank[-1]), a=a.replace(A, 'archive:').replace('/dev/shm/prefill-speed-20261029/', 'shm:'), b=b.replace(A, 'archive:').replace('/dev/shm/prefill-speed-20261029/', 'shm:'))
        if 'second' in j: r['second_request'] = j['second'].get('passed', j.get('second_ok'))
        if 'ones' in j: r['ones_ok'] = all(o['ok'] for o in j['ones']); r['ones_checked'] = len(j['ones'])
        if 'inventory' in j: r['inventory_differ'] = {k: v.get('differ_count') for k, v in j['inventory'].items()}
        if 'target' in j:
            t = j['target']; d = j.get('draft')
            r.update(target_exact=t['exact'], target_prefix_zero=len(t['extended']), target_differ=len(t.get('differ') or []),
                     draft_exact=d['exact'] if d else None, draft_prefix_zero=len(d['extended']) if d else None, equal=bool(j.get('passed')))
        else:
            r.update(target_compared=j['compared'], target_differ=j['differ_count'], only_one_side=len(j['only_one_side']), other_fields_differ=bool(j['other_fields_differ']),
                     draft_compared=j.get('draft_compared'), draft_differ=j.get('draft_differ_count'), draft_tokens_equal=j.get('draft_tokens_equal'))
            r['equal'] = not (j['differ_count'] or j['only_one_side'] or j['other_fields_differ'] or j.get('draft_differ_count') or j.get('draft_only_one_side') or j.get('draft_tokens_equal') is False
                              or j.get('second_ok') is False or ('ones' in j and not all(o['ok'] for o in j['ones'])))
        rows.append(r)
# Phases named *expect-fail* run the faulty build r6 on purpose: their comparisons must DIFFER (the gate sees the bug).
exp = [r for r in rows if 'expect-fail' in r['phase']]; gate = [r for r in rows if 'expect-fail' not in r['phase']]
out = dict(comparisons=len(gate), all_equal=all(r['equal'] for r in gate), expect_fail_comparisons=len(exp),
           expect_fail_rows_that_differ=sum(not r['equal'] for r in exp), rows=rows)
(D / 'results/gates.json').write_text(json.dumps(out, indent=1) + '\n')
print(out['comparisons'], 'comparisons, all equal:', out['all_equal'], '| expect-fail:', out['expect_fail_comparisons'], 'of which differ', out['expect_fail_rows_that_differ'])
for r in rows: print(r['phase'], r['kind'], 'rank', r['rank'], r['a'], 'vs', r['b'], 'equal' if r['equal'] else 'DIFFER')
