# Markdown table from a campaign summary: rows = <arm><round> suffixes, columns = the five prompts, median of 5,
# 3K document; then the mean check ms, engram-row us and MiB read per row. Usage: tab_runs.py summary.txt
import re, statistics as st, sys
sp, io = {}, {}
for l in open(sys.argv[1]):
    m = re.match(r'(\S+?)_(\w+): spec decode: .* = ([0-9.]+) tok/s; draft ([0-9.]+) ms \+ check ([0-9.]+) ms', l)
    if m: sp[(m.group(1), m.group(2))] = (float(m.group(3)), float(m.group(4)), float(m.group(5)))
    m = re.match(r'(\S+?)_(\w+): host io during decode: ([0-9.]+) MiB read from disk, (\d+) major page faults; engram rows ([0-9.]+) us', l)
    if m: io[(m.group(1), m.group(2))] = (float(m.group(3)), float(m.group(5)))
P = ['code', 'prose', 'analysis', 'ops', 'docs']
arms = []
for (p, a) in sp:
    if a not in arms: arms.append(a)
print('| run | ' + ' | '.join(P) + ' | median of 5 | 3K document | check ms (mean of 6) | engram rows us/step | MiB from disk |')
print('| --- |' + ' --- |' * (len(P) + 5))
for a in arms:
    if not any((p, a) in sp for p in P): continue  # e.g. the fresh prompts' settings
    v = [sp.get((p, a), (float('nan'),))[0] for p in P]
    k = sp.get(('p3k', a), (float('nan'),))[0]
    allp = P + ['p3k']
    ch = [sp[(p, a)][2] for p in allp if (p, a) in sp]
    en = [io[(p, a)][1] for p in allp if (p, a) in io]
    mb = [io[(p, a)][0] for p in allp if (p, a) in io]
    med = st.median([x for x in v if x == x]) if any(x == x for x in v) else float('nan')
    print(f'| {a} | ' + ' | '.join(f'{x:.2f}' for x in v) + f' | {med:.2f} | {k:.2f} | {st.mean(ch):.2f} | {st.mean(en):.0f} | {sum(mb):.1f} |')
