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
        r = dict(phase=f.name[:-len('-compare.txt')], kind='cross-context' if rank.startswith('rankx') else 'bitwise', rank=int(rank[-1]), a=a.replace(A, 'archive:'), b=b.replace(A, 'archive:'))
        if 'target' in j:
            t = j['target']; d = j.get('draft')
            r.update(target_exact=t['exact'], target_prefix_zero=len(t['extended']), target_differ=len(t.get('differ') or []),
                     draft_exact=d['exact'] if d else None, draft_prefix_zero=len(d['extended']) if d else None, equal=bool(j.get('passed')))
        else:
            r.update(target_compared=j['compared'], target_differ=j['differ_count'], only_one_side=len(j['only_one_side']), other_fields_differ=bool(j['other_fields_differ']),
                     draft_compared=j.get('draft_compared'), draft_differ=j.get('draft_differ_count'), draft_tokens_equal=j.get('draft_tokens_equal'))
            r['equal'] = not (j['differ_count'] or j['only_one_side'] or j['other_fields_differ'] or j.get('draft_differ_count') or j.get('draft_only_one_side') or j.get('draft_tokens_equal') is False)
        rows.append(r)
out = dict(comparisons=len(rows), all_equal=all(r['equal'] for r in rows), rows=rows)
(D / 'results/gates.json').write_text(json.dumps(out, indent=1) + '\n')
print(out['comparisons'], 'comparisons, all equal:', out['all_equal'])
for r in rows: print(r['phase'], r['kind'], 'rank', r['rank'], r['a'], 'vs', r['b'], 'equal' if r['equal'] else 'DIFFER')
