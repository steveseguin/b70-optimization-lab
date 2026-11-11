import sys, statistics as S
from collections import defaultdict
sys.path.insert(0, '/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine/tools/perf')
import dsv41_timeline as TL

path = sys.argv[1]
T = TL.read_timeline(path)
N = T['names']
def cls(nid):
    n = N.get(nid, '')
    if n.startswith('RowsP<RowsPair<RowsPair<HcFinishRows, RopeRows'): return 'QB'
    if n.startswith('RowsP<RowsPair<NoRows, DenseRows<GemvQ8P<40u') or n.startswith('RowsP<RowsPair<NoRows, DenseRows<GemvQ6KP<5u'): return 'XR'
    if n == 'RowsP<RopeRows<ActF32> >': return 'ROPE'
    if n == 'QbPush': return 'PUSH'
    if n.startswith('QbWaitRope'): return 'WAIT'
    if n.startswith('Xchg'): return 'X'
    if n.startswith('SkNormPairW'): return 'NP'
    if n.startswith('RowsP<RowsPair<HcDotsRows<5120u, 8u>, RowsPair<DenseRows<GemvQ8P<160u') or n.startswith('RowsP<RowsPair<NoRows, RowsPair<DenseRows'): return 'QA'
    if n.startswith('WindowAppendP'): return 'WA'
    if n.startswith('SparseScore'): return 'SC'
    if n.startswith('SparseSoftmax'): return 'SM'
    if n.startswith('SparseOut'): return 'SO'
    return n
# one-token steps = steps with QB launches
steps = sorted({st for (st, c), v in T['L'].items() if any(cls(x.nid) == 'QB' for x in v)})
cards = sorted({c for (st, c) in T['L']})
caus = TL.align_causal(T, 1000.0)
for key, v in T['L'].items():
    o = caus[key]
    for x in v:
        x.s, x.e = x.ds - o, x.de - o
print('# %s  one-token steps %s' % (path, steps))
D = defaultdict(list)   # (card, quantity) -> values (us)
arr = defaultdict(list) # layer -> list per step of per-card arrival
lastc = defaultdict(int); margins = []; hl = []
period = []
walls = []
for st in steps:
    per = {}
    for c in cards:
        v = sorted(T['L'][(st, c)], key=lambda x: x.idx)
        qi = [i for i, x in enumerate(v) if cls(x.nid) == 'QB']
        lay = []
        for L, i in enumerate(qi):
            j = i
            while cls(v[j].nid) != 'NP': j -= 1
            np_ = v[j]
            pre = v[j + 1:i]          # helper sends
            q = v[i]
            k = i + 1
            while not (cls(v[k].nid) == 'X' and v[k].xpart == 0): k += 1
            xa = v[k]
            mid = v[i + 1:k]
            # previous exchange end before the layer's first launch
            p = j
            while p > 0 and cls(v[p].nid) != 'X': p -= 1
            prevx = v[p] if cls(v[p].nid) == 'X' else v[0]
            d = dict(L=L, np_end=np_.e, q_s=q.s, q_e=q.e, q_d=(q.e - q.s) / 1e3, xa_s=xa.s, xa_e=xa.e,
                     xa_d=(xa.e - xa.s) / 1e3, prev_e=prevx.e if prevx is not v[0] else v[0].s)
            d['pre'] = [(cls(x.nid), (x.e - x.s) / 1e3) for x in pre]
            d['pre_span'] = (q.s - np_.e) / 1e3
            d['mid'] = [(cls(x.nid), (x.e - x.s) / 1e3) for x in mid]
            d['wait'] = sum((x.e - x.s) / 1e3 for x in mid if cls(x.nid) == 'WAIT')
            d['rope'] = sum((x.e - x.s) / 1e3 for x in mid if cls(x.nid) == 'ROPE')
            d['att'] = sum((x.e - x.s) / 1e3 for x in mid if cls(x.nid) in ('WA', 'SC', 'SM', 'SO'))
            d['oa'] = (mid[-1].e - mid[-1].s) / 1e3
            d['q_to_xa'] = (xa.s - q.s) / 1e3
            d['prev_to_xa'] = (xa.s - d['prev_e']) / 1e3
            d['prev_to_q'] = (q.s - d['prev_e']) / 1e3
            if pre:
                d['push_e'] = [x.e for x in pre if cls(x.nid) == 'PUSH'][0]
            lay.append(d)
        per[c] = lay
    nl = min(len(per[c]) for c in cards)
    b = [T['st'][(st, c)][0] for c in cards if (st, c) in T['st']]
    e = [max(x.e for x in T['L'][(st, c)]) for c in cards]
    walls.append((max(e) - min(b)) / 1e6)
    for L in range(nl):
        A = {c: per[c][L]['xa_s'] for c in cards}
        srt = sorted(cards, key=lambda c: -A[c])
        lastc[srt[0]] += 1
        margins.append((A[srt[0]] - A[srt[1]]) / 1e3)
        heavy = max(A[2], A[5]); light = max(A[c] for c in (0, 1, 3, 4))
        hl.append((heavy - light) / 1e3)
        for c in cards:
            d = per[c][L]
            for kq in ('q_d', 'xa_d', 'wait', 'rope', 'att', 'oa', 'q_to_xa', 'pre_span', 'prev_to_xa', 'prev_to_q'):
                D[(c, kq)].append(d[kq])
            for nm, du in d['pre']:
                D[(c, 'pre:' + nm)].append(du)
            if 'push_e' in d:
                # heavy target: lateness of the push end vs the heavy q_b end
                pass
        if L > 0:
            period.append((max(per[c][L]['xa_e'] for c in cards) - max(per[c][L - 1]['xa_e'] for c in cards)) / 1e3)
        # push lateness: for each heavy, its helpers' push end minus heavy q_b end
        for h, hs in ((2, (1, 3)), (5, (4, 0))):
            if 'push_e' in per[hs[0]][L]:
                pe = max(per[x][L]['push_e'] for x in hs)
                D[(h, 'push_late_vs_qb_end')].append((pe - per[h][L]['q_e']) / 1e3)
print('step wall ms:', ' '.join('%.3f' % w for w in walls), ' mean %.3f' % S.mean(walls))
print('layer period (output-a end to next output-a end, latest card), us: median %.2f mean %.2f' % (S.median(period), S.mean(period)))
def m(c, k):
    v = D.get((c, k))
    return ('%6.2f' % S.median(v)) if v else '     -'
keys = ['prev_to_q', 'pre_span', 'q_d', 'wait', 'rope', 'att', 'oa', 'q_to_xa', 'prev_to_xa', 'xa_d', 'pre:XR', 'pre:ROPE', 'pre:PUSH', 'push_late_vs_qb_end']
print('per card, median per layer (us):')
print('%-20s' % 'quantity' + ''.join('     c%d' % c for c in cards))
for k in keys:
    print('%-20s' % k + ''.join(' ' + m(c, k) for c in cards))
print('mean per layer (us):')
for k in ['q_d', 'q_to_xa', 'prev_to_xa', 'xa_d']:
    print('%-20s' % k + ''.join('  %6.2f' % S.mean(D[(c, k)]) for c in cards))
n = sum(lastc.values())
print('last to start output-a: ' + ', '.join('c%d %d%%' % (c, 100 * lastc[c] / n) for c in cards) + '  (margin median %.2f us)' % S.median(margins))
print('heavy minus light arrival at output-a (latest heavy - latest light), us: median %.2f, p10 %.2f, p90 %.2f' % (S.median(hl), TL.pct(hl, 10), TL.pct(hl, 90)))
