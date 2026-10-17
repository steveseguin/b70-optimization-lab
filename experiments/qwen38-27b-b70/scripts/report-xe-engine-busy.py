"""Busy fraction of each card's compute engine over decode-only sample pairs (generated tokens rose, prompt tokens
did not, same client set), grouped into runs of consecutive such pairs (one per answer)."""
import json, sys, time
rows = [json.loads(l) for l in open(sys.argv[1])]
runs, cur = [], None
for a, b in zip(rows, rows[1:]):
    ok = (a['gen'] is not None and b['gen'] is not None and b['gen'] > a['gen'] and b['prompt'] == a['prompt']
          and a['n'] == b['n'] and set(a['cards']) == set(b['cards']))
    if not ok:
        if cur: runs.append(cur); cur = None
        continue
    if cur is None: cur = {'t0': a['t'], 'gen': 0, 'dt': 0.0, 'busy': {}, 'bcs': {}}
    cur['t1'] = b['t']; cur['gen'] += b['gen'] - a['gen']
    for k in a['cards']:
        dc = b['cards'][k][0] - a['cards'][k][0]; dt = b['cards'][k][1] - a['cards'][k][1]; db = b['cards'][k][2] - a['cards'][k][2]
        if dc < 0 or dt <= 0: continue
        x = cur['busy'].setdefault(k, [0, 0]); x[0] += dc; x[1] += dt
        y = cur['bcs'].setdefault(k, [0, 0]); y[0] += db; y[1] += dt
if cur: runs.append(cur)
for r in runs:
    if r['gen'] < 40: continue
    busy = ' '.join('%s ccs %.1f%% bcs %.1f%%' % (k[5:7], 100 * v[0] / v[1], 100 * r['bcs'][k][0] / r['bcs'][k][1])
                    for k, v in sorted(r['busy'].items()))
    print('%s-%s %4.1fs gen %4d  %s' % (time.strftime('%H:%M:%S', time.localtime(r['t0'])),
                                         time.strftime('%H:%M:%S', time.localtime(r['t1'])), r['t1'] - r['t0'], r['gen'], busy))
