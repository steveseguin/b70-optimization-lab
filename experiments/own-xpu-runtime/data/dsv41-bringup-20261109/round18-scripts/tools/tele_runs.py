#!/usr/bin/env python3
# per run: the decode window = the last `dec` seconds before power falls at the end; mean power / clock / idle per tile
import sys, re
D = sys.argv[1]
rows = [l.split() for l in open(D + "/telemetry.smp")]
marks = {}
for l in open(D + "/marks.txt"):
    n, k, t = l.split(); marks.setdefault(n, {})[k] = float(t)
dec = {}
for l in open(D + "/summary.txt"):
    m = re.match(r"(\S+): spec decode: .* in ([\d.]+)s = ([\d.]+) tok/s; draft ([\d.]+) ms \+ check ([\d.]+)", l)
    if m: dec[m.group(1)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)), float(m.group(5)))
by = {}
for r in rows:
    by.setdefault(int(r[1]), []).append((float(r[0]), int(r[2]) if r[2].isdigit() else -1, r[3], int(r[4]) if r[4].isdigit() else 0))
for name, mk in marks.items():
    if name not in dec or "end" not in mk: continue
    s, tps, dr, ck = dec[name]
    e = mk["end"]
    out = []
    for tile in sorted(by):
        r = [x for x in by[tile] if mk["start"] <= x[0] <= e]
        # find the last 0.2 s window with power > 120 W: decode end
        pw = [(r[i][0], (r[i + 1][3] - r[i][3]) / 1e6 / max(1e-6, r[i + 1][0] - r[i][0])) for i in range(len(r) - 1)]
        hi = [t for t, p in pw if p > 120]
        if not hi: out.append("  -"); continue
        t1 = hi[-1]; t0 = t1 - s + 0.3
        w = [x for x in r if t0 <= x[0] <= t1]
        en = (w[-1][3] - w[0][3]) / 1e6 / (w[-1][0] - w[0][0])
        busy = [x[1] for x in w if x[1] > 0]
        fq = sum(busy) / max(1, len(busy)); idle = 1 - len(busy) / len(w)
        thr = sum(1 for x in w if x[2] != "none")
        lo = sum(1 for f in busy if f < 2700)
        out.append(f"{en:4.0f}W {fq:4.0f}MHz lo{lo:3d} thr{thr:2d}")
    print(f"{name:14s} {tps:7.2f} c{ck:5.2f} | " + " | ".join(out))
