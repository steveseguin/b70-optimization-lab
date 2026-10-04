#!/usr/bin/env python3
"""Does allocating VRAM on a B70 consume the same amount of HOST memory?

Allocates and touches device tensors in steps and prints, after each step, the host's MemAvailable and this
process's own DRM fdinfo memory keys (system and VRAM regions) and RSS.
    ZE_AFFINITY_MASK=<card> python probe-vram-host-shadow.py [gib_per_step] [steps]
"""
import glob, os, sys, time, torch
step = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
steps = int(sys.argv[2]) if len(sys.argv) > 2 else 4
dev = torch.device('xpu')


def meminfo():
    d = {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open('/proc/meminfo')}
    return {k: d[k] for k in ('MemAvailable', 'MemFree', 'AnonPages', 'Cached', 'Shmem', 'Slab', 'Unevictable')}


def fdinfo():
    out = {}
    for f in glob.glob(f'/proc/{os.getpid()}/fdinfo/*'):
        try:
            kv = dict(l.split(':', 1) for l in open(f).read().splitlines() if ':' in l)
        except OSError:
            continue
        if 'drm-client-id' not in kv:
            continue
        for k, v in kv.items():
            if k.startswith(('drm-total-', 'drm-resident-', 'drm-shared-', 'drm-active-', 'drm-purgeable-')) and 'cycles' not in k:
                n = v.split(); mib = int(n[0]) * {'KiB': 1 / 1024, 'MiB': 1, 'GiB': 1024}.get(n[1] if len(n) > 1 else '', 1 / 2**20)
                out[k] = max(out.get(k, 0), round(mib))
    return out


def rss():
    return {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open(f'/proc/{os.getpid()}/status') if l.startswith(('VmRSS', 'RssAnon', 'RssShmem'))}


def show(tag):
    print(tag, 'host', meminfo(), '| proc', rss(), '| drm', {k: v for k, v in sorted(fdinfo().items()) if v}, flush=True)


torch.zeros(1, device=dev); torch.xpu.synchronize()
show('start       ')
keep = []
for i in range(steps):
    t = torch.empty(int(step * 2**30), dtype=torch.uint8, device=dev); t.fill_(7); torch.xpu.synchronize()
    keep.append(t); time.sleep(1)
    show(f'+{(i + 1) * step:5.1f} GiB  ')
del keep, t
torch.xpu.empty_cache(); torch.xpu.synchronize(); time.sleep(2)
show('after free  ')
