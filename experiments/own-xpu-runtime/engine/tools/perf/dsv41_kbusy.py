"""Device time per kernel family, mean per step and card, of two OWN_TIMELINE files (e.g. a one-token timeline and
an OWN_TIMELINE_CHECKS one): python3 -I dsv41_kbusy.py one.txt check.txt (round19 tg87, 2026-11-11)."""
import sys, re
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsv41_timeline as T
from collections import defaultdict
def fam(n):
    n = re.sub(r'<.*', '', n) if not n.startswith('RowsP') else n
    if n.startswith('RowsP'):
        m = re.findall(r'(Gemv\w+|NormRows|HcDotsRows|HcFinishRows|RopeRows|Route\w+|Engram\w+|\w+Rows\w*)', n)
        n = 'RowsP:' + '+'.join(dict.fromkeys(m))
    return n
def busy(path):
    t = T.read_timeline(path)
    acc = defaultdict(float); cnt = defaultdict(float)
    keys = list(t['L'].keys()); steps = sorted(set(k[0] for k in keys)); cards = sorted(set(k[1] for k in keys))
    for k, v in t['L'].items():
        for x in v:
            nm = fam(t['names'].get(x.nid, '?'))
            acc[nm] += (x.de - x.ds) / 1e3; cnt[nm] += 1
    d = len(steps) * len(cards)
    return {k: (acc[k] / d, cnt[k] / d) for k in acc}
a = busy(sys.argv[1]); b = busy(sys.argv[2])
rows = sorted(set(a) | set(b), key=lambda k: -(b.get(k, (0, 0))[0] - a.get(k, (0, 0))[0]))
print('%-60s %9s %6s %9s %6s %9s' % ('family', 'one us', 'n', 'check us', 'n', 'diff'))
for k in rows:
    x = a.get(k, (0, 0)); y = b.get(k, (0, 0))
    print('%-60s %9.1f %6.1f %9.1f %6.1f %9.1f' % (k[:60], x[0], x[1], y[0], y[1], y[0] - x[0]))
print('total', sum(v[0] for v in a.values()), sum(v[0] for v in b.values()))
