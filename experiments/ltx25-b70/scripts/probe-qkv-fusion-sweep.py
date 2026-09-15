"""Complete fusion table for every fusable projection site in an LTX block.

Sites where two or three projections share an input can be stacked into one GEMM.
Exactness is shape-dependent, so every site is tested at every token count it can
see, with several seeds, and a site only qualifies if it is exact at ALL of them.
"""
import json, time
import torch
import torch.nn.functional as F

torch.use_deterministic_algorithms(True, warn_only=False)
DEV, DT = 'xpu:0', torch.bfloat16
CTX = (32, 48, 64, 96, 128, 192, 256, 512)   # possible conditioning lengths
SEEDS = (0, 1, 2)

# site, inner, K, parts, token counts this site can actually see
SITES = [
    ('attn1 video self qkv',   4096, 4096, 3, (64, 256)),
    ('attn2 video cross kv',   4096, 4096, 2, CTX),
    ('audio_attn1 self qkv',   2048, 2048, 3, (26,)),
    ('audio_attn2 cross kv',   2048, 2048, 2, CTX),
    ('a2v cross kv (audio)',   2048, 2048, 2, (26,)),
    ('v2a cross kv (video)',   2048, 4096, 2, (64, 256)),
]

def timeit(fn, iters=60, warmup=15):
    for _ in range(warmup): fn()
    torch.xpu.synchronize(DEV)
    t0 = time.perf_counter()
    for _ in range(iters): fn()
    torch.xpu.synchronize(DEV)
    return (time.perf_counter() - t0) / iters

table = []
for name, inner, K, parts, tokens in SITES:
    per_shape = []
    for M in tokens:
        exact_all, sep_ms, fus_ms = True, [], []
        for seed in SEEDS:
            torch.manual_seed(seed)
            Ws = [torch.randn(inner, K, dtype=DT, device=DEV) for _ in range(parts)]
            bs = [torch.randn(inner, dtype=DT, device=DEV) for _ in range(parts)]
            Wf = torch.cat(Ws, 0).contiguous(); bf = torch.cat(bs, 0).contiguous()
            x = torch.randn(1, M, K, dtype=DT, device=DEV)
            sep = [F.linear(x, W, b) for W, b in zip(Ws, bs)]
            chunks = F.linear(x, Wf, bf).split(inner, dim=-1)
            if not all(torch.equal(a.view(torch.int16), c.view(torch.int16)) for a, c in zip(sep, chunks)):
                exact_all = False
            if seed == 0:
                sep_ms.append(timeit(lambda: [F.linear(x, W, b) for W, b in zip(Ws, bs)]))
                fus_ms.append(timeit(lambda: F.linear(x, Wf, bf)))
            del Ws, bs, Wf, bf, x, sep, chunks
            torch.xpu.empty_cache()
        per_shape.append({'tokens': M, 'bit_exact_all_seeds': exact_all,
                          'separate_ms': round(sep_ms[0] * 1e3, 4), 'fused_ms': round(fus_ms[0] * 1e3, 4),
                          'speedup': round(sep_ms[0] / fus_ms[0], 3)})
    qualifies = all(s['bit_exact_all_seeds'] for s in per_shape)
    table.append({'site': name, 'inner': inner, 'K': K, 'parts': parts,
                  'qualifies_at_every_shape': qualifies,
                  'worst_speedup': round(min(s['speedup'] for s in per_shape), 3),
                  'best_speedup': round(max(s['speedup'] for s in per_shape), 3),
                  'shapes': per_shape})

fuse = [t for t in table if t['qualifies_at_every_shape']]
print(json.dumps({'sites': len(table), 'qualifying': len(fuse), 'seeds': list(SEEDS),
                  'fuse_these': [t['site'] for t in fuse],
                  'do_not_fuse': [t['site'] for t in table if not t['qualifies_at_every_shape']],
                  'table': table}, indent=2))
