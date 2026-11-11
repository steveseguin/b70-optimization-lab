#!/usr/bin/env python3
"""Table of a long-document campaign's summary.txt (round 18 e82 / e84 / e85): per run the prompt length,
prompt reading tok/s, plain or guessing answer tok/s (draft / check ms per cycle), and the answer checks.
  python3 -I tab_long.py summary.txt > table.md"""
import re
import sys

runs, order, checks = {}, [], {}
for line in open(sys.argv[1]):
    line = line.rstrip('\n')
    m = re.match(r'^(\S+?): (.*)$', line)
    if m:
        name, rest = m.groups()
        r = runs.setdefault(name, {})
        if name not in order:
            order.append(name)
        p = re.match(r'prompt: (\d+) tokens read on the cards in ([\d.]+)s \(([\d.]+) tok/s', rest)
        if p:
            r['tokens'], r['read'] = int(p.group(1)), float(p.group(3))
        d = re.match(r'decode: (\d+) steps after the first, [\d.]+ s/step, ([\d.]+) tok/s', rest)
        if d:
            r['steps'], r['dec'] = int(d.group(1)), float(d.group(2))
        s = re.match(r'spec decode: .* = ([\d.]+) tok/s; draft ([\d.]+) ms \+ check ([\d.]+) ms per cycle; (.*)$', rest)
        if s:
            r['spec'], r['draft'], r['check'], r['same'] = float(s.group(1)), s.group(2), s.group(3), s.group(4)
        h = re.match(r'host io during decode: ([\d.]+) MiB read', rest)
        if h:
            r['io'] = float(h.group(1))
        continue
    a = re.match(r'^(\S+) (ANSWER\S+|SPEED\S+|TRACE\S+|IDS\S+)$', line)
    if a:
        checks.setdefault(a.group(1), []).append(a.group(2))
        if a.group(1) not in order:
            order.append(a.group(1))

print('| run | prompt tokens | reading tok/s | answer tok/s | ms per step (plain) | draft + check ms | disk MiB in answers | checks |')
print('| --- | --- | --- | --- | --- | --- | --- | --- |')
for n in order:
    r = runs.get(n, {})
    if not r and n not in checks:
        continue
    tok = f"{r['tokens']:,}" if 'tokens' in r else ''
    rd = f"{r['read']:.1f}" if 'read' in r else ''
    if 'spec' in r:
        ans, ms, dc = f"{r['spec']:.2f} (guessing)", '', f"{r['draft']} + {r['check']}"
    elif 'dec' in r:
        ans, ms, dc = f"{r['dec']:.2f}", f"{1000.0 / r['dec']:.2f}", ''
    else:
        ans = ms = dc = ''
    io = f"{r['io']:.1f}" if 'io' in r else ''
    ck = ', '.join(checks.get(n, []) + ([r['same']] if 'same' in r else []))
    print(f'| {n} | {tok} | {rd} | {ans} | {ms} | {dc} | {io} | {ck} |')
