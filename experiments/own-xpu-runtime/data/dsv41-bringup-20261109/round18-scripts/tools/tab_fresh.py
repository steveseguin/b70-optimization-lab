# Fresh prompts run cold then warm with one setting each: per prompt the two runs, then per setting the median
# cost of the cold run (check ms per round and tok/s). Usage: tab_fresh.py summary.txt
import re, statistics as st, sys
sp, io, same = {}, {}, {}
for l in open(sys.argv[1]):
    m = re.match(r'(f\d+)_([a-z]+)(cold|warm): spec decode: \d+ tokens in (\d+) cycles.* = ([0-9.]+) tok/s; draft ([0-9.]+) ms \+ check ([0-9.]+) ms', l)
    if m: sp[(m.group(1), m.group(2), m.group(3))] = (float(m.group(5)), float(m.group(7)), int(m.group(4)))
    m = re.match(r'(f\d+)_([a-z]+)(cold|warm): host io during decode: ([0-9.]+) MiB read from disk, (\d+) major page faults; engram rows ([0-9.]+) us', l)
    if m: io[(m.group(1), m.group(2), m.group(3))] = (float(m.group(4)), float(m.group(6)))
    m = re.match(r'(f\d+) cold/warm (SAME|DIFFER)', l)
    if m: same[m.group(1)] = m.group(2)
print('| prompt | setting | cold tok/s | warm tok/s | cold / warm | check ms cold | check ms warm | MiB from disk cold / warm | engram rows us cold / warm | cold = warm text |')
print('| --- |' + ' --- |' * 9)
pen = {}
for f in sorted({k[0] for k in sp}, key=lambda s: int(s[1:])):
    for a in sorted({k[1] for k in sp if k[0] == f}):
        c, w = sp.get((f, a, 'cold')), sp.get((f, a, 'warm'))
        if not c or not w: continue
        ic, iw = io.get((f, a, 'cold'), (0, 0)), io.get((f, a, 'warm'), (0, 0))
        pen.setdefault(a, []).append((c[0] / w[0], c[1] - w[1]))
        print(f'| {f} | {a} | {c[0]:.2f} | {w[0]:.2f} | {c[0] / w[0]:.3f} | {c[1]:.2f} | {w[1]:.2f} | {ic[0]:.1f} / {iw[0]:.1f} | {ic[1]:.0f} / {iw[1]:.0f} | {same.get(f, "?")} |')
for a, v in pen.items():
    print(f'setting {a}: {len(v)} prompts, cold / warm tok/s median {st.median(x[0] for x in v):.3f}, '
          f'check +{st.median(x[1] for x in v):.2f} ms per round (median)')
