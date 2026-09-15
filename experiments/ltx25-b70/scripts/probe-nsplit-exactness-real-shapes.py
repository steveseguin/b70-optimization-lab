"""Is an output-column (N) split bit-exact at the token counts LTX really runs?

The earlier probe used M=64 and M=256 for every layer, but the audio stream runs
at 26 tokens and the text cross-attention at the conditioning length. Splitting a
GEMM's N can change the kernel's tiling, so exactness must be checked at the
shapes that actually occur, not representative ones.
"""
import json, itertools
import torch
import torch.nn.functional as F

torch.use_deterministic_algorithms(True, warn_only=False)
torch.manual_seed(0)
DEV, DT = 'xpu:0', torch.bfloat16

# (name, N, K, token counts that actually occur for this layer)
LAYERS = [
    ('video attn1/attn2 to_q,to_k,to_v', 4096, 4096, (64, 256)),
    ('video attn to_out',                4096, 4096, (64, 256)),
    ('video ff.net.0.proj',             16384, 4096, (64, 256)),
    ('video ff.net.2',                   4096, 16384, (64, 256)),
    ('audio attn to_q,to_k,to_v',        2048, 2048, (26,)),
    ('audio attn to_out',                2048, 2048, (26,)),
    ('audio_ff.net.0.proj',              8192, 2048, (26,)),
    ('audio_ff.net.2',                   2048, 8192, (26,)),
    ('a2v to_q (video->audio dim)',      2048, 4096, (64, 256)),
    ('a2v to_out',                       4096, 2048, (64, 256)),
    ('v2a to_q',                         2048, 2048, (26,)),
    ('v2a to_out',                       2048, 4096, (26,)),
    ('text cross to_k,to_v (ctx len)',   4096, 4096, (128, 256)),
]

rows, splits = [], (2, 4)
for name, N, K, tokens in LAYERS:
    W = torch.randn(N, K, dtype=DT, device=DEV)
    b = torch.randn(N, dtype=DT, device=DEV)
    for M, ways in itertools.product(tokens, splits):
        if N % ways:
            continue
        x = torch.randn(1, M, K, dtype=DT, device=DEV)
        full = F.linear(x, W, b)
        step = N // ways
        parts = [F.linear(x, W[i * step:(i + 1) * step], b[i * step:(i + 1) * step]) for i in range(ways)]
        joined = torch.cat(parts, dim=-1)
        exact = torch.equal(full.view(torch.int16), joined.view(torch.int16))
        rows.append({'layer': name, 'N': N, 'K': K, 'tokens': M, 'ways': ways, 'bit_exact': bool(exact)})
        del x, full, parts, joined
    del W, b
    torch.xpu.empty_cache()

bad = [r for r in rows if not r['bit_exact']]
out = {'cases': len(rows), 'all_bit_exact': not bad, 'failures': bad,
       'by_ways': {w: {'cases': sum(1 for r in rows if r['ways'] == w),
                       'exact': sum(1 for r in rows if r['ways'] == w and r['bit_exact'])}
                   for w in splits},
       'rows': rows}
print(json.dumps(out, indent=2))
