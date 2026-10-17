#!/usr/bin/env python3
"""Read a hang's evidence (notes/2026-10-17-hang-repro.md): the b70-step-breadcrumbs blocks of both ranks from a server
log, and optionally a folder of rolling engine-register snapshots (`<pci>-NN.txt`, debugfs gt0/hw_engines).

  analyze-hang-evidence.py --log server.log [--hw DIR]

Breadcrumbs: for each block (rank, reason) the last steps; then, step by step, whether the two ranks were given the
same step (tokens, per-request scheduled and computed tokens) and issued the same collectives (count, elements,
signature; 0.2.0 blocks only). The first step where they differ is printed.
Engine snapshots: per card and engine (ccs0, bcs0), in time order, the instruction the command streamer last parsed
(IPEHR), its position (ACTHD), the running context (CURRENT_LRCA) and RING_INSTDONE. ROW_INSTDONE is not used: it
reads 0 on every row of an idle engine too (checked on the live server, 2026-10-17 13:17). Healthy server values seen:
idle 0x00000000/0xfffffffe; busy STATE_COMPUTE_MODE 0x61050001 with 0xffdeffff or 0xffdfffff; semaphore wait
0x0e009003 with 0xffdefffe. The 06:23 dump had 0x61050001 with 0xffdefffe.
"""
import argparse
import os
import re
from collections import defaultdict

ap = argparse.ArgumentParser()
ap.add_argument('--log', required=True)
ap.add_argument('--hw')
a = ap.parse_args()

STEP = re.compile(r'#(\d+) (\S+) tokens (\d+) fin (\d+) pre (\d+)( ONE-LAUNCH)? ((?:\[[^\]]*\] ?)*) ?\| (?:coll (\d+) elems (\d+) sig (\w+) \| )?(.*)$')
blocks = []
cur = None
for line in open(a.log, errors='replace'):
    m = re.search(r'b70_step_breadcrumbs rank (\S+) (STALL|FAILED)(.*?); last \d+ steps', line)
    if m:
        cur = {'rank': m.group(1), 'reason': (m.group(2) + m.group(3))[:200], 'steps': {}}
        blocks.append(cur)
        continue
    if cur is not None:
        s = STEP.search(line)
        if s:
            cur['steps'][int(s.group(1))] = {
                't': s.group(2), 'tokens': int(s.group(3)), 'fin': int(s.group(4)), 'one_launch': bool(s.group(6)),
                'reqs': s.group(7), 'coll': s.group(8), 'elems': s.group(9), 'sig': s.group(10), 'events': s.group(11)}
        elif not line.strip().startswith('(') and '#' not in line:
            cur = None

print('%d breadcrumb blocks' % len(blocks))
for b in blocks:
    last = max(b['steps']) if b['steps'] else None
    print('  rank %s %s; steps %s..%s' % (b['rank'], b['reason'], min(b['steps']) if b['steps'] else '-', last))
    for i in sorted(b['steps'])[-4:]:
        s = b['steps'][i]
        print('    #%d %s tokens %d fin %d%s coll %s elems %s sig %s | %s' % (
            i, s['t'], s['tokens'], s['fin'], ' ONE-LAUNCH' if s['one_launch'] else '', s['coll'], s['elems'], s['sig'],
            s['reqs'][:160]))
by_rank = defaultdict(dict)
for b in blocks:
    by_rank[b['rank']].update(b['steps'])
if '0' in by_rank and '1' in by_rank:
    common = sorted(set(by_rank['0']) & set(by_rank['1']))
    print('steps seen by both ranks: %d (%s..%s)' % (len(common), common[0] if common else '-', common[-1] if common else '-'))
    diff = None
    for i in common:
        x, y = by_rank['0'][i], by_rank['1'][i]
        kx = (x['tokens'], re.sub(r'\| w comp[^\]]*', '', x['reqs']), x['coll'], x['elems'], x['sig'])
        ky = (y['tokens'], re.sub(r'\| w comp[^\]]*', '', y['reqs']), y['coll'], y['elems'], y['sig'])
        if kx != ky:
            diff = i
            print('FIRST DIFFERENCE at step #%d:\n  rank 0: %s\n  rank 1: %s' % (i, kx, ky))
            break
    if diff is None:
        print('the two ranks were given the same steps and issued the same collectives in every common step')
    only = sorted(set(by_rank['0']) ^ set(by_rank['1']))
    if only:
        print('steps seen by one rank only:', only[-6:])

if a.hw:
    rows = defaultdict(list)
    for f in sorted(os.listdir(a.hw)):
        m = re.match(r'(0000:\w\w:00\.0)-(\d\d)\.txt$', f)
        if not m:
            continue
        text = open(os.path.join(a.hw, f), errors='replace').read()
        t = re.search(r'^# (\S+ \S+)', text)
        engine = None
        regs = defaultdict(dict)
        for line in text.splitlines():
            e = re.match(r'^(\w+\d+) \(physical\)', line)
            if e:
                engine = e.group(1)
                continue
            r = re.match(r'^\s+(\w+(?:\[\d+\])?): (0x[0-9a-f]+)', line)
            if r and engine in ('ccs0', 'bcs0'):
                regs[engine][r.group(1)] = r.group(2)
        for engine, rr in regs.items():
            rows[(m.group(1), engine)].append((t.group(1) if t else '?', rr.get('IPEHR'), rr.get('ACTHD'),
                                                rr.get('CURRENT_LRCA'), rr.get('RING_INSTDONE')))
    for key in sorted(rows):
        print('engine snapshots %s %s (time, IPEHR, ACTHD, CURRENT_LRCA, RING_INSTDONE):' % key)
        for r in sorted(rows[key]):
            print('   ', *r)
