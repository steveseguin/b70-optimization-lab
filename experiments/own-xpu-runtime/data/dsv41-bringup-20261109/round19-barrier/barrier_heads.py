#!/usr/bin/env python3
"""barrier_heads.py: the stable-mode barrier model of barrier_sim.py with prompt heads split per head (not per 4).

Hypothetical layouts of 64 heads at granularity 4 / 2 / 1 (8-16 heads per card, so a group of 8 heads touches at
most two cards), per 512-token prompt piece (stable mode) and per one-token decode step.

Head cost per card (prompt; q_b rows, attention score / softmax / out, output-a rows):
  L  linear: cost_c(h) = cost_c(now) * h / h_now
  S  piecewise linear f(h) through (8, f8) (f8 measured: 8-head cards 4+5 / 12-head cards 1+2, all 230 W), (12, 1),
     (16, f16), f16 fitted so that the model reproduces st1's measured loss of heads 4,2,2,4,2,2;
     cost_c(h) = cost_c(now) * f(h) / f(h_now)
Split groups: a card whose head range starts / ends inside a group of 8 publishes after its attention, runs its
whole-group output-a rows, waits for the partner's publish and pulls the partner's heads of that group (prompt:
the profile's 4-head pull floor / 4 per head), then its share of the split group's rows (output-a rows per card
= 128 per head, as the engine's units). X1 copy bytes = 128 rows per head.
Decode: today whole groups (8,8,16,8,8,16); if a layout were used in one-token steps too, q_b / output-a /
attention scale affinely between the decode profile's 8- and 16-head cards, plus one pair wait per layer for split
groups (cost: the median one-token exchange on the last card to arrive).

Run: nice -n 19 python3 -I barrier_heads.py > barrier_heads.out.txt
"""
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, '/home/steve/dsv41-work/barrier')
import barrier_sim as B  # noqa: E402

NC = B.NC
CUR_H = tuple(4 * u for u in B.CUR_UNITS)  # 12,12,12,12,8,8
H1_H = tuple(4 * u for u in B.H1_UNITS)    # 16,8,8,16,8,8
DEC_H = (8, 8, 16, 8, 8, 16)               # one-token steps: whole groups 8c/6 (tp_setup tog0 / tog1)
# st1 (dsv41-work/runs/st1-smtoff-20261115T1652, tp115 stable): read s and first step s (incl. kernel build)
ST1 = {'3K def': (4.93, 0.81), '3K h1': (5.82, 0.91), '10K def': (15.55, 0.78), '10K h1': (18.44, 0.91)}


def bounds(heads):
    b = [0]
    for h in heads:
        b.append(b[-1] + h)
    return b


def pairs_h(heads):
    """per card: [(partner, heads pulled from it, own heads in that split group)]"""
    b = bounds(heads)
    out = []
    for c in range(NC):
        h0, h1 = b[c], b[c + 1]
        if h1 - h0 < 8:
            raise ValueError('fewer than 8 heads on a card')
        p = []
        if h0 % 8:
            p.append((c - 1, h0 % 8, 8 - h0 % 8))
        if h1 % 8:
            p.append((c + 1, 8 - h1 % 8, h1 % 8))
        out.append(p)
    return out


def curve_lin(h, hnow):
    return h / hnow


def make_curve(f8, f16):
    def f(h):
        if h <= 12:
            return f8 + (h - 8) * (1 - f8) / 4
        return 1 + (h - 12) * (f16 - 1) / 4
    return lambda h, hnow: f(h) / f(hnow)


def make_progs_h(base, piece, heads, curve, fl, ab, bw, prt=None):
    a, b = ab
    td0 = B.rows(B.H, (0,) * 6)
    tm0 = B.rows(B.MID, (0,) * 6)
    te0 = B.rows(B.ENGR, (0,) * 6)
    pr = pairs_h(heads)
    pull1 = fl['p2'] / 4.0  # us per pulled head (the profile's 4-head pull floor)
    progs, copy, fams = [], [], []
    for c in range(NC):
        h = heads[c]
        hf = curve(h, CUR_H[c])
        sc = {f: hf for f in B.HEADF}
        if prt:
            tk = B.rows(B.HALF, prt)
            sc['qakv'] = sc['router'] = tk[c] / B.HALF
        mib = {'X1': (B.OTOTAL // 64 * h * B.HALF * 4) / B.MIB + B.DS_MIB, 'X2': td0[c] * B.HALF * 4 / B.MIB,
               'X4': td0[c] * B.HALF * 4 / B.MIB, 'X3': tm0[c] * 7 * B.HALF * 4 / B.MIB + B.DS_MIB,
               'ENG': te0[c] * 2 * 2 * B.HALF * 4 / B.MIB,
               'PRT': (B.rows(B.HALF, prt)[c] * 1792 * 4 / B.MIB) if prt else 0.0}
        cp = {s: a + b * bw * m for s, m in mib.items()}
        P, F, npair = [], [], 0
        for it in base[(piece, c)]:
            k = it[0]
            if k == 'k':
                f = it[1]
                P.append(('k', it[2] * sc.get(f, 1.0)))
                F.append(f)
                if prt and ((f == 'qakv' and len(F) >= 2 and F[-2] == 'qakv') or f == 'router'):
                    lab = ('PRT', f, sum(1 for x in F if x == f))
                    P += [('push', lab), ('bar', lab)]
                    F += [None, None]
            elif k == 'oa':
                tot = it[1]['oa'] * hf
                own_split = sum(o for _, _, o in pr[c])
                if pr[c]:
                    P.append(('pub', npair))
                    F.append('pair')
                    if h - own_split > 0:
                        P.append(('k', tot * (h - own_split) / h))
                        F.append('out_a')
                    P.append(('pw', npair, tuple(d for d, _, _ in pr[c]), pull1 * sum(n for _, n, _ in pr[c])))
                    F.append('pair')
                    P.append(('k', tot * own_split / h))
                    F.append('out_a')
                else:
                    P.append(('k', tot))
                    F.append('out_a')
                npair += 1
            elif k == 'push':
                P.append(('push', it[2]))
                F.append(None)
                if it[2][0] != 'ENG':
                    P.append(('bar', it[2]))
                    F.append(None)
            elif k == 'await':
                P.append(('await', it[1]))
                F.append(None)
        progs.append(P)
        fams.append(F)
        copy.append(cp)
    return progs, fams, copy


class Ctx:
    def __init__(self):
        t, self.pieces, cards, self.base, prof, self.fl = B.read_prompt(B.PROMPT)
        self.ab = B.copy_fit()
        self.bw = 1.4
        self.cache = {}

    def T(self, heads, curve_key, curve, prt=None):
        key = (tuple(heads), curve_key, prt)
        if key not in self.cache:
            v = []
            for st in self.pieces:
                progs, fams, copy = make_progs_h(self.base, st, heads, curve, self.fl, self.ab, self.bw, prt)
                v.append(B.simulate(progs, copy, self.fl, self.fl['p1'])[0])
            self.cache[key] = statistics.mean(v) / 1e3
        return self.cache[key]


# ---- decode with a head layout
def dec_head_fam(nm):
    if nm.startswith('RowsP<RowsPair<RowsPair<HcFinishRows, RopeRows') and ('GemvQ8P<40u' in nm or 'GemvQ6KP<5u' in nm):
        return 'q_b'
    if nm.startswith(('GemvQ8P<128u', 'GemvQ6KP<16u')):
        return 'out_a'
    if nm.startswith('SparseOutF'):
        return 'attn'
    return None


class Dec:
    def __init__(self):
        self.steps, self.progs, self.spans = B.read_decode(B.DECODE)
        # affine head cost per family from the 8-head cards (0, 1, 3, 4) and the 16-head cards (2, 5)
        acc = defaultdict(float)
        nl = defaultdict(float)
        for s in self.steps:
            for c in range(NC):
                for f, d, nm in self.progs[s][c]:
                    hf = dec_head_fam(nm)
                    if hf:
                        acc[(hf, c)] += d / len(self.steps)
                        nl[(hf, c)] += 1.0 / len(self.steps)
        self.per = {f: [acc[(f, c)] for c in range(NC)] for f in ('q_b', 'out_a', 'attn')}
        self.slope = {}  # (us per step at 8 heads, at 16 heads, us per head per step, us per head per LAUNCH)
        for f, v in self.per.items():
            m8 = statistics.mean(v[c] for c in range(NC) if DEC_H[c] == 8)
            m16 = statistics.mean(v[c] for c in range(NC) if DEC_H[c] == 16)
            n = statistics.mean(nl[(f, c)] for c in range(NC))
            self.slope[f] = (m8, m16, (m16 - m8) / 8.0, (m16 - m8) / 8.0 / n)
        # per-instance exchange cost (last card to arrive) of the XchgP launches: the pair wait stand-in
        mins = []
        for s in self.steps:
            xs = [[d for f, d, nm in self.progs[s][c] if f == 'x' and nm.startswith('XchgP') and not nm.startswith('XchgPull')]
                  for c in range(NC)]
            for i in range(len(xs[0])):
                mins.append(min(xs[c][i] for c in range(NC)))
        self.pair_us = statistics.median(mins)

    def step(self, heads):
        pr = pairs_h(heads)
        tot = 0.0
        for s in self.steps:
            per = self.progs[s]
            segs = [[] for _ in range(NC)]
            xc = [[] for _ in range(NC)]
            for c in range(NC):
                cur = []
                for f, d, nm in per[c]:
                    if f == 'x':
                        segs[c].append(cur)
                        xc[c].append(d)
                        cur = []
                        continue
                    if f == 'copy':
                        continue
                    hf = dec_head_fam(nm)
                    if hf:
                        d = max(0.0, d + self.slope[hf][3] * (heads[c] - DEC_H[c]))
                    if hf == 'attn' and pr[c]:
                        cur.append(('k', d))
                        cur.append(('pub',))
                        continue
                    if hf == 'out_a' and pr[c]:
                        own = sum(o for _, _, o in pr[c])
                        cur.append(('k', d * (heads[c] - own) / heads[c]))
                        cur.append(('pw', tuple(p for p, _, _ in pr[c])))
                        cur.append(('k', d * own / heads[c]))
                        continue
                    cur.append(('k', d))
                segs[c].append(cur)
            T = 0.0
            for i in range(len(segs[0])):
                tp = [None] * NC
                for c in range(NC):  # time at the publish
                    t = 0.0
                    for it in segs[c][i]:
                        if it[0] == 'pub':
                            tp[c] = t
                            break
                        if it[0] == 'k':
                            t += it[1]
                ends = []
                for c in range(NC):
                    t = 0.0
                    for it in segs[c][i]:
                        if it[0] == 'k':
                            t += it[1]
                        elif it[0] == 'pw':
                            t = max([t] + [tp[d] for d in it[1] if tp[d] is not None]) + self.pair_us
                    ends.append(t)
                T += max(ends)
                if i < len(xc[0]):
                    T += min(xc[c][i] for c in range(NC))
            tot += T
        return tot / len(self.steps) / 1e3


def layouts(g, lo=8, hi=16, total=64):
    vals = list(range(lo, hi + 1, g))

    def rec(k, rest):
        if k == 1:
            if rest in vals:
                yield (rest,)
            return
        for v in vals:
            if lo * (k - 1) <= rest - v <= hi * (k - 1):
                for r in rec(k - 1, rest - v):
                    yield (v,) + r
    return list(rec(NC, total))


def local1(ctx, start, key, curve):
    """steepest descent with moves of one head between two cards (granularity 1)"""
    cur = tuple(start)
    best = ctx.T(cur, key, curve)
    while True:
        top = None
        for i in range(NC):
            for j in range(NC):
                if i == j:
                    continue
                h = list(cur)
                h[i] += 1
                h[j] -= 1
                if max(h) > 16 or min(h) < 8:
                    continue
                v = ctx.T(tuple(h), key, curve)
                if v < best - 1e-6 and (top is None or v < top[0]):
                    top = (v, tuple(h))
        if top is None:
            return cur, best
        best, cur = top


def main():
    out = print
    ctx = Ctx()
    dec = Dec()
    lin = curve_lin
    out('# barrier_heads.py output (stable mode, copies x%.1f; prompt %s; decode %s)' % (ctx.bw, B.PROMPT, B.DECODE))
    out()
    out('## A. Which kernel families scale with heads (prompt profile, ms per piece, mean of the two pieces)')
    fam = defaultdict(float)
    for st in ctx.pieces:
        for c in range(NC):
            for it in ctx.base[(st, c)]:
                if it[0] == 'k':
                    fam[(it[1], c)] += it[2] / len(ctx.pieces) / 1e3
                elif it[0] == 'oa':
                    fam[('out_a', c)] += it[1]['oa'] / len(ctx.pieces) / 1e3
    names = sorted(set(f for f, _ in fam))
    out('  family       ' + ''.join('%9s' % ('c%d' % c) for c in range(NC)) + '   (c4+c5)/(c1+c2)  [8 / 12 heads, all 230 W]')
    for f in names:
        v = [fam[(f, c)] for c in range(NC)]
        r = (v[4] + v[5]) / (v[1] + v[2]) if v[1] + v[2] > 0 else float('nan')
        out('  %-12s ' % f + ''.join('%9.2f' % x for x in v) + '   %.3f' % r)
    f8raw = sum(fam[(f, c)] for f in B.HEADF for c in (4, 5)) / sum(fam[(f, c)] for f in B.HEADF for c in (1, 2))
    REP = ('exp_up', 'exp_down', 'out_b', 'qakv', 'index', 'sh_gateup', 'sh_down')  # the same work on every card
    spd = sum(fam[(f, c)] for f in REP for c in (4, 5)) / sum(fam[(f, c)] for f in REP for c in (1, 2))
    f8 = f8raw / spd
    out('  head-scaled families together (q_b + attn + out_a), cards 4+5 / 1+2: %.3f; the same-work families %s: %.3f '
        '(card speed); head cost 8 / 12 heads = %.3f / %.3f = %.3f (linear %.3f)' % (f8raw, '+'.join(REP), spd, f8raw, spd, f8, 8 / 12))
    out('  decode (one-token profile, us per step; 8-head cards 0,1,3,4 / 16-head cards 2,5): ' + '; '.join(
        '%s %.1f / %.1f (%+.2f per head)' % (f, m8, m16, sl) for f, (m8, m16, sl, _) in dec.slope.items()))
    out('  decode pair-wait stand-in: median per-instance XchgP on the last card %.2f us; decode model %.3f ms per step '
        '(today, whole groups); profile span %.3f' % (dec.pair_us, dec.step(DEC_H), statistics.mean(dec.spans) / 1e3))

    out()
    out('## B. Check: heads 12,12,12,12,8,8 in the per-head model = section 4 of barrier_sim.out.txt')
    T0 = ctx.T(CUR_H, 'L', lin)
    out('  stable model %.2f ms per piece; heads 16,8,8,16,8,8 linear %.2f ms (%+.1f %%)' % (
        T0, ctx.T(H1_H, 'L', lin), 100 * (ctx.T(H1_H, 'L', lin) / T0 - 1)))

    out()
    out('## C. The 16-head cost f16 implied by st1 (fit: model loss of 16,8,8,16,8,8 = measured loss)')
    tg = {'3K read': ST1['3K h1'][0] / ST1['3K def'][0] - 1,
          '3K without first step': (ST1['3K h1'][0] - ST1['3K h1'][1]) / (ST1['3K def'][0] - ST1['3K def'][1]) - 1,
          '10K without first step': (ST1['10K h1'][0] - ST1['10K h1'][1]) / (ST1['10K def'][0] - ST1['10K def'][1]) - 1}
    fits = {}
    for prt, pn in ((None, 'tp109 structure'), ((3, 2, 2, 3, 3, 3), 'rough tp115 emulation')):
        for tn, target in tg.items():
            base_T = ctx.T(CUR_H, 'S%s' % (prt,), make_curve(f8, 1.0), prt)
            lo, hi = 1.0, 5.0
            for _ in range(40):
                mid = (lo + hi) / 2
                v = ctx.T(H1_H, 'fit%.6f%s' % (mid, prt), make_curve(f8, mid), prt) / base_T - 1
                if v < target:
                    lo = mid
                else:
                    hi = mid
            fits[(pn, tn)] = (lo + hi) / 2
            out('  %-22s target %+.1f %% (%s): f16 = %.2f x the 12-head cost (linear: 1.33)' % (pn, 100 * target, tn, fits[(pn, tn)]))
    f16 = fits[('tp109 structure', '3K without first step')]
    S = make_curve(f8, f16)
    out('  used below (S): f(8) = %.3f, f(12) = 1, f(16) = %.2f, piecewise linear; f(13) = %.2f, f(14) = %.2f, f(15) = %.2f' % (
        f8, f16, 1 + (f16 - 1) / 4, 1 + 2 * (f16 - 1) / 4, 1 + 3 * (f16 - 1) / 4))

    out()
    out('## D. Layouts (8-16 heads per card, sum 64), stable model ms per 512-token piece; decode ms per one-token step')
    D0 = dec.step(DEC_H)
    T0S = ctx.T(CUR_H, 'S', S)

    def row(hd, note=''):
        tl, ts = ctx.T(hd, 'L', lin), ctx.T(hd, 'S', S)
        try:
            ds = dec.step(hd)
        except ValueError:
            ds = float('nan')
        out('  %-20s L %7.2f (%+5.1f %%)  S %7.2f (%+5.1f %%)  decode with this layout %.3f (%+.1f %%)  pairs %s %s' % (
            ','.join(map(str, hd)), tl, 100 * (tl / T0 - 1), ts, 100 * (ts / T0S - 1), ds, 100 * (ds / D0 - 1),
            [[p for p, _, _ in x] for x in pairs_h(hd)], note))
    out('  today: prompt L %.2f / S %.2f ms; decode keeps whole groups %s: %.3f ms (any prompt layout leaves it so)' % (
        T0, T0S, ','.join(map(str, DEC_H)), D0))
    row(CUR_H, '(today)')
    row(H1_H, '(H1, measured +18.1 %)')
    row((12, 10, 10, 12, 10, 10), '(coordinator example)')
    row((11, 11, 11, 11, 10, 10), '(coordinator example)')
    row((10, 10, 10, 10, 12, 12))
    row((11, 11, 10, 11, 11, 10))
    row(DEC_H, '(the decode layout)')
    for g in (4, 2):
        Ls = layouts(g)
        for key, cv in (('L', lin), ('S', S)):
            r = sorted((ctx.T(hd, key, cv), hd) for hd in Ls)
            out('  granularity %d, %d layouts, best by %s:' % (g, len(Ls), key))
            for _, hd in r[:4]:
                row(hd)
            if key == 'S' and g == 2:
                top2S = [hd for _, hd in r[:6]]
            if key == 'L' and g == 2:
                top2L = [hd for _, hd in r[:6]]
    for key, cv, starts in (('L', lin, top2L), ('S', S, top2S)):
        res = sorted(set(local1(ctx, s0, key, cv) for s0 in starts + [CUR_H, (11, 11, 11, 11, 10, 10)]), key=lambda x: x[1])
        out('  granularity 1, best by %s (one-head moves from the best granularity-2 layouts and today):' % key)
        for hd, _ in res[:3]:
            row(hd)


if __name__ == '__main__':
    main()
