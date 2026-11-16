#!/usr/bin/env python3
"""barrier_sim.py: what the stable mode (OWN_PX_SERIAL=1) costs per 512-token prompt piece, and what same-bits
rebalancing (OWN_TP_HEADS, OWN_TP_WEIGHTS) would win, modelled from a profiled px-512 prompt timeline.

CPU only, stdlib only.  Run:  nice -n 19 python3 -I barrier_sim.py [--prompt TL] [--decode TL] [--quick]

Model (see README.md):
  * Each card runs its recorded kernel sequence with the recorded per-kernel durations (profiled run: per-kernel
    times valid, overlap between queues not).
  * Stable mode: right after each exchange push (X1 output-a, X2 output-b, X3 expert act, X4 FFN rows, per half),
    the card spins until every peer's copy of that exchange has landed (backend_sycl_v41_mt.inc bcs_fire ->
    bcs_wait).  Card c's copy starts when c's producer ends and takes copy(bytes_c); card c is released at
    max over peers d != c of (producer end_d + copy_d) + the wait launch's floor.  The engram push (once per piece)
    has no serial wait; its reader (px_eng at layer 1) waits for every peer's copy.
  * Pair swaps (XchgPair, split head groups): the card publishes after its attention, runs its whole-group output-a
    rows, then waits for its partner's publish and pulls 4 heads per partner (pull floor from the profile).
  * Overlap mode (OWN_PX_SERIAL=0, for checking the model against the profile): pushes do not block, the reader's
    XchgWaitB waits for every peer's copy flag, copies queue in order on each card's copy engine.
  * Copy time = a + b * MiB per peer, fitted to the six-card push bench (dsv41-work/bcs/README.md, Gen5);
    --bw-scale multiplies b (Gen4 links in the stable mode: assumption, see README).
"""
import argparse
import math
import re
import statistics
import sys
from collections import Counter, defaultdict

TOOLS = '/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine/tools/perf'
sys.path.insert(0, TOOLS)
import dsv41_timeline as TL  # noqa: E402

PROMPT = '/home/steve/dsv41-work/runs/tlp109/tlp_px512.txt'
DECODE = '/home/steve/dsv41-work/runs/tg109/tl_one.txt'

# ---- geometry (backend_sycl_v41.hpp tp_setup / head_layout; bcs/README.md shapes)
H, MID, OTOTAL, HALF, NC = 5120, 2304, 8192, 256, 6
ENGR = 5 * H            # engram rows (both layers' rows per token: 2 slots per token)
UR = OTOTAL // 16       # output-a rows per unit of 4 heads
CUR_UNITS = (3, 3, 3, 3, 2, 2)
H1_UNITS = (4, 2, 2, 4, 2, 2)
# six-card copy-engine push bench, 256-token halves (bcs/README.md table "Stress bench", order2.txt):
# (MiB to each of five peers, us for the push)
BENCH = [(0.84, 137.5), (1.50, 260.4), (2.62, 442.8), (0.13, 21.3), (16.7, 2974.0)]
DS_MIB = 0.13           # OWN_MT_DSPLIT partial tokens riding X1 and X3 (bench row "ds partial tokens")
MIB = 1024.0 * 1024.0
# measured 3K reads (unprofiled) used only as a check of the model's stable-mode cost
MEAS = {'tp114 overlap, Gen5 (dsv41 lane note)': 4.19, 'tp115 stable, def heads (st1 c1_p3k_def)': 4.93,
        'tp115 stable, heads 4,2,2,4,2,2 (st1 c1_p3k_h1)': 5.82}

HEADF = {'q_b', 'out_a', 'attn'}
TMF = {'exp_up', 'swiglu', 'sh_gateup'}
TDF = {'exp_down', 'sh_down', 'combine', 'out_b'}
TEF = {'engram'}
CAT = {'exp_up': 'experts', 'exp_down': 'experts', 'sh_gateup': 'experts', 'exp_group': 'experts', 'swiglu': 'experts',
       'combine': 'experts', 'qakv': 'dense rows', 'router': 'dense rows', 'compress': 'dense rows', 'q_b': 'dense rows',
       'out_a': 'dense rows', 'out_b': 'dense rows', 'sh_down': 'dense rows', 'engram': 'dense rows',
       'attn': 'attention+index', 'index': 'attention+index', 'norms': 'norms+mix', 'kv': 'small/other',
       'embed': 'small/other', 'eng_get': 'small/other', 'pair': 'pair swaps'}


def kdim(name):
    """input width K of a DenseRowsWSC row kernel (WsQ8 / WsH16: 32 per unit; WsQ6 / WsQ6S / WsQ5: 256)"""
    m = re.search(r'DenseRowsWSC<Ws(Q8|H16|Q6S|Q6|Q5)<(\d+)u>', name)
    if not m:
        return None, None
    q, n = m.group(1), int(m.group(2))
    return q, n * (32 if q in ('Q8', 'H16') else 256)


def fam_of(name, nxt):
    if name == 'XchgWaitB':
        return 'wait'
    if name == 'XchgPair':
        return 'pair'
    if name.startswith(('EmbedRowA', 'Broadcast4PA')):
        return 'embed'
    if name.startswith(('RoutedUP', 'RoutedQ2KF', 'RoutedIQ')):
        k = int(re.search(r'<(\d+)u>', name).group(1))
        return 'exp_up' if k == 20 else 'exp_down'
    if name.startswith('RoutePMRows'):
        return 'sh_gateup'  # router top-6 + hc finish + shared gate / up rows (tm split); rows dominate
    if name.startswith('ExpertGroupPM'):
        return 'exp_group'
    if name.startswith('SwigluBothSM'):
        return 'swiglu'
    if name.startswith('MoeCombineAM'):
        return 'combine'
    if name.startswith(('ScoreM', 'SoftmaxM', 'OutM')):
        return 'attn'
    if name.startswith(('IndexerScoreBM', 'TopKSelM', 'CidxFillM', 'RowsP<DenseRowsG<GemvH16P')):
        return 'index'
    if name.startswith(('WindowAppendM', 'RingCommitM', 'PubAppendAM', 'StatePackM', 'SkCompressPoolWM')) or \
            'RopeRows' in name:
        return 'kv'
    if name.startswith('EngRowsA'):
        return 'eng_get'
    q, K = kdim(name)
    if K is not None:
        if q == 'H16':
            if K == 5120:
                return 'router' if nxt.startswith('RoutePMRows') else 'compress'
            return 'index'  # indexer query rows (K 1280, replicated)
        return {5120: 'qakv', 1280: 'q_b', 4096: 'out_a', 8192: 'out_b', 2304: 'sh_down', 6144: 'engram'}.get(K, 'other')
    return 'norms'  # NormRows, SkDotsWM, SkNormPairWM, HcPre/Post*, HcFinishRows, RmsNormA, EngramGateWM


# ---- engine row splits (backend_sycl_v41.hpp tp_setup: split(n, c, al, w))
def split(n, c, al, w):
    W = Wc = 0
    for d in range(NC):
        wd = w[d] if w[d] > 0 else 1
        if d < c:
            Wc += wd
        W += wd
    u = n // al
    wc = w[c] if w[c] > 0 else 1
    a = (u * Wc // W) * al
    b = n if c + 1 == NC else (u * (Wc + wc) // W) * al
    return a, b


def rows(n, w, al=16):
    return [split(n, c, al, w)[1] - split(n, c, al, w)[0] for c in range(NC)]


def head_pairs(units):
    """per card: list of partner cards (head_layout: a group split between neighbours)"""
    u = [0]
    for x in units:
        u.append(u[-1] + x)
    P = []
    for c in range(NC):
        p = []
        if u[c] & 1:
            p.append(c - 1)
        if u[c + 1] & 1:
            p.append(c + 1)
        P.append(p)
    return P


def pct(v, p):
    return TL.pct(v, p)


# ---- reading the prompt timeline into per-card programs
def read_prompt(path):
    t = TL.read_timeline(path)
    N = t['names']
    pieces = sorted(set(k[0] for k in t['L']))
    cards = sorted(set(k[1] for k in t['L']))
    base = {}
    prof = {}
    floors = {'wait': [], 'p1': [], 'p2': []}
    for st in pieces:
        for c in cards:
            v = t['L'][(st, c)]
            seq = [(N[x.nid], (x.de - x.ds) / 1e3) for x in v]
            prof[(st, c)] = {'span': (max(x.de for x in v) - min(x.ds for x in v)) / 1e3,
                             'busy': sum(d for _, d in seq),
                             'xwait': sum(d for nm, d in seq if nm == 'XchgWaitB'),
                             'xpair': sum(d for nm, d in seq if nm == 'XchgPair'), 'n': len(seq)}
            items, pend = [], None
            for i, (nm, d) in enumerate(seq):
                nxt = seq[i + 1][0] if i + 1 < len(seq) else ''
                f = fam_of(nm, nxt)
                if f == 'wait':
                    items.append(['await', None, d])
                    floors['wait'].append(d)
                    continue
                if f == 'pair':
                    if pend is None:
                        pend = {'oa': 0.0, 'p1': d, 'p2': 0.0}
                        floors['p1'].append(d)
                    else:
                        pend['p2'] = d
                        floors['p2'].append(d)
                    continue
                if f == 'out_a':
                    if pend is None:
                        pend = {'oa': 0.0, 'p1': 0.0, 'p2': 0.0}
                    pend['oa'] += d
                    if nxt != 'XchgPair':  # the half's last output-a launch: X1's producer
                        items.append(['oa', pend])
                        items.append(['push', 'X1'])
                        pend = None
                    continue
                items.append(['k', f, d])
                if f == 'out_b':
                    items.append(['push', 'X2'])
                elif f == 'swiglu':
                    items.append(['push', 'X3'])
                elif f == 'combine':
                    items.append(['push', 'X4'])
                elif f == 'engram' and fam_of(nxt, '') != 'engram':
                    items.append(['push', 'ENG'])
            # label the pushes (site, layer, half) and the waits in px_layers' order
            cnt = Counter()
            for it in items:
                if it[0] == 'push':
                    s = it[1]
                    n = cnt[s]
                    cnt[s] += 1
                    it.append((s, 0, 0) if s == 'ENG' else (s, n // 2, n % 2))
            NL = cnt['X1'] // 2
            order = []
            for L in range(NL):
                order += [('X1', L, 0), ('X1', L, 1), ('X2', L, 0), ('X2', L, 1), ('X3', L, 0), ('X3', L, 1), ('X4', L, 0)]
                if L == 0 and cnt['ENG']:
                    order.append(('ENG', 0, 0))
                order.append(('X4', L, 1))
            ws = [it for it in items if it[0] == 'await']
            if len(ws) != len(order):
                raise SystemExit('piece %d card %d: %d waits, expected %d' % (st, c, len(ws), len(order)))
            for it, lab in zip(ws, order):
                it[1] = lab
            base[(st, c)] = items
    fl = {'wait': pct(floors['wait'], 25), 'p1': statistics.median(floors['p1']), 'p2': pct(floors['p2'], 10),
          'wait_p10': pct(floors['wait'], 10), 'wait_p50': pct(floors['wait'], 50), 'p2_min': min(floors['p2']),
          'p2_p50': pct(floors['p2'], 50), 'n_wait': len(floors['wait']), 'n_p2': len(floors['p2'])}
    return t, pieces, cards, base, prof, fl


def copy_fit():
    xs = [x for x, _ in BENCH]
    ys = [y for _, y in BENCH]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b


class Cfg:
    def __init__(self, units=CUR_UNITS, w=(0,) * 6, alpha=1.0, prt=None, bw=1.0, serial=True, fl=None, ab=None):
        self.units, self.w, self.alpha, self.prt, self.bw, self.serial, self.fl, self.ab = \
            tuple(units), tuple(w), alpha, prt, bw, serial, fl, ab


def make_progs(base, piece, cfg):
    """per card: the sim program (items with durations) and per push label the copy time in us"""
    a, b = cfg.ab
    td0, tm0, te0 = rows(H, (0,) * 6), rows(MID, (0,) * 6), rows(ENGR, (0,) * 6)
    td1, tm1, te1 = rows(H, cfg.w), rows(MID, cfg.w), rows(ENGR, cfg.w)
    pairs = head_pairs(cfg.units)
    progs, copy, fams = [], [], []
    for c in range(NC):
        hf = (cfg.units[c] / CUR_UNITS[c]) ** cfg.alpha
        sc = {}
        for f in HEADF:
            sc[f] = hf
        for f in TMF:
            sc[f] = tm1[c] / tm0[c]
        for f in TDF:
            sc[f] = td1[c] / td0[c]
        for f in TEF:
            sc[f] = te1[c] / te0[c]
        if cfg.prt:  # rough OWN_PRT emulation: q_a + kv rows and the router logits by tokens (16-token units)
            tk = rows(HALF, cfg.prt)
            sc['qakv'] = sc['router'] = tk[c] / HALF
        oab = (UR * cfg.units[c] * HALF * 4) / MIB + DS_MIB
        mib = {'X1': oab, 'X2': td1[c] * HALF * 4 / MIB, 'X4': td1[c] * HALF * 4 / MIB,
               'X3': tm1[c] * 7 * HALF * 4 / MIB + DS_MIB, 'ENG': te1[c] * 2 * 2 * HALF * 4 / MIB,
               'PRT': (rows(HALF, cfg.prt)[c] * 1792 * 4 / MIB) if cfg.prt else 0.0}
        cp = {s: a + b * cfg.bw * m for s, m in mib.items()}
        P, F, npair = [], [], 0
        for it in base[(piece, c)]:
            k = it[0]
            if k == 'k':
                f = it[1]
                d = it[2] * sc.get(f, 1.0)
                P.append(('k', d))
                F.append(f)
                if cfg.prt and ((f == 'qakv' and len(F) >= 2 and F[-2] == 'qakv') or f == 'router'):
                    # the token shares are all-gathered before their readers (taken as a tight barrier)
                    P.append(('push', ('PRT', f, sum(1 for x in F if x == f))))
                    F.append(None)
                    P.append(('bar', ('PRT', f, sum(1 for x in F if x == f))))
                    F.append(None)
            elif k == 'oa':
                tot = it[1]['oa'] * hf
                u = cfg.units[c]
                npr = len(pairs[c])
                if npr:
                    P.append(('pub', npair))
                    F.append('pair')
                    whole = tot * (u - npr) / u
                    if whole > 0:
                        P.append(('k', whole))
                        F.append('out_a')
                    P.append(('pw', npair, tuple(pairs[c]), cfg.fl['p2'] * npr))
                    F.append('pair')
                    P.append(('k', tot * npr / u))
                    F.append('out_a')
                else:
                    P.append(('k', tot))
                    F.append('out_a')
                npair += 1
            elif k == 'push':
                P.append(('push', it[2]))
                F.append(None)
                if cfg.serial and it[2][0] != 'ENG':
                    P.append(('bar', it[2]))
                    F.append(None)
            elif k == 'await':
                P.append(('await', it[1]))
                F.append(None)
        progs.append(P)
        fams.append(F)
        copy.append(cp)
    return progs, fams, copy


def simulate(progs, copy, fl, pub_us):
    n = len(progs)
    t = [0.0] * n
    ptr = [0] * n
    cfree = [0.0] * n
    flag = [dict() for _ in range(n)]
    pub = [dict() for _ in range(n)]
    wait = [0.0] * n
    eps = fl['wait']
    while True:
        moved = False
        for c in range(n):
            P = progs[c]
            while ptr[c] < len(P):
                it = P[ptr[c]]
                k = it[0]
                if k == 'k':
                    t[c] += it[1]
                elif k == 'push':
                    lab = it[1]
                    s = max(t[c], cfree[c])
                    e = s + copy[c][lab[0]]
                    cfree[c] = e
                    flag[c][lab] = e
                elif k in ('bar', 'await'):
                    lab = it[1]
                    ok = all(lab in flag[d] for d in range(n) if d != c)
                    if not ok:
                        break
                    r = max([t[c]] + [flag[d][lab] for d in range(n) if d != c])
                    wait[c] += r - t[c]
                    t[c] = r + eps
                elif k == 'pub':
                    t[c] += pub_us
                    pub[c][it[1]] = t[c]
                elif k == 'pw':
                    if not all(it[1] in pub[d] for d in it[2]):
                        break
                    r = max([t[c]] + [pub[d][it[1]] for d in it[2]])
                    wait[c] += r - t[c]
                    t[c] = r + it[3]
                ptr[c] += 1
                moved = True
        if all(ptr[c] == len(progs[c]) for c in range(n)):
            break
        if not moved:
            raise SystemExit('deadlock at ' + str([progs[c][ptr[c]] if ptr[c] < len(progs[c]) else None for c in range(n)]))
    return max(t), t, wait


def segments(progs, fams, pub_us):
    """stable mode: cut every card's program at its barriers; per segment and card the busy time by family
    (the pair swaps' publish + pull floors count as busy 'pair'; their waits do not)"""
    out = []
    for c in range(NC):
        segs, cur, lab_list = [], defaultdict(float), []
        for it, f in zip(progs[c], fams[c]):
            if it[0] == 'k':
                cur[f] += it[1]
            elif it[0] == 'pub':
                cur['pair'] += pub_us
            elif it[0] == 'pw':
                cur['pair'] += it[3]
            elif it[0] == 'bar' or (it[0] == 'await' and it[1][0] == 'ENG'):
                segs.append(cur)
                lab_list.append(it[1])
                cur = defaultdict(float)
        segs.append(cur)
        lab_list.append(('END', 0, 0))
        out.append((segs, lab_list))
    labs = out[0][1]
    for c in range(1, NC):
        if out[c][1] != labs:
            raise SystemExit('barrier sequences differ between card 0 and card %d' % c)
    return [[out[c][0][i] for c in range(NC)] for i in range(len(labs))], labs


SEGNAME = {'X1': 'attention block (post, q_a/kv, q_b, attention, output-a)', 'X2': 'output-b rows',
           'X3': 'FFN in (router, shared + routed gate/up, SwiGLU)', 'X4': 'FFN out (routed + shared down)',
           'ENG': 'engram rows (whole piece, once)', 'END': 'last post', 'PRT': 'prt token shares'}


def run(base, pieces, cfg, pub_us):
    res = []
    for st in pieces:
        progs, fams, copy = make_progs(base, st, cfg)
        T, tc, w = simulate(progs, copy, cfg.fl, pub_us)
        res.append((T, tc, w, progs, fams, copy))
    return res


def mean_T(res):
    return statistics.mean(r[0] for r in res) / 1e3


# ---- decode (one-token steps): every exchange is a synchronous pull = a barrier
DEC_TM = ('RoutedUQ', 'SwigluBothS', 'RoutePRows')


def dec_fam(nm):
    if nm.startswith(('XchgP', 'XchgQ', 'XchgPull')):
        return 'x'
    if nm.startswith(('RoutedUQ', 'RoutedQ2KF', 'RoutedIQ')):
        return 'tm' if int(re.search(r'<(\d+)u', nm).group(1)) == 20 else 'td'
    if nm.startswith(('SwigluBothS', 'RoutePRows')):
        return 'tm'
    if nm.startswith('FlDownComb') or nm.startswith(('GemvQ8P<256u', 'GemvQ6KP<32u')):
        return 'td'
    if nm.startswith('GemvQ6KP<24u'):
        return 'te'
    if nm.startswith('copy'):
        return 'copy'
    return 'o'


def read_decode(path):
    t = TL.read_timeline(path)
    N = t['names']
    steps = sorted(set(k[0] for k in t['L']))
    progs, spans, wsum = {}, [], defaultdict(float)
    for s in steps:
        per = []
        for c in range(NC):
            v = t['L'][(s, c)]
            per.append([(dec_fam(N[x.nid]), (x.de - x.ds) / 1e3, N[x.nid]) for x in v])
            spans.append((max(x.de for x in v) - min(x.ds for x in v)) / 1e3)
        nx = [sum(1 for f, _, _ in p if f == 'x') for p in per]
        if len(set(nx)) != 1:
            raise SystemExit('decode step %d: exchange counts differ %s' % (s, nx))
        progs[s] = per
    return steps, progs, spans


def dec_sim(per, w):
    td0, tm0, te0 = rows(H, (0,) * 6), rows(MID, (0,) * 6), rows(ENGR, (0,) * 6)
    td1, tm1, te1 = rows(H, w), rows(MID, w), rows(ENGR, w)
    sc = [{'tm': tm1[c] / tm0[c], 'td': td1[c] / td0[c], 'te': te1[c] / te0[c]} for c in range(NC)]
    segs = [[] for _ in range(NC)]
    xc = [[] for _ in range(NC)]
    for c in range(NC):
        cur = 0.0
        for f, d, _ in per[c]:
            if f == 'x':
                segs[c].append(cur)
                xc[c].append(d)
                cur = 0.0
            elif f != 'copy':
                cur += d * sc[c].get(f, 1.0)
        segs[c].append(cur)
    T = 0.0
    for i in range(len(segs[0])):
        T += max(segs[c][i] for c in range(NC))
        if i < len(xc[0]):
            T += min(xc[c][i] for c in range(NC))  # transport + launch on the last card to arrive
    return T


def dec_mean(steps, progs, w):
    return statistics.mean(dec_sim(progs[s], w) for s in steps) / 1e3


def shares_to_w(sh, tot=192):
    return tuple(max(1, int(round(x * tot))) for x in sh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompt', default=PROMPT)
    ap.add_argument('--decode', default=DECODE)
    ap.add_argument('--bw', type=float, default=1.4, help='copy slowdown vs the Gen5 bench (stable mode, Gen4 links; 1.4 = the '
                    'measured stable / overlap cost, section 4)')
    ap.add_argument('--quick', action='store_true')
    A = ap.parse_args()
    out = print

    t, pieces, cards, base, prof, fl = read_prompt(A.prompt)
    a, b = copy_fit()
    out('# barrier_sim.py output (prompt %s, decode %s)' % (A.prompt, A.decode))
    out()
    out('## 1. Data and boundaries')
    out('pieces %s, cards %s' % (pieces, cards))
    for st in pieces:
        for c in cards:
            it = base[(st, c)]
            pu = Counter(x[1] for x in it if x[0] == 'push')
            out('  piece %d card %d: %4d launches, pushes %s, waits %d, output-a groups %d, span %.2f ms' % (
                st, c, prof[(st, c)]['n'], dict(sorted(pu.items())), sum(1 for x in it if x[0] == 'await'),
                sum(1 for x in it if x[0] == 'oa'), prof[(st, c)]['span'] / 1e3))
    same = all([x[2] for x in base[(st, c)] if x[0] == 'push'] == [x[2] for x in base[(st, 0)] if x[0] == 'push']
               for st in pieces for c in cards)
    out('push sequence (site, layer, half) identical on all six cards in both pieces: %s' % same)
    out('XchgWaitB floor (p25 of %d launches) %.2f us (p10 %.2f, median %.2f); XchgPair publish median %.2f us; '
        'pair pull floor (p10 of %d waits) %.1f us (min %.1f, median %.1f)' % (
            fl['n_wait'], fl['wait'], fl['wait_p10'], fl['wait_p50'], fl['p1'], fl['n_p2'], fl['p2'], fl['p2_min'],
            fl['p2_p50']))
    out('copy fit to the push bench: %.1f us + %.1f us per MiB per peer (Gen5); stable-mode scale --bw %.2f' % (a, b, A.bw))
    for m, us in BENCH:
        out('  bench %.2f MiB x5: %.1f us, fit %.1f us' % (m, us, a + b * m))
    out('copies per push at the current split (MiB per peer -> us at bw %.2f):' % A.bw)
    cfg0 = Cfg(fl=fl, ab=(a, b), bw=A.bw)
    _, _, cp = make_progs(base, pieces[0], cfg0)
    for c in cards:
        out('  card %d: ' % c + ', '.join('%s %.0f' % (s, cp[c][s]) for s in ('X1', 'X2', 'X3', 'X4', 'ENG')))

    out()
    out('## 2. Per card and piece: compute busy (no exchange kernels) by family category, ms')
    cats = ['experts', 'dense rows', 'attention+index', 'norms+mix', 'small/other']
    tot_busy = {}
    for st in pieces:
        out('piece %d' % st)
        out('  card  ' + ''.join('%17s' % x for x in cats) + '   busy  | profile: span  XchgWaitB  XchgPair')
        for c in cards:
            acc = defaultdict(float)
            for it in base[(st, c)]:
                if it[0] == 'k':
                    acc[CAT.get(it[1], 'small/other')] += it[2]
                elif it[0] == 'oa':
                    acc['dense rows'] += it[1]['oa']
            tb = sum(acc.values())
            tot_busy[(st, c)] = tb
            p = prof[(st, c)]
            out('  %d     ' % c + ''.join('%17.2f' % (acc[x] / 1e3) for x in cats) + '  %7.2f | %13.2f %10.2f %9.2f' % (
                tb / 1e3, p['span'] / 1e3, p['xwait'] / 1e3, p['xpair'] / 1e3))

    out()
    out('## 3. Model check: overlap mode (OWN_PX_SERIAL=0, Gen5 copies as in the profiled run) vs the profile')
    cfgO = Cfg(fl=fl, ab=(a, b), bw=1.0, serial=False)
    resO = run(base, pieces, cfgO, fl['p1'])
    for (T, tc, w, *_), st in zip(resO, pieces):
        out('  piece %d: model %.2f ms, profile span %.2f-%.2f ms; waits per card model / profile (XchgWaitB + XchgPair) ms:'
            % (st, T / 1e3, min(prof[(st, c)]['span'] for c in cards) / 1e3, max(prof[(st, c)]['span'] for c in cards) / 1e3))
        out('    ' + '  '.join('c%d %.1f/%.1f' % (c, w[c] / 1e3, (prof[(st, c)]['xwait'] + prof[(st, c)]['xpair']) / 1e3)
                              for c in cards))

    out()
    out('## 4. Stable mode (OWN_PX_SERIAL=1): barrier model, copies at bw %.2f' % A.bw)
    cfgS = Cfg(fl=fl, ab=(a, b), bw=A.bw)
    resS = run(base, pieces, cfgS, fl['p1'])
    imb_all = []
    segrows = defaultdict(lambda: {'n': 0, 'excess': 0.0, 'max': 0.0, 'mean': 0.0, 'who': Counter(), 'fam': defaultdict(float)})
    for (T, tc, w, progs, fams, copy), st in zip(resS, pieces):
        segs, labs = segments(progs, fams, fl['p1'])
        smax = smean = 0.0
        for sg, lab in zip(segs, labs):
            busy = [sum(sg[c].values()) for c in range(NC)]
            mx, mn = max(busy), statistics.mean(busy)
            smax += mx
            smean += mn
            cm = busy.index(mx)
            r = segrows[lab[0]]
            r['n'] += 1
            r['excess'] += mx - mn
            r['max'] += mx
            r['mean'] += mn
            r['who'][cm] += mx - mn
            for f in set().union(*[sg[c].keys() for c in range(NC)]):
                r['fam'][f] += sg[cm].get(f, 0.0) - statistics.mean(sg[c].get(f, 0.0) for c in range(NC))
        cpy = 0.0
        for it in progs[0]:
            if it[0] == 'bar':
                cpy += max(copy[d][it[1][0]] for d in range(NC)) + fl['wait']
            if it[0] == 'await' and it[1][0] == 'ENG':
                cpy += max(copy[d]['ENG'] for d in range(NC))
        mxc = max(tot_busy[(st, c)] for c in cards)
        Tov = resO[pieces.index(st)][0]
        imb_all.append((smax - smean, T))
        out('  piece %d: model %.2f ms = sum of segment maxima %.2f + barriers (slowest copy + wait floor) %.2f '
            '+ pair waits / other %.2f' % (st, T / 1e3, smax / 1e3, cpy / 1e3, (T - smax - cpy) / 1e3))
        out('           sum of segment means %.2f ms; slowest card total busy %.2f ms (card %d); mean card busy %.2f'
            % (smean / 1e3, mxc / 1e3, max(cards, key=lambda c: tot_busy[(st, c)]),
               statistics.mean(tot_busy[(st, c)] for c in cards) / 1e3))
        out('           imbalance (sum max - sum mean) %.2f ms = %.1f %% of the piece; copies + waits %.2f ms = %.1f %%;'
            ' stable / overlap model %.3f' % ((smax - smean) / 1e3, 100 * (smax - smean) / T, cpy / 1e3, 100 * cpy / T, T / Tov))
        out('           of which segment-level (sum max - slowest card total) %.2f ms, card-total (slowest - mean) %.2f ms'
            % ((smax - mxc) / 1e3, (mxc - statistics.mean(tot_busy[(st, c)] for c in cards)) / 1e3))
    out('  measured 3K reads: ' + '; '.join('%s %.2f s' % kv for kv in MEAS.items()) + '; tp115 stable / tp114 overlap %.3f'
        % (MEAS['tp115 stable, def heads (st1 c1_p3k_def)'] / MEAS['tp114 overlap, Gen5 (dsv41 lane note)']))
    for bw in (1.0, 1.2):
        r2 = run(base, pieces, Cfg(fl=fl, ab=(a, b), bw=bw), fl['p1'])
        out('  sensitivity: copies at bw %.2f -> stable model %.2f ms per piece, stable / overlap %.3f; vs bw %.2f: %+.2f ms (%+.1f %%)'
            % (bw, mean_T(r2), mean_T(r2) / mean_T(resO), A.bw, mean_T(r2) - mean_T(resS), 100 * (mean_T(r2) / mean_T(resS) - 1)))
    progs, copy = resS[0][3], resS[0][5]
    bys = defaultdict(float)
    for it in progs[0]:
        if it[0] == 'bar':
            bys[it[1][0]] += max(copy[d][it[1][0]] for d in range(NC))
        if it[0] == 'await' and it[1][0] == 'ENG':
            bys['ENG'] += max(copy[d]['ENG'] for d in range(NC))
    out('  copy time per piece by exchange (slowest sender, bw %.2f), ms: ' % A.bw +
        ', '.join('%s %.2f' % (k, v / 1e3) for k, v in sorted(bys.items())) +
        '; stable - overlap model %.2f ms (%.1f %% of the stable piece)' % (mean_T(resS) - mean_T(resO),
                                                                           100 * (1 - mean_T(resO) / mean_T(resS))))

    out()
    out('## 5. Where the imbalance sits (stable mode, both pieces summed; ms)')
    ex_tot = sum(r['excess'] for r in segrows.values())
    out('  segment type (ends at)                                  n   sum max  sum mean  max-mean  share  max card (by excess ms)')
    for lab, r in sorted(segrows.items(), key=lambda kv: -kv[1]['excess']):
        out('  %-55s %3d %9.2f %9.2f %9.2f %5.1f%%  %s' % (
            lab + ' ' + SEGNAME.get(lab, ''), r['n'], r['max'] / 1e3, r['mean'] / 1e3, r['excess'] / 1e3,
            100 * r['excess'] / ex_tot, ', '.join('c%d %.1f' % (c, v / 1e3) for c, v in r['who'].most_common())))
        top = sorted(r['fam'].items(), key=lambda kv: -kv[1])[:5]
        out('      the max card\'s excess over the mean by family: ' + ', '.join('%s %+.2f' % (f, v / 1e3) for f, v in top))

    out()
    out('## 6. (a) prompt heads OWN_TP_HEADS=4,2,2,4,2,2 (16/8/8/16/8/8, no pair swaps), per piece')
    T0 = mean_T(resS)
    out('  stable model, current heads 3,3,3,3,2,2: %.2f ms' % T0)
    for alpha in (1.0, 1.14):
        r = run(base, pieces, Cfg(units=H1_UNITS, alpha=alpha, fl=fl, ab=(a, b), bw=A.bw), fl['p1'])
        out('  heads 4,2,2,4,2,2, head-scaled kernels x (heads ratio)^%.2f: %.2f ms (%+.1f %%)' % (alpha, mean_T(r), 100 * (mean_T(r) / T0 - 1)))
    # alpha from the profile: 8-head cards 4/5 vs 12-head cards 1/2 (all 230 W)
    hk = defaultdict(float)
    for st in pieces:
        for c in cards:
            for it in base[(st, c)]:
                if it[0] == 'k' and it[1] in ('q_b', 'attn'):
                    hk[c] += it[2]
                elif it[0] == 'oa':
                    hk[c] += it[1]['oa']
    r8 = (hk[4] + hk[5]) / (hk[1] + hk[2])
    out('  head-scaled kernels, cards 4+5 (8 heads) / cards 1+2 (12 heads): %.3f -> exponent %.2f; per card ms per piece: %s'
        % (r8, math.log(r8) / math.log(8 / 12), ', '.join('c%d %.1f' % (c, hk[c] / len(pieces) / 1e3) for c in cards)))
    r = run(base, pieces, Cfg(units=H1_UNITS, fl=fl, ab=(a, b), bw=A.bw, serial=False), fl['p1'])
    out('  overlap mode (for reference): current %.2f ms, heads 4,2,2,4,2,2 %.2f ms (%+.1f %%)' % (
        mean_T(resO), mean_T(r), 100 * (mean_T(r) / mean_T(resO) - 1)))
    out('  rough tp115 emulation (OWN_PRT=3: q_a + kv and router rows by token weights 3,2,2,3,3,3, their gathers as barriers):')
    rp0 = run(base, pieces, Cfg(prt=(3, 2, 2, 3, 3, 3), fl=fl, ab=(a, b), bw=A.bw), fl['p1'])
    rp1 = run(base, pieces, Cfg(units=H1_UNITS, prt=(3, 2, 2, 3, 3, 3), fl=fl, ab=(a, b), bw=A.bw), fl['p1'])
    rp2 = run(base, pieces, Cfg(units=H1_UNITS, prt=(2, 3, 3, 2, 3, 3), fl=fl, ab=(a, b), bw=A.bw), fl['p1'])
    out('    current heads %.2f ms; heads 4,2,2,4,2,2 %.2f ms (%+.1f %%; measured 3K read %+.1f %%); heads 4,2,2,4,2,2 with token '
        'weights 2,3,3,2,3,3 %.2f ms (%+.1f %%)' % (mean_T(rp0), mean_T(rp1), 100 * (mean_T(rp1) / mean_T(rp0) - 1),
                                                     100 * (MEAS['tp115 stable, heads 4,2,2,4,2,2 (st1 c1_p3k_h1)'] /
                                                            MEAS['tp115 stable, def heads (st1 c1_p3k_def)'] - 1),
                                                     mean_T(rp2), 100 * (mean_T(rp2) / mean_T(rp0) - 1)))
    lin = run(base, pieces, Cfg(units=H1_UNITS, fl=fl, ab=(a, b), bw=A.bw), fl['p1'])
    mh = MEAS['tp115 stable, heads 4,2,2,4,2,2 (st1 c1_p3k_h1)'] / MEAS['tp115 stable, def heads (st1 c1_p3k_def)'] - 1
    out('  measured loss / model loss: %.1f (linear, tp109 structure), %.1f (rough tp115 emulation)' % (
        mh / (mean_T(lin) / T0 - 1), mh / (mean_T(rp1) / mean_T(rp0) - 1)))

    out()
    out('## 7. (b) row weights OWN_TP_WEIGHTS (expert / shared / output-b / engram rows), prompt and decode')
    steps, dprogs, dspans = read_decode(A.decode)
    D0 = dec_mean(steps, dprogs, (0,) * 6)
    out('  decode model (one-token steps %d-%d, barriers at the %d exchanges): %.3f ms per step; profile span %.3f ms'
        % (steps[0], steps[-1], sum(1 for f, _, _ in dprogs[steps[0]][0] if f == 'x'), D0, statistics.mean(dspans) / 1e3))
    dw = defaultdict(float)
    for s in steps:
        for c in range(NC):
            for f, d, _ in dprogs[s][c]:
                if f in ('tm', 'td', 'te'):
                    dw[(c, f)] += d / len(steps)
    out('  decode weighted kernels per step, us (tm / td / te): ' + '; '.join(
        'c%d %.0f/%.0f/%.0f' % (c, dw[(c, 'tm')], dw[(c, 'td')], dw[(c, 'te')]) for c in range(NC)))

    cache = {}

    def prompt_T(w, units=CUR_UNITS, prt=None):
        key = (tuple(w), tuple(units), prt)
        if key not in cache:
            cache[key] = mean_T(run(base, pieces, Cfg(units=units, w=tuple(w), prt=prt, fl=fl, ab=(a, b), bw=A.bw), fl['p1']))
        return cache[key]

    def isearch(obj, start=(32,) * 6, lo=16, hi=48):
        """integer neighbourhood search over OWN_TP_WEIGHTS (single +-1/2/4 and pair transfers of 1/2)"""
        w = list(start)
        best = obj(w)
        ev = 1
        while True:
            cands = []
            for i in range(6):
                for d in (1, 2, 4, -1, -2, -4):
                    w2 = list(w)
                    w2[i] += d
                    cands.append(w2)
                for j in range(6):
                    if j != i:
                        for d in (1, 2):
                            w2 = list(w)
                            w2[i] += d
                            w2[j] -= d
                            cands.append(w2)
            top = None
            for w2 in cands:
                if min(w2) < lo or max(w2) > hi:
                    continue
                v = obj(w2)
                ev += 1
                if v < best - 1e-6 and (top is None or v < top[0]):
                    top = (v, w2)
            if top is None:
                return w, best, ev
            best, w = top

    for units, nm in ((CUR_UNITS, '3,3,3,3,2,2'), (H1_UNITS, '4,2,2,4,2,2')):
        Tb = prompt_T((0,) * 6, units)
        w, T, ev = isearch(lambda w: prompt_T(w, units))
        Dw = dec_mean(steps, dprogs, w)
        out('  heads %s: equal rows %.2f ms -> best OWN_TP_WEIGHTS=%s %.2f ms per piece (%+.1f %%), %d evaluations;'
            ' decode %.3f -> %.3f ms per step (%+.1f %%)' % (nm, Tb, ','.join(map(str, w)), T, 100 * (T / Tb - 1), ev, D0, Dw,
                                                              100 * (Dw / D0 - 1)))
        out('    rows per card at these weights: td %s, tm %s, te %s' % (rows(H, w), rows(MID, w), rows(ENGR, w)))
        if Dw > D0:
            out('    break-even: %.0f one-token answer steps per 512-token prompt piece (prompt gain %.2f ms / decode cost %.4f ms per step)'
                % ((Tb - T) / (Dw - D0), Tb - T, Dw - D0))
    w, Dm, ev = isearch(lambda w: dec_mean(steps, dprogs, w))
    out('  decode-only best OWN_TP_WEIGHTS=%s: %.3f ms per step (%+.1f %%); prompt piece then %.2f ms (%+.1f %%)'
        % (','.join(map(str, w)), Dm, 100 * (Dm / D0 - 1), prompt_T(w), 100 * (prompt_T(w) / T0 - 1)))
    for k in (20, 80):
        w, v, ev = isearch(lambda w: prompt_T(w) + k * dec_mean(steps, dprogs, w))
        out('  joint best for %d answer steps per prompt piece: OWN_TP_WEIGHTS=%s piece %.2f ms (%+.2f), step %.3f ms (%+.4f)'
            % (k, ','.join(map(str, w)), prompt_T(w), prompt_T(w) - T0, dec_mean(steps, dprogs, w), dec_mean(steps, dprogs, w) - D0))

    out()
    out('## 8. (c) every prompt head layout with 2-4 units per card (stable model, equal rows)')
    res = []
    def comps(n, k):
        if k == 1:
            if 2 <= n <= 4:
                yield (n,)
            return
        for x in (2, 3, 4):
            if n - x >= 2 * (k - 1):
                for r in comps(n - x, k - 1):
                    yield (x,) + r
    for u in comps(16, 6):
        res.append((mean_T(run(base, pieces, Cfg(units=u, fl=fl, ab=(a, b), bw=A.bw), fl['p1'])), u))
    res.sort()
    out('  %d layouts; best 8 and the current / H1:' % len(res))
    for T, u in res[:8]:
        out('    %s  %.2f ms (%+.1f %%)  pairs %s' % (','.join(map(str, u)), T, 100 * (T / T0 - 1), head_pairs(u)))
    for T, u in res:
        if u in (CUR_UNITS, H1_UNITS):
            out('    %s  %.2f ms (%+.1f %%) rank %d' % (','.join(map(str, u)), T, 100 * (T / T0 - 1), res.index((T, u)) + 1))

    out()
    out('## 9. (c) prompt-only token weights OWN_PRT_W under the rough tp115 emulation (indicative only)')
    pr = []
    def comps1(n, k):
        if k == 1:
            if 1 <= n <= 5:
                yield (n,)
            return
        for x in range(1, 6):
            if n - x >= k - 1:
                for r in comps1(n - x, k - 1):
                    yield (x,) + r
    for u in (CUR_UNITS, H1_UNITS):
        pr = sorted((prompt_T((0,) * 6, u, p), p) for p in comps1(16, 6))
        base_p = prompt_T((0,) * 6, u, (3, 2, 2, 3, 3, 3))
        out('  heads %s: %d weight vectors; OWN_PRT_W=3,2,2,3,3,3 %.2f ms; best: %s' % (
            ','.join(map(str, u)), len(pr), base_p,
            '; '.join('%s %.2f (%+.1f %%)' % (','.join(map(str, p)), T, 100 * (T / base_p - 1)) for T, p in pr[:4])))


if __name__ == '__main__':
    main()
