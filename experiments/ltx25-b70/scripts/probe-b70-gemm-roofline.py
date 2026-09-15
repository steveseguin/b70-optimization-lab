"""Offline B70 GEMM/bandwidth probe for the LTX 2.5 sampler bottleneck.

No ComfyUI, no model load, no server. Allocates BF16 weights of the actual
LTX block shapes and measures achieved bandwidth at the real decode token
counts. Also gates same-device output-column (N) partition for bitwise
equality, which is the prerequisite for any tensor-parallel plan.
"""
import json, time, sys
import torch
import torch.nn.functional as F

torch.use_deterministic_algorithms(True, warn_only=False)
DEV = 'xpu:0'

def sync(d=DEV):
    torch.xpu.synchronize(d)

def timeit(fn, iters, warmup=5):
    for _ in range(warmup):
        fn()
    sync()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    sync()
    return (time.perf_counter() - t0) / iters

def bw(nbytes, seconds):
    return nbytes / seconds / 1e9

# ---- 1. pure copy roofline -------------------------------------------------
res = {'device': torch.xpu.get_device_properties(0).name}
N = 1 << 28  # 256M bf16 = 512 MiB
a = torch.empty(N, dtype=torch.bfloat16, device=DEV)
b = torch.empty(N, dtype=torch.bfloat16, device=DEV)
t = timeit(lambda: b.copy_(a), 20)
res['copy_roofline_GBps'] = round(bw(2 * N * 2, t), 1)   # read+write
del a, b
torch.xpu.empty_cache()

# ---- 2. real LTX linear shapes at real token counts ------------------------
SHAPES = [
    ('ff.net.0.proj',   16384, 4096),
    ('ff.net.2',         4096, 16384),
    ('attn.to_q',        4096, 4096),
    ('audio_ff.net.0',   8192, 2048),
    ('audio_ff.net.2',   2048, 8192),
]
rows = []
for name, Nout, K in SHAPES:
    W = torch.randn(Nout, K, dtype=torch.bfloat16, device=DEV)
    wbytes = W.numel() * 2
    for M in (64, 256):
        x = torch.randn(1, M, K, dtype=torch.bfloat16, device=DEV)
        t = timeit(lambda: F.linear(x, W), 50)
        flops = 2 * M * Nout * K
        rows.append({'layer': name, 'N': Nout, 'K': K, 'M': M,
                     'ms': round(t * 1e3, 4),
                     'weight_MiB': round(wbytes / 2**20, 1),
                     'achieved_GBps': round(bw(wbytes, t), 1),
                     'TFLOPs': round(flops / t / 1e12, 2)})
        del x
    del W
    torch.xpu.empty_cache()
res['linears'] = rows

# ---- 3. bitwise gate: full N vs two N/2 halves, same device -----------------
gate = []
for name, Nout, K in SHAPES:
    W = torch.randn(Nout, K, dtype=torch.bfloat16, device=DEV)
    for M in (64, 256):
        x = torch.randn(1, M, K, dtype=torch.bfloat16, device=DEV)
        full = F.linear(x, W)
        half = Nout // 2
        split = torch.cat((F.linear(x, W[:half]), F.linear(x, W[half:])), dim=-1)
        eq = torch.equal(full, split)
        # signed-zero / bit-level check
        biteq = torch.equal(full.view(torch.int16), split.view(torch.int16))
        t_full = timeit(lambda: F.linear(x, W), 50)
        t_half = timeit(lambda: F.linear(x, W[:half]), 50)
        gate.append({'layer': name, 'M': M, 'value_equal': bool(eq), 'bit_equal': bool(biteq),
                     'full_ms': round(t_full * 1e3, 4), 'half_ms': round(t_half * 1e3, 4),
                     'half_speedup_vs_full': round(t_full / t_half, 3)})
        del x, full, split
    del W
    torch.xpu.empty_cache()
res['n_split_gate'] = gate

print(json.dumps(res, indent=2))
