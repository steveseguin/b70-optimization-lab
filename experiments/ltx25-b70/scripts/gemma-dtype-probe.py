"""The shipped Gemma stack runs fp32 activations over bf16 weights
(capture receipt: output_dtype torch.float32; placement receipt: scaled_embedding
float32). Every probe so far used bf16 activations and got 5.4 ms/layer against
the shipped ~30 ms/layer. Does the activation dtype account for it?
"""
import sys, time, torch
PK = '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-graph-capture-42/source'
sys.path.insert(0, PK)
torch.xpu.set_device(0)
DEV = 'xpu:0'
torch.use_deterministic_algorithms(True)
import comfy.ops
from comfy.text_encoders.gemma4 import Gemma4_12B_Config, Gemma4Transformer

N = 6
def timed(fn, iters=10, warm=3):
    for _ in range(warm): fn()
    torch.xpu.synchronize(0)
    t = time.perf_counter()
    for _ in range(iters): fn()
    torch.xpu.synchronize(0)
    return (time.perf_counter() - t) / iters * 1e3

for weight_dt in (torch.bfloat16,):
    cfg = Gemma4_12B_Config(); cfg.num_hidden_layers = N; cfg.vocab_size = 4096
    stack = Gemma4Transformer(cfg, device=DEV, dtype=weight_dt, ops=comfy.ops.manual_cast)
    with torch.no_grad():
        for p in stack.parameters():
            p.copy_(torch.randn_like(p, dtype=torch.float32).to(weight_dt) * 0.02)
        for b in stack.buffers():
            if b.is_floating_point(): b.copy_(torch.ones_like(b))
        for act_dt in (torch.bfloat16, torch.float32):
            x = torch.randn(1, 1024, cfg.hidden_size, dtype=act_dt, device=DEV)
            ms = timed(lambda: stack(None, embeds=x, dtype=act_dt, intermediate_output='all'))
            print('weights %-9s activations %-9s  %8.3f ms total => %7.3f ms/layer'
                  % (str(weight_dt).replace('torch.', ''), str(act_dt).replace('torch.', ''), ms, ms / N))

# and the raw GEMM at the MLP shape, both ways
M, K, Nn = 1024, 3840, 15360
for dt in (torch.bfloat16, torch.float32):
    a = torch.randn(M, K, dtype=dt, device=DEV); w = torch.randn(K, Nn, dtype=dt, device=DEV)
    ms = timed(lambda: torch.mm(a, w), iters=20)
    print('  mm %-9s %d,%d,%d  %7.3f ms  = %6.1f TFLOP/s' % (
        str(dt).replace('torch.', ''), M, K, Nn, ms, 2 * M * K * Nn / (ms / 1e3) / 1e12))
