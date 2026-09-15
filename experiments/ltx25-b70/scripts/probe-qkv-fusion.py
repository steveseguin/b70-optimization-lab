"""Does fusing q/k/v into one GEMM help, and is it bitwise exact?

Self-attention computes to_q(x), to_k(x), to_v(x) from the SAME input, so the
three weights can be stacked into one [3*inner, K] matrix. Each output row keeps
its full K reduction, so the arithmetic per element is unchanged -- but the GEMM
shape changes, which can change the kernel. Exactness must be measured.
"""
import json, time
import torch
import torch.nn.functional as F

torch.use_deterministic_algorithms(True, warn_only=False)
torch.manual_seed(0)
DEV, DT = 'xpu:0', torch.bfloat16

def timeit(fn, iters=100, warmup=20):
    for _ in range(warmup): fn()
    torch.xpu.synchronize(DEV)
    t0 = time.perf_counter()
    for _ in range(iters): fn()
    torch.xpu.synchronize(DEV)
    return (time.perf_counter() - t0) / iters

CASES = [
    ('video self-attn qkv', 4096, 4096, 3, (64, 256)),
    ('audio self-attn qkv', 2048, 2048, 3, (26,)),
    ('v2a self-attn qkv',   2048, 2048, 3, (26,)),
    ('video cross kv',      4096, 4096, 2, (128, 256)),
    ('a2v cross kv',        2048, 2048, 2, (26,)),
]
rows = []
for name, inner, K, parts, tokens in CASES:
    Ws = [torch.randn(inner, K, dtype=DT, device=DEV) for _ in range(parts)]
    bs = [torch.randn(inner, dtype=DT, device=DEV) for _ in range(parts)]
    Wf = torch.cat(Ws, dim=0).contiguous()
    bf = torch.cat(bs, dim=0).contiguous()
    for M in tokens:
        x = torch.randn(1, M, K, dtype=DT, device=DEV)
        sep = [F.linear(x, W, b) for W, b in zip(Ws, bs)]
        fused = F.linear(x, Wf, bf)
        chunks = fused.split(inner, dim=-1)
        exact = all(torch.equal(a.view(torch.int16), c.view(torch.int16)) for a, c in zip(sep, chunks))
        t_sep = timeit(lambda: [F.linear(x, W, b) for W, b in zip(Ws, bs)])
        t_fus = timeit(lambda: F.linear(x, Wf, bf))
        rows.append({'case': name, 'inner': inner, 'K': K, 'parts': parts, 'tokens': M,
                     'bit_exact': bool(exact),
                     'separate_ms': round(t_sep * 1e3, 4), 'fused_ms': round(t_fus * 1e3, 4),
                     'speedup': round(t_sep / t_fus, 3)})
        del x, sep, fused, chunks
    del Ws, bs, Wf, bf
    torch.xpu.empty_cache()

exact_all = all(r['bit_exact'] for r in rows)
out = {'all_bit_exact': exact_all,
       'failures': [r['case'] + f" @{r['tokens']}" for r in rows if not r['bit_exact']],
       'mean_speedup': round(sum(r['speedup'] for r in rows) / len(rows), 3),
       'rows': rows}
print(json.dumps(out, indent=2))
