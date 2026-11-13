import sys
# dump launch sequence of (step, card): idx, dur us, name (shortened)
f, step, card = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
lo = int(sys.argv[4]) if len(sys.argv) > 4 else 0; hi = int(sys.argv[5]) if len(sys.argv) > 5 else 10**9
names = {}
out = []
for ln in open(f):
    p = ln.split()
    if p[0] == 'kname': names[int(p[1])] = ln.split(None, 2)[2].strip()
    elif p[0][0].isdigit() and len(p) >= 13 and int(p[0]) == step and int(p[1]) == card:
        out.append((int(p[2]), int(p[3]), (int(p[8]) - int(p[7])) / 1e3, int(p[10]), int(p[11])))
out.sort()
for i, (idx, nid, d, xp, xm) in enumerate(out):
    if lo <= i < hi:
        print(f'{i:4d} {d:7.1f} x{xp:>2} {names[nid][:150]}')
