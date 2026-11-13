"""Per check: role sums (us) per card, then the median over checks of each M (role sums per check, not per name).
usage: python3 -I roles_ck.py timeline spec first_line cards"""
import sys, statistics as st, collections, importlib.util
spec_ = importlib.util.spec_from_file_location('r', '/home/steve/dsv41-work/ckm/tools/roles.py')
tl, spec, first = sys.argv[1], sys.argv[2], int(sys.argv[3])
cards = [int(c) for c in sys.argv[4].split(',')]
rows = [l.split() for l in open(spec) if l.strip() and not l.startswith('#')]
src = open('/home/steve/dsv41-work/ckm/tools/roles.py').read()
role = None
exec(src[src.index('def role'):src.index('roles = collections')], globals())
names = {}
acc = collections.defaultdict(lambda: collections.defaultdict(float))
for ln in open(tl):
    p = ln.split()
    if not p: continue
    if p[0] == 'kname': names[int(p[1])] = ln.split(None, 2)[2].strip().replace('ActF32', 'A').replace('u,', ',').replace('u>', '>').replace(' ', ''); continue
    if not p[0][0].isdigit() or len(p) < 13: continue
    c = int(p[1])
    if c not in cards: continue
    acc[(int(p[0]), c)][role(names[int(p[3])])] += (int(p[8]) - int(p[7])) / 1e3
steps = sorted(set(k[0] for k in acc))
M = {s: int(rows[first - 1 + (s - steps[0])][5]) + 1 for s in steps}
R = sorted(set(r for v in acc.values() for r in v))
Ms = sorted(set(M.values()))
for c in cards:
    print(f'card {c}: role us per check (median over checks)  ' + ''.join(f'{"M=%d" % m:>8}' for m in Ms) + '   slope/token M2->6')
    for r in R + ['TOTAL']:
        v = [st.median([(sum(acc[(s, c)].values()) if r == 'TOTAL' else acc[(s, c)].get(r, 0.0)) for s in steps if M[s] == m]) for m in Ms]
        print(f'  {r:20s}' + ''.join(f'{x:8.0f}' for x in v) + f'   {(v[-1] - v[1]) / 4:8.1f}')
