"""Does this torch+XPU build support graph capture, and how much launch
overhead would it remove at LTX's real op sizes?"""
import json, time, inspect
import torch
import torch.nn.functional as F

res = {}
res['torch'] = torch.__version__
res['has_xpu_graph_attr'] = [n for n in dir(torch.xpu) if 'graph' in n.lower()]
try:
    import torch.xpu.graphs as g
    res['xpu_graphs_module'] = [n for n in dir(g) if not n.startswith('_')]
except Exception as e:
    res['xpu_graphs_module'] = repr(e)
for name in ('XPUGraph', 'graph', 'make_graphed_callables', 'is_current_stream_capturing'):
    res[f'torch.xpu.{name}'] = hasattr(torch.xpu, name)

# ---- measure raw per-op launch overhead at LTX elementwise sizes ----
DEV = 'xpu:0'
def timeit(fn, iters, warmup=10):
    for _ in range(warmup): fn()
    torch.xpu.synchronize(DEV)
    t0 = time.perf_counter()
    for _ in range(iters): fn()
    torch.xpu.synchronize(DEV)
    return (time.perf_counter()-t0)/iters

x = torch.randn(1, 64, 4096, dtype=torch.bfloat16, device=DEV)
y = torch.randn(1, 64, 4096, dtype=torch.bfloat16, device=DEV)
s = torch.randn(1, 1, 4096, dtype=torch.bfloat16, device=DEV)
res['tiny_add_us']     = round(timeit(lambda: x.add(y), 200)*1e6, 2)
res['tiny_addcmul_us'] = round(timeit(lambda: x.clone().addcmul_(y, s), 200)*1e6, 2)
res['tiny_rmsnorm_us'] = round(timeit(lambda: F.rms_norm(x, (4096,)), 200)*1e6, 2)
q = torch.randn(1, 32, 64, 128, dtype=torch.bfloat16, device=DEV)
res['sdpa_us']         = round(timeit(lambda: F.scaled_dot_product_attention(q, q, q), 200)*1e6, 2)

# chain of many tiny ops: measures pure dispatch cost accumulation
def chain(n):
    a = x
    for _ in range(n):
        a = a + y
    return a
t50  = timeit(lambda: chain(50), 50)
t100 = timeit(lambda: chain(100), 50)
res['per_op_dispatch_us'] = round((t100-t50)/50*1e6, 2)
print(json.dumps(res, indent=2))
