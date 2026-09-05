#!/usr/bin/env python3
"""Does an XPU graph replay pay per Triton launch? 96 trivial Triton launches vs 96 native launches, eager and replayed (one B70; serving env)."""
import os, statistics, time
import torch, triton, triton.language as tl
device = torch.device("xpu:0"); torch.xpu.set_device(device)
@triton.jit
def _tiny(x_ptr, n, BLOCK: tl.constexpr):
    pid = tl.program_id(0); offs = pid * BLOCK + tl.arange(0, BLOCK)
    v = tl.load(x_ptr + offs, mask=offs < n, other=0.0)
    tl.store(x_ptr + offs, v + 1.0, mask=offs < n)
x = torch.zeros(400 * 64, device=device, dtype=torch.float32)
y = torch.zeros(400 * 64, device=device, dtype=torch.float32)
def triton_seq(k):
    for _ in range(k): _tiny[(400,)](x, x.numel(), BLOCK=64)
def native_seq(k):
    for _ in range(k): y.add_(1.0)
def wall(fn, n=20):
    fn(); torch.xpu.synchronize(); ts = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(); torch.xpu.synchronize(); ts.append(1e3 * (time.perf_counter() - t0))
    return round(statistics.median(ts), 3)
K = 96
print(f"eager: {K} triton launches {wall(lambda: triton_seq(K))} ms; {K} native launches {wall(lambda: native_seq(K))} ms")
for name, fn in (("triton", lambda: triton_seq(K)), ("native", lambda: native_seq(K)), ("mixed", lambda: (triton_seq(K), native_seq(K)))):
    s = torch.xpu.Stream()
    with torch.xpu.stream(s):
        for _ in range(3): fn()
    torch.xpu.synchronize()
    g = torch.xpu.XPUGraph()
    with torch.xpu.graph(g, stream=s):
        fn()
    torch.xpu.synchronize()
    print(f"graph replay of {K} {name} launches: {wall(lambda: g.replay())} ms per replay")
