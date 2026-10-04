#!/usr/bin/env python3
"""Does a kernel on one card make the runtime share every other card's buffers with it, and what does that cost?

A live four-card LTX server showed every device buffer exported as a dma-buf and attached to the three other
cards, with the kernel holding about as much host RAM (`GPUActive` in /proc/meminfo) as the server had allocated
in VRAM. This probe reproduces that in the smallest form: allocate on one card, then run a trivial kernel on
another, and watch the per-card driver placement (`vram0` = card memory, `gtt` = system pages or imports), the
host's `GPUActive`, and the speed of the same matrix-vector product before and after.

    [NEOReadDebugKeys=1 <Key>=<v> ...] python probe-multicard-buffer-sharing.py [gib]

All four cards must be visible and no server may be running. Prints only.
"""
import glob, os, sys, time, torch

GIB = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
NDEV = torch.xpu.device_count()
devs = [torch.device(f'xpu:{i}') for i in range(NDEV)]


def fdinfo():
    cards, seen = {}, set()
    for f in glob.glob(f'/proc/{os.getpid()}/fdinfo/*'):
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
            if k in ('drm-total-gtt', 'drm-total-vram0'):
                n = v.split()
                c[k[10:]] = c.get(k[10:], 0) + round(int(n[0]) * {'KiB': 1 / 1024, 'MiB': 1, 'GiB': 1024}.get(n[1] if len(n) > 1 else '', 1 / 2**20))
    return {c: (v.get('vram0', 0), v.get('gtt', 0)) for c, v in sorted(cards.items())}


def host():
    d = {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open('/proc/meminfo')}
    return {'GPUActive': d.get('GPUActive'), 'MemAvailable': d['MemAvailable']}


def show(tag):
    for d in devs:
        torch.xpu.synchronize(d)
    time.sleep(1.0)
    print(f'{tag:46s} (vram,gtt) MiB per card {fdinfo()} | host {host()}', flush=True)


def bench(w, x, label):
    d = w.device
    for _ in range(3):
        y = w @ x
    torch.xpu.synchronize(d); t0 = time.time()
    for _ in range(20):
        y = w @ x
    torch.xpu.synchronize(d); dt = (time.time() - t0) / 20
    print(f'    {label:40s} {dt * 1e3:8.2f} ms per product, {w.numel() * 2 / dt / 1e9:7.1f} GB/s of weight read', flush=True)
    return y.cpu()


print('env', {k: v for k, v in os.environ.items() if k.startswith(('NEO', 'ZE_', 'SYCL', 'UR_')) or k in (
    'DisableIndirectAccess', 'DetectIndirectAccessInKernel', 'EnableMultiRootDeviceContexts',
    'EnableConcurrentSharedCrossP2PDeviceAccess', 'MakeIndirectAllocationsResidentAsPack')}, 'devices', NDEV, flush=True)
show('start (no device touched)')
torch.zeros(1, device=devs[0]); show('xpu:0 initialised')

rows, cols = 8192, int(GIB * 2**30 / 2 / 8192)
w0 = torch.empty(rows, cols, dtype=torch.bfloat16, device=devs[0]); w0.normal_()
x0 = torch.empty(cols, 1, dtype=torch.bfloat16, device=devs[0]); x0.normal_()
show(f'{GIB} GiB weight created on xpu:0')
ya = bench(w0, x0, 'xpu:0 product, other cards untouched')

for i in range(1, NDEV):
    t = torch.zeros(8, device=devs[i]) + 1; torch.xpu.synchronize(devs[i])
    show(f'trivial kernel run on xpu:{i}')
yb = bench(w0, x0, 'xpu:0 product, after other cards ran')
show('after second timing on xpu:0')

w1 = torch.empty(rows, cols, dtype=torch.bfloat16, device=devs[1]); w1.normal_()
x1 = torch.empty(cols, 1, dtype=torch.bfloat16, device=devs[1]); x1.normal_()
show(f'{GIB} GiB weight created on xpu:1')
bench(w1, x1, 'xpu:1 product (new weight)')
t = torch.zeros(8, device=devs[0]) + 1; torch.xpu.synchronize(devs[0])
show('trivial kernel run on xpu:0')
bench(w1, x1, 'xpu:1 product, after xpu:0 ran')
yc = bench(w0, x0, 'xpu:0 product, third timing')
moved = w0.to(devs[1]); torch.xpu.synchronize(devs[1])
show('xpu:0 weight copied to xpu:1')
print('    xpu:0 results identical across timings:', bool(torch.equal(ya, yb) and torch.equal(yb, yc)), flush=True)
del w0, w1, moved, x0, x1, t
for i in range(NDEV):
    torch.xpu.empty_cache()
show('after free')
