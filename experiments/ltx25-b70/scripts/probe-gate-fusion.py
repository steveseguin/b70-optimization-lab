"""Every projection group in an LTX block that shares an input, including the gate.

The block's weight reads only reach 61.5% of roofline because it issues many
small GEMMs, each paying about 28 us of fixed overhead. Fewer GEMMs is the fix.
`to_q` and `to_gate_logits` both consume x, and in self-attention so do to_k and
to_v, so each group can become one GEMM -- if that is bitwise exact at every
shape the site sees.
"""
import json, time
import torch
import torch.nn.functional as F

torch.use_deterministic_algorithms(True, warn_only=False)
DEV, DT = 'xpu:0', torch.bfloat16
CTX = (32, 64, 128, 192, 256)
SEEDS = (0, 1, 2)
H = 32   # heads, so the gate projection is [32, K]

# name, K, list of output widths in the group, token counts the site sees
GROUPS = [
    ('attn1 self q,k,v,gate',    4096, [4096, 4096, 4096, H], (64, 256)),
    ('attn2 cross q,gate',       4096, [4096, H],             (64, 256)),
    ('attn2 cross k,v',          4096, [4096, 4096],          CTX),
    ('audio_attn1 self q,k,v,gate', 2048, [2048, 2048, 2048, H], (26,)),
    ('audio_attn2 q,gate',       2048, [2048, H],             (26,)),
    ('audio_attn2 k,v',          2048, [2048, 2048],          CTX),
    ('a2v q,gate',               4096, [2048, H],             (64, 256)),
    ('a2v k,v',                  2048, [2048, 2048],          (26,)),
    ('v2a q,gate',               2048, [2048, H],             (26,)),
    ('v2a k,v',                  4096, [2048, 2048],          (64, 256)),
]

def timeit(fn, iters=80, warmup=20):
    for _ in range(warmup): fn()
    torch.xpu.synchronize(DEV)
    t0 = time.perf_counter()
    for _ in range(iters): fn()
    torch.xpu.synchronize(DEV)
    return (time.perf_counter() - t0) / iters

table = []
for name, K, widths, tokens in GROUPS:
    shapes = []
    for M in tokens:
        exact = True
        sep_ms = fus_ms = None
        for seed in SEEDS:
            torch.manual_seed(seed)
            Ws = [torch.randn(w, K, dtype=DT, device=DEV) for w in widths]
            bs = [torch.randn(w, dtype=DT, device=DEV) for w in widths]
            Wf = torch.cat(Ws, 0).contiguous(); bf = torch.cat(bs, 0).contiguous()
            x = torch.randn(1, M, K, dtype=DT, device=DEV)
            sep = [F.linear(x, W, b) for W, b in zip(Ws, bs)]
            chunks, off = [], 0
            fused = F.linear(x, Wf, bf)
            for w in widths:
                chunks.append(fused[..., off:off + w]); off += w
            if not all(torch.equal(a.view(torch.int16), c.view(torch.int16)) for a, c in zip(sep, chunks)):
                exact = False
            if seed == 0:
                sep_ms = timeit(lambda: [F.linear(x, W, b) for W, b in zip(Ws, bs)])
                fus_ms = timeit(lambda: F.linear(x, Wf, bf))
            del Ws, bs, Wf, bf, x, sep, fused, chunks
            torch.xpu.empty_cache()
        shapes.append({'tokens': M, 'bit_exact': exact, 'gemms_saved': len(widths) - 1,
                       'separate_ms': round(sep_ms * 1e3, 4), 'fused_ms': round(fus_ms * 1e3, 4),
                       'saved_ms': round((sep_ms - fus_ms) * 1e3, 4),
                       'speedup': round(sep_ms / fus_ms, 3)})
    table.append({'group': name, 'K': K, 'widths': widths, 'parts': len(widths),
                  'qualifies': all(s['bit_exact'] for s in shapes), 'shapes': shapes})

ok = [t for t in table if t['qualifies']]
print(json.dumps({'groups': len(table), 'qualifying': len(ok),
                  'fuse': [t['group'] for t in ok],
                  'reject': [t['group'] for t in table if not t['qualifies']],
                  'table': table}, indent=2))
