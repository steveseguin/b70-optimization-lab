#!/usr/bin/env python3
"""Which way of creating a device tensor puts its buffer in VRAM, and which in system memory?

The xe driver reports, per process and card, how much buffer memory sits in each placement: `vram0` (the card's
own memory) and `gtt` (system RAM pages the card reaches over PCIe). A live LTX server showed ~34 GB per sampler
card in `gtt` with VRAM nearly empty. This probe creates tensors the different ways the server does and prints
the placement after each, then times the same matrix-vector product on a weight in each placement.

    [ZE_AFFINITY_MASK=<card>] python probe-vram-placement-paths.py [xpu_index] [gib]

No server may be running on the card. Nothing here is written anywhere but stdout.
"""
import glob, os, sys, time, torch

IDX = int(sys.argv[1]) if len(sys.argv) > 1 else 0
GIB = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
dev = torch.device(f'xpu:{IDX}')
N = int(GIB * 2**30)


def fdinfo():
    """{card: {region: MiB}} for this process, one entry per DRM client."""
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
            if k in ('drm-total-system', 'drm-total-gtt', 'drm-total-vram0'):
                n = v.split()
                c[k[10:]] = c.get(k[10:], 0) + round(int(n[0]) * {'KiB': 1 / 1024, 'MiB': 1, 'GiB': 1024}.get(n[1] if len(n) > 1 else '', 1 / 2**20))
    return cards


def host():
    d = {l.split(':')[0]: int(l.split()[1]) // 1024 for l in open('/proc/meminfo')}
    return d['MemAvailable']


def sync():
    torch.xpu.synchronize(dev)


last = {}


def show(tag):
    global last
    sync(); time.sleep(0.5)
    now = fdinfo()
    delta = {c: {r: v - last.get(c, {}).get(r, 0) for r, v in regs.items() if v - last.get(c, {}).get(r, 0)} for c, regs in now.items()}
    print(f'{tag:44s} delta {({c: d for c, d in delta.items() if d})}  | now {now} | host MemAvailable {host()} MiB', flush=True)
    last = now


torch.zeros(1, device=dev); show('start')
keep = []

t = torch.empty(N, dtype=torch.uint8, device=dev); t.fill_(7); keep.append(t)
show('A empty on device, filled on device')

h = torch.ones(N, dtype=torch.uint8)
t = h.to(dev); keep.append(t)
show('B host tensor .to(device)')

t = h.to(dev, non_blocking=True); keep.append(t)
show('C host tensor .to(device, non_blocking)')

t = torch.empty(N, dtype=torch.uint8, device=dev); t.copy_(h); keep.append(t)
show('D empty on device, copy_ from host')

t = keep[1].clone(); keep.append(t)
show('E clone of B on device')

p = torch.nn.Parameter(torch.ones(N // 2, dtype=torch.bfloat16), requires_grad=False)
m = torch.nn.Module(); m.w = p; m.to(dev); keep.append(m)
show('F nn.Module.to(device) (bf16 parameter)')

del h, t
# Timing: one weight per placement path, the same values, the same matrix-vector product.
rows, cols = 8192, int(GIB * 2**30 / 2 / 8192)
wh = torch.randn(rows, cols, dtype=torch.float32).to(torch.bfloat16)
w_to = wh.to(dev)
show('G weight host .to(device)')
w_dev = torch.empty(rows, cols, dtype=torch.bfloat16, device=dev); w_dev.copy_(w_to)
show('H weight device-to-device copy')
x = torch.randn(cols, 1, dtype=torch.float32).to(torch.bfloat16).to(dev)


def bench(w, label):
    for _ in range(3):
        y = w @ x
    sync(); t0 = time.time()
    for _ in range(20):
        y = w @ x
    sync(); dt = (time.time() - t0) / 20
    print(f'  {label:30s} {dt * 1e3:8.2f} ms per product, {w.numel() * 2 / dt / 1e9:7.1f} GB/s of weight read', flush=True)
    return y.cpu()


for rep in range(2):
    ya = bench(w_to, 'weight from host .to(device)')
    yb = bench(w_dev, 'weight copied on device')
print('  results equal:', bool(torch.equal(ya, yb)))
show('end')
