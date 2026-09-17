#!/usr/bin/env python3
"""Why do two clips on two cards not overlap? Isolate the cross-card copy.

(1) ceiling: clip A runs all 48 block-sized GEMMs on xpu:0 and clip B all 48
    on xpu:1, two free threads, no cross-card traffic at all;
(2) device copy: the 21/27 split with x.to(other) blocking copies (as before);
(3) pinned staging: the same split, but the activation goes device -> pinned
    host (non_blocking) -> other device (non_blocking) with events, so no
    driver-level peer copy is involved.
All variants are checked bit for bit against the serial run. Exclusive cards.
"""
import threading, time
import torch

STEPS, D, H, M = 11, 4096, 16384, 256
BLOCKS0, BLOCKS1 = 21, 27


def weights(dev, n, seed):
    g = torch.Generator(device='cpu'); g.manual_seed(seed)
    return [[(torch.randn(D, H, generator=g).to(dtype=torch.bfloat16, device=dev),
              torch.randn(H, D, generator=g).to(dtype=torch.bfloat16, device=dev)) for _ in range(3)] for _ in range(n)]


def chain(x, blocks):
    for pairs in blocks:
        for w_up, w_down in pairs:
            x = (torch.nn.functional.silu(x @ w_up) @ w_down) * 0.5 + x
    return x


def capture(fn, inp_shape, dev):
    inp = torch.empty(inp_shape, dtype=torch.bfloat16, device=dev)
    with torch.xpu.device(dev):
        s = torch.xpu.Stream(device=dev); s.wait_stream(torch.xpu.current_stream(dev))
        with torch.xpu.stream(s):
            for _ in range(3): fn(inp)
        torch.xpu.current_stream(dev).wait_stream(s); torch.xpu.synchronize(dev)
        out = torch.empty_like(inp)
        g = torch.xpu.XPUGraph()
        with torch.xpu.graph(g, stream=torch.xpu.Stream(device=dev)):
            out.copy_(fn(inp))
    torch.xpu.synchronize(dev)
    return g, inp, out


torch.xpu.set_device(0)
W0 = weights('xpu:0', BLOCKS0, 7); W1 = weights('xpu:1', BLOCKS1, 9)
x_a = torch.randn(M, D).to(dtype=torch.bfloat16, device='xpu:0')
x_b = torch.randn(M, D).to(dtype=torch.bfloat16, device='xpu:0')
seg0 = {}; seg1 = {}
for name in ('A', 'B'):
    seg0[name] = capture(lambda t: chain(t, W0), (M, D), 'xpu:0')
    seg1[name] = capture(lambda t: chain(t, W1), (M, D), 'xpu:1')


def serial_split(name, x):
    g0, i0, o0 = seg0[name]; g1, i1, o1 = seg1[name]
    for _ in range(STEPS):
        i0.copy_(x); g0.replay(); i1.copy_(o0.to('xpu:1')); g1.replay(); x = o1.to('xpu:0').clone()
    return x


def timed(fn):
    torch.xpu.synchronize(0); torch.xpu.synchronize(1); t = time.perf_counter(); r = fn()
    torch.xpu.synchronize(0); torch.xpu.synchronize(1); return r, time.perf_counter() - t


def two_threads(fa, fb):
    res = {}
    ta = threading.Thread(target=lambda: res.__setitem__('A', fa())); tb = threading.Thread(target=lambda: res.__setitem__('B', fb()))
    ta.start(); tb.start(); ta.join(); tb.join(); return res


eq = lambda a, b: torch.equal(a.view(torch.int16), b.view(torch.int16))
(ra, rb), t_serial = timed(lambda: (serial_split('A', x_a), serial_split('B', x_b)))
_, t_serial = timed(lambda: (serial_split('A', x_a), serial_split('B', x_b)))

# (1) ceiling: no cross-card traffic; A on xpu:0 only (seg0 twice), B on xpu:1 only (seg1 twice) -> different math, timing only
def only0(name, x):
    g0, i0, o0 = seg0[name]
    for _ in range(STEPS * 2):
        i0.copy_(x); g0.replay(); x = o0.clone()
    return x
def only1(name, x):
    g1, i1, o1 = seg1[name]
    for _ in range(STEPS * 2):
        i1.copy_(x); g1.replay(); x = o1.clone()
    return x
xb1 = x_b.to('xpu:1')
_, t_ceiling_serial = timed(lambda: (only0('A', x_a), only1('B', xb1)))
_, t_ceiling_threads = timed(lambda: two_threads(lambda: only0('A', x_a), lambda: only1('B', xb1)))
print({'no-copy ceiling: serial_s': round(t_ceiling_serial, 3), 'threads_s': round(t_ceiling_threads, 3), 'speedup': round(t_ceiling_serial / t_ceiling_threads, 3)}, flush=True)

# (2) device copy split, two free threads
res, t_dev = timed(lambda: two_threads(lambda: serial_split('A', x_a), lambda: serial_split('B', x_b)))
print({'device-copy split: serial_s': round(t_serial, 3), 'threads_s': round(t_dev, 3), 'speedup': round(t_serial / t_dev, 3), 'exact': [eq(res['A'], ra), eq(res['B'], rb)]}, flush=True)

# (3) pinned-host staging, per-thread streams and events
def staged_split(name, x):
    g0, i0, o0 = seg0[name]; g1, i1, o1 = seg1[name]
    s0 = torch.xpu.Stream(device='xpu:0'); s1 = torch.xpu.Stream(device='xpu:1')
    host = torch.empty((M, D), dtype=torch.bfloat16).pin_memory(); host2 = torch.empty((M, D), dtype=torch.bfloat16).pin_memory()
    for _ in range(STEPS):
        with torch.xpu.device(0), torch.xpu.stream(s0):
            i0.copy_(x); g0.replay(); host.copy_(o0, non_blocking=True); e0 = torch.xpu.Event(); e0.record(s0)
        with torch.xpu.device(1), torch.xpu.stream(s1):
            e0.synchronize()                      # host waits for the D2H; the other card keeps running
            i1.copy_(host, non_blocking=True); g1.replay(); host2.copy_(o1, non_blocking=True); e1 = torch.xpu.Event(); e1.record(s1)
        with torch.xpu.device(0), torch.xpu.stream(s0):
            e1.synchronize(); x = torch.empty_like(x); x.copy_(host2, non_blocking=True)
    s0.synchronize(); s1.synchronize()
    return x
res, t_st = timed(lambda: two_threads(lambda: staged_split('A', x_a), lambda: staged_split('B', x_b)))
print({'pinned-staged split: threads_s': round(t_st, 3), 'speedup_vs_serial': round(t_serial / t_st, 3), 'exact': [eq(res['A'], ra), eq(res['B'], rb)]}, flush=True)
