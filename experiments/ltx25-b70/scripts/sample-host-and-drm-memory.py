#!/usr/bin/env python3
"""Every 5 s: host meminfo, the server's RSS split, and its DRM fdinfo memory per card (system vs VRAM regions)."""
import glob, json, re, subprocess, sys, time, os
out = sys.argv[1]
def server_pid():
    try:
        s = subprocess.check_output(['ss', '-ltnp'], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return None
    m = re.search(r':8188 .*pid=(\d+)', s)
    return int(m.group(1)) if m else None
def to_mib(v):
    n = v.split(); return int(n[0]) * {'KiB': 1 / 1024, 'MiB': 1, 'GiB': 1024}.get(n[1] if len(n) > 1 else '', 1 / 2**20)
while not os.path.exists(out + '.stop'):
    row = {'t': time.strftime('%H:%M:%S', time.gmtime())}
    mi = {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open('/proc/meminfo')}
    row['host'] = {k: mi[k] for k in ('MemAvailable', 'MemFree', 'AnonPages', 'Cached', 'Slab', 'SwapFree', 'GPUActive')}
    pid = server_pid()
    if pid:
        try:
            row['proc'] = {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open(f'/proc/{pid}/status') if l.startswith(('VmRSS', 'RssAnon', 'RssFile', 'VmSwap'))}
        except OSError:
            pass
        cards, seen = {}, set()
        for f in glob.glob(f'/proc/{pid}/fdinfo/*'):
            try:
                kv = dict(l.split(':', 1) for l in open(f).read().splitlines() if ':' in l)
            except OSError:
                continue
            key = (kv.get('drm-pdev', '').strip(), kv.get('drm-client-id', '').strip())
            if not key[0] or key in seen:
                continue
            seen.add(key)
            c = cards.setdefault(key[0][5:7], {})
            for k, v in kv.items():
                if k.startswith(('drm-total-', 'drm-resident-')):
                    c[k[4:]] = c.get(k[4:], 0) + round(to_mib(v))
        row['drm'] = cards
    open(out, 'a').write(json.dumps(row) + '\n')
    time.sleep(5)
