import sys, os, re
sys.path.insert(0, '/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine/tools/perf')
import dsv41_timeline as T
def fam(n):
    n = re.sub(r'<.*', '', n) if not n.startswith('RowsP') else n
    if n.startswith('RowsP'):
        m = re.findall(r'(Gemv\w+|NormRows|HcDotsRows|HcFinishRows|RopeRows|Route\w+|Engram\w+|\w+Rows\w*)', n)
        n = 'RowsP:' + '+'.join(dict.fromkeys(m))
    return n
from collections import defaultdict
t = T.read_timeline(sys.argv[1])
keys = list(t['L'].keys()); steps = sorted(set(k[0] for k in keys)); cards = sorted(set(k[1] for k in keys))
def cat(n):
    if re.search(r'Xchg', n): return 'exchanges'
    if re.search(r'Routed|RoutePM|ExpertGroup|MoeCombine|Swiglu', n): return 'experts'
    if re.search(r'Sparse|OutMJ|Score|Window|Cidx|Indexer|TopK', n): return 'attention+index'
    if re.search(r'Dense|Gemv|PaceK|FlDownComb|RowsDotsK|RoutePRows|FlNormK', n): return 'dense rows (+riders)'
    if re.search(r'Norm|HcPostPre|Dots', n): return 'norms+mix'
    return 'small/other'
for c in [int(x) for x in sys.argv[2:]]:
    acc = defaultdict(float); cnt = defaultdict(float); span = []
    for s in steps:
        v = t['L'].get((s, c), [])
        if not v: continue
        span.append((max(x.de for x in v) - min(x.ds for x in v)) / 1e3)
        for x in v:
            nm = fam(t['names'].get(x.nid, '?')); acc[nm] += (x.de - x.ds) / 1e3; cnt[nm] += 1
    n = len(steps)
    cats = defaultdict(float); ccnt = defaultdict(float)
    for k in acc: cats[cat(k)] += acc[k] / n; ccnt[cat(k)] += cnt[k] / n
    print(f'card {c}: {n} steps, busy {sum(acc.values())/n/1000:.2f} ms, span {sum(span)/len(span)/1000:.2f} ms, launches {sum(cnt.values())/n:.0f}')
    for k, v in sorted(cats.items(), key=lambda kv: -kv[1]): print(f'  {k:24s} {v/1000:6.2f} ms  {ccnt[k]:5.0f} launches')
    if c == int(sys.argv[2]):
        print('  top families:')
        for k, v in sorted(acc.items(), key=lambda kv: -kv[1])[:22]: print(f'    {v/n:8.1f} us {cnt[k]/n:5.0f} x {v/cnt[k]:6.2f}  {k[:70]}')
