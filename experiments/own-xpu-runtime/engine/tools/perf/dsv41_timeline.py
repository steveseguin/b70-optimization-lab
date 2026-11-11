#!/usr/bin/env python3
"""Where the idle time of a DeepSeek V4.1 answer step goes: the per-launch timeline of every card.

Input: the file of OWN_TIMELINE=<file> (dsv41_timeline.patch; format in backend_sycl_v41.hpp, "OWN_TIMELINE") and,
optionally, the file of OWN_XWAIT=<file> from the same run (needs the -DOWN41_XWAIT build).

Per card, mean per step over the window:
  busy       sum of the launches' GPU time (kernels and the few copies on the card's queue)
  idle       the gaps between consecutive launches, split by cause:
             host late   the card had finished the previous launch before the host had submitted the next one
                         (t_submit > previous t_end; the part of the gap up to t_submit). "after a host wait": the
                         host was inside a queue wait (twait) during that time.
             dev gap     the next launch was already submitted, yet the card started it later (launch latency,
                         dependencies inside the driver)
  lead-in    card thread's step begin -> first launch start;  tail: last launch end -> end of the step's last wait
  exchanges  time inside exchange kernels; with OWN_XWAIT split into waiting for the last peer's flag and the rest
             (push / copy / overhead)
Then: the 20 largest gaps with the launches around them, idle by the launch that follows, and the critical-path
guess: which card starts each exchange last (its peers wait for it), per exchange kind.

Clock alignment (--align): "cal" uses the file's host-clock times (each card's device timer mapped through
zeDeviceGetGlobalTimestamps pairs; comparable across cards); "causal" maps each card's device times per step so
that its earliest launch starts --min-lat-us after its submit (assumes the same minimum launch latency on every
card, ~1 us error); "auto" (default) takes "cal" when it passes the checks below, else "causal". The report
prints both methods' offsets against each other.

Usage (CPU only, stdlib only):
  python3 -I dsv41_timeline.py TIMELINE [--xwait XWFILE] [--align auto|cal|causal|none] [--steps a-b] [--top 20]
"""
import argparse
import bisect
import math
import os
import statistics
import sys
from collections import defaultdict

XP = {0: 'output-a', 1: 'model rows', 2: 'expert act', 3: 'engram', 4: 'draft output-a', 5: 'output-a blk', -1: 'other'}


def pct(v, p):
    if not v:
        return float('nan')
    s = sorted(v)
    k = (len(s) - 1) * p / 100.0
    f = math.floor(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def short(name, n=44):
    return name if len(name) <= n else name[:n - 3] + '...'


class Launch:
    __slots__ = ('step', 'card', 'idx', 'nid', 'sub', 's', 'e', 'ds', 'de', 'dsub', 'xpart', 'xmode', 'xk')

    def __init__(self, f):
        (self.step, self.card, self.idx, self.nid, self.sub, self.s, self.e, self.ds, self.de, self.dsub,
         self.xpart, self.xmode, self.xk) = (int(x) for x in f[:13])


def read_timeline(path):
    T = {'cards': {}, 'cal': defaultdict(list), 'names': {}, 'st': {}, 'hw': defaultdict(list),
         'L': defaultdict(list), 'hdr': []}
    with open(path) as fh:
        for ln in fh:
            f = ln.split()
            if not f:
                continue
            if f[0] == '#':
                T['hdr'].append(ln.strip())
            elif f[0] == 'card':
                T['cards'][int(f[1])] = {'pci': f[2], 'res': int(f[3]), 'hz': int(f[4]), 'kbits': int(f[5]),
                                         'tbits': int(f[6])}
            elif f[0] == 'cal':
                c, st, ok, ticks, dns, hns, lo, hi = (int(x) for x in f[1:9])
                T['cal'][c].append({'step': st, 'ok': ok, 'ticks': ticks, 'dev': dns, 'host': hns, 'lo': lo, 'hi': hi})
            elif f[0] == 'kname':
                T['names'][int(f[1])] = ln.split(None, 2)[2].strip() if len(f) > 2 else '?'
            elif f[0] == 'st':
                T['st'][(int(f[1]), int(f[2]))] = (int(f[3]), int(f[4]))
            elif f[0] == 'hw':
                T['hw'][(int(f[1]), int(f[2]))].append((int(f[3]), int(f[4])))
            elif len(f) >= 13 and f[0].lstrip('-').isdigit():
                x = Launch(f)
                T['L'][(x.step, x.card)].append(x)
    for v in T['L'].values():
        v.sort(key=lambda x: x.idx)
    return T


def read_xwait(path):
    """xw <step> <card> <k> <label> <polls x6> <ticks x6> [<push ticks> <kernel ticks> <answer step>]"""
    X = {}
    with open(path) as fh:
        for ln in fh:
            f = ln.split()
            if len(f) < 17 or f[0] != 'xw':
                continue
            st, c, k, lab = int(f[1]), int(f[2]), int(f[3]), int(f[4])
            polls = [int(x) for x in f[5:11]]
            ticks = [int(x) for x in f[11:17]]
            push = int(f[17]) if len(f) > 17 else 0
            tot = int(f[18]) if len(f) > 18 else 0
            ans = int(f[19]) if len(f) > 19 else -1
            X[(ans, c, k)] = {'bstep': st, 'label': lab, 'polls': polls, 'ticks': ticks, 'push': push, 'tot': tot}
    return X


def align_causal(T, min_lat_ns):
    """per (step, card): offset so that min(start - submit) = min_lat"""
    off = {}
    for key, v in T['L'].items():
        d = [x.ds - x.sub for x in v]
        off[key] = min(d) - min_lat_ns
    return off


def check_cal(T):
    """per card: is the file's cal mapping plausible? returns (ok, notes, per-card offset cal - causal in us)"""
    notes = []
    ok = True
    for c in sorted(T['cards']):
        cal = T['cal'].get(c, [])
        good = [k for k in cal if k['ok']]
        if not good:
            notes.append('c%d: no clock pair' % c)
            ok = False
            continue
        bad2 = sum(1 for k in good if k['ok'] == 2)
        if bad2:
            notes.append('c%d: %d of %d clock pairs used the bracket middle (driver host time outside the bracket)'
                         % (c, bad2, len(good)))
        lat = [x.s - x.sub for (st, cc), v in T['L'].items() if cc == c for x in v]
        if not lat:
            continue
        p1 = pct(lat, 1)
        if p1 < -50e3 or pct(lat, 50) > 5e6:
            notes.append('c%d: cal mapping implausible (start - submit: p1 %.1f us, median %.1f us)'
                         % (c, p1 / 1e3, pct(lat, 50) / 1e3))
            ok = False
    return ok, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('timeline')
    ap.add_argument('--xwait', help='OWN_XWAIT file of the same run')
    ap.add_argument('--align', default='auto', choices=['auto', 'cal', 'causal', 'none'])
    ap.add_argument('--min-lat-us', type=float, default=1.0, help='causal alignment: minimum submit -> start')
    ap.add_argument('--steps', help='a-b: only these answer steps')
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--xw-mhz', type=float, default=0.0, help='exchange clock rate (default: fitted to the timeline)')
    a = ap.parse_args()

    T = read_timeline(a.timeline)
    if not T['L']:
        sys.exit('%s: no launch lines' % a.timeline)
    names = T['names']
    if a.steps:
        s0, _, s1 = a.steps.partition('-')
        s0, s1 = int(s0), int(s1 or s0)
        T['L'] = {k: v for k, v in T['L'].items() if s0 <= k[0] <= s1}
    steps = sorted({k[0] for k in T['L']})
    cards = sorted({k[1] for k in T['L']})
    ns = len(steps)
    out = print

    # ---- clocks
    cal_ok, notes = check_cal(T)
    mode = a.align
    if mode == 'auto':
        mode = 'cal' if cal_ok else 'causal'
    caus = align_causal(T, a.min_lat_us * 1e3)
    # cal vs causal: offsets of the cal mapping in the causal frame (us), per card (median over steps)
    cross = {}
    for c in cards:
        d = []
        for st in steps:
            v = T['L'].get((st, c))
            if v:
                d.append(statistics.median((x.ds - caus[(st, c)]) - x.s for x in v) / 1e3)
        if d:
            cross[c] = statistics.median(d)
    if mode == 'causal':
        for key, v in T['L'].items():
            o = caus[key]
            for x in v:
                x.s, x.e = x.ds - o, x.de - o
    elif mode == 'none':
        for v in T['L'].values():
            for x in v:
                x.s, x.e = x.ds, x.de

    out('# OWN_TIMELINE %s: %d answer steps (%s), cards %s, clocks: %s'
        % (os.path.basename(a.timeline), ns, '%d-%d' % (steps[0], steps[-1]) if steps else '-',
           ','.join(str(c) for c in cards), mode))
    for n in notes:
        out('#   ' + n)
    if cross:
        ref = statistics.median(cross.values())
        out('#   cal vs causal alignment, per card (us, relative to the median card): '
            + ', '.join('c%d %+.1f' % (c, cross[c] - ref) for c in cards)
            + '   (spread = the alignment uncertainty across cards)')
    if mode == 'none':
        out('#   clocks NOT aligned: cross-card numbers (step wall, last into exchange) are meaningless')

    # ---- per card per step
    agg = defaultdict(lambda: defaultdict(float))  # card -> quantity -> sum over steps
    gaps = []          # (gap_ns, step, card, cause, before name, after name, host_late_ns)
    after = defaultdict(lambda: [0.0, 0.0, 0.0])  # name -> [host late, dev gap, count]
    overlaps = 0
    for (st, c), v in sorted(T['L'].items()):
        A = agg[c]
        hw = sorted(T['hw'].get((st, c), []))
        busy = sum(max(0, x.e - x.s) for x in v)
        A['busy'] += busy
        A['span'] += v[-1].e - v[0].s
        A['n'] += len(v)
        sb = T['st'].get((st, c))
        if sb:
            A['lead'] += max(0, v[0].s - sb[0])
            A['tail'] += max(0, sb[1] - max(x.e for x in v))
            A['thread'] += sb[1] - sb[0]
        for i in range(1, len(v)):
            p, x = v[i - 1], v[i]
            g = x.s - p.e
            if g < 0:
                overlaps += 1
                continue
            late = min(g, max(0, x.sub - p.e))
            dev = g - late
            waited = 0
            if late > 0 and hw:
                # host queue-wait time inside [p.e, x.sub]
                lo, hi = p.e, p.e + late
                for (wa, wb) in hw:
                    if wb > lo and wa < hi:
                        waited += min(wb, hi) - max(wa, lo)
            A['late'] += late
            A['late_wait'] += waited
            A['dev'] += dev
            A['idle'] += g
            nm = names.get(x.nid, '?')
            after[nm][0] += late
            after[nm][1] += dev
            after[nm][2] += 1
            cause = ('host late, in a queue wait' if waited > late / 2 else 'host late') if late > dev else 'dev gap'
            gaps.append((g, st, c, cause, names.get(p.nid, '?'), nm, late))
        ex = [x for x in v if names.get(x.nid, '').startswith('Xchg')]
        A['xchg'] += sum(x.e - x.s for x in ex)
        A['xn'] += len(ex)

    def ms(c, k):
        return agg[c][k] / ns / 1e6

    # step wall (cross-card): earliest card-thread begin -> latest launch end
    walls = []
    for st in steps:
        b = [T['st'][(st, c)][0] for c in cards if (st, c) in T['st']]
        e = [max(x.e for x in T['L'][(st, c)]) for c in cards if (st, c) in T['L']]
        if b and e:
            walls.append((max(e) - min(b)) / 1e6)
    out()
    if walls:
        out('Step wall (first card thread begin -> last launch end): %.3f ms mean (min %.3f, max %.3f)'
            % (statistics.mean(walls), min(walls), max(walls)))
    out()
    out('Per card, ms per step (mean over %d steps):' % ns)
    out('%-5s %7s %7s %7s %7s %7s %7s %7s %7s %7s %6s' % ('card', 'span', 'busy', 'idle', 'hostlate', '(inwait)',
                                                           'devgap', 'lead-in', 'tail', 'xchg', 'launch'))
    for c in cards:
        out('c%-4d %7.3f %7.3f %7.3f %7.3f %7.3f %7.3f %7.3f %7.3f %7.3f %6.0f'
            % (c, ms(c, 'span'), ms(c, 'busy'), ms(c, 'idle'), ms(c, 'late'), ms(c, 'late_wait'), ms(c, 'dev'),
               ms(c, 'lead'), ms(c, 'tail'), ms(c, 'xchg'), agg[c]['n'] / ns))
    if overlaps:
        out('(%d launch pairs overlap on one queue: an in-order queue should not; alignment or a profiling artefact)'
            % overlaps)

    # ---- exchanges: wait vs the rest (OWN_XWAIT), and who is last
    X = read_xwait(a.xwait) if a.xwait else {}
    rate = a.xw_mhz / 1e3 if a.xw_mhz else 0.0  # ticks per ns
    fitn = 0
    if X and not rate:
        pts = []
        for (st, c), v in T['L'].items():
            for x in v:
                r = X.get((st, c, x.xk)) if x.xk >= 0 else None
                if r and r['tot'] and x.e > x.s:
                    pts.append((r['tot'], x.e - x.s))
        if len(pts) >= 8:
            # least squares: duration_ns = a + ticks / rate
            mx = statistics.mean(p[0] for p in pts)
            my = statistics.mean(p[1] for p in pts)
            sxx = sum((p[0] - mx) ** 2 for p in pts)
            sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
            if sxx > 0 and sxy > 0:
                slope = sxy / sxx
                rate = 1.0 / slope
                icp = my - slope * mx
                fitn = len(pts)
                syy = sum((p[1] - my) ** 2 for p in pts)
                r2 = sxy * sxy / (sxx * syy) if syy > 0 else 0
                out()
                out('Exchange clock fitted on %d exchanges: %.0f MHz, kernel overhead %.2f us, R^2 %.3f'
                    % (fitn, rate * 1e3, icp / 1e3, r2))
    if X and not rate:
        rate = 2.4  # packet194's assumption; uncalibrated
        out('(exchange clock not fitted: %.0f MHz assumed)' % (rate * 1e3))

    # group exchanges across cards: the j-th exchange launch of a step is the same exchange on every card
    kinds = defaultdict(lambda: {'n': 0, 'last': defaultdict(int), 'late': [], 'wait': defaultdict(float),
                                 'dur': defaultdict(float), 'xlast': defaultdict(int)})
    mism = 0
    for st in steps:
        per = {c: [x for x in T['L'].get((st, c), []) if names.get(x.nid, '').startswith('Xchg')] for c in cards}
        nmin = min((len(v) for v in per.values()), default=0)
        if any(len(v) != nmin for v in per.values()):
            mism += 1
        nh = 0
        for j in range(nmin):
            xs = {c: per[c][j] for c in cards}
            x0 = xs[cards[0]]
            if any(xs[c].xpart != x0.xpart or xs[c].xmode != x0.xmode for c in cards):
                mism += 1
            kind = XP.get(x0.xpart, 'part %d' % x0.xpart)
            if x0.xpart == 1:
                kind = 'output-b rows' if nh % 2 == 0 else 'ffn rows'
                nh += 1
            if x0.xmode == 1:
                kind += ' (push)'
            K = kinds[kind]
            K['n'] += 1
            for c in cards:
                K['dur'][c] += xs[c].e - xs[c].s
            if x0.xmode != 1 and len(cards) > 1:
                order = sorted(cards, key=lambda c: xs[c].s)
                K['last'][order[-1]] += 1
                K['late'].append(xs[order[-1]].s - xs[order[-2]].s)
            if X:
                rec = {c: X.get((st, c, xs[c].xk)) for c in cards if xs[c].xk >= 0}
                rec = {c: r for c, r in rec.items() if r}
                if len(rec) >= 2:
                    # the peer the others waited longest for
                    w = {t: statistics.mean(rec[c]['ticks'][t] for c in rec if c != t) for t in rec}
                    K['xlast'][max(w, key=lambda t: w[t])] += 1
                    for c, r in rec.items():
                        K['wait'][c] += max(r['ticks'][t] for t in range(6) if t != c) / rate
    out()
    out('Exchanges per step: kind, count, mean ms in the kernels per card%s; the card that STARTS the exchange last'
        % (' (wait = waiting for the last flag, OWN_XWAIT)' if X else ''))
    out('(its peers wait for it), share of exchanges, and by how much it trails the second-last (median us):')
    for kind, K in sorted(kinds.items(), key=lambda kv: -sum(kv[1]['dur'].values())):
        n = K['n'] / ns
        dur = ' '.join('%.3f' % (K['dur'][c] / ns / 1e6) for c in cards)
        s = '  %-20s %5.1f  dur %s' % (kind, n, dur)
        if X and K['wait']:
            s += '  wait ' + ' '.join('%.3f' % (K['wait'].get(c, 0) / ns / 1e6) for c in cards)
        if K['last']:
            tot = sum(K['last'].values())
            s += '  last: ' + ', '.join('c%d %.0f%%' % (c, 100.0 * K['last'][c] / tot)
                                        for c in sorted(K['last'], key=lambda c: -K['last'][c])[:3])
            s += '  by %.1f' % (pct(K['late'], 50) / 1e3)
        if K['xlast']:
            tot = sum(K['xlast'].values())
            s += '  [xwait last: ' + ', '.join('c%d %.0f%%' % (c, 100.0 * K['xlast'][c] / tot)
                                               for c in sorted(K['xlast'], key=lambda c: -K['xlast'][c])[:3]) + ']'
        out(s)
    if mism:
        out('  (%d steps / exchanges where the cards\' exchange sequences differ: grouping may be off)' % mism)
    tl = defaultdict(int)
    for K in kinds.values():
        for c, k in K['last'].items():
            tl[c] += k
    if tl:
        tot = sum(tl.values())
        out('  all exchanges, last to start: ' + ', '.join('c%d %.0f%%' % (c, 100.0 * tl[c] / tot) for c in
                                                          sorted(tl, key=lambda c: -tl[c])))
    if X:
        out('  wait per card, ms per step: ' + ', '.join(
            'c%d %.3f' % (c, sum(K['wait'].get(c, 0) for K in kinds.values()) / ns / 1e6) for c in cards)
            + '   (exchange kernel time minus wait = push / copy / overhead)')

    # ---- idle by the launch that follows
    out()
    out('Idle before each kernel type (us per step, mean card): host late / dev gap / launches per step')
    rows = sorted(after.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:12]
    nc = len(cards) * ns
    for nm, (late, dev, n) in rows:
        out('  %8.1f %8.1f %6.1f  %s' % (late / nc / 1e3, dev / nc / 1e3, n / nc, short(nm, 70)))

    # ---- top gaps
    out()
    out('Largest %d gaps (us): step card cause | before -> after' % a.top)
    for g, st, c, cause, b, nm, late in sorted(gaps, reverse=True)[:a.top]:
        out('  %8.1f  s%-3d c%d  %-27s | %s -> %s' % (g / 1e3, st, c, cause + (' %.1f' % (late / 1e3) if late else ''),
                                                   short(b, 34), short(nm, 34)))
    # host-side step hand-off
    hs = []
    for i in range(1, len(steps)):
        p, n = steps[i - 1], steps[i]
        if n != p + 1:
            continue
        pe = [T['st'][(p, c)][1] for c in cards if (p, c) in T['st']]
        nb = [T['st'][(n, c)][0] for c in cards if (n, c) in T['st']]
        if pe and nb:
            hs.append((min(nb) - max(pe)) / 1e3)
    if hs:
        out()
        out('Between steps (last card thread done -> first card thread starts the next): median %.1f us, max %.1f us'
            % (pct(hs, 50), max(hs)))


if __name__ == '__main__':
    main()
