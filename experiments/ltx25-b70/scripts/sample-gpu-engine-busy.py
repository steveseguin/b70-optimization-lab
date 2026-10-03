#!/usr/bin/env python3
"""Sample per-card GPU engine busy time for one process from DRM fdinfo (no GPU access, no hooks).

The xe driver exposes, per open DRM client, cumulative busy cycles per engine
class (`drm-cycles-ccs` compute, `drm-cycles-bcs` copy) and the elapsed cycle
count (`drm-total-cycles-*`) in /proc/<pid>/fdinfo/<fd>. Busy delta divided by
total delta over an interval is that card's engine utilisation by this
process. Reading fdinfo does not open the device, so it is safe to run next
to a live server (unlike xpu-smi polling).

    sample-gpu-engine-busy.py <pid> <out.jsonl> [--interval 2]

Writes one JSON line per interval: {"t": unix, "cards": {pdev: {"ccs": util,
"bcs": util, "ccs_busy_s": seconds, "bcs_busy_s": seconds}}} and stops when
the process exits.
"""
import argparse, glob, json, os, time

ap = argparse.ArgumentParser()
ap.add_argument('pid', type=int)
ap.add_argument('out')
ap.add_argument('--interval', type=float, default=2.0)
a = ap.parse_args()


def snap(pid):
    cards = {}
    seen = set()
    for f in glob.glob(f'/proc/{pid}/fdinfo/*'):
        try:
            kv = dict(l.split(':', 1) for l in open(f).read().splitlines() if ':' in l)
        except OSError:
            continue
        pdev = kv.get('drm-pdev', '').strip()
        cid = kv.get('drm-client-id', '').strip()
        if not pdev or (pdev, cid) in seen:
            continue
        seen.add((pdev, cid))
        c = cards.setdefault(pdev, {'ccs': 0, 'bcs': 0, 'total': 0})
        for eng in ('ccs', 'bcs'):
            c[eng] += int(kv.get(f'drm-cycles-{eng}', '0').split()[0])
        c['total'] = max(c['total'], int(kv.get('drm-total-cycles-ccs', '0').split()[0]))
    return cards


prev, tprev = snap(a.pid), time.time()
with open(a.out, 'a') as out:
    while os.path.exists(f'/proc/{a.pid}'):
        time.sleep(a.interval)
        cur, t = snap(a.pid), time.time()
        row = {'t': round(t, 3), 'dt': round(t - tprev, 3), 'cards': {}}
        for pdev, c in sorted(cur.items()):
            p = prev.get(pdev)
            if not p or c['total'] <= p['total']:
                continue
            dtot = c['total'] - p['total']
            hz = dtot / (t - tprev)
            row['cards'][pdev] = {e: round((c[e] - p[e]) / dtot, 4) for e in ('ccs', 'bcs')}
            row['cards'][pdev].update({e + '_busy_s': round((c[e] - p[e]) / hz, 4) for e in ('ccs', 'bcs')})
        out.write(json.dumps(row) + '\n'); out.flush()
        prev, tprev = cur, t
