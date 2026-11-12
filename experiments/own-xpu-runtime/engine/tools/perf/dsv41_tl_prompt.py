#!/usr/bin/env python3
"""Where a prompt block's time goes, from an OWN_TIMELINE_PROMPT file (tl-prompt patch, pb256/tlp).

Usage: python3 -I tl_prompt.py <timeline file> [--card N] [--layers] [--scale K]

Per recorded block and card (host-clock ns from the file, printed in us):
  span       first launch start .. last launch end on the compute queue qs (q1)
  q1 busy    union of q1 launches (compute + any exchange still on q1)
  q1 idle    span - busy, split into
               await   q1 waited for a fired PX pull (px w marker) that had not ended yet
               beside  a gap with no await while a pull ran on xqs (register-mode clash / no free slots)
               other   gaps with no pull running (host submission, launch latency)
Per PX site (px f markers; X1 output-a, X2 output-b, X3 act, X4 FFN rows; half A / B) and for the unmarked xqs
launches (pair swaps, engram pull):
  pull       its run time on xqs (start .. end)
  hidden     the part of it with a q1 launch running at the same time
  exposed    pull - hidden
  start dly  start - max(end of the q1 launch it was queued after, end of the previous xqs launch)
  skew       the part of the pull before the last card started the same pull (a pull publishes at its start):
             waiting for peers, not copying (needs every card in the file)
Without PX (plain blocks) the exchange kernels run on q1: their time is listed by part (XP_*).
--scale K multiplies the per-block sums by K (e.g. 12 PX blocks of a 3K read / blocks recorded).
"""
import sys
from collections import defaultdict

SITES = {0: 'X1 out-a', 1: 'X2 out-b', 2: 'X3 act', 3: 'X4 ffn'}
XPART = {0: 'XP_OA', 1: 'XP_H', 2: 'XP_ACT', 3: 'XP_ENG', 4: 'XP_OAD', 5: 'XP_OAP'}


def load(path):
    names, L, px, st = {}, defaultdict(list), defaultdict(list), {}
    with open(path) as f:
        for ln in f:
            if not ln.strip() or ln[0] == '#':
                continue
            p = ln.split()
            if p[0] == 'kname':
                names[int(p[1])] = ln.split(None, 2)[2].strip() if len(p) > 2 else '?'
            elif p[0] == 'st':
                st[(int(p[1]), int(p[2]))] = (int(p[3]), int(p[4]))
            elif p[0] == 'px':
                step, c, kind, site, half, idx, grf = int(p[1]), int(p[2]), p[3], int(p[4]), int(p[5]), int(p[6]), int(p[7])
                px[(step, c)].append((kind, site, half, idx, grf))
            elif p[0] in ('card', 'cal', 'hw'):
                continue
            elif len(p) >= 13 and p[0].lstrip('-').isdigit():
                step, c, idx, nid = int(p[0]), int(p[1]), int(p[2]), int(p[3])
                s, e = int(p[5]), int(p[6])
                xq = int(p[13]) if len(p) > 13 else 0
                L[(step, c)].append(dict(idx=idx, nid=nid, s=s, e=e, xpart=int(p[10]), xmode=int(p[11]), xq=xq))
    for k in L:
        L[k].sort(key=lambda r: r['idx'])
        for r in L[k]:
            r['name'] = names.get(r['nid'], '?')
    return L, px, st


def short(n):
    for key in ('XchgPull2', 'XchgPair', 'XchgPull'):
        if key in n:
            return key
    n = n.replace('typeinfo name for ', '')
    return n[:70]


def overlap(a0, a1, ivs, j0=0):
    """sum of the intersection of [a0, a1] with sorted disjoint intervals ivs; j0: a start hint"""
    t = 0
    for s, e in ivs[j0:]:
        if s >= a1:
            break
        if e <= a0:
            continue
        t += min(a1, e) - max(a0, s)
    return t


def analyse_block(recs, marks):
    q1 = [r for r in recs if r['xq'] == 0]
    xq = [r for r in recs if r['xq'] != 0]
    out = dict(span=0, busy=0, await_=0, beside=0, other=0, sites=defaultdict(lambda: defaultdict(float)),
               xq_on_q1=defaultdict(float), beside_names=defaultdict(float), pulls=[])
    if not q1:
        return out
    # q1 intervals (in-order queue: sequential; union anyway)
    ivs = []
    for r in q1:
        if ivs and r['s'] <= ivs[-1][1]:
            ivs[-1][1] = max(ivs[-1][1], r['e'])
        else:
            ivs.append([r['s'], r['e']])
    out['span'] = q1[-1]['e'] - q1[0]['s']
    out['busy'] = sum(e - s for s, e in ivs)
    # exchange kernels still on q1 (plain blocks, or outside the halves)
    for r in q1:
        if any(k in r['name'] for k in ('XchgPull', 'XchgPair')):
            out['xq_on_q1'][short(r['name']) + ' ' + XPART.get(r['xpart'], str(r['xpart']))] += r['e'] - r['s']
    # site of each xqs launch (f markers: idx = the launch's index in its step)
    by_idx = {r['idx']: r for r in recs}
    site_of = {}
    occ = defaultdict(int)
    for kind, site, half, idx, grf in marks:
        if kind == 'f' and idx in by_idx:
            key = (site, half, occ[(site, half)])
            occ[(site, half)] += 1
            site_of[idx] = (SITES.get(site, str(site)) + (' A' if half == 0 else ' B'), key, grf)
    eocc = defaultdict(int)
    for r in xq:
        if r['idx'] in site_of:
            r['site'], r['key'], r['grf'] = site_of[r['idx']]
        else:
            nm = short(r['name'])
            lab = 'pair' if nm == 'XchgPair' else 'engram' if r['xpart'] == 3 else nm + ' ' + XPART.get(r['xpart'], '?')
            r['site'], r['key'], r['grf'] = lab, (lab, eocc[lab]), r['xq']
            eocc[lab] += 1
    # each xqs launch: hidden / exposed / start delay
    prev_xe = None
    q1_by_idx = [r['idx'] for r in q1]
    import bisect
    for r in xq:
        d = r['e'] - r['s']
        hid = overlap(r['s'], r['e'], ivs)
        j = bisect.bisect_left(q1_by_idx, r['idx']) - 1
        dep = q1[j]['e'] if j >= 0 else r['s']
        ready = max(dep, prev_xe) if prev_xe is not None else dep
        prev_xe = r['e']
        S = out['sites'][r['site']]
        S['n'] += 1
        S['pull'] += d
        S['hidden'] += hid
        S['exposed'] += d - hid
        S['delay'] += max(0, r['s'] - ready)
        r['hid'], r['dly'] = hid, max(0, r['s'] - ready)
        out['pulls'].append(r)
    # q1 gaps: await / beside / other
    waits = {}  # q1 launch idx -> the pull it waited for
    fired = {}
    for kind, site, half, idx, grf in marks:
        if kind == 'f':
            fired[(site, half)] = idx
        elif kind == 'w' and idx >= 0 and (site, half) in fired:
            pr = by_idx.get(fired[(site, half)])
            if pr is not None:
                # the first q1 launch at or after idx
                j = bisect.bisect_left(q1_by_idx, idx)
                if j < len(q1):
                    waits[q1[j]['idx']] = pr
    xs = sorted(((r['s'], r['e'], r) for r in xq), key=lambda t: t[0])
    for i in range(1, len(q1)):
        a, b = q1[i - 1]['e'], q1[i]['s']
        if b <= a:
            continue
        g = b - a
        pr = waits.get(q1[i]['idx'])
        w = 0
        if pr is not None:
            w = max(0, min(b, pr['e']) - a)
            out['await_'] += w
            out['sites'][pr['site']]['await'] += w
        rest = g - w
        if rest <= 0:
            continue
        a2 = a + w
        bes = 0
        for s, e, r in xs:
            if s >= b:
                break
            if e <= a2:
                continue
            o = min(b, e) - max(a2, s)
            if o > 0:
                bes = max(bes, o)
                out['sites'][r['site']]['beside'] += o
                out['beside_names'][short(q1[i]['name'])] += o
        out['beside'] += bes
        out['other'] += rest - bes
    return out


def skew(L, step):
    """per card: the part of each marked pull before the last card started the same pull"""
    starts = defaultdict(dict)
    for (st, c), recs in L.items():
        if st != step:
            continue
        for r in recs:
            if r['xq'] != 0 and 'key' in r:
                starts[(r['site'], r['key'])][c] = r
    res = defaultdict(lambda: defaultdict(float))
    for k, per in starts.items():
        if len(per) < 2:
            continue
        last = max(r['s'] for r in per.values())
        for c, r in per.items():
            res[c][k[0]] += max(0, min(r['e'], last) - r['s'])
    return res


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 1
    path, card, layers, scale = a[0], None, '--layers' in a, 1.0
    if '--card' in a:
        card = int(a[a.index('--card') + 1])
    if '--scale' in a:
        scale = float(a[a.index('--scale') + 1])
    L, px, st = load(path)
    steps = sorted({s for s, _ in L})
    us = lambda ns: ns * scale / 1000.0
    tot = defaultdict(lambda: defaultdict(float))
    for step in steps:
        cards = sorted(c for s, c in L if s == step)
        res = {c: analyse_block(L[(step, c)], px.get((step, c), [])) for c in cards}
        sk = skew(L, step)
        print(f"== block step {step} (prompt block {step - 20000})" + (f", x{scale:g}" if scale != 1 else ''))
        print("card  wall(st)   span     q1busy   idle: await   beside    other   | xqs pulls  hidden  exposed")
        for c in cards:
            if card is not None and c != card:
                continue
            r = res[c]
            w = st.get((step, c))
            pull = sum(S['pull'] for S in r['sites'].values())
            hid = sum(S['hidden'] for S in r['sites'].values())
            print(f"{c:4d} {us(w[1] - w[0]) if w else 0:9.0f} {us(r['span']):9.0f} {us(r['busy']):9.0f} "
                  f"{us(r['await_']):10.0f} {us(r['beside']):8.0f} {us(r['other']):8.0f}   | {us(pull):9.0f} "
                  f"{us(hid):7.0f} {us(pull - hid):8.0f}")
            for k, v in (('span', r['span']), ('busy', r['busy']), ('await', r['await_']), ('beside', r['beside']),
                         ('other', r['other']), ('pull', pull), ('hidden', hid)):
                tot[c][k] += v
        for c in cards:
            if card is not None and c != card:
                continue
            r = res[c]
            if r['sites']:
                print(f"  card {c} per site (us): n, pull, hidden, exposed, q1 await, q1 beside, start delay, skew")
                for name in sorted(r['sites']):
                    S = r['sites'][name]
                    print(f"    {name:12s} {int(S['n']):4d} {us(S['pull']):8.0f} {us(S['hidden']):8.0f} "
                          f"{us(S['exposed']):8.0f} {us(S['await']):8.0f} {us(S['beside']):8.0f} "
                          f"{us(S['delay']):8.0f} {us(sk[c][name]):8.0f}")
            if r['xq_on_q1']:
                print(f"  card {c} exchange kernels on q1 (us): " +
                      ", ".join(f"{k} {us(v):.0f}" for k, v in sorted(r['xq_on_q1'].items())))
            if r['beside_names']:
                top = sorted(r['beside_names'].items(), key=lambda t: -t[1])[:6]
                print(f"  card {c} q1 launches held beside a pull (us): " + "; ".join(f"{k} {us(v):.0f}" for k, v in top))
            if layers and r['pulls']:
                print(f"  card {c} each xqs launch: site, grf, pull, hidden, start delay (us)")
                for p in r['pulls']:
                    print(f"    {p['idx']:6d} {p['site']:12s} {p['grf']:4d} {us(p['e'] - p['s']):8.1f} "
                          f"{us(p['hid']):8.1f} {us(p['dly']):8.1f}")
    if len(steps) > 1:
        print(f"== sum over {len(steps)} blocks (us)")
        for c in sorted(tot):
            t = tot[c]
            print(f"{c:4d} span {us(t['span']):.0f} busy {us(t['busy']):.0f} await {us(t['await']):.0f} "
                  f"beside {us(t['beside']):.0f} other {us(t['other']):.0f} pulls {us(t['pull']):.0f} "
                  f"hidden {us(t['hidden']):.0f}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
