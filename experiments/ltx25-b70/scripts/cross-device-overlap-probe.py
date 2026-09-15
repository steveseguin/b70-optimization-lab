"""The realistic shape: the sampler is XPU graph replays (almost no Python) on
xpu:0, the decoder is many small eager ops (Python-dispatch heavy) on xpu:3.
If the GIL serialises them, pipelining the decode is worthless.
"""
import threading, time, torch

# --- sampler side: a captured graph on xpu:0, replayed ---------------------
torch.xpu.set_device(0)
x0 = torch.randn(256, 4096, dtype=torch.bfloat16, device='xpu:0')
w0 = torch.randn(4096, 16384, dtype=torch.bfloat16, device='xpu:0')
w1 = torch.randn(16384, 4096, dtype=torch.bfloat16, device='xpu:0')
for _ in range(5):
    ((x0 @ w0) @ w1)
torch.xpu.synchronize(0)
g = torch.xpu.XPUGraph()
s = torch.xpu.Stream(device=0)
with torch.xpu.device(0), torch.no_grad(), torch.xpu.graph(g, stream=s):
    out0 = (x0 @ w0) @ w1
torch.xpu.synchronize(0)

REPLAYS = 400
def sampler():
    with torch.xpu.device(0):
        for _ in range(REPLAYS):
            g.replay()
        torch.xpu.synchronize(0)

# --- decoder side: lots of small eager ops on xpu:3 ------------------------
torch.xpu.set_device(3)
t3 = [torch.randn(1, 128, 256, 256, dtype=torch.bfloat16, device='xpu:3') for _ in range(3)]
OPS = 900
def decoder():
    with torch.xpu.device(3):
        a, b, c = t3
        for i in range(OPS):
            y = torch.nn.functional.silu(a)
            y = y * b
            y = y + c
            a = torch.nn.functional.group_norm(y, 32)
        torch.xpu.synchronize(3)

def timeit(fn, n=3):
    best = 1e9
    for _ in range(n):
        t = time.perf_counter(); fn(); best = min(best, time.perf_counter() - t)
    return best

a = timeit(sampler); b = timeit(decoder)
print('alone:  graph-replay sampler xpu:0 %.3f s   dispatch-heavy decode xpu:3 %.3f s   sum %.3f s' % (a, b, a + b))

best = 1e9
for _ in range(3):
    t0 = time.perf_counter()
    ts = [threading.Thread(target=sampler), threading.Thread(target=decoder)]
    for t in ts: t.start()
    for t in ts: t.join()
    best = min(best, time.perf_counter() - t0)
saved = (a + b) - best
print('together: wall %.3f s   perfect overlap would be %.3f' % (best, max(a, b)))
print('hidden %.3f s of the %.3f s that could be hidden  => %.0f%%' % (saved, min(a, b), 100 * saved / min(a, b)))
