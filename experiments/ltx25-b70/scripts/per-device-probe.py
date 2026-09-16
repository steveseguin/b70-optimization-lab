"""Are the four B70s equal? The text encoder runs on xpu:2 at ~30 ms/layer while
the identical stack offline on xpu:0 runs at ~5.2 ms/layer.
"""
import sys, time, torch
PK = '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-graph-capture-42/source'
sys.path.insert(0, PK)
torch.use_deterministic_algorithms(True)
import comfy.ops
from comfy.text_encoders.gemma4 import Gemma4_12B_Config, Gemma4Transformer

N, DT = 6, torch.bfloat16

def timed(fn, iters=10, warm=3):
    for _ in range(warm):
        fn()
    torch.xpu.synchronize()
    t = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.xpu.synchronize()
    return (time.perf_counter() - t) / iters * 1e3

print('%-8s %14s %14s %14s' % ('device', 'ms/layer', 'copy GB/s', 'GEMM TFLOP/s'))
for dev in range(torch.xpu.device_count()):
    torch.xpu.set_device(dev)
    D = f'xpu:{dev}'
    cfg = Gemma4_12B_Config(); cfg.num_hidden_layers = N; cfg.vocab_size = 4096
    stack = Gemma4Transformer(cfg, device=D, dtype=DT, ops=comfy.ops.manual_cast)
    with torch.no_grad():
        for p in stack.parameters():
            p.copy_(torch.randn_like(p, dtype=torch.float32).to(DT) * 0.02)
        for b in stack.buffers():
            if b.is_floating_point():
                b.copy_(torch.ones_like(b))
        x = torch.randn(1, 1024, cfg.hidden_size, dtype=DT, device=D)
        ms = timed(lambda: stack(None, embeds=x, dtype=DT, intermediate_output='all')) / N

        n = 1 << 26
        a = torch.empty(n, dtype=DT, device=D); b2 = torch.empty(n, dtype=DT, device=D)
        cp = 2 * n * 2 / (timed(lambda: b2.copy_(a), iters=20) / 1e3) / 1e9

        M = K = Nn = 4096
        xx = torch.randn(M, K, dtype=DT, device=D); ww = torch.randn(K, Nn, dtype=DT, device=D)
        tf = 2 * M * K * Nn / (timed(lambda: torch.mm(xx, ww), iters=20) / 1e3) / 1e12
    print('%-8s %14.3f %14.1f %14.1f' % (D, ms, cp, tf))
    del stack, x, a, b2, xx, ww
    torch.xpu.empty_cache()
